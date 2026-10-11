"""Drive Football Manager 2024 fast, in the background (dev testkit only; FM is not elevated).

    python testkit/fm.py start                 # launch FM24 (Steam) and load the most recent save
    python testkit/fm.py reload                # reload "Matchday Lab" without saving (~7 s): back to match day
    python testkit/fm.py to-match              # Continue (Quick Pick, Submit Team, ...) until kick-off
    python testkit/fm.py skip-match            # play FM's match out (commentary only, top speed) to home
    python testkit/fm.py matchday              # reload + to-match + skip-match, timed
    python testkit/fm.py prefs                 # check FM's match settings: commentary only, replays off, max speed
    python testkit/fm.py state                 # current screen, main button and text
    python testkit/fm.py click "Quick Pick"    # click a button by its text
    python testkit/fm.py key space             # post a key

FM24 takes mouse and key messages posted to its window while it is in the background, so nothing here
moves the cursor or takes focus. Screens are read with Windows Graphics Capture + OCR (physical pixels; FM
is per-monitor DPI aware so click coordinates are the same pixels). Keep FM maximized, never minimized.
Space presses FM's main top-right button (Continue, Submit Team, Kick Off, ...), but pauses a live match,
so it is only pressed when that button shows a known label.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win  # noqa: E402

TITLE = "Football Manager 2024"
STEAM_APP = 2252570
LAB_SAVE = "Matchday Lab"
HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "..", "research", "shots")
u = win.user32

WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202
WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x0100, 0x0101, 0x0102
CLOCK = re.compile(r"\b(\d{1,3}):(\d{2})\b")

# Main-button labels Space may press (never during play: there Space pauses the match).
ADVANCE = ("CONTINUE", "NEXT UNREAD", "MATCHES", "TEAM SELECTION", "SUBMIT TEAM", "GO TO MATCH",
           "DRESSING ROOM", "MATCH PREVIEW", "KICK OFF", "START SECOND HALF", "SOCIAL FEED", "MUST RESPOND")

# Layout in a 2000-px-wide frame (FM scales its UI with the window; measured on 2560x1334).
GEAR = (1840, 23)                     # match settings panel toggle during a match
PLAY = (1950, 23)                     # resume button when FM paused the match
FM_MENU = (1596, 38)                  # "FM" game menu in the top bar
HL_DROPDOWN = (1400, 110)
REPLAYS = {"On": (1641, 114), "Off": (1697, 114)}
SLIDERS = (175, 229, 283)             # y of: speed during highlights, text-only highlights, between highlights
SLIDER_X = (1222, 1582)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


class Fm:
    def __init__(self):
        self.h = win.find_window(TITLE)
        self.lines: list = []
        self.text = ""
        self.img = None

    # ------------------------------------------------------------ input (posted, no focus)
    def click(self, x: float, y: float, settle: float = 0.05):
        lp = (int(y) << 16) | (int(x) & 0xFFFF)
        u.PostMessageW(self.h, WM_MOUSEMOVE, 0, lp)
        time.sleep(settle)
        u.PostMessageW(self.h, WM_LBUTTONDOWN, 1, lp)
        time.sleep(0.05)
        u.PostMessageW(self.h, WM_LBUTTONUP, 0, lp)

    def click_at(self, pt: tuple[float, float]):
        """Click a point given in the 2000-px layout frame."""
        k = self.k()
        self.click(pt[0] * k, pt[1] * k)

    def drag(self, src: tuple[float, float], dst: tuple[float, float], steps: int = 12):
        lp = lambda x, y: (int(y) << 16) | (int(x) & 0xFFFF)
        u.PostMessageW(self.h, WM_MOUSEMOVE, 0, lp(*src))
        time.sleep(0.1)
        u.PostMessageW(self.h, WM_LBUTTONDOWN, 1, lp(*src))
        time.sleep(0.2)
        for i in range(1, steps + 1):
            u.PostMessageW(self.h, WM_MOUSEMOVE, 1, lp(src[0] + (dst[0] - src[0]) * i / steps,
                                                     src[1] + (dst[1] - src[1]) * i / steps))
            time.sleep(0.04)
        time.sleep(0.2)
        u.PostMessageW(self.h, WM_LBUTTONUP, 0, lp(*dst))

    def key(self, name: str, hold: float = 0.03):
        vk = win.vk_of(name)
        sc = u.MapVirtualKeyW(vk, 0)
        ext = 1 << 24 if vk in win.EXTENDED else 0
        u.PostMessageW(self.h, WM_KEYDOWN, vk, 1 | (sc << 16) | ext)
        if len(name) == 1:
            u.PostMessageW(self.h, WM_CHAR, ord(name), 1 | (sc << 16))
        time.sleep(hold)
        u.PostMessageW(self.h, WM_KEYUP, vk, 1 | (sc << 16) | ext | (3 << 30))

    # ------------------------------------------------------------ screen
    def shot(self):
        for _ in range(20):
            try:
                return win.capture(self.h, 2.0)
            except OSError:
                time.sleep(0.25)
                self.h = win.find_window(TITLE)
        raise RuntimeError("FM24 window not capturable (minimized?)")

    def k(self) -> float:
        return (self.img or self.shot()).size[0] / 2000

    def read(self):
        self.img = self.shot()
        self.lines = win.ocr(self.img)
        self.text = win.text_of(self.lines)
        return self.lines

    def has(self, *phrases: str) -> bool:
        t = win.norm(self.text)
        return all(win.norm(p) in t for p in phrases)

    def top(self) -> str:
        """Text of the top bar's left part: page title, or the match clock/score/status."""
        k = self.k()
        return " | ".join(" ".join(w.text for w in ln) for ln in self.lines if ln[0].y < 58 * k and ln[0].x < 940 * k)

    def clock(self) -> int | None:
        """Match clock in game seconds when a match is on screen."""
        k = self.k()
        t = " ".join(" ".join(w.text for w in ln) for ln in self.lines if ln[0].y < 45 * k and ln[0].x < 160 * k)
        m = CLOCK.search(t)
        return int(m.group(1)) * 60 + int(m.group(2)) if m else None

    def button(self) -> str:
        """Label of FM's main top-right button (CONTINUE, NEXT UNREAD, SUBMIT TEAM, KICK OFF, ...).
        Read from a scaled, grey-inverted crop: OCR misses white-on-purple at 1:1. Only labels from ADVANCE
        count: during a match this corner shows stadium ads."""
        from PIL import ImageOps
        img = self.img or self.shot()
        w, h = img.size
        crop = ImageOps.invert(img.crop((int(w * 0.86), 0, w, int(h * 0.065))).convert("L")).convert("RGB")
        lines = win.ocr(crop, scale=2.0)
        label = " ".join(wd.text for ln in lines for wd in ln if re.search(r"[A-Za-z]{2}", wd.text)).upper()
        return next((a for a in ADVANCE if label.startswith(a)), "")

    def find(self, phrase: str, region: tuple[float, float, float, float] | None = None, exact: bool = False):
        """Center of `phrase` on the last read screen; region = (x0, y0, x1, y1) as fractions of the window.
        exact: whole words must match (for short labels like "Ok", which OCR also reads as "0k")."""
        lines = self.lines
        if region and self.img is not None:
            w, h = self.img.size
            x0, y0, x1, y1 = region[0] * w, region[1] * h, region[2] * w, region[3] * h
            lines = [ln for ln in lines if any(x0 <= wd.x <= x1 and y0 <= wd.y <= y1 for wd in ln)]
        if not exact:
            return win.find_text(lines, phrase)
        want = [win.norm(t) for t in phrase.split()]
        alias = {"ok": {"ok", "0k"}}
        for ln in lines:
            toks = [win.norm(wd.text) for wd in ln]
            for i in range(len(toks) - len(want) + 1):
                if all(toks[i + j] in alias.get(want[j], {want[j]}) for j in range(len(want))):
                    a, b = ln[i], ln[i + len(want) - 1]
                    return (a.x + b.x + b.w) / 2, a.y + a.h / 2
        return None

    def click_text(self, phrase: str, region=None, reread: bool = True, exact: bool = False) -> bool:
        if reread:
            self.read()
        p = self.find(phrase, region, exact)
        if not p:
            return False
        self.click(*p)
        return True

    def screen(self) -> str:
        self.read()
        t = win.norm(self.text)
        top = win.norm(self.top())
        rules = [
            ("mainmenu", lambda: "startanewgame" in t and "loadgame" in t),
            ("loading", lambda: "loadinggame" in t),
            ("injury", lambda: "injuredplayers" in t),
            ("savedialog", lambda: "currentgameisnotsaved" in t),
            ("confirm", lambda: "proceedtomatch" in t or "dontshowthismessageagain" in t),
            ("loadlist", lambda: "loadgame" in top or ("loadgame" in t and ("browse" in t or ("delete" in t and "cancel" in t)))),
            ("fulltime", lambda: "fulltime" in top),
            ("halftime", lambda: "halftime" in top),
            ("teamtalk", lambda: "peptalk" in top),
            ("prematch", lambda: "prematch" in top),
            ("match", lambda: self.clock() is not None and "vs" not in top),
            ("teamselection", lambda: "teamselection" in top),
            ("game", lambda: "inbox" in t and "squad" in t),
        ]
        for name, test in rules:
            if test():
                return name
        return "unknown"

    def save(self, name: str):
        (self.img or self.shot()).save(os.path.join(SHOTS, name + ".png"))


# ------------------------------------------------------------------ match settings
def _orange(px) -> bool:
    r, g, b = px[:3]
    return r > 200 and 110 < g < 200 and b < 90


def read_prefs(fm: Fm) -> dict:
    """Current highlight mode, replays and speed sliders (0..1) from the open settings panel."""
    k = fm.k()
    img = fm.img.convert("RGB")
    hl = " ".join(" ".join(w.text for w in ln) for ln in fm.lines
                  if 1222 * k <= ln[0].x <= 1560 * k and 95 * k <= ln[0].y <= 125 * k)
    replays = "On" if _orange(img.getpixel((int(REPLAYS["On"][0] * k), int(REPLAYS["On"][1] * k)))) else "Off"
    sliders = []
    for y in SLIDERS:
        xs = [x for x in range(int(SLIDER_X[0] * k) - 10, int(SLIDER_X[1] * k) + 10)
              if _orange(img.getpixel((x, int(y * k))))]
        sliders.append(round(((sum(xs) / len(xs)) / k - SLIDER_X[0]) / (SLIDER_X[1] - SLIDER_X[0]), 3) if xs else None)
    return {"highlights": hl.strip(), "replays": replays, "sliders": sliders}


def set_prefs(fm: Fm, highlights: str, replays: str, sliders: list[float | None]):
    k = fm.k()
    fm.click_at(HL_DROPDOWN)
    time.sleep(1.0)
    fm.read()
    if not fm.click_text(highlights, region=(1222 * k / fm.img.size[0], 0.1, 0.8, 0.4), reread=False, exact=True):
        log(f"highlight option {highlights!r} not found")
    time.sleep(0.8)
    fm.click_at(REPLAYS[replays])
    time.sleep(0.4)
    for y, f in zip(SLIDERS, sliders):
        if f is not None:
            fm.click_at((SLIDER_X[0] + min(max(f, 0.0), 1.0) * (SLIDER_X[1] - SLIDER_X[0]) - (4 if f >= 1 else 0), y))
            time.sleep(0.3)


def prefs(fm: Fm | None = None):
    """Make sure FM's match settings are commentary only, replays off, all speeds max (the user keeps them
    like that). Only changes what differs. Needs a match on screen (the panel lives in the match view)."""
    fm = fm or Fm()
    fm.click_at(GEAR)
    time.sleep(1.2)
    fm.read()
    cur = read_prefs(fm)
    if cur["highlights"] != "Only Commentary" or cur["replays"] != "Off" or \
            any(s is None or s < 0.97 for s in cur["sliders"]):
        log("FM match settings were", cur, "-> commentary only, replays off, max speed")
        set_prefs(fm, "Only Commentary", "Off", [1.0, 1.0, 1.0])
    fm.click_at(GEAR)                 # close the panel
    time.sleep(0.5)


# ------------------------------------------------------------------ actions
def start(timeout: float = 180) -> Fm:
    """Launch FM24 through Steam (if needed) and load the most recent save."""
    t0 = time.time()
    if not u.FindWindowW(None, TITLE):
        os.startfile(f"steam://rungameid/{STEAM_APP}")
    while True:
        try:
            fm = Fm()
            break
        except RuntimeError:
            if time.time() - t0 > timeout:
                raise
            time.sleep(1)
    while time.time() - t0 < timeout:
        scr = fm.screen()
        if scr == "mainmenu":
            if not (fm.click_text("Load '", reread=False) or fm.click_text("MOST RECENT", reread=False)):
                fm.click_text("LOAD GAME", reread=False)
        elif scr not in ("unknown", "loading"):
            log(f"FM24 ready ({scr}) after {time.time() - t0:.1f}s")
            return fm
        time.sleep(1.0)
    raise TimeoutError("FM24 did not reach a game screen")


def reload(save: str = LAB_SAVE, timeout: float = 90) -> Fm:
    """FM menu -> Load Game -> don't save -> `save` -> Load; returns on the game's home/inbox screen."""
    t0 = time.time()
    fm = Fm()
    stage = "menu"
    if fm.screen() != "loadlist":
        fm.click_at(FM_MENU)
        time.sleep(1.2)
        if not fm.click_text("Load Game", region=(0.78, 0, 1, 0.25), exact=True):
            raise RuntimeError("FM menu: no Load Game")
    while time.time() - t0 < timeout:
        time.sleep(0.8)
        scr = fm.screen()
        if scr == "savedialog":
            fm.click_text("No", reread=False, exact=True)
        elif scr == "loadlist" and stage != "loading":
            p = fm.find(save, exact=True)
            if p:
                fm.click(*p)
                time.sleep(0.5)
                if fm.click_text("Load", region=(0.55, 0.7, 0.75, 0.85), exact=True):
                    stage = "loading"
        elif scr == "game" and stage == "loading":
            log(f"reloaded {save!r} in {time.time() - t0:.1f}s")
            return fm
    raise TimeoutError(f"could not reload {save!r}")


def to_match(timeout: float = 240, until: str | None = None) -> Fm:
    """Continue until today's match kicks off: inbox items, Quick Pick + Submit Team, briefing, team talk,
    Kick Off. Returns once the match clock is on screen, or earlier on screen `until` ("prematch": squads
    final, match not started; "submit": team selection after Quick Pick)."""
    t0 = time.time()
    fm = Fm()
    picked = False
    while time.time() - t0 < timeout:
        scr = fm.screen()
        if scr == "match":
            log(f"kick-off after {time.time() - t0:.1f}s")
            return fm
        if until and scr == until:
            log(f"{scr} after {time.time() - t0:.1f}s")
            return fm
        if scr == "injury":
            handle_injury(fm)
            continue
        if scr == "confirm":                          # "Proceed to match?" and similar Yes/No prompts
            if not (fm.click_text("Yes", reread=False, exact=True) or fm.click_text("Ok", reread=False, exact=True)):
                fm.save("fm_confirm_unhandled")
            time.sleep(1.2)
            continue
        b = fm.button()
        if b == "MUST RESPOND":                       # an inbox item FM won't continue without (test saves only)
            fm.key("space")
            time.sleep(2.0)
            fm.read()
            if not any(fm.click_text(t, reread=False, exact=True) for t in ("Reject Offer", "Reject", "Ignore")):
                fm.save("fm_must_respond_unhandled")
            time.sleep(1.5)
            continue
        if b == "SUBMIT TEAM" and not picked:
            picked = fm.click_text("Quick Pick", reread=False, exact=True)
            time.sleep(1.0)
            continue
        if b == "SUBMIT TEAM" and until == "submit":
            log(f"team selection after {time.time() - t0:.1f}s")
            return fm
        if b:
            fm.key("space")
            time.sleep(1.5 if b in ("CONTINUE", "NEXT UNREAD") else 2.0)
        else:
            time.sleep(1.0)
    raise TimeoutError("did not reach kick-off")


def handle_injury(fm: Fm):
    """FM paused for an injured player and will not resume until he is replaced: Ok, then drag the first
    suitable substitute onto him (goalkeeper for a goalkeeper), then Play."""
    fm.click_text("Ok", reread=False, exact=True)
    time.sleep(1.2)
    fm.read()
    k = fm.k()
    names = sorted((ln for ln in fm.lines if 560 * k <= ln[0].x < 860 * k and 220 * k < ln[0].y < 1000 * k
                    and re.search(r"[A-Za-z]{2}", " ".join(w.text for w in ln))), key=lambda ln: ln[0].y)
    inj_y = [w.y for ln in fm.lines for w in ln if w.text == "Inj"]

    def pos(ln):
        y = ln[0].y
        return " ".join(w.text for l2 in fm.lines for w in l2 if 900 * k <= w.x < 1200 * k and abs(w.y - y) < 12 * k)

    hurt = next((ln for ln in names[:11] if any(abs(ln[0].y - y) < 12 * k for y in inj_y)), None)
    if hurt is None:
        log("injury: injured player not found")
        fm.save("fm_injury_unhandled")
        return
    gk = pos(hurt).startswith("GK")
    sub = next((ln for ln in names[11:] if pos(ln).startswith("GK") == gk), None)
    if sub is None:
        log("injury: no substitute found")
        fm.save("fm_injury_unhandled")
        return
    name = lambda ln: " ".join(w.text for w in ln)
    log(f"injury: {name(sub)} replaces {name(hurt)}")
    fm.drag((sub[0].x + 40 * k, sub[0].y + sub[0].h / 2), (hurt[0].x + 40 * k, hurt[0].y + hurt[0].h / 2))
    time.sleep(1.0)
    fm.click_text("Confirm Changes", exact=True)
    time.sleep(1.0)
    fm.click_at(PLAY)
    time.sleep(1.5)


def to_full_time(timeout: float = 600) -> Fm:
    """Play FM's live match to the FULL TIME screen and stop there (before FM commits anything)."""
    t0 = time.time()
    fm = Fm()
    last_clock, still_since = None, time.time()
    while time.time() - t0 < timeout:
        scr = fm.screen()
        if scr == "fulltime":
            log(f"full time after {time.time() - t0:.1f}s")
            return fm
        if scr == "match":
            c = fm.clock()
            if c != last_clock:
                last_clock, still_since = c, time.time()
            elif time.time() - still_since > 6:
                fm.click_at(PLAY)
                still_since = time.time()
            time.sleep(1.0)
            continue
        if scr == "injury":
            handle_injury(fm)
            continue
        if scr == "confirm":
            fm.click_text("Yes", reread=False, exact=True) or fm.click_text("Ok", reread=False, exact=True)
            time.sleep(1.2)
            continue
        if fm.button() in ("START SECOND HALF", "DRESSING ROOM", "KICK OFF"):
            fm.key("space")
            time.sleep(1.8)
        else:
            time.sleep(1.0)
    raise TimeoutError("FM match did not reach full time")


def skip_match(timeout: float = 600, check_prefs: bool = False, verbose: bool = False) -> dict:
    """Play FM's match out as fast as FM allows (commentary only, top speed — set once in FM's match
    settings; check_prefs re-checks them), through half time and the post-match screens, back to the game.
    Returns the final score shown at full time."""
    t0 = time.time()
    fm = Fm()
    fast = not check_prefs
    score, full_time = None, False
    last_clock, still_since = None, time.time()
    last_log, last_scr = 0.0, None
    while time.time() - t0 < timeout:
        scr = fm.screen()
        if verbose and (scr != last_scr or time.time() - last_log > 10):
            log(f"  {time.time() - t0:6.1f}s {scr:13} clock={fm.clock()} button={fm.button()!r} | {fm.top()[:70]!r}")
            last_log, last_scr = time.time(), scr
        m = re.search(r"\b(\d{1,2})\s*-\s*(\d{1,2})\b", fm.top()) if scr in ("match", "fulltime", "halftime") else None
        if m:
            score = (int(m.group(1)), int(m.group(2)))      # the score box is not always read; keep the last one
        if scr == "match":
            if not fast:
                prefs(fm)
                fast = True
            c = fm.clock()
            if c != last_clock:
                last_clock, still_since = c, time.time()
            elif time.time() - still_since > 6:              # paused by FM (tactics view, ...)
                fm.click_at(PLAY)
                still_since = time.time()
            time.sleep(1.0)
            continue
        if scr == "injury":
            handle_injury(fm)
            continue
        if scr == "confirm":
            fm.click_text("Yes", reread=False, exact=True) or fm.click_text("Ok", reread=False, exact=True)
            time.sleep(1.2)
            continue
        if scr == "fulltime" and not full_time:
            full_time = True
            log(f"full time {score} after {time.time() - t0:.1f}s")
        if full_time and scr == "game":
            log(f"back in the game after {time.time() - t0:.1f}s")
            return {"score": score, "seconds": round(time.time() - t0, 1)}
        b = fm.button()
        if b and not (full_time and scr == "unknown" and b in ("CONTINUE", "NEXT UNREAD", "MATCHES")):
            fm.key("space")                                  # (never Continue past match day once it is over)
            time.sleep(1.8)
        else:
            time.sleep(1.0)
    raise TimeoutError("FM match did not finish")


def matchday(reload_first: bool = True) -> dict:
    t0 = time.time()
    if reload_first:
        reload()
    to_match()
    r = skip_match()
    r["total"] = round(time.time() - t0, 1)
    log(f"match day done in {r['total']}s: {r}")
    return r


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["start", "reload", "state", "click", "key", "to-match", "skip-match",
                                    "matchday", "prefs"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--save")
    a = ap.parse_args()
    if a.cmd == "start":
        start()
    elif a.cmd == "reload":
        reload(a.arg or LAB_SAVE)
    elif a.cmd == "state":
        fm = Fm()
        print(fm.screen(), "| button:", fm.button(), "| clock:", fm.clock())
        for ln in fm.lines:
            print(f"  ({int(ln[0].x)},{int(ln[0].y)}) " + " ".join(w.text for w in ln))
        if a.save:
            fm.save(a.save)
    elif a.cmd == "click":
        print(Fm().click_text(a.arg))
    elif a.cmd == "key":
        Fm().key(a.arg)
    elif a.cmd == "prefs":
        prefs()
    elif a.cmd == "to-match":
        to_match()
    elif a.cmd == "skip-match":
        print(skip_match())
    else:
        print(matchday())
