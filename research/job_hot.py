"""Elevated: the real Bridge._play/_drive with a sample match day (FM24 not read or written, FM's background match
off): python job_hot.py HOME AWAY. Logs whether SPFL26 was restarted or loaded live, and the time to the
pre-match screen -> research/hot_<home>.txt; SPFL26 screenshots in %LOCALAPPDATA%\\MatchdayBridge\\last_match."""
import ctypes
import json
import os
import shutil
import sys
import time
import tkinter as tk

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
import fm_writer  # noqa: E402
import matchday_bridge as mb  # noqa: E402


class NoFm:
    def __init__(self, *a, **k):
        raise RuntimeError("FM24 not used in this test")


fm_writer.FmResultWriter = NoFm
mb.Bridge.watch = lambda self: None
mb.Bridge._fm_sim = lambda self: None
HOME, AWAY = sys.argv[1], sys.argv[2]
CLUB_IDS = {"Oldham Athletic": 694, "Atlanta United FC": 72047296}
OUT = open(os.path.join(ROOT, "research", f"hot_{HOME.split()[0].lower()}.txt"), "w", encoding="utf-8")
T0 = time.time()


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
log(f"SPFL26 running before: {mb.is_running('FL_2026.exe')}")
root.after(500, br.play)


def poll():
    t = br.view.title_var.get()
    if t in ("Your turn", "Pick the teams in SPFL26") or time.time() - T0 > 400:
        log(f"{t} | {br.view.body_var.get()[:100]} | {br.view.detail_var.get()[:120]}")
        log(f"loaded live: {br.live is not None}")
        shots = os.path.join(os.environ["LOCALAPPDATA"], "MatchdayBridge", "last_match")
        for n in os.listdir(shots):
            shutil.copy2(os.path.join(shots, n), os.path.join(ROOT, "research", "shots", f"hot_{HOME.split()[0].lower()}_{n}"))
        root.after(500, root.destroy)
        return
    root.after(500, poll)


root.after(1000, poll)
root.mainloop()
OUT.close()
print(open(os.path.join(ROOT, "research", f"hot_{HOME.split()[0].lower()}.txt"), encoding="utf-8").read())
