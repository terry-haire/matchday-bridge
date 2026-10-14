"""Elevated: which stadium SPFL26 uses for the FM24 match day that is open in FM24 right now (read only; FM24's match
is not touched): the real Bridge._play/_drive into the running SPFL26, then the pre-match Stadium screen (OCR +
screenshot), Kick Off, the stadium module's log lines and a screenshot in play. Report research/stadium.txt, shots
research/shots/stadium_*.png. SPFL26 is left at its main menu and the borrowed players are put back."""
import ctypes
import os
import sys
import time
import tkinter as tk

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
sys.path.insert(1, os.path.join(ROOT, "testkit"))
import fm_writer  # noqa: E402
import matchday_bridge as mb  # noqa: E402
import spfl  # noqa: E402
import win  # noqa: E402
from fm_reader import FmReader  # noqa: E402


class NoFm:
    def __init__(self, *a, **k):
        raise RuntimeError("FM24 is not written in this test")


fm_writer.FmResultWriter = NoFm
mb.Bridge.watch = lambda self: None
mb.Bridge._fm_sim = lambda self: None
SHOTS = os.path.join(ROOT, "research", "shots")
SIDER_LOG = os.path.join(spfl.SIDER, "sider.log")
OUT = open(os.path.join(ROOT, "research", "stadium.txt"), "w", encoding="utf-8")
T0 = time.time()


def log(s):
    line = f"{time.time() - T0:6.1f}s {s}"
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


def screen_text(s, tag):
    img = s.shot()
    img.save(os.path.join(SHOTS, f"stadium_{tag}.png"))
    return win.text_of(win.ocr(img, scale=1.0)).replace("\n", " | ")


ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
md = FmReader().matchday()
log(f"FM24 match day: {md['home']['name']} v {md['away']['name']} ({len(md['home']['players'])} + "
    f"{len(md['away']['players'])} players), human: {[md[s]['name'] for s in ('home', 'away') if md[s]['human']]}")
log_mark = os.path.getsize(SIDER_LOG)
spfl.set_test(match_minutes=2, extra_time=0, penalties=0)
root = tk.Tk()
br = mb.Bridge(root)
br.game = next(g for g in br.games if g.key == "spfl26")   # a Football Life job (PES 2021 is games[0])
br.matchday = md
root.after(300, br.play)


def poll():
    t = br.view.title_var.get()
    if t in ("Your turn", "Pick the teams in Football Life 2026") or time.time() - T0 > 400:
        log(f"bridge: {t} | live load: {br.live is not None} | plan home {br.plan['home']['spfl_name']} "
            f"({br.plan['home']['spfl_team']}), away {br.plan['away']['spfl_name']} ({br.plan['away']['spfl_team']})")
        root.after(300, root.quit)
        return
    root.after(500, poll)


root.after(1000, poll)
root.mainloop()
try:
    s = spfl.Spfl()
    log(f"pre-match: {screen_text(s, '1_prematch')[:200]}")
    s.press("LEFT")                                    # Kick Off -> Stadium
    time.sleep(0.6)
    s.press("A")
    time.sleep(1.5)
    log(f"Stadium screen: {screen_text(s, '2_settings')[:300]}")
    s.press("B")
    time.sleep(1.2)
    s.press("RIGHT")                                   # back onto Kick Off
    time.sleep(0.6)
    log(f"back on: {screen_text(s, '3_back')[:120]}")
    spfl.play_intro(s, time.time())
    time.sleep(1)
    screen_text(s, "4_in_play")
    text = open(SIDER_LOG, encoding="utf-8", errors="replace").read()[log_mark:]
    lines = [ln for ln in text.splitlines() if "stadiums.lua" in ln and ("tadium" in ln) and "Using setting" not in ln]
    for ln in lines[:20]:
        log(f"sider: {ln[:220]}")
    spfl.skip_match(to_menu=True)
finally:
    spfl.set_test(match_minutes=None)
    br._restore_live()
    root.destroy()
    log("done")
    OUT.close()
