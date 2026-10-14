"""End to end in PES 2021 without FM24 (dev research): the real Bridge sets up HOME v AWAY (research/job_pes.py), then
this script plays the match out as an idle user - A when the clock stands still (set pieces, help popups, half
time), START on the replay viewer, B on the pause menu - while the bridge's own result thread reads the live score
and the scorers from PES 2021's goal captions. Ends at the bridge's full-time message (no FM24 fixture: "enter the
result yourself").

    python research/job_pes_e2e.py HOME AWAY        -> research/pes_e2e.txt
"""
import ctypes
import json
import os
import re
import sys
import threading
import time
import tkinter as tk

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
import fm_writer  # noqa: E402
import matchday_bridge as mb  # noqa: E402
import spfl_pad  # noqa: E402
import spfl_scorers as sc  # noqa: E402


class NoFm:
    def __init__(self, *a, **k):
        raise RuntimeError("FM24 not used in this test")


fm_writer.FmResultWriter = NoFm
mb.Bridge.watch = lambda self: None
mb.Bridge._fm_sim = lambda self: None
HOME, AWAY = sys.argv[1], sys.argv[2]
CLUB_IDS = {"Oldham Athletic": 694, "Atlanta United FC": 72047296}
OUT = open(os.path.join(ROOT, "research", "pes_e2e.txt"), "w", encoding="utf-8")
T0 = time.time()
CLOCK = re.compile(r"^\d{1,3}:\d\d$")


def log(s):
    OUT.write(f"{time.time() - T0:6.1f}s {s}\n")
    OUT.flush()


ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
root = tk.Tk()
br = mb.Bridge(root)
md = json.load(open(os.path.join(ROOT, "tests", "sample_matchday.json"), encoding="utf-8"))
md = {**md, "home": {**md["home"], "name": HOME, "short": HOME.split()[0], "human": False,
                     "club_id": CLUB_IDS.get(HOME)},
      "away": {**md["away"], "name": AWAY, "short": AWAY.split()[0], "human": True, "club_id": CLUB_IDS.get(AWAY)}}
br.matchday = md
game = next(i for i, g in enumerate(br.games) if g.key == "pes2021")
root.after(500, lambda: br.choose(game))
state = {"playing": False, "done": False}


def play():
    """The idle user: keeps the match going until the bridge reports full time."""
    frames = sc.WindowFrames(sc._window())
    last_clock, still = None, 0
    spfl_pad.press("A")                                   # Kick Off on the pre-match screen
    log("harness: kick off")
    while not state["done"] and time.time() - T0 < 1500:
        time.sleep(2.0)
        img = frames.client_image(1.0)
        if img is None:
            continue
        words = [w for ln in sc.ocr_words(img) for w in ln]
        text = " ".join(w[0] for w in words).lower()
        top = [w[0] for w in words if w[2] < img.height * 0.08]
        clock = next((w for w in top if CLOCK.match(w)), None)
        if "replay" in text and ("toggle display" in text or "save replay" in text or " end" in text):
            spfl_pad.press("START")                       # replay viewer: End
            log("harness: replay viewer -> START")
            still = 0
        elif "return to top menu" in text:
            spfl_pad.press("RIGHT")                       # Cancel (highlighted) | Return
            time.sleep(0.5)
            spfl_pad.press("A")
            log("harness: Return to Top Menu? -> Return")
        elif "full time" in text and "top menu" in text:
            img.save(os.path.join(ROOT, "research", "shots", "pes_fulltime.png"))
            spfl_pad.taps("RIGHT*9", 120)                 # Top Menu is the last entry, as at half time
            time.sleep(0.5)
            spfl_pad.press("A")
            log("harness: full time -> Top Menu")
        elif "pause menu" in text:
            spfl_pad.press("B")
            log("harness: pause menu -> B")
        elif clock is None or clock == last_clock:
            still += 1
            if still >= 2:                                # nothing moves for ~4 s: a set piece or a menu waits
                spfl_pad.press("A")
                still = 0
        else:
            still = 0
        last_clock = clock
    frames.stop()


def poll():
    t = br.view.title_var.get()
    if t == "Your turn" and not state["playing"]:
        state["playing"] = True
        log(f"bridge: {t} | {br.view.body_var.get()[:120]}")
        threading.Thread(target=play, daemon=True).start()
    elif t.startswith(("Pick the teams in", "Could not build")):
        log(f"bridge stopped: {t} | {br.view.detail_var.get()}")
        state["done"] = True
    elif t.startswith(("Full time", "Nothing goes into FM24")) or time.time() - T0 > 1500:
        log(f"bridge: {t} | {br.view.body_var.get()} | {br.view.detail_var.get()}")
        state["done"] = True
    if state["done"]:
        root.after(1500, root.destroy)
        return
    root.after(500, poll)


root.after(1000, poll)
root.mainloop()
log("bridge log, goals:")
for line in open(mb.LOG, encoding="utf-8").read().splitlines()[-400:]:
    if "SPFL goal" in line or "Live in PES" in line or "Full time" in line:
        log("  " + line)
OUT.close()
print(open(os.path.join(ROOT, "research", "pes_e2e.txt"), encoding="utf-8").read())
