"""Walks PES 2021 or SP Football Life 2026 from its title screen to the pre-match screen of the FM24 fixture.

Title -> Match -> Local Match -> side select (controller 1 on the FM24 club the player manages) -> Select Team
(both clubs: set directly through matchday.lua's list-cursor hook, see spfl_select; by scrolling to the league and
club names with OCR when the hook is not there) -> pre-match screen (kits, stadium, Kick Off), where the player
takes over. PES 2021's top menu is a grid of unlabelled icons (Match is the top-left one; the panel title names the
highlighted icon) and its Match menu a short list (Local Match first); neither wraps round.

Input goes in as controller User 1 through the bridge's XInput proxy (spfl_pad), so the game window does not
need focus. Screens are read with Windows Graphics Capture + Windows OCR (spfl_scorers): every step waits for
the screen it expects, so a slow load only makes it slower, and anything unexpected hands the menus back to
the player (the old "pick the teams yourself" message) instead of pressing on.
"""
from __future__ import annotations

import ctypes
import difflib
import os
import re
import time
import unicodedata

import spfl_pad
from spfl_scorers import WindowFrames, game_window, ocr_words, screen_image

user32 = ctypes.windll.user32

# Select Team columns in a 1280x720 frame: list x range per side; the highlighted entry is the large one at
# y 236-300 with up to 3 small entries above and below it.
COLUMNS = {"home": (115, 585), "away": (690, 1165)}
LIST_Y, CENTER_Y = (110, 640), (236, 300)
TRANSLIT = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "ß": "ss", "đ": "d",
                          "Đ": "D", "ı": "i", "ð": "d", "þ": "th"})
OCR_FOLD = str.maketrans({"1": "l", "i": "l", "|": "l", "0": "o", "6": "o"})


def fold(s: str) -> str:
    """Accent/case-free letters and digits, with the characters Windows OCR confuses folded together."""
    s = unicodedata.normalize("NFKD", (s or "").translate(TRANSLIT))
    s = re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())
    return s.translate(OCR_FOLD)


def similarity(want: str, seen: str) -> float:
    a, b = fold(want), fold(seen)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if len(b) >= 8 and a.startswith(b) or len(a) >= 8 and b.startswith(a):
        return 0.9                                    # a long name cut short (or with a suffix) on screen
    return difflib.SequenceMatcher(None, a, b).ratio()


def text_of(lines) -> str:
    return "\n".join(" ".join(w[0] for w in ln) for ln in lines)


class DriveError(RuntimeError):
    pass


class BackOutError(DriveError):
    """The running game could not be brought back to its menus (e.g. it is in a match): restart it instead."""


HUD = re.compile(r"\b[0-9oO]{1,3}\s*[:.]\s*[0-9oO]{2}\b")


def in_match(lines, height: float = 0) -> bool:
    """The match HUD: SPFL26's clock ("0:00", OCR often reads "o:oo") with its LIVE badge; PES 2021's clock alone,
    at the top of the frame (given its height)."""
    t = text_of(lines)
    if HUD.search(t) and "live" in t.lower():
        return True
    return bool(height) and any(HUD.fullmatch(w[0].strip()) and w[2] < height * 0.12 for ln in lines for w in ln)


class Driver:
    def __init__(self, plan: dict, user_side: str, status=None, log=None, shots: str | None = None,
                 sider: str | None = None, exe: str = "FL_2026.exe", before_teams=None):
        self.plan, self.user_side = plan, user_side
        self.status = status or (lambda s: None)
        self.log = log or (lambda s: None)
        self.before_teams = before_teams    # called on reaching Select Team (the bridge writes the squads in)
        self.h, self.frames = 0, None
        self.cancelled = False
        self.shots = shots
        self.exe, self.pes = exe, exe.lower() == "pes2021.exe"
        self.height = 0
        self.club_settle = 0.0              # seconds between landing on a club and confirming it
        if sider is None:
            import install
            game = install.find_spfl26()
            sider = os.path.join(game, "SiderAddons") if game else ""
        self.sider = sider

    def keep(self, name: str):
        """Screenshot for the log folder (what the bridge saw at each step of the last match)."""
        if not self.shots:
            return
        try:
            os.makedirs(self.shots, exist_ok=True)
            self.shot(3).save(os.path.join(self.shots, f"{name}.png"))
        except Exception:  # noqa: BLE001 - diagnostics only
            pass

    # ------------------------------------------------------------------ screen
    def window(self) -> int:
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        h = game_window(self.exe)
        if h != self.h:
            if self.frames:
                self.frames.stop()
            self.h, self.frames = h, None
        return h

    def shot(self, timeout: float = 20.0):
        end = time.time() + timeout
        while time.time() < end:
            h = self.window()
            if h and not user32.IsIconic(h):
                try:
                    if self.frames is None or self.frames.closed:
                        self.frames = WindowFrames(h)
                    img = self.frames.client_image(1.0)
                except Exception:  # noqa: BLE001 - capture unavailable: the screen still shows a game on top
                    img = None
                if img is None or img.width < 640 or not img.getbbox():
                    img = screen_image(h) if user32.GetForegroundWindow() == h else None
                if img is not None and img.width >= 640:
                    self.height = img.height
                    return img
            time.sleep(0.3)
        raise DriveError("the game window can't be seen (minimized?)")

    def read(self):
        img = self.shot()
        k = img.width / 1280
        return img, ocr_words(img, scale=1.0 if k >= 0.94 else 1.4)

    def screen(self):
        img, lines = self.read()
        t = fold(text_of(lines))
        rules = [
            ("sider", ["sider7"]),
            ("topdialog", ["returntotopmenu", "cancel"]),        # PES 2021: Cancel (selected) | Return
            ("pause", ["pausemenu"]),
            ("rematchmenu", ["startmatch", "returntotopmenu"]),
            ("leavedialog", ["previousscreen", "proceed"]),     # No (selected) | Yes
            ("title", ["enter", "gameversion"]),
            ("title", ["pressanybutton"]),                       # PES 2021
            ("fulltime", ["fulltime", "topmenu"]),
            ("prematch", ["kickoff", "gameplan"]),
            ("sides", ["home", "away", "confirm", "coachmode"]),
            ("teams", ["home", "away", "confirm", "random"]),
            ("matchmenu", ["localmatch", "randommatch"]),
            ("matchmenu", ["localmatch", "coop", "training"]),   # PES 2021, over the top menu
            ("mainmenu", ["footballlife2026"]),
            ("mainmenu", ["featuredplayers"]),                   # PES 2021 top menu
        ]
        for name, need in rules:
            if all(fold(n) in t for n in need):
                return name, lines
        return "unknown", lines

    def press(self, seq: str, gap: float = 0.1):
        spfl_pad.taps(seq, gap * 1000)

    def wait(self, names, timeout: float, leave: str | None = None):
        """Wait for one of `names` (or, with `leave`, for any known screen other than it)."""
        end = time.time() + timeout
        last = None
        while time.time() < end:
            self.check()
            scr, lines = self.screen()
            if scr != last:
                self.log(f"spfl screen: {scr}")
                last = scr
            if scr == "sider":
                self.press("LT+RT")                         # the Sider overlay is open: close it
                time.sleep(0.5)
            elif scr in names or (leave and scr not in (leave, "unknown")):
                return scr, lines
            time.sleep(0.25)
        raise DriveError(f"the game stayed on the {last} screen")

    def advance(self, button: str, frm: str, timeout: float = 30.0, retry: float = 2.0):
        """Press `button` (again every `retry` s: menus drop input while they animate) until `frm` is left."""
        end = time.time() + timeout
        while time.time() < end:
            self.press(button)
            try:
                return self.wait((), retry, leave=frm)
            except DriveError:
                continue
        raise DriveError(f"the game did not leave the {frm} screen")

    def check(self):
        if self.cancelled:
            raise DriveError("cancelled")

    # ------------------------------------------------------------------ Select Team
    def column(self, side: str) -> list[tuple[int, str]]:
        """Visible entries of one Select Team list as (offset from the highlighted entry, text)."""
        img = self.shot()
        k = img.width / 1280
        x0, x1 = COLUMNS[side]
        lines = ocr_words(img, box=(x0 * k, LIST_Y[0] * k, x1 * k, LIST_Y[1] * k), scale=1.5 / max(k, 0.5))
        above, below, center = [], [], None
        for ln in lines:
            name = " ".join(w[0] for w in ln)
            y, h = ln[0][2] / k, max(w[4] for w in ln) / k
            if CENTER_Y[0] <= y <= CENTER_Y[1] and h > 18:
                center = name
            elif y < CENTER_Y[0]:
                above.append((y, name))
            elif y > 500:
                below.append((y, name))
        out = [(i - len(above), n) for i, (_, n) in enumerate(sorted(above))]
        out.append((0, center or ""))
        out += [(i + 1, n) for i, (_, n) in enumerate(sorted(below))]
        return out

    def pick(self, side: str, target: str, kind: str) -> str:
        """Move the highlighted league/club of `side` onto `target`: scroll the list (it does not wrap: turn
        round at an end) until an entry reads close enough, then step onto it."""
        direction, last, turns, moved = "DOWN", None, 0, False
        for _ in range(80):
            self.check()
            col = self.column(side)
            scored = sorted(((similarity(target, n), o, n) for o, n in col if n), reverse=True)
            if scored and scored[0][0] >= 0.82:
                _, o, n = scored[0]
                if o == 0 and not moved and kind == "club":   # land on it with a move: SPFL26 rebuilds its line-up
                    self.press("UP" if len(col) > 1 and col[0][0] < 0 else "DOWN", gap=0.09)
                    moved = True
                    time.sleep(0.25)
                    continue
                if o == 0:
                    self.log(f"spfl {side} {kind}: {n!r} for {target!r}")
                    return n
                self.press(f"{'DOWN' if o > 0 else 'UP'}*{abs(o)}", gap=0.09)
                moved = True
                time.sleep(0.25)
                continue
            view = [n for _, n in col]
            if view == last:
                turns += 1
                if turns > 2:
                    break
                direction = "UP" if direction == "DOWN" else "DOWN"
            last = view
            self.press(f"{direction}*6", gap=0.08)
            moved = True
            time.sleep(0.25)
        raise DriveError(f"{target!r} is not in the {side} {kind} list")

    def pick_teams(self):
        if self.before_teams:
            try:
                self.before_teams()
            except Exception as e:  # noqa: BLE001 - the squads from the LiveCPK root are still there
                self.log(f"spfl squads not written before Select Team: {e}")
        self._wait_rosters()
        hook = None
        try:
            from spfl_select import SelectHook
            hook = SelectHook(self.sider, self.exe)
        except Exception as e:  # noqa: BLE001 - older matchday.lua or no access: scroll the lists by OCR
            self.log(f"spfl Select Team hook not available ({e}): scrolling the lists")
        try:
            for side in ("home", "away"):
                p = self.plan[side]
                self.status(f"Selecting {p['spfl_name']} ({side})")
                done = self.fast_pick(hook, side) if hook else None
                if done == "club":
                    continue
                if p.get("league") and done != "league":
                    self.pick(side, p["league"], "league")
                    self.press("A")
                    time.sleep(0.6)
                self.pick(side, p["spfl_name"], "club")
                if side == "away":
                    self.keep("2_teams")
                self.press("A")
                time.sleep(0.6)
        finally:
            if hook:
                hook.close()

    def _wait_rosters(self, timeout: float = 15.0):
        """SPFL26 builds a club's line-up when the Select Team cursor lands on it, from the live roster at that
        moment: wait until matchday.lua has written the FM24 rosters (it polls request.txt every second)."""
        want = {self.plan[s]["spfl_team"]: self.plan[s].get("ids") for s in ("home", "away")}
        if not all(want.values()):
            return
        try:
            from spfl_live import live_rosters
        except ImportError:
            return
        end = time.time() + timeout
        while True:
            try:
                have = live_rosters(set(want), self.exe)
            except OSError as e:
                self.log(f"spfl rosters not readable ({e})")
                return
            if all(have.get(t) == ids for t, ids in want.items()):
                return
            if time.time() > end:
                self.log("spfl rosters still not the FM24 squads; picking the teams anyway")
                return
            time.sleep(0.3)

    def fast_pick(self, hook, side: str) -> str | None:
        """One column through matchday.lua's Select Team hook (spfl_select): one cursor move tells which list widget
        the column is, the club's team id gives both indices, and each cursor is set with a single press.
        Returns "club" when league and club are confirmed, "league" when only the league is (the OCR pick does the
        club), None when nothing is (the OCR pick does both)."""
        p = self.plan[side]
        stage = None
        try:
            t0 = time.time()
            w = self._column_widget(hook)
            league, club = hook.find(w, p["spfl_team"])
            if not hook.club_mode(w):
                self._set_cursor(hook, w, league, lambda: hook.league_cursor(w), len(hook.leagues(w)))
                self.press("A")
                if not hook.wait(lambda: hook.club_mode(w), 3.0):
                    raise RuntimeError("the league was not confirmed")
            elif len(hook.leagues(w)) != 1:
                raise RuntimeError("the column is in its club list already")
            stage = "league"                     # PES 2021 LITE: its one list of clubs starts confirmed
            n = len(hook.clubs(hook.leagues(w)[league]))
            self._set_cursor(hook, w, club, lambda: hook.club_cursor(w, league), n)
            landed = time.time()
            seen = dict(self.column(side)).get(0, "")
            if seen and similarity(p["spfl_name"], seen) < 0.6:
                raise RuntimeError(f"the column shows {seen!r}")
            self.log(f"spfl {side}: league {league}, club {club} = {seen!r} via the Select Team hook "
                     f"({time.time() - t0:.1f}s)")
            if side == "away":
                self.keep("2_teams")
            time.sleep(max(0.0, self.club_settle - (time.time() - landed)))
            self.press("A")
            time.sleep(0.6)
            return "club"
        except Exception as e:  # noqa: BLE001 - the OCR pick takes over from where this stopped
            hook.disarm()
            self.log(f"spfl {side}: Select Team hook not used ({e})")
            return stage

    def _column_widget(self, hook) -> int:
        """The active column's list widget: the one whose league cursor moves on DOWN (UP at the list's end), or whose
        club cursor does when its only list starts confirmed (PES 2021 LITE)."""
        end = time.time() + 5
        while time.time() < end:
            for button in ("DOWN", "UP"):
                n0 = hook.moves()
                self.press(button)
                if hook.wait(lambda: hook.moves() != n0, 0.5):
                    w, cell = hook.last_list()
                    if cell - w == 0x118:
                        return w
                    from spfl_select import L_CURSOR
                    if hook.club_mode(w) and any(cell == lg + L_CURSOR for lg in hook.leagues(w)):
                        return w
                    raise RuntimeError("the cursor that moved is not a Select Team list's")
        raise RuntimeError("the Select Team list did not move")

    def _set_cursor(self, hook, w: int, target: int, read, n: int):
        """Armed hook + one DOWN (UP on the last entry): the game stores `target` as the new cursor. The cursor always
        moves onto the target (off it first when it is there already): SPFL26 builds the highlighted club's line-up
        only on a move, and the roster may have changed since it was last highlighted."""
        if read() == target and n > 1:
            before = read()
            self.press("DOWN" if target < n - 1 else "UP")
            if not hook.wait(lambda: read() != before, 0.8):
                raise RuntimeError("the cursor did not move off the entry")
        hook.arm(w, target)
        try:
            for _ in range(4):
                self.press("DOWN" if read() < n - 1 else "UP")
                if hook.wait(lambda: read() == target, 0.8):
                    time.sleep(0.15)                   # let the list redraw before A
                    return
            raise RuntimeError(f"the cursor stayed at {read()} (wanted {target})")
        finally:
            hook.disarm()

    # ------------------------------------------------------------------ PES 2021 menus
    def _pes_match_icon(self):
        """Top menu: Match is the top-left icon (the grid does not wrap); its panel reads "Kick Off / Face off
        against ... in various match types" ("Welcome!" on the very first start)."""
        for _ in range(3):
            self.press("UP*2,LEFT*4", gap=0.12)
            time.sleep(0.6)
            t = fold(text_of(self.read()[1]))
            if fold("variousmatchtypes") in t or fold("welcome") in t:
                return
        raise DriveError("PES 2021's Match icon could not be found on the top menu")

    def _pes_local_match(self):
        """Match menu: Local Match is the first of three entries (no wrap); the highlighted one is drawn white."""
        for _ in range(3):
            self.press("UP*3", gap=0.12)
            time.sleep(0.5)
            img = self.shot()
            w, h = img.width, img.height
            px = img.crop((int(w * 0.10), int(h * 0.415), int(w * 0.26), int(h * 0.455))).convert("L").resize((1, 1))
            if px.getpixel((0, 0)) > 150:
                return
        raise DriveError("PES 2021's Local Match entry could not be highlighted")

    # ------------------------------------------------------------------ the whole walk
    def back_out(self, timeout: float = 60.0):
        """A game that was already running can be on any menu: back out to side select (or the main menu, match menu
        or title screen) first. Full time: Top Menu; PES 2021's pause menu: Top Menu too (its last entry); anything
        else: B (Return)."""
        self.status("Back to the game's main menu")
        end = time.time() + timeout
        unknown_since = None
        while time.time() < end:
            self.check()
            scr, lines = self.screen()
            self.log(f"spfl screen (backing out): {scr}")
            if scr in ("title", "mainmenu", "matchmenu", "sides"):
                return
            if scr == "unknown":
                if unknown_since is None:
                    unknown_since = time.time()
                    self.log(f"spfl unknown screen reads: {text_of(lines).replace(chr(10), ' | ')[:160]!r}")
                if in_match(lines, self.height if self.pes else 0):
                    if not self.pes:
                        raise BackOutError("the game is in the middle of a match")
                    self.press("START")                  # PES 2021: pause, then Top Menu (below)
                    time.sleep(1.5)
                    continue
                if time.time() - unknown_since > 20:     # not a loading screen: somewhere B does not get out of
                    raise BackOutError("the game is on a screen the bridge can't back out of")
            else:
                unknown_since = None
            if scr == "sider":
                self.press("LT+RT")
            elif scr in ("leavedialog", "topdialog"):   # "...settings will be lost. Proceed?" -> Yes; PES -> Return
                self.press("RIGHT", gap=0.15)
                time.sleep(0.4)
                self.press("A")
            elif scr in ("fulltime", "pause") and self.pes:
                self.press("RIGHT*9", gap=0.12)         # PES 2021: Top Menu is the last entry (no wrap)
                time.sleep(0.4)
                self.press("A")                         # -> "Return to Top Menu?" (topdialog)
            elif scr == "fulltime":
                self.press("RIGHT*2", gap=0.15)         # Rematch / Select Team / Top Menu
                time.sleep(0.3)
                self.press("A")
                time.sleep(1.5)
                self.press("A")                      # "return to the top menu?" -> Yes
            else:
                self.press("B")
            time.sleep(0.5 if scr == "teams" else 1.5)  # Select Team steps back one list per B, same screen
        raise BackOutError("could not get the game back to its main menu")

    def run(self, start_timeout: float = 150.0, from_anywhere: bool = False) -> None:
        """Raises DriveError when the player has to take over (the reason is in the message)."""
        if self.shots and os.path.isdir(self.shots):
            for n in os.listdir(self.shots):
                if n.endswith(".png"):
                    try:
                        os.remove(os.path.join(self.shots, n))
                    except OSError:
                        pass
        self.status("Waiting for the game to start")
        end = time.time() + start_timeout
        while not self.window():
            self.check()
            if time.time() > end:
                raise DriveError("the game did not open a window")
            time.sleep(0.5)
        spfl_pad.release()
        if not spfl_pad.polled(20):
            raise DriveError("the game is not reading the bridge's controller input (xinput1_3.dll proxy)")
        if from_anywhere:
            self.back_out()
        sides_done = teams_done = False
        end = time.time() + 240
        while time.time() < end:
            scr, _ = self.wait(("title", "mainmenu", "matchmenu", "sides", "teams", "prematch", "pause"), 120)
            if scr == "title":
                self.status("Title screen")
                self.advance("A", "title", 60)
            elif scr == "mainmenu":
                self.status("Main menu > Match")
                if self.pes:
                    self._pes_match_icon()
                self.advance("A", "mainmenu")
            elif scr == "matchmenu":
                self.status("Match > Local Match")
                if self.pes:
                    self._pes_local_match()
                self.advance("A", "matchmenu")
            elif scr == "sides":
                if not sides_done:
                    you = self.plan[self.user_side]["fm_name"]
                    self.status(f"Controller 1 on {you} ({self.user_side})")
                    self.press("LEFT*2", gap=0.15)          # leftmost = Home whatever the start position
                    if self.user_side == "away":
                        self.press("RIGHT*2", gap=0.15)     # Home -> CPU (middle) -> Away
                    sides_done = True
                    time.sleep(0.4)
                    self.keep("1_sides")
                self.advance("A", "sides", 20, retry=3)
            elif scr == "teams":
                if teams_done:
                    self.advance("A", "teams", 20)         # Confirm
                    continue
                self.pick_teams()
                teams_done = True
            elif scr == "pause":
                self.press("B")
                time.sleep(0.5)
            elif scr == "prematch":
                if not teams_done:
                    raise DriveError("the game went to a match before the teams were picked")
                self.status("Ready")
                self.keep("3_prematch")
                return
        raise DriveError("the game did not reach the pre-match screen")

    def close(self):
        spfl_pad.release()
        if self.frames:
            self.frames.stop()
