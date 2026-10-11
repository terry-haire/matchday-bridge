"""Football Manager 2024 in the background: spot the pre-match screen, play FM's match out to full time while the
player is in SP Football Life 2026, and leave the match screen once the SPFL26 result is written.

FM24 takes mouse and key messages posted to its window while it is in the background (nothing moves the cursor
or takes focus). Screens are read with Windows Graphics Capture + Windows OCR (spfl_scorers), in physical
pixels, which is what FM (per-monitor DPI aware) uses for its client coordinates too. FM's UI must be in
English; keep FM's window open (it may be covered, not minimized).

Match flow (FM24 24.4, lab save 2026-10-10): BRIEFING (GO TO MATCH) -> TEAM NEWS (DRESSING ROOM; today's match is
readable in memory from here) -> PEP TALK (MATCH PREVIEW) -> PRE-MATCH (KICK OFF) -> live match -> FULL TIME.
"""
from __future__ import annotations

import ctypes
import re
import time
import unicodedata

from spfl_scorers import WindowFrames, ocr_words, screen_image

TITLE = "Football Manager 2024"
user32 = ctypes.windll.user32
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202
WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x0100, 0x0101, 0x0102
VK = {"space": 0x20, "enter": 0x0D, "esc": 0x1B}
CLOCK = re.compile(r"\b(\d{1,3}):(\d{2})\b")
# Main top-right button labels that may be pressed (Space presses it; never during play: there Space pauses).
ADVANCE = ("CONTINUE", "NEXT UNREAD", "MATCHES", "TEAM SELECTION", "SUBMIT TEAM", "GO TO MATCH",
           "DRESSING ROOM", "MATCH PREVIEW", "KICK OFF", "START SECOND HALF", "SOCIAL FEED")
GAME_BUTTONS = ("CONTINUE", "NEXT UNREAD", "MATCHES", "SOCIAL FEED")      # the main button outside match day
PLAY = (1950, 23)            # resume button when FM paused the match (2000-px-wide layout frame)
# top-bar words of FM's match screens (team news to post-match); outside them the match has been left
MATCH_TOPS = ("fulltime", "halftime", "talk", "prematch", "teamnews", "briefing", "postmatch", "dressingroom")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


class FmError(RuntimeError):
    pass


class FmUi:
    def __init__(self):
        self.h, self.frames = 0, None
        self.img, self.lines, self.text = None, [], ""

    # ------------------------------------------------------------------ window / input
    def window(self) -> int:
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        h = user32.FindWindowW(None, TITLE)
        if h != self.h:
            self.stop()
            self.h = h
        return h

    def shot(self, timeout: float = 15.0):
        """FM's client area: straight from the screen while FM is the active window (always current), else from
        Windows Graphics Capture, restarted when its newest frame is old (a stopped capture repeats its last
        frame)."""
        end = time.time() + timeout
        while time.time() < end:
            h = self.window()
            if h and not user32.IsIconic(h):
                if user32.GetForegroundWindow() == h:
                    try:
                        img = screen_image(h)
                        if img is not None and img.width >= 800:
                            return img
                    except OSError:
                        pass
                try:
                    if self.frames is not None and not self.frames.closed and self.frames.age() > 4:
                        self.stop()
                    if self.frames is None or self.frames.closed:
                        self.frames = WindowFrames(h)
                    img = self.frames.client_image(1.0)
                    if img is not None and img.width >= 800 and self.frames.age() < 4:
                        return img
                except Exception:  # noqa: BLE001 - capture restarts on the next try
                    self.frames = None
            time.sleep(0.3)
        raise FmError("FM24's window can't be seen (minimized?)")

    def k(self) -> float:
        return (self.img or self.shot()).width / 2000

    def click(self, x: float, y: float):
        lp = (int(y) << 16) | (int(x) & 0xFFFF)
        user32.PostMessageW(self.h, WM_MOUSEMOVE, 0, lp)
        time.sleep(0.05)
        user32.PostMessageW(self.h, WM_LBUTTONDOWN, 1, lp)
        time.sleep(0.05)
        user32.PostMessageW(self.h, WM_LBUTTONUP, 0, lp)

    def drag(self, src, dst, steps: int = 12):
        lp = lambda x, y: (int(y) << 16) | (int(x) & 0xFFFF)
        user32.PostMessageW(self.h, WM_MOUSEMOVE, 0, lp(*src))
        time.sleep(0.1)
        user32.PostMessageW(self.h, WM_LBUTTONDOWN, 1, lp(*src))
        time.sleep(0.2)
        for i in range(1, steps + 1):
            user32.PostMessageW(self.h, WM_MOUSEMOVE, 1, lp(src[0] + (dst[0] - src[0]) * i / steps,
                                                         src[1] + (dst[1] - src[1]) * i / steps))
            time.sleep(0.04)
        time.sleep(0.2)
        user32.PostMessageW(self.h, WM_LBUTTONUP, 0, lp(*dst))

    def key(self, name: str):
        vk = VK[name]
        sc = user32.MapVirtualKeyW(vk, 0)
        user32.PostMessageW(self.h, WM_KEYDOWN, vk, 1 | (sc << 16))
        time.sleep(0.03)
        user32.PostMessageW(self.h, WM_KEYUP, vk, 1 | (sc << 16) | (3 << 30))

    def enable(self, on: bool):
        """Block (or give back) mouse and keyboard input to FM24 while the match-day choice is open."""
        h = self.window()
        if h:
            user32.EnableWindow(h, bool(on))

    def minimized(self) -> bool:
        h = self.window()
        return bool(h) and bool(user32.IsIconic(h))

    def stop(self):
        if self.frames:
            self.frames.stop()
        self.frames = None

    # ------------------------------------------------------------------ reading
    def read(self):
        self.img = self.shot()
        self.lines = ocr_words(self.img)
        self.text = "\n".join(" ".join(w[0] for w in ln) for ln in self.lines)
        return self.lines

    def bar(self, img) -> tuple[int, int]:
        """(height, left-part width) of FM's top bar in pixels of `img`: FM draws it at a size set by the display
        scale, so a window narrower than the 2560-px one this was measured on still gets the whole bar."""
        k = img.width / 2000
        try:
            s = user32.GetDpiForWindow(self.h) / 96 if self.h else 1.0
        except (AttributeError, OSError):
            s = 1.0
        return int(max(58 * k, 52 * s, img.height * 0.05)), int(max(940 * k, img.width * 0.5))

    def top(self, fresh: bool = False) -> str:
        """Text of the top bar's left part: page title ("PRE-MATCH", "TEAM NEWS"), or the clock/score."""
        if fresh:
            img = self.img = self.shot()
            bh, bw = self.bar(img)
            lines = ocr_words(img, box=(0, 0, bw, bh), scale=1.5 if bh < 90 else 1.0)
            return " | ".join(" ".join(w[0] for w in ln) for ln in lines)
        bh, bw = self.bar(self.img or self.shot())
        return " | ".join(" ".join(w[0] for w in ln) for ln in self.lines if ln[0][2] < bh and ln[0][1] < bw)

    def clock(self) -> int | None:
        k = self.k()
        bh, _ = self.bar(self.img)
        t = " ".join(" ".join(w[0] for w in ln) for ln in self.lines if ln[0][2] < bh * 0.8 and ln[0][1] < max(160 * k, bh * 3))
        m = CLOCK.search(t)
        return int(m.group(1)) * 60 + int(m.group(2)) if m else None

    def button(self, fresh: bool = False) -> str:
        """Label of FM's main top-right button, from a scaled, inverted crop (OCR misses white-on-purple)."""
        from PIL import ImageOps
        img = self.shot() if fresh or self.img is None else self.img
        if fresh:
            self.img = img
        w, h = img.size
        bh, _ = self.bar(img)
        left = int(min(w * 0.86, w - bh * 4.2))
        crop = ImageOps.invert(img.crop((left, 0, w, int(max(h * 0.065, bh * 1.1)))).convert("L")).convert("RGB")
        label = " ".join(wd[0] for ln in ocr_words(crop, scale=2.0) for wd in ln
                         if re.search(r"[A-Za-z]{2}", wd[0])).upper()
        return next((a for a in ADVANCE if label.startswith(a)), "")

    def find(self, phrase: str, exact: bool = False):
        want = [norm(t) for t in phrase.split()]
        alias = {"ok": {"ok", "0k"}}
        for ln in self.lines:
            toks = [norm(w[0]) for w in ln]
            for i in range(len(toks) - len(want) + 1):
                ok = all((toks[i + j] in alias.get(want[j], {want[j]})) if exact else toks[i + j].startswith(want[j])
                         for j in range(len(want)))
                if ok:
                    a, b = ln[i], ln[i + len(want) - 1]
                    return (a[1] + b[1] + b[3]) / 2, a[2] + a[4] / 2
        return None

    def click_text(self, phrase: str, exact: bool = True) -> bool:
        p = self.find(phrase, exact)
        if p:
            self.click(*p)
        return bool(p)

    def click_button(self, label: str) -> bool:
        """Click a button: an OCR line that is exactly `label` (not the same words inside a sentence)."""
        want = norm(label)
        alias = {"ok": {"ok", "0k"}}.get(want, {want})
        for ln in self.lines:
            if norm(" ".join(w[0] for w in ln)) in alias:
                a, b = ln[0], ln[-1]
                self.click((a[1] + b[1] + b[3]) / 2, a[2] + a[4] / 2)
                return True
        return False

    def screen(self) -> str:
        self.read()
        t, top = norm(self.text), norm(self.top())
        rules = [
            ("injury", lambda: "injuredplayers" in t),
            ("confirm", lambda: "proceedtomatch" in t or "dontshowthismessageagain" in t),
            ("fulltime", lambda: "fulltime" in top),
            ("halftime", lambda: "halftime" in top),
            ("teamtalk", lambda: "peptalk" in top),
            ("prematch", lambda: "prematch" in top),
            ("match", lambda: self.clock() is not None and "vs" not in top),
            ("teamselection", lambda: "teamselection" in top),
            ("game", lambda: "inbox" in t and "squad" in t),
        ]
        return next((name for name, test in rules if test()), "unknown")

    # ------------------------------------------------------------------ match day
    def at_prematch(self) -> bool:
        """FM24 shows the pre-match screen (the player pressed Match Preview): top bar PRE-MATCH or the main
        button KICK OFF. Cheap: two small OCR crops. What was read is kept in `seen` for the log."""
        try:
            top = self.top(fresh=True)
            b = self.button()
            self.seen = f"top {top[:60]!r} button {b!r}"
            live = bool(CLOCK.search(top)) and bool(re.search(r"\b\d{1,2}\s*-\s*\d{1,2}\b", top))
            return "prematch" in norm(top) or b == "KICK OFF" or live
        except FmError as e:
            self.seen = str(e)
            return False

    def confirm(self):
        self.click_text("Yes") or self.click_text("Ok")
        time.sleep(1.2)

    def handle_injury(self, log=print):
        """FM paused for an injured player and waits until he is replaced: Ok, drag the first suitable
        substitute (a goalkeeper for a goalkeeper) onto him, Confirm Changes, Play."""
        self.click_text("Ok")
        time.sleep(1.2)
        self.read()
        k = self.k()
        names = sorted((ln for ln in self.lines if 560 * k <= ln[0][1] < 860 * k and 220 * k < ln[0][2] < 1000 * k
                        and re.search(r"[A-Za-z]{2}", " ".join(w[0] for w in ln))), key=lambda ln: ln[0][2])
        inj_y = [w[2] for ln in self.lines for w in ln if w[0] == "Inj"]

        def row(ln, x0, x1):
            y = ln[0][2]
            return " ".join(w[0] for l2 in self.lines for w in l2 if x0 * k <= w[1] < x1 * k and abs(w[2] - y) < 12 * k)

        pos = lambda ln: row(ln, 900, 1200)
        hurt_rows = lambda ln: any(abs(ln[0][2] - y) < 12 * k for y in inj_y)
        # a substitute who already came on (and maybe off again) has a match rating; an injured one shows Inj
        fresh = lambda ln: not hurt_rows(ln) and not re.search(r"\d+[.,]\d", row(ln, 1900, 2000))
        hurt = next((ln for ln in names[:11] if hurt_rows(ln)), None)
        sub = None
        if hurt is not None:
            gk = pos(hurt).startswith("GK")
            sub = next((ln for ln in names[11:] if fresh(ln) and pos(ln).startswith("GK") == gk), None)
        if hurt is None or sub is None:
            log("FM injury screen: no replacement found; playing on")
            self.click(PLAY[0] * k, PLAY[1] * k)
            time.sleep(1.5)
            return
        name = lambda ln: " ".join(w[0] for w in ln)
        log(f"FM injury: {name(sub)} replaces {name(hurt)}")
        self.drag((sub[0][1] + 40 * k, sub[0][2] + sub[0][4] / 2), (hurt[0][1] + 40 * k, hurt[0][2] + hurt[0][4] / 2))
        time.sleep(1.0)
        self.read()
        self.click_text("Confirm Changes")
        time.sleep(1.0)
        self.click(PLAY[0] * k, PLAY[1] * k)
        time.sleep(1.5)

    def play_to_full_time(self, status=None, log=print, timeout: float = 1800) -> None:
        """From the pre-match screen: Kick Off, then keep FM's match going (half time, confirmations, injuries,
        pauses) until the FULL TIME screen, and stop there (FM commits the result only when it is left)."""
        status = status or (lambda s: None)
        t0 = time.time()
        last_clock, still_since, last_scr = None, time.time(), None
        while time.time() - t0 < timeout:
            if self.minimized():                     # FM can't be seen: wait until its window is back
                if last_scr != "minimized":
                    log("fm: minimized, waiting for its window")
                    status("FM24 is minimized: its match continues when its window is back")
                    last_scr = "minimized"
                time.sleep(2)
                continue
            scr = self.screen()
            if scr != last_scr:
                log(f"fm screen: {scr}")
                last_scr = scr
            if scr == "fulltime":
                status("FM24 full time")
                return
            if scr == "match":
                c = self.clock()
                if c is not None:
                    status(f"FM24's own match (background): {c // 60}'")
                if c != last_clock:
                    last_clock, still_since = c, time.time()
                elif time.time() - still_since > 8:           # paused (tactics view, ...): resume
                    k = self.k()
                    self.click(PLAY[0] * k, PLAY[1] * k)
                    still_since = time.time()
                time.sleep(1.5)
                continue
            if scr == "injury":
                self.handle_injury(log)
                continue
            if scr == "confirm":
                self.confirm()
                continue
            if self.button() in ("KICK OFF", "START SECOND HALF", "DRESSING ROOM", "MATCH PREVIEW"):
                self.key("space")
                time.sleep(2.0)
            else:
                time.sleep(1.0)
        raise FmError("FM24's match did not reach full time")

    def leave_match(self, log=print, timeout: float = 180) -> None:
        """FULL TIME -> back to the game screens (this is when FM saves the result), as fast as FM allows: the top
        bar and the main button are read from one capture (two small OCR crops), the button is pressed and the
        next screen is waited for only until the label changes. Stops at the first game screen (a Continue /
        Next Unread / Matches button outside the match screens): never Continues past match day."""
        t0 = time.time()
        presses = off = 0
        if self.minimized():                         # the SPFL26 match is over: bring FM back without focusing it
            user32.ShowWindow(self.h, 4)             # SW_SHOWNOACTIVATE
            time.sleep(1.5)
            log("fm: restored its minimized window")
        while time.time() - t0 < timeout:
            top = self.top(fresh=True)
            b = self.button()
            on_match = any(w in norm(top) for w in MATCH_TOPS) or re.search(r"\b\d{1,2}\s*-\s*\d{1,2}\b", top)
            if not on_match and top.strip() and (b in GAME_BUTTONS or not b):
                off += 1                             # a game screen
                if b or off >= 3:
                    log(f"fm: left the match screen ({presses} presses, {time.time() - t0:.0f}s)")
                    return
                time.sleep(0.4)
                continue
            off = 0
            if b:
                self.key("space")
                presses += 1
                for _ in range(15):                  # wait for the next screen (title or button), not a pause
                    time.sleep(0.3)
                    if self.top(fresh=True) != top or self.button() != b:
                        break
                else:                                # nothing changed: a question is open over the screen
                    self.answer_dialog(log)
                continue
            self.read()                              # no main button: a question, an injury, a loading screen
            if not self.answer_dialog(log, reread=False):
                time.sleep(0.5)
        raise FmError("FM24 did not leave the match screen")

    def answer_dialog(self, log=print, reread: bool = True) -> bool:
        """A question FM asks on the way out of a match. The post-match pep talk ("No pep talk has been given...
        hand over the pep talk to <assistant>?") is handed over to the assistant, as a delegated talk would be;
        anything else is confirmed (Yes / Ok / Proceed)."""
        if reread:
            self.read()
        t = norm(self.text)
        if "nopeptalkhasbeengiven" in t or "handoverthepeptalk" in t:
            self.key("enter")                        # its focused button is Hand Over (OCR can't read the buttons)
            log("fm: post-match pep talk handed over to the assistant")
            time.sleep(1.5)
            return True
        for label in ("Yes", "Ok", "Proceed"):
            if self.click_button(label):
                log(f"fm: answered a question with {label!r}")
                time.sleep(1.2)
                return True
        return False
