"""Drive SP Football Life 2026 fast, in the background (run ELEVATED: the game runs as admin).

    python testkit/spfl.py start                      # (re)start SPFL26, wait for the title screen
    python testkit/spfl.py kickoff --home "Atlanta United FC" --away "Oldham Athletic" --user away
    python testkit/spfl.py skip-match                 # finish the current match in seconds, leave to menu
    python testkit/spfl.py state                      # what screen are we on

Never takes focus: input goes in as controller User 1 through the testkit XInput proxy (pad.py), screens are
read with Windows Graphics Capture (works while the window is covered; do not minimize it).
Speed comes from reacting to the screen (OCR, ~0.25 s) instead of fixed waits, 1-minute matches without
extra time/penalties (matchday_test.lua), and START on every skippable cut-scene/replay.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pad  # noqa: E402
import win  # noqa: E402

GAME = r"C:\Program Files (x86)\SP Football Life 2026"
HOME_LEAGUE = AWAY_LEAGUE = None
SIDER = os.path.join(GAME, "SiderAddons")
MD = os.path.join(SIDER, "matchday")
TITLE = "SP Football Life 2026"
SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "research", "shots")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ------------------------------------------------------------------ Sider test module
def set_test(**kv):
    """Write SiderAddons\\matchday\\test.txt (read by matchday_test.lua every second)."""
    cur = read_kv(os.path.join(MD, "test.txt"))
    cur.update({k: str(v) for k, v in kv.items() if v is not None})
    for k in [k for k, v in kv.items() if v is None]:
        cur.pop(k, None)
    with open(os.path.join(MD, "test.txt"), "w") as f:
        f.write("".join(f"{k}={v}\n" for k, v in cur.items()))


def read_kv(path) -> dict:
    try:
        return dict(re.findall(r"([\w_]+)=([^\r\n]*)", open(path, encoding="utf-8").read()))
    except OSError:
        return {}


_last_state: dict = {}


def game_state() -> dict:
    """From matchday_test.lua: ptr (live match), period (1/2 halves, 3 = finished), minute, second, home,
    away, paused, running (clock), stage (12 = waiting for kick-off), ev_* counters."""
    global _last_state
    path = os.path.join(MD, "test_state.txt")
    for _ in range(10):              # the module rewrites the file ~10x/s: retry an empty/partial read
        st = read_kv(path)
        if "ptr" in st and "t" in st:
            _last_state = st
            return st
        time.sleep(0.015)
    return dict(_last_state)         # still mid-write: the previous state is better than "no match"


def team_id(name: str) -> int:
    if name.isdigit():
        return int(name)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bridge"))
    from spfl_db import PesDb
    db = PesDb.load(GAME, [os.path.join(SIDER, "livecpk", "matchday"), os.path.join(SIDER, "livecpk", "root")])
    want = win.norm(name)
    names = {tid: win.norm(db.team_name(tid)) for tid in db.team_index}
    for tid, n in names.items():
        if n == want:
            return tid
    close = [tid for tid, n in names.items() if n.startswith(want) or want.startswith(n) and len(n) > 4]
    if len(close) == 1:
        return close[0]
    raise SystemExit(f"team not in SPFL26: {name} (candidates: {[db.team_name(t) for t in close][:8]})")


# ------------------------------------------------------------------ screens
# Old keyboard-style names still used by the callers -> User 1 pad buttons (pad.py).
KEY_TO_PAD = {"enter": "A", "esc": "B", "back": "B", "up": "UP", "down": "DOWN", "left": "LEFT",
              "right": "RIGHT", "x": "A", "space": "LT+RT"}


class Spfl:
    def __init__(self):
        self.h = win.find_window(TITLE)

    def shot(self):
        for _ in range(40):
            try:
                img = win.capture(self.h)
                if img.width > 100 and img.height > 100:
                    return img
            except OSError:
                pass
            time.sleep(0.25)
            try:
                self.h = win.find_window(TITLE)  # the game re-creates its window on some transitions
            except RuntimeError:
                pass
        raise RuntimeError("SPFL26 window not capturable (minimized?)")

    def read(self, img=None):
        img = img or self.shot()
        lines = win.ocr(img, scale=1.0 if img.width >= 1200 else 1.5)
        t = win.norm(win.text_of(lines))
        if "sider7" in t or "stadiumservercommands" in t:   # Sider overlay (pad LT+RT toggles it)
            log("hiding Sider overlay")
            self.press("LT+RT")
            time.sleep(0.3)
            img = self.shot()
            lines = win.ocr(img, scale=1.0 if img.width >= 1200 else 1.5)
        return img, lines

    def screen(self) -> tuple[str, list]:
        """Classify the current screen from its text."""
        img, lines = self.read()
        t = win.norm(win.text_of(lines))
        rules = [
            ("pause", ["pausemenu"]),                       # START opened it; B (Return) resumes
            ("teamsheet", ["teamsheet"]),                   # Game Plan -> team sheet: A would swap players
            ("rematchmenu", ["startmatch", "returntotopmenu"]),   # after Rematch: "Start Match" preselected
            ("title", ["enter", "gameversion"]),
            ("fulltime", ["fulltime", "topmenu"]),
            ("fulltimestats", ["fulltime", "matchstats"]),
            ("halftime", ["halftime", "matchstats"]),
            ("halftime", ["2ndhalf"]),                      # half-time menu, "2nd Half" preselected
            ("highlights", ["matchhighlights"]),
            ("halftime", ["halftime"]),                     # same menu when OCR misses the red "2nd Half"
            ("prematch", ["kickoff", "gameplan"]),
            ("sides", ["home", "away", "confirm", "coachmode"]),
            ("teams", ["home", "away", "confirm", "random"]),
            ("matchmenu", ["localmatch", "randommatch"]),
            ("mainmenu", ["footballlife2026"]),
        ]
        for name, need in rules:
            if all(n in t for n in need):
                return name, lines
        if game_state().get("ptr", "0") not in ("0", ""):
            return "match", lines
        return "unknown", lines

    def press(self, seq: str, gap: float = 0.1):
        """'down*3,enter' or 'DOWN*3,A': pad buttons of User 1 (keyboard-style names are translated)."""
        for part in [p.strip() for p in seq.split(",") if p.strip()]:
            name, _, n = part.partition("*")
            pad.taps(f"{KEY_TO_PAD.get(name.lower(), name.upper())}*{n or 1}", gap * 1000)

    btn = press

    def wait_change(self, frm: str, timeout=20.0, poll=0.15):
        end = time.time() + timeout
        while time.time() < end:
            scr, lines = self.screen()
            if scr not in (frm, "unknown"):
                log("screen:", scr)
                return scr, lines
            time.sleep(poll)
        raise TimeoutError(f"still on {frm}")

    def advance(self, seq: str, frm: str, timeout=40.0, retry=2.0):
        """Press `seq` and re-press every `retry` s until the screen leaves `frm` (menus drop early input)."""
        end = time.time() + timeout
        while time.time() < end:
            self.press(seq)
            t = time.time() + retry
            while time.time() < t:
                scr, lines = self.screen()
                if scr not in (frm, "unknown"):
                    log("screen:", scr)
                    return scr, lines
                time.sleep(0.1)
        raise TimeoutError(f"still on {frm}")

    def wait(self, names, timeout=60.0, poll=0.25):
        names = {names} if isinstance(names, str) else set(names)
        end = time.time() + timeout
        last = None
        while time.time() < end:
            s, lines = self.screen()
            if s != last:
                log("screen:", s)
                last = s
            if s in names:
                return s, lines
            time.sleep(poll)
        self.shot().save(os.path.join(SHOTS, "spfl_timeout.png"))
        raise TimeoutError(f"waited for {names}, still on {last}")


# ------------------------------------------------------------------ actions
def install_test_module():
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "matchday_test.lua")
    dst = os.path.join(SIDER, "modules", "matchday_test.lua")
    if not os.path.exists(dst) or open(src, "rb").read() != open(dst, "rb").read():
        import shutil
        shutil.copy2(src, dst)
    ini = os.path.join(SIDER, "sider.ini")
    text = open(ini, encoding="utf-8", errors="replace").read()
    line = 'lua.module = "matchday_test.lua"'
    # before SPFL's matchset.lua: it answers "set_match_settings" itself, so later modules never see it
    anchor = 'lua.module = "matchset.lua"'
    if anchor in text and text.find(line) != -1 and text.find(line) < text.find(anchor):
        return
    text = re.sub(r'[ \t]*lua\.module = "matchday_test\.lua"\r?\n', "", text)
    if anchor in text:
        text = text.replace(anchor, line + "\n" + anchor, 1)
    else:
        text = text.replace('lua.module = "matchday.lua"', 'lua.module = "matchday.lua"\n' + line)
    open(ini, "w", encoding="utf-8").write(text)


def start(match_minutes: int | None = 1):
    for exe in ("FL_2026.exe", "sider.exe"):
        subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True)
    time.sleep(2)
    install_test_module()
    if pad.install():
        log("installed the testkit XInput proxy into the game folder")
    pad.ensure()
    set_test(match_minutes=match_minutes or None, extra_time=0, penalties=0)
    user_window = win.user32.GetForegroundWindow()
    t0 = time.time()
    # DEVNULL + detached: the launcher must not inherit our stdout pipe (it would keep callers waiting forever)
    subprocess.Popen([os.path.join(GAME, "FL 2026 start.exe")], cwd=GAME, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x00000008 | 0x00000200)
    while True:
        try:
            s = Spfl()
            break
        except RuntimeError:
            if time.time() - t0 > 90:
                raise
            time.sleep(0.5)
    give_back_focus(s, user_window)
    s.wait("title", timeout=90)
    give_back_focus(s, user_window)
    if not pad.polled():
        log("WARNING: the game is not reading the testkit pad (proxy not loaded?)")
    log(f"title screen after {time.time() - t0:.1f}s")
    return s


def give_back_focus(s: Spfl, user_window: int):
    """A freshly started game grabs the foreground; hand it back to whatever the user was using."""
    if user_window and user_window != s.h and win.is_foreground(s.h) and win.user32.IsWindow(user_window):
        win.focus(user_window, timeout=0.5)


def to_team_select(s: Spfl, user_side: str):
    """Title / main menu -> Match -> Local Match -> side select (controller on user_side) -> team select."""
    step = {"title": "enter", "mainmenu": "enter", "matchmenu": "enter"}
    for _ in range(12):
        scr, _ = s.wait(["title", "mainmenu", "matchmenu", "sides", "teams"], 90)
        if scr in step:
            s.advance(step[scr], scr, 60)
            continue
        if scr == "sides":
            if user_side in ("away", "none"):            # User 1 starts on Home; middle = CPU vs CPU
                s.press("RIGHT*2" if user_side == "away" else "RIGHT", gap=0.15)
            s.advance("enter", "sides", 20, retry=3)
            continue
        return
    raise RuntimeError("could not reach team select")


# ------------------------------------------------------------------ team select
LEAGUES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spfl_team_leagues.json")


def column(s: Spfl, side: str) -> list[tuple[int, str]]:
    """Visible entries of the home/away list as (offset from the highlighted entry, name).
    3 small entries above the big highlighted one and up to 3 below it."""
    img = s.shot()
    k = img.width / 1280
    x0, x1 = ((115, 585) if side == "home" else (690, 1165))
    lines = win.ocr(img, box=(x0 * k, 110 * k, x1 * k, 640 * k), scale=1.5)
    above, below, center = [], [], None
    for ln in lines:
        name = " ".join(w.text for w in ln)
        y = ln[0].y / k
        h = max(w.h for w in ln) / k
        if 236 <= y <= 300 and h > 18:
            center = name
        elif y < 236:
            above.append((y, name))
        elif y > 500:
            below.append((y, name))
    out = [(i - len(above), n) for i, (_, n) in enumerate(sorted(above))]
    out.append((0, center or ""))
    out += [(i + 1, n) for i, (_, n) in enumerate(sorted(below))]
    return out


def pick(s: Spfl, side: str, target: str, kind: str) -> str:
    """Move the highlighted league/team of `side` to `target` (accent/case-insensitive prefix match)."""
    want = win.norm(target)
    match = lambda n: bool(n) and (win.norm(n).startswith(want) or (len(win.norm(n)) > 6 and want.startswith(win.norm(n))))
    direction, last = "down", None
    for _ in range(40):
        col = column(s, side)
        hit = [o for o, n in col if match(n)]
        if hit:
            o = min(hit, key=abs)
            if o == 0:
                log(f"{kind} ({side}): {dict(col)[0]}")
                return dict(col)[0]
            s.press(f"{'down' if o > 0 else 'up'}*{abs(o)}", gap=0.09)
            time.sleep(0.2)
            continue
        view = [n for _, n in col]
        if view == last:                      # end of a non-wrapping list: turn round
            direction = "up" if direction == "down" else "down"
        last = view
        s.press(f"{direction}*7", gap=0.08)
        time.sleep(0.2)
    raise RuntimeError(f"{target!r} not found in the {side} {kind} list")


def league_of(team: str) -> str:
    import json
    try:
        m = json.load(open(LEAGUES, encoding="utf-8"))
    except (OSError, ValueError):
        m = {}
    want = win.norm(team)
    if want in m:
        return m[want]
    close = [v for k, v in m.items() if want.startswith(k) or k.startswith(want)]
    if len(close) == 1:
        return close[0]
    raise SystemExit(f"league of {team!r} unknown: pass --home-league/--away-league once (it is remembered)")


def remember_league(team: str, league: str):
    import json
    try:
        m = json.load(open(LEAGUES, encoding="utf-8"))
    except (OSError, ValueError):
        m = {}
    m[win.norm(team)] = league
    json.dump(m, open(LEAGUES, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def select_teams(s: Spfl, home: str, away: str, home_league: str, away_league: str):
    for side, team, league in (("home", home, home_league), ("away", away, away_league)):
        pick(s, side, league, "league")
        s.press("enter")
        time.sleep(0.5)
        pick(s, side, team, "team")
        remember_league(team, league)
        s.press("enter")
        time.sleep(0.5)


def has_skip(lines) -> bool:
    """A START-to-skip prompt is on screen (cut-scene, replay, highlights) or the replay viewer (START = End).
    Not "Toggle Display": the full-time menu shows that too."""
    t = win.norm(win.text_of(lines))
    return "skip" in t or "savereplay" in t


def live(st: dict) -> bool:
    return st.get("ptr", "0") not in ("0", "")


class ClockRate:
    """Game seconds per real second over the last ~1 s. ~90 while the ball is in play with 1-minute matches;
    ~0-1 at dead balls, celebrations, replays and while players walk back for a kick-off."""

    def __init__(self):
        self.hist = []

    def update(self, st: dict) -> float | None:
        now = time.time()
        if not live(st) or "minute" not in st:
            self.hist.clear()
            return None
        g = int(st["minute"]) * 60 + int(st["second"])
        if self.hist and self.hist[-1][1] != st.get("period"):
            self.hist.clear()
        self.hist.append((now, st.get("period"), g))
        while len(self.hist) > 2 and now - self.hist[1][0] >= 1.0:
            self.hist.pop(0)
        t, _, g0 = self.hist[0]
        return (g - g0) / (now - t) if now - t >= 0.8 else None


def restart_play(s: "Spfl"):
    """Kick-off / free kick / throw-in / goal kick for the user's team: short pass."""
    s.press("A")


HUD_CLOCK = re.compile(r"\b\d{1,3} ?[:.,;'\u2019\ufffd\u2022]{1,2} ?\d{2}\b")   # OCR of "72:46" varies


def in_match_action(scr: str, lines, st: dict, recent_pause: bool = False, cutscenes: bool = False) -> str:
    """Button for a non-playing moment. START skips cut-scenes, replays and highlights (the "Skip" prompt only
    shows once a button was pressed); B leaves the pause menu / team sheet; A confirms menus and kicks off.
    Sider has no match data (ptr=0) until the first kick-off, so the pre-match intro is told apart from the
    kick-off wait by the HUD clock on screen."""
    if scr in ("pause", "teamsheet"):
        return "B"
    if scr in ("halftime", "fulltimestats", "prematch", "fulltime", "rematchmenu"):
        return "A"
    if has_skip(lines) or scr == "highlights":
        return "START"                               # highlight reels only show "Skip" after a press
    if recent_pause:
        return "A"                                   # just closed a pause menu: kick off, don't pause again
    if HUD_CLOCK.search(win.text_of(lines)):
        return "A"                                   # match HUD: waiting for a kick-off / set piece
    if live(st):
        return "START" if st.get("paused") == "1" else "A"
    return "START" if cutscenes else "A"


class Actor:
    """Presses the in_match_action button, waiting after START so a fading 'Skip' prompt is not pressed twice
    (a second START opens the pause menu). `cutscenes`: past the pre-match menu, unknown screens are intro
    cut-scenes."""

    def __init__(self, s: "Spfl", verbose: bool = False, cutscenes: bool = False):
        self.s, self.verbose, self.paused_at, self.cutscenes = s, verbose, 0.0, cutscenes

    def act(self, scr: str, lines, st: dict):
        if scr == "pause":
            self.paused_at = time.time()
        if scr in ("prematch", "fulltime", "rematchmenu"):
            self.cutscenes = True
        act = in_match_action(scr, lines, st, time.time() - self.paused_at < 6, self.cutscenes)
        if self.verbose:
            log(f"  {act:5} {scr} ptr={st.get('ptr')} period={st.get('period')} paused={st.get('paused')} "
                f"stage={st.get('stage')} | {win.text_of(lines)[:50]!r}")
        self.s.press(act)
        time.sleep(1.5 if act == "START" else 0.3)


def kickoff(home: str | None, away: str | None, user_side: str = "away"):
    """Local Match: pick both teams by name (OCR), then kick off and skip the intro until the clock runs."""
    t0 = time.time()
    s = Spfl()
    to_team_select(s, user_side)
    if home and away:
        select_teams(s, home, away, HOME_LEAGUE or league_of(home), AWAY_LEAGUE or league_of(away))
    return play_intro(s, t0)


def rematch():
    """Full-time screen -> Rematch (same teams and sides, no team select): fastest way to replay a match."""
    t0 = time.time()
    s = Spfl()
    s.wait(["fulltime", "rematchmenu"], 30)
    return play_intro(s, t0)


def play_intro(s: "Spfl", t0: float, verbose: bool = False):
    """confirm prompts -> pre-match -> Kick Off -> loading -> intro cut-scenes (START skips) -> kick-off
    (pass, when the user's team has it). Returns when the ball is in play."""
    seen_prematch = False
    rate = ClockRate()
    actor = Actor(s, verbose)
    end = time.time() + 150
    while time.time() < end:
        st = game_state()
        r = rate.update(st)
        if r is not None and r > 5:
            break
        if live(st) and st.get("paused") == "0":
            restart_play(s)
            time.sleep(0.6)
            continue
        scr, lines = s.screen()
        if scr == "prematch" and not seen_prematch:
            seen_prematch = True
            log(f"pre-match after {time.time() - t0:.1f}s")
        actor.act(scr, lines, st)
    log(f"ball in play after {time.time() - t0:.1f}s", {k: game_state().get(k) for k in ("minute", "second")})
    return s


def clock() -> tuple[int, int]:
    st = game_state()
    return int(st.get("minute", 0) or 0), int(st.get("second", 0) or 0)


def skip_match(to_menu: bool = True, verbose: bool = False):
    """Play the current match out as fast as the game allows.
    Ball in play: wait. Dead ball / kick-off with the user's team on the ball: pass (A).
    Cut-scene, replay, highlights, replay viewer: START. Half time / full-time stats: A.
    With match_minutes=1 a whole match takes ~2 min."""
    t0 = time.time()
    s = Spfl()
    rate = ClockRate()
    actor = Actor(s, verbose, cutscenes=True)
    last_act = 0.0
    passes = 0
    while time.time() - t0 < 900:
        st = game_state()
        r = rate.update(st)
        if r is not None and r > 5 and st.get("paused") == "0":
            passes = 0
            time.sleep(0.1)                      # ball in play
            continue
        if time.time() - last_act < 0.9 or (live(st) and r is None and st.get("period") != "3"):
            time.sleep(0.1)
            continue
        last_act = time.time()
        if live(st) and st.get("paused") == "0" and st.get("period") != "3":
            passes += 1
            if passes % 5 == 4:                  # A did nothing for a while (goal celebration?): try START
                s.press("START")
                time.sleep(1.2)
                scr, lines = s.screen()
                if verbose:
                    log(f"  START at stall {st.get('minute')}:{st.get('second')} -> {scr} | {win.text_of(lines)[:50]!r}")
                if scr == "pause":
                    s.press("B")
                    time.sleep(0.5)
                continue
            if verbose:
                log(f"  pass  {st.get('minute')}:{st.get('second')} rate={r} stage={st.get('stage')}")
            restart_play(s)
            continue
        passes = 0
        scr, lines = s.screen()
        if scr == "fulltime":
            break
        actor.act(scr, lines, st)
    else:
        raise TimeoutError("match did not finish")
    st = game_state()
    log(f"full time {st.get('home')}-{st.get('away')} after {time.time() - t0:.1f}s")
    s.shot().save(os.path.join(SHOTS, "spfl_fulltime.png"))
    if not to_menu:
        return s
    s.press("RIGHT*2")                           # Rematch -> Select Team -> Top Menu
    scr, lines = s.advance("A", "fulltime", 20)
    menus = ("mainmenu", "matchmenu", "title", "sides", "teams", "prematch")
    for _ in range(20):                          # A only on the "back to the top menu?" question: never on a
        if scr in menus:                         # menu, where A would walk into a new match
            break
        if scr == "unknown" and "yes" in win.norm(win.text_of(lines)).replace("eyes", ""):
            s.press("A")
        time.sleep(0.8)
        scr, lines = s.screen()
    log(f"main menu after {time.time() - t0:.1f}s")
    return s


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["start", "kickoff", "skip-match", "state", "roundtrip"])
    ap.add_argument("--home")
    ap.add_argument("--away")
    ap.add_argument("--user", choices=["home", "away"], default="away")
    ap.add_argument("--minutes", type=int, default=1)
    ap.add_argument("--home-league")
    ap.add_argument("--away-league")
    a = ap.parse_args()
    HOME_LEAGUE, AWAY_LEAGUE = a.home_league, a.away_league
    if a.cmd == "start":
        start(a.minutes)
    elif a.cmd == "kickoff":
        kickoff(a.home, a.away, a.user)
    elif a.cmd == "skip-match":
        skip_match()
    elif a.cmd == "roundtrip":
        t0 = time.time()
        start(a.minutes)
        kickoff(a.home, a.away, a.user)
        skip_match()
        log(f"round trip {time.time() - t0:.1f}s")
    else:
        s = Spfl()
        scr, lines = s.screen()
        print(scr, game_state())
        print(win.text_of(lines))
