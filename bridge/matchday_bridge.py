"""Matchday Bridge: FM24 career -> play your club's matches in eFootball PES 2021 or SP Football Life 2026.

Watches Football Manager 2024. When your club reaches match day (team news), it asks where to play: PES 2021,
Football Life 2026 (each installed one gets a button) or let FM sim. Play builds both FM24 match squads into
that game (ratings from FM24 attributes; clubs the game can't pick play in a spare slot under their FM24 name and
crest), loads them into the running game or (re)starts it, walks its menus to the pre-match screen of the
fixture (controller 1 on your club), and writes the result and scorers back into FM24.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import datetime
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk

import install
from fm_writer import fm_minute
from games import find_games
from spfl_build import MatchBuilder, request_lines
from spfl_db import PesDb
from ui import View

APP = "Matchday Bridge"
TEXT = {r["id"]: r["text"] for r in json.load(open(install.resource("sheets", "ui_text.json"), encoding="utf-8"))}


LOG = os.path.join(os.environ.get("LOCALAPPDATA", "."), "MatchdayBridge", "bridge.log")


_last_log = [""]


def log(s: str):
    if s == _last_log[0]:
        return
    _last_log[0] = s
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s.replace("\n", " | ") + "\n")
    except OSError:
        pass


def is_running(exe: str) -> bool:
    return bool(pids_of(exe))


def is_window(h: int) -> bool:
    return bool(h) and bool(ctypes.windll.user32.IsWindow(h))


def pids_of(exe: str) -> list[int]:
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {exe}", "/NH", "/FO", "CSV"], capture_output=True,
                         text=True, creationflags=0x08000000).stdout
    pids = []
    for line in out.splitlines():
        cols = [c.strip('"') for c in line.split('","')]
        if len(cols) > 1 and cols[0].lower() == exe.lower() and cols[1].isdigit():
            pids.append(int(cols[1]))
    return pids


def stop_processes(exes) -> None:
    """The game only reads its database at start-up; sider.exe sometimes outlives it, so stop both by PID."""
    for exe in exes:
        for pid in pids_of(exe):
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, creationflags=0x08000000)
    for _ in range(20):
        if not any(pids_of(e) for e in exes):
            return
        time.sleep(0.5)


def two_lines(text: str) -> tuple[str, str]:
    head, _, rest = text.partition("\n")
    return head, rest


class Bridge:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.fm_dir = install.find_fm24()
        self.games = find_games()                   # PES 2021 first
        self.game = self.games[0] if self.games else None   # the game of the current match day
        self.setup_done = threading.Event()
        self.reader = None
        self.prompted_for = None
        self.busy = False
        self.writer = None
        self.plan = None
        self.matchday = None
        self.choosing = False
        self.fm_ok = False
        self.fm_done = threading.Event()
        from fm_drive import FmUi
        self.fm_ui = FmUi()
        self.fm_ui.enable(True)             # a previous run may have quit with its question open over FM24
        self.view = View(root, APP, [g.short for g in self.games], self.choose, lambda: self.choose(None))
        self.view.footer(f"Log  {LOG}")
        root.bind("<Return>", lambda e: self.choose(0) if self.view.play_btn and self.view.play_btn.enabled else None)
        if not self.fm_dir:
            self.view.status("FM24 not found", "error")
            self.view.idle("Football Manager 2024 not found")
            self.view.message("Football Manager 2024 not found", TEXT["fm_missing"])
            return
        if not self.games:
            self.view.status("No game found", "error")
            self.view.idle("PES 2021 / Football Life 2026 not found")
            self.view.message("No game to play in", TEXT["game_missing"])
            return
        log("games: " + ", ".join(f"{g.name} ({g.dir})" for g in self.games))
        self.waiting_view()
        threading.Thread(target=self._setup, daemon=True).start()
        threading.Thread(target=self.watch, daemon=True).start()

    def _setup(self) -> list[str]:
        """Each game's Sider gets the module (PES 2021 first gets Sider itself, downloaded once); then the faces
        tables are read ahead. Problems show under the waiting message and again when that game is picked."""
        problems = []
        try:
            for g in self.games:
                try:
                    done = install.install_pes2021(g.dir) if g.key == "pes2021" else install.install_spfl(g.dir)
                    log(f"{g.short}: " + "; ".join(done))
                except PermissionError as e:
                    if ctypes.windll.shell32.IsUserAnAdmin():
                        problems.append(f"{g.short} could not be set up ({e}). Close {g.short} and start Matchday "
                                        "Bridge again.")
                    else:
                        problems.append(f"Run Matchday Bridge as administrator once so it can set up {g.short}'s "
                                        "Sider folder.")
                except Exception as e:  # noqa: BLE001 - e.g. no internet for the Sider download: tried again on play
                    problems.append(f"{g.short} is not set up yet ({e}).")
            for p in problems:
                log(p)
            if problems and not (self.busy or self.choosing):
                self.ui(self.view.detail, " ".join(problems))
        finally:
            self.setup_done.set()
        for g in self.games:
            try:
                from spfl_faces import real_face_ids
                log(f"{g.short} players with a real face: {len(real_face_ids(g.dir))}")
            except Exception as e:  # noqa: BLE001 - read again (and logged) when a match is built
                log(f"{g.short} real faces not read yet ({e})")
        return problems

    # ------------------------------------------------------------------ UI helpers (any thread)
    def ui(self, fn, *args, **kw):
        self.root.after(0, lambda: fn(*args, **kw))

    def say(self, title: str, body: str = "", detail: str = ""):
        log(" ".join(x for x in (title, body, detail) if x))
        self.ui(self.view.message, title, body, detail)

    def detail_msg(self, s: str):
        log(s)
        self.ui(self.view.detail, s)

    def game_names(self) -> str:
        return " or ".join(g.name for g in self.games)

    def waiting_view(self, detail: str = ""):
        self.view.status("Watching FM24", "ok")
        self.view.idle("Waiting for match day", "Play FM24 as normal. The choice pops up in FM24 when you press "
                       "Match Preview.")
        self.view.step(-1)
        self.view.buttons(False, False)
        self.view.message("Waiting for match day", "Play FM24 as normal. When you press Match Preview on match day, "
                          f"FM24 asks whether you want to play the match yourself in {self.game_names()}.", detail)

    def card_teams(self, plan: dict | None = None) -> tuple[dict, dict]:
        md = self.matchday
        out = []
        for side in ("home", "away"):
            p = plan[side] if plan else {}
            out.append({"name": md[side]["name"], "human": md[side].get("human"), "abbr": p.get("abbr", "")})
        return out[0], out[1]

    # ------------------------------------------------------------------ FM watcher
    def watch(self):
        """Today's match is readable from FM's Team News screen on (a memory scan, every few seconds); from then
        on FM's screen is watched for the pre-match screen Match Preview opens, where the choice pops up."""
        from fm_reader import FmReader, match_key
        armed, armed_at, seen_at, why = None, 0.0, 0.0, None
        while True:
            try:
                if not is_running("fm.exe"):
                    self.reader, armed = None, None
                    if not self.busy:
                        log("Waiting for Football Manager 2024 to start...")
                        self.ui(self.view.status, "FM24 not running", "idle")
                    time.sleep(5)
                    continue
                if self.busy or self.choosing:
                    time.sleep(2)
                    continue
                if self.reader is None:
                    self.reader = FmReader()
                    self.ui(self.view.status, "Watching FM24", "ok")
                if armed is None or time.time() - armed_at > 30:
                    md = self.reader.matchday(skip=self.prompted_for)
                    key = md and match_key(md)
                    if not md or key == self.prompted_for:
                        reason = getattr(self.reader, "why", "") if not md else "this match day was already handled"
                        if reason != why:                   # once per change: why there is nothing to ask yet
                            why = reason
                            log(f"no match day to ask about: {reason}")
                        armed = None
                        self.fm_ui.stop()
                        time.sleep(4)
                        continue
                    why = None
                    if key != armed:
                        log(f"match day in FM24: {md['home']['name']} v {md['away']['name']} (waiting for Match Preview)")
                        self.matchday = md
                        self.ui(self.view.fixture, *self.card_teams(), "FM24  ·  Match day")
                        self.ui(self.view.status, "Match day: waiting for Match Preview", "warn")
                    armed, armed_at = key, time.time()
                if self.fm_ui.at_prematch():
                    log(f"FM24 pre-match screen: {self.fm_ui.seen}")
                    self.prompted_for, armed = armed, None
                    self.choosing = True
                    self.root.after(0, self.prompt)
                elif time.time() - seen_at > 20:
                    seen_at = time.time()
                    log(f"waiting for Match Preview; FM24 shows {self.fm_ui.seen}")
                time.sleep(0.7)
            except Exception as e:  # noqa: BLE001
                self.reader, armed = None, None
                log(f"Reading FM24 failed ({e}); retrying...")
                self.ui(self.view.status, "FM24 read failed, retrying", "warn")
                time.sleep(5)

    def prompt(self):
        """The choice, over FM24's pre-match screen; FM takes no input until it is answered."""
        md = self.matchday
        home, away = md["home"]["name"], md["away"]["name"]
        log(f"prompt in FM24: {home} v {away}")
        self.view.fixture(*self.card_teams(), "FM24  ·  Match day")
        self.view.step(-1)
        self.view.status("Choose in FM24", "warn")
        self.view.message("Match day: choose in FM24", f"{home} v {away}: play it in {self.game_names()} or let "
                          "FM24 simulate it. The choice is open in FM24's window.")
        try:
            import fm_graphics
            from PIL import Image
            from ui import ChoiceDialog
            teams = []
            for side in ("home", "away"):
                png = fm_graphics.club_logo(self.fm_dir, md[side].get("club_id"))
                teams.append({"name": md[side]["name"], "human": md[side].get("human"),
                              "logo": Image.open(io.BytesIO(png)).convert("RGBA") if png else None})
            h = self.fm_ui.window()
            r = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(h, ctypes.byref(r))
            self.fm_ui.enable(False)
            self.dialog = ChoiceDialog(self.root, (r.left, r.top, r.right, r.bottom), teams, "FM24",
                                       [g.short for g in self.games], self.choose, lambda: self.choose(None))
            self.root.after(1500, self._keep_dialog_up)
        except Exception as e:  # noqa: BLE001 - fall back to this window's buttons
            log(f"choice in FM24 not shown ({e}); asking in the bridge window")
            self.fm_ui.enable(True)
            self.view.buttons(True, True)
            self.view.message(*two_lines(TEXT["prompt"].format(home=home, away=away, game=self.game_names())))
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.root.lift()

    def _keep_dialog_up(self):
        """FM24 sets itself always-on-top; keep the question above it while it is open."""
        d = getattr(self, "dialog", None)
        if d is None or d.done:
            return
        if not is_window(self.fm_ui.h):
            d.close()
            self.choose(None)
            return
        for t in (d.shade, d.win):
            t.lift()
            t.attributes("-topmost", True)
        self.root.after(1500, self._keep_dialog_up)

    def choose(self, game: int | None):
        """game: index into self.games (the button pressed), None = let FM24 simulate."""
        self.fm_ui.enable(True)
        self.choosing = False
        self.view.buttons(False, False)
        self.root.attributes("-topmost", False)
        if game is not None and 0 <= game < len(self.games):
            if not self.busy:
                self.game = self.games[game]
            self.play()
        else:
            self.let_sim()

    def let_sim(self):
        if self.busy:
            return
        for g in self.games:
            install.clear_match_root(g.sider)
        self.view.score(None, None, "FM24 SIMULATES", "idle")
        self.view.status("Watching FM24", "ok")
        self.view.message("FM24 simulates this one", "Waiting for the next match day...")

    # ------------------------------------------------------------------ the game (PES 2021 / SPFL26)
    def play(self):
        if self.busy or not self.matchday:
            return
        self.busy = True
        self.fm_done = threading.Event()
        self.fm_ok = False
        self.view.step(0)
        self.view.status(f"Preparing {self.game.short}", "busy")
        self.view.message("Building the squads", f"Rebuilding both FM24 match squads in {self.game.name}...")
        threading.Thread(target=self._play, daemon=True).start()
        threading.Thread(target=self._fm_sim, daemon=True).start()

    def _fm_sim(self):
        """FM24 plays its own match out in the background meanwhile, so the SPFL26 result can go in as soon as
        it is known (FM keeps the full-time screen open until the bridge leaves it)."""
        try:
            self.fm_ui.play_to_full_time(status=lambda s: setattr(self, "fm_status", s), log=log)
            self.fm_ok = True
            log(f"FM24 is at full time, waiting for the {self.game.short} result")
        except Exception as e:  # noqa: BLE001 - the player can still play FM's match out by hand
            log(f"FM24 auto-sim stopped: {e}")
        finally:
            self.fm_done.set()

    def user_side(self) -> str:
        md = self.matchday
        if md["away"].get("human") and not md["home"].get("human"):
            return "away"
        return "home"

    def _play(self):
        md, g = self.matchday, self.game
        try:
            self._ensure_setup(g)
            sider, root = g.sider, g.root
            self.writer = None
            fm_date = None
            try:
                from fm_writer import FmResultWriter
                self.writer = FmResultWriter(md["home"]["team_ptr"], md["away"]["team_ptr"])
                if self.writer.lock_fixture() is None:
                    flipped = FmResultWriter(md["away"]["team_ptr"], md["home"]["team_ptr"])
                    if flipped.lock_fixture() is not None:
                        md = self.matchday = {**md, "home": md["away"], "away": md["home"]}
                        self.writer = flipped
                fm_date = fm_date_text(self.writer.date)
            except Exception as e:  # noqa: BLE001
                self.writer = None
                self.detail_msg(f"FM24 fixture not found for the result write-back ({e}).")
            install.clear_match_root(sider)
            db = PesDb.load(g.dir, g.extra_roots)
            try:
                from spfl_faces import real_face_ids
                faces = real_face_ids(g.dir)
            except Exception as e:  # noqa: BLE001 - records are lent without knowing their faces
                faces = None
                log(f"{g.short} real faces not read ({e})")
            b = self.builder = MatchBuilder(db, faces, g.key)
            plan = b.build(md, fm_date_value(self.writer.date) if self.writer and self.writer.date else datetime.date.today())
            self.plan = plan
            b.write_root(root)
            self._write_crests(root, md, plan)
            if b.face_lends or b.portrait_lends or b.blank_portraits:
                try:
                    from spfl_faces import lend_faces
                    n = lend_faces(g.dir, root, b.face_lends, b.portrait_lends, b.blank_portraits)
                    log(f"faces: {len(b.face_lends)} players show their own {g.short} face, {len(b.hidden_faces)} "
                        f"borrowed real faces hidden, {len(b.blank_portraits)} without a portrait ({n} files)")
                except Exception as e:  # noqa: BLE001 - the borrowed records keep their own faces
                    log(f"faces not lent ({e})")
            os.makedirs(os.path.join(sider, "matchday"), exist_ok=True)
            for stale in ("result.txt",):
                if os.path.exists(os.path.join(sider, "matchday", stale)):
                    os.remove(os.path.join(sider, "matchday", stale))
            with open(os.path.join(sider, "matchday", "build.log"), "w", encoding="utf-8") as f:
                f.write("\n".join(b.log))
            home, away = self.card_teams(plan)
            self.ui(self.view.fixture, home, away, f"FM24  ·  {fm_date}" if fm_date else "FM24")
            where = "; ".join(f"{p['fm_name']}: " + (f"in {p['slot_name'].title()}'s slot" if p["spare_slot"]
                                                       else f"{p['spfl_name']} ({p['league'] or g.short})")
                              for p in (plan["home"], plan["away"]))
            log(f"plan in {g.short}: {where}")
            self.ui(self.view.step, 1)
            import spfl_scorers
            spfl_scorers.use_game(g.exe)
            for other in self.games:                  # one game at a time: both would read the bridge's controller
                if other is not g and is_running(other.exe):
                    log(f"closing {other.short}: this match is played in {g.short}")
                    self._restore_live()
                    stop_processes((other.exe, "sider.exe"))
            hot = self._load_running(b)
            req = os.path.join(sider, "matchday", "request.txt")
            with open(req + ".tmp", "w", encoding="utf-8") as f:     # the running game polls this file
                f.write(request_lines(md, plan, "FM24", fm_date or datetime.date.today().isoformat()))
            os.replace(req + ".tmp", req)
            if hot:
                self.ui(self.view.status, f"{g.short} already running", "busy")
                self.say(f"Loading the match into {g.name}",
                         f"{g.short} is already running: the FM24 squads went straight into it, no restart needed.",
                         where)
                pad_ok = True
            else:
                self.ui(self.view.status, f"Starting {g.short}", "busy")
                self.say(f"Starting {g.name}", TEXT["game_restart"].format(game=g.name), where)
                if is_running(g.exe) or is_running("sider.exe"):
                    stop_processes((g.exe, "sider.exe"))
                pad_ok = self._install_pad()
                self._launch()
                if not self._sider_ready():
                    raise RuntimeError(f"Sider did not load in {g.short}, so the FM24 squads can't go in. Its log "
                                       f"{os.path.join(g.sider, 'sider.log')} says why.")
            threading.Thread(target=self.wait_result, daemon=True).start()
            self._drive(pad_ok, hot)
        except Exception as e:  # noqa: BLE001
            self.busy = False
            log(f"build failed: {e}")
            self.ui(self.view.step, 0, True)
            self.ui(self.view.status, "Build failed", "error")
            self.say(f"Could not build the {g.short} match", str(e))

    def _ensure_setup(self, g):
        """The game's Sider is set up (PES 2021: downloaded) before its first match; a failed setup is retried."""
        self.setup_done.wait(300)
        sider_ok = os.path.exists(os.path.join(g.sider, "sider.exe" if g.key == "pes2021" else "sider.ini"))
        if sider_ok and os.path.exists(os.path.join(g.sider, "modules", "matchday.lua")):
            return
        self.ui(self.view.message, f"Setting up {g.name}", "Getting Sider, the mod loader the bridge uses in the game "
                "(official Sider 7.4.1 from GitHub)..." if g.key == "pes2021" else "")
        done = install.install_pes2021(g.dir) if g.key == "pes2021" else install.install_spfl(g.dir)
        log(f"{g.short}: " + "; ".join(done))

    def _sider_ready(self, timeout: float = 360.0) -> bool:
        """Wait until matchday.lua has started in the game just launched: it rewrites hooks.txt once Sider has set up
        its hooks, seconds after the start normally, but minutes on the first start after Sider was installed (Sider
        then searches the whole exe while the game is already up). The menus are walked only after that."""
        g = self.game
        p = os.path.join(g.matchday, "hooks.txt")
        since, said = self.launched_at, False
        end = time.time() + timeout
        while time.time() < end:
            try:
                if os.path.getmtime(p) >= since:
                    log(f"matchday.lua started in {g.short} {time.time() - since:.0f}s after the launch")
                    return True
            except OSError:
                pass
            if not said and time.time() - since > 45:
                said = True
                self.say(f"Starting {g.name}", "Sider is still setting itself up inside the game. The first start "
                         "after it was installed takes a few minutes; later starts take seconds.")
            time.sleep(1)
        log(f"matchday.lua did not start in {g.short} within {timeout:.0f}s")
        return False

    def _write_live(self):
        """The FM24 players straight into the running game's memory (Select Team is reached, so its database is
        loaded). After a fresh start the LiveCPK root normally put them there already; this covers a Sider that came
        up after the game had read its database (first start after Sider was installed)."""
        if getattr(self, "live", None) is not None:
            return
        from spfl_live import LiveDb
        live = LiveDb(self.game.exe)
        n = live.write_players(self.builder.assigned)
        self.live = live
        log(f"wrote {n} FM24 players into {self.game.short}'s memory at Select Team")

    def _launch(self):
        """Start the game with Sider. SPFL26: its own launcher, as administrator. PES 2021: sider.exe, which starts
        the game through Steam (start.game in sider.ini); explorer.exe runs it un-elevated like a double-click, so
        neither Steam nor the game inherits the bridge's administrator rights. A Sider set up without start.game
        gets the game started through Steam here as well."""
        g = self.game
        self.launched_at = time.time()
        if g.key == "spfl26":
            ctypes.windll.shell32.ShellExecuteW(None, "runas", os.path.join(g.dir, "FL 2026 start.exe"), None, g.dir, 1)
            return
        subprocess.Popen(["explorer.exe", os.path.join(g.sider, "sider.exe")], creationflags=0x08000000)

        def steam_fallback():
            time.sleep(25)
            if not is_running(g.exe):
                log(f"{g.short} did not start from Sider; asking Steam")
                subprocess.Popen(["explorer.exe", f"steam://rungameid/{install.PES_APPID}"], creationflags=0x08000000)
        threading.Thread(target=steam_fallback, daemon=True).start()

    def _load_running(self, builder) -> bool:
        """A running game (with the controller proxy and this version of matchday.lua) gets the squads written
        into its memory instead of a restart. False: restart as before."""
        g = self.game
        prev, self.live = getattr(self, "live", None), None
        if not is_running(g.exe):
            return False
        try:
            import spfl_pad
            spfl_pad.shm()
            if not self._lua_current():
                log(f"{g.short} is running without Sider (e.g. started from Steam) or with an older matchday.lua: "
                    "restarting it")
                return False
            if not spfl_pad.polled(2):
                log(f"{g.short} is running without the controller proxy: restarting it")
                return False
            self._restore_live(prev)                 # the previous match's FM24 players stayed in until now
            from spfl_live import LiveDb
            self.live = LiveDb(g.exe)
            n = self.live.write_players(builder.assigned)
            log(f"wrote {n} FM24 players into the running {g.short}")
            return True
        except Exception as e:  # noqa: BLE001 - fall back to a restart (the LiveCPK root is written already)
            log(f"could not load the match into the running {g.short} ({e}): restarting it")
            if getattr(self, "live", None):
                self.live.restore()
            self.live = None
            return False

    def _lua_current(self) -> bool:
        """The running game has Sider in it (a game started from Steam alone has not) and loaded a matchday.lua that
        knows this exe (0.6.0+): sider.dll is among its modules and its sider.log line says so."""
        g = self.game
        try:
            from procmem import Proc
            p = Proc(g.exe)
            try:
                p._module("sider.dll")
            finally:
                p.close()
        except (LookupError, OSError, PermissionError, ProcessLookupError):
            return False
        try:
            text = open(os.path.join(g.sider, "sider.log"), encoding="utf-8", errors="replace").read()
        except OSError:
            return False
        m = re.findall(r"matchday: matchday\.lua (\d+)\.(\d+)(?:\.(\d+))?", text)
        return bool(m) and tuple(int(x or 0) for x in m[-1]) >= (0, 6, 0)

    def _write_crests(self, root: str, md: dict, plan: dict):
        """Clubs in a spare slot wear FM24's own logo as their crest (a drawn badge when FM has none)."""
        import fm_graphics
        for side in ("home", "away"):
            p = plan[side]
            if not p["spare_slot"]:
                continue
            try:
                png = fm_graphics.club_logo(self.fm_dir, md[side].get("club_id"))
                fm_graphics.write_crests(root, p["spfl_team"],
                                         fm_graphics.crest_images(png, p["fm_name"], p.get("abbr", "")))
                p["crest"] = "FM24 logo" if png else "drawn badge"
                log(f"crest for {p['fm_name']}: {p['crest']} (FM club id {md[side].get('club_id')})")
            except Exception as e:  # noqa: BLE001 - the spare slot keeps its own crest
                log(f"crest for {p['fm_name']} not written: {e}")

    def _install_pad(self) -> bool:
        """The XInput proxy that lets the bridge press controller-1 buttons in the background (game closed)."""
        try:
            import spfl_pad
            spfl_pad.shm()
            if spfl_pad.install(self.game.dir, install.resource("spfl", "xinput", "xinput1_3.dll")):
                log(f"installed the controller proxy xinput1_3.dll into the {self.game.short} folder")
            return True
        except Exception as e:  # noqa: BLE001 - no auto-pick: the player picks the teams as before
            log(f"controller proxy not installed: {e}")
            return False

    def _drive(self, pad_ok: bool, hot: bool = False):
        """Title screen -> Local Match -> sides -> teams -> pre-match screen, then the player takes over."""
        plan, side, g = self.plan, self.user_side(), self.game
        you = plan[side]["fm_name"]
        where = {s: f" ({plan[s]['league']})" if plan[s]["league"] else "" for s in ("home", "away")}
        manual = TEXT["pick_teams"].format(home_spfl=plan["home"]["spfl_name"], away_spfl=plan["away"]["spfl_name"],
                                           home_where=where["home"], away_where=where["away"])
        self.ui(self.view.step, 2)
        self.ui(self.view.status, "Picking teams", "busy")
        self.say("Setting up the match", TEXT["drive_busy"].format(home=plan["home"]["spfl_name"], game=g.short,
                                                                   away=plan["away"]["spfl_name"], you=you))
        err = "the controller proxy could not be installed"
        if pad_ok:
            from spfl_drive import BackOutError, DriveError, Driver
            for attempt in (("hot", "cold") if hot else ("cold",)):
                if attempt == "cold" and hot:
                    self._restart_game(err)
                d = Driver(plan, side, status=lambda s: self.detail_msg(s), log=log,
                           shots=os.path.join(os.path.dirname(LOG), "last_match"), sider=g.sider, exe=g.exe,
                           before_teams=self._write_live)
                try:
                    d.run(from_anywhere=(attempt == "hot"))
                    err = None
                except BackOutError as e:            # the running game is stuck somewhere: restart it
                    err = str(e)
                    d.keep("fail")
                    continue
                except DriveError as e:
                    err = str(e)
                    d.keep("fail")
                except Exception as e:  # noqa: BLE001
                    err = f"unexpected error: {e}"
                    d.keep("fail")
                finally:
                    d.close()
                break
        if err is None:
            self.ui(self.view.step, 3)
            self.ui(self.view.status, f"Your turn in {g.short}", "ok")
            self.say("Your turn", TEXT["drive_ready"].format(you=you, side=side, game=g.short),
                     f"The live score shows here. Scorers are read from {g.short}'s goal captions, so keep its window "
                     "open (it may be covered, not minimized).")
        else:
            log(f"auto-pick stopped: {err}")
            self.ui(self.view.step, 2, True)
            self.ui(self.view.status, "Pick the teams yourself", "warn")
            self.say(f"Pick the teams in {g.short}", manual + f" Put controller 1 on {you} ({side}).",
                     f"Automatic setup stopped: {err}.")

    def _restart_game(self, why: str):
        """The running game could not be set up from where it was: start it again (the squads are in the
        LiveCPK root already; matchday.lua reads request.txt when it loads)."""
        g = self.game
        log(f"restarting {g.short}: {why}")
        self.ui(self.view.status, f"Restarting {g.short}", "busy")
        self.say(f"Restarting {g.name}", f"It could not be set up where it was ({why}), so it is "
                 "restarted with this match's squads.")
        self.live = None                             # the game's memory goes with it
        stop_processes((g.exe, "sider.exe"))
        res = os.path.join(g.matchday, "result.txt")
        if os.path.exists(res):
            os.remove(res)                           # the abandoned match's live score
        self._install_pad()
        self._launch()
        if not self._sider_ready():
            log(f"Sider did not load in {g.short} (see {os.path.join(g.sider, 'sider.log')})")

    def wait_result(self):
        try:
            self._wait_result()
        finally:
            self.busy = False

    def _wait_result(self):
        game = self.game
        p = os.path.join(game.matchday, "result.txt")
        md = self.matchday
        goals: list[dict] = []          # one per goal: side, minute, scorer (FM person id or None)
        readers: list[threading.Thread] = []
        prefetch = None
        self.prefetched = None
        self.spfl_over = threading.Event()
        scorer = None
        shown = ""
        self.player_goals = None
        try:
            from spfl_scorers import ScorerReader
            scorer = ScorerReader(self.plan)
        except Exception as e:  # noqa: BLE001 - no OCR: the score still goes back, scorers stay FM's own
            self.detail_msg(f"Scorers can't be read from {game.short} ({e}); only the score goes back.")

        def read_scorer(g):
            hit = scorer.read(g["side"]) if scorer else None
            g["own"] = bool(hit and hit.get("own_goal"))
            g["pid"] = hit.get("fm_pid") if hit else None
            g["name"] = hit.get("name") if hit else None
            log(f"goal {g['minute']}' side {g['side']}: {g['name'] or 'scorer not read'}"
                + (" (own goal)" if g["own"] else ""))

        def label(g) -> str:
            return f"{g['name'] or ('own goal' if g.get('own') else '?')}{' (og)' if g.get('own') and g['name'] else ''}" \
                   f" {g['minute']}'"

        def scorer_lines() -> str:
            out = []
            for side in (0, 1):
                mine = [label(g) for g in goals if g["side"] == side]
                if mine:
                    out.append(f"{md['home' if side == 0 else 'away']['name']}: " + ", ".join(mine))
            return "\n".join(out)

        while True:
            time.sleep(0.4)
            if prefetch is None and self.fm_done.is_set() and self.fm_ok and self.writer and self.writer.date:
                prefetch = threading.Thread(target=self._prefetch, daemon=True)   # FM waits at full time already
                prefetch.start()
            if not os.path.exists(p):
                continue
            try:
                r = dict(l.split("=", 1) for l in open(p, encoding="utf-8").read().split() if "=" in l)
            except OSError:
                continue
            hg, ag = int(r.get("home", 0)), int(r.get("away", 0))
            line = f"{md['home']['name']} {hg}-{ag} {md['away']['name']}"
            marks = [x for x in r.get("goals", "").split(",") if x]
            if len(marks) < len(goals):                      # a new SPFL match started
                goals = []
            for x in marks[len(goals):]:
                m = re.fullmatch(r"([ha])(\d+)p(\d+)", x)
                if not m:
                    continue
                g = {"side": 0 if m.group(1) == "h" else 1, "minute": fm_minute(int(m.group(2)), int(m.group(3))),
                     "pid": None, "name": None}
                goals.append(g)
                t = threading.Thread(target=read_scorer, args=(g,), daemon=True)
                t.start()
                readers.append(t)
            if r.get("final") != "1":
                live = f"{line} ({r.get('minute')}')|{scorer_lines()}"
                if live != shown:
                    if not shown:
                        self.ui(self.view.step, 3)
                        self.ui(self.view.status, f"Live in {game.short}", "ok")
                    shown = live
                    log(f"Live in {game.short}: {live}")
                    self.ui(self.view.score, hg, ag, f"LIVE  {r.get('minute')}'", "live")
                    self.ui(self.view.message, f"Live in {game.name}",
                            scorer_lines() or "No goals yet.", getattr(self, "fm_status", ""))
                continue
            if int(r.get("minute", 0)) < 90 and int(r.get("period", 0)) < 3:
                self.spfl_over.set()
                self.ui(self.view.score, hg, ag, f"LEFT AT {r.get('minute')}'", "warn")
                self.ui(self.view.step, 3, True)
                self.ui(self.view.status, "Match left early", "warn")
                self.say("Nothing goes into FM24", f"The {game.short} match was left at {r.get('minute')}' ({line}), so "
                         "FM24's own result stands. Carry on in FM24.")
                return
            break
        for t in readers:
            t.join(timeout=10)
        length = 120 if int(r.get("minute", 0)) > 90 else 90   # SPFL logs a last-second goal after full time
        for g in goals:
            g["minute"] = min(g["minute"], length)
        goals = reconcile_goals(goals, hg, ag)
        self.ui(self.view.score, hg, ag, "FULL TIME", "ok")
        if not self.writer or not self.writer.date:
            self.ui(self.view.step, 4, True)
            self.ui(self.view.status, "Enter the result in FM24", "warn")
            self.say(f"Full time: {line}", "The FM24 fixture could not be found, so enter the result yourself.")
            return
        read = sum(1 for g in goals if g["pid"])
        self.ui(self.view.step, 4)
        self.ui(self.view.status, "Waiting for FM24's full time", "busy")
        title, body = two_lines(TEXT["writeback_wait"].format(home=md["home"]["name"], away=md["away"]["name"], game=game.short,
                                                              hg=hg, ag=ag))
        self.say(title, body, f"Scorers read from {game.short}: {read} of {hg + ag}. "
                 + ", ".join(label(g) for g in goals))
        events, prepared, left, left_at, leave_tries = None, False, False, 0.0, 0
        self.spfl_over.set()
        if prefetch is not None:
            prefetch.join(timeout=60)                # its scans and the writes below must not overlap
        while True:
            time.sleep(1)
            try:
                if not is_running("fm.exe"):
                    self.ui(self.view.step, 4, True)
                    self.ui(self.view.status, "Not saved", "error")
                    self.say("Not saved", f"FM24 closed before its match finished; the {game.short} score was not saved.")
                    return
                res = self.writer.apply(hg, ag)
                if not prepared and res["finished"]:          # FM's full time: its own events still intact
                    prepared = True
                    try:
                        events = self._prepare_events(goals)
                    except Exception as e:  # noqa: BLE001 - the score still goes back; scorers stay FM's own
                        log(f"scorers not written: {e}")
                if events is not None:
                    self.writer.apply_events(events)
                if res["written"] and not res["committed"] and self.fm_done.is_set() and \
                        (not left or (time.time() - left_at > 30 and leave_tries < 2)):
                    left, left_at, leave_tries = True, time.time(), leave_tries + 1
                    if self.fm_ok:
                        self.detail_msg(f"FM24 full time: {game.short} result swapped in; leaving FM's match screen.")
                        try:
                            self.fm_ui.leave_match(log=log)
                        except Exception as e:  # noqa: BLE001
                            self.detail_msg(f"Leave FM24's match screen to save the result ({e}).")
                    else:
                        self.detail_msg(f"FM24 full time: {game.short} result swapped in. Leave the match screen to save it.")
                if res["committed"]:
                    if events is not None:
                        self.writer.apply_events(events)
                    self.ui(self.view.step, 5)
                    self.ui(self.view.status, "Saved in FM24", "ok")
                    self.ui(self.view.score, hg, ag, "SAVED IN FM24", "ok")
                    self.say(TEXT["writeback_done"].format(home=md["home"]["name"], away=md["away"]["name"],
                                                           hg=hg, ag=ag),
                             scorer_lines() or "No goals.", "Waiting for the next match day...")
                    for wait in (0, 6):                       # FM copies the match stats again when you leave
                        time.sleep(wait)
                        self._apply_stats()
                    return
            except Exception as e:  # noqa: BLE001
                self.detail_msg(f"Write-back retrying ({e})")

    def _prefetch(self):
        """FM24 sits at full time while the player is still in SPFL26: read FM's own events and find today's
        player-stat records now (both are memory scans of several seconds), so the result goes in at once."""
        try:
            md = self.matchday
            t = time.time()
            self.writer.copies(rescan=True)
            fm_events = self.writer.fm_events()
            if fm_events is None:
                raise RuntimeError("FM's fixture is not finished in memory yet")
            pids = {pl["pid"] for side in ("home", "away") for pl in md[side]["players"] if pl.get("pid")}
            runs = self.writer.live_stats(pids, fm_events)
            self.prefetched = (fm_events, pids, runs)
            log(f"FM24 full time read ahead in {time.time() - t:.0f}s: {len(fm_events)} events, {len(runs)} stat runs")
            while not self.spfl_over.wait(120):      # keep the fixture copies fresh until the SPFL26 result
                self.writer.copies(rescan=True)
        except Exception as e:  # noqa: BLE001 - the write-back reads them itself then
            log(f"FM24 read-ahead failed: {e}")

    def _restore_live(self, live=None):
        """The SPFL26 players a match borrowed get their own records back (the game keeps running). Done when the
        next match is loaded or the bridge closes, not at full time: a Rematch in SPFL26 keeps the FM24 teams."""
        if live is None:
            live, self.live = getattr(self, "live", None), None
        if live:
            try:
                log(f"restored {live.restore()} players in the game")
            except Exception as e:  # noqa: BLE001 - the game may have been closed
                log(f"the game's players not restored: {e}")

    def _prepare_events(self, goals: list[dict]):
        """At FM's full time: FM's own events (read before anything is changed), then the SPFL scorers' event
        list and per-player goals. Returns the event list to keep in every fixture copy."""
        from fm_writer import merge_events
        md = self.matchday
        pre = getattr(self, "prefetched", None)
        if pre:
            self.fm_events, self.stat_pids, runs = pre
        else:
            self.fm_events = self.writer.fm_events()
            self.stat_pids = {pl["pid"] for side in ("home", "away") for pl in md[side]["players"] if pl.get("pid")}
            runs = None
        fallback = {i: [p["fm_pid"] for p in reversed(self.plan[side]["players"]) if p.get("starter") and p.get("fm_pid")
                        and not p.get("gk")] for i, side in enumerate(("home", "away"))}
        events = merge_events(goals, self.fm_events, fallback, own_goal_fallback(md))
        self.player_goals = {}
        for e in events:
            if e[2] in (0, 2):
                self.player_goals[e[0]] = self.player_goals.get(e[0], 0) + 1
        log(f"FM events {self.fm_events} -> {events}")
        if runs is not None:
            n = self.writer.apply_player_stats(runs, self.player_goals)
            log(f"player stats updated in {len(runs)} runs ({n} records), read ahead")
        else:
            self._apply_stats()
        return events

    def _apply_stats(self):
        """Per-player goals in every copy of today's match stats that still has FM's own goals (the match
        panel's goal icons)."""
        if self.player_goals is None:
            return
        try:
            runs = self.writer.live_stats(self.stat_pids, self.fm_events)
            n = self.writer.apply_player_stats(runs, self.player_goals)
            log(f"player stats updated in {len(runs)} runs ({n} records)")
        except Exception as e:  # noqa: BLE001 - the match panel icons are cosmetic; the event list is what counts
            log(f"player stats not updated: {e}")


def fm_date_value(d: int) -> datetime.date:
    return datetime.date((d >> 16) & 0xFFFF, 1, 1) + datetime.timedelta(days=(d & 0x1FF) - 1)


def fm_date_text(d: int | None) -> str | None:
    return fm_date_value(d).strftime("%d %b %Y").lstrip("0") if d else None


def own_goal_fallback(md: dict) -> dict[int, list[int]]:
    """{side: FM person ids} for an own goal whose player could not be read: the side's starting defenders
    (centre backs first), then its other outfield starters."""
    from spfl_build import best_positions
    from fl26db import POSITIONS
    order = {"CB": 0, "LB": 1, "RB": 1, "DMF": 2}
    out = {}
    for i, side in enumerate(("home", "away")):
        starters = [p for p in md[side]["players"] if p.get("slot", 99) < 11 and p.get("pid")]
        ranked = sorted((order.get(POSITIONS[best_positions(p)[0]], 3), p["slot"], p["pid"]) for p in starters
                        if POSITIONS[best_positions(p)[0]] != "GK")
        out[i] = [pid for _, _, pid in ranked]
    return out


def reconcile_goals(goals: list[dict], hg: int, ag: int) -> list[dict]:
    """Make the logged SPFL goals agree with the final score per side: extra marks are dropped, missing goals
    are added at full time with an unknown scorer."""
    out = []
    for side, n in ((0, hg), (1, ag)):
        mine = [g for g in goals if g["side"] == side][:n]
        mine += [{"side": side, "minute": 90, "pid": None, "name": None} for _ in range(n - len(mine))]
        out += mine
    return sorted(out, key=lambda g: g["minute"])


def main():
    if "--selftest" in sys.argv:            # checks the bundled capture + OCR: the game window's text -> bridge.log
        import spfl_drive  # noqa: F401
        import fm_drive  # noqa: F401
        import fm_graphics
        import spfl_pad
        import ui  # noqa: F401
        from spfl_scorers import WindowFrames, _window, ocr_lines, use_game
        dll = install.resource("spfl", "xinput", "xinput1_3.dll")
        found = find_games()
        game = next((g for g in found if is_running(g.exe)), found[0] if found else None)
        logo = fm_graphics.club_logo(install.find_fm24(), 694)
        try:
            from spfl_live import LiveDb
            live = (f"{len(LiveDb(game.exe).addr)} live players in {game.short}" if game and is_running(game.exe)
                    else "no game running")
        except Exception as e:  # noqa: BLE001
            live = f"live players not read: {e}"
        from PIL import Image, ImageTk
        t = tk.Tk()
        ph = ImageTk.PhotoImage(Image.open(io.BytesIO(logo)) if logo else Image.new("RGBA", (8, 8)))
        t.destroy()
        log(f"selftest: games {[g.short for g in found]}, proxy {os.path.getsize(dll) if os.path.exists(dll) else 'MISSING'} B, "
            f"installed in game: {spfl_pad.installed(game.dir, dll) if game else None}, game reading it: "
            f"{spfl_pad.polled(2)}, FM24 logo for club 694: {len(logo) if logo else None} B, "
            f"ImageTk {ph.width()}x{ph.height()}, {live}")
        if game:
            use_game(game.exe)
        h = _window()
        frames = WindowFrames(h) if h else None
        img = frames.client_image(2.0) if frames else None
        log(f"selftest: game window {h:#x} ({game.short if game else 'no game'}), frame {img.size if img else None}, "
            f"OCR {ocr_lines(img)[:8] if img else None!r}")
        if frames:
            frames.stop()
        return
    if "--uninstall" in sys.argv:
        from tkinter import messagebox
        done = []
        for g in find_games():
            if is_running(g.exe):
                done.append(f"{g.short}: still running, nothing removed; close it and run --uninstall again")
                continue
            done += [f"{g.short}: {d}" for d in install.uninstall_game(g.dir, g.sider, g.name)]
        tk.Tk().withdraw()
        messagebox.showinfo(APP, "\n".join(done) or "Neither PES 2021 nor SP Football Life 2026 found; nothing to remove.")
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))   # physical pixels, like FM24
    except (OSError, AttributeError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (OSError, AttributeError):
            pass
    root = tk.Tk()
    br = Bridge(root)
    try:
        root.mainloop()
    finally:
        br.fm_ui.enable(True)               # never leave FM24 without input if the choice was still open
        br._restore_live()


if __name__ == "__main__":
    main()
