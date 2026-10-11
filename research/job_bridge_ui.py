"""Elevated: the real Bridge UI + _play/_drive flow with a sample match day (FM24 is not read or written).
Screenshots of the bridge window -> research/shots/bridge_*.png, log -> research/bridge_ui_test.txt"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import ctypes
import json
import os
import sys
import time
import tkinter as tk

ROOT = MDB
sys.path.insert(0, os.path.join(ROOT, "bridge"))
from PIL import ImageGrab  # noqa: E402

import fm_writer  # noqa: E402
import matchday_bridge as mb  # noqa: E402


class NoFm:
    def __init__(self, *a, **k):
        raise RuntimeError("FM24 not used in this test")


fm_writer.FmResultWriter = NoFm
mb.Bridge.watch = lambda self: None
OUT = open(os.path.join(ROOT, "research", "bridge_ui_test.txt"), "w", encoding="utf-8")
T0 = time.time()
ctypes.windll.shcore.SetProcessDpiAwareness(1)
root = tk.Tk()
root.geometry("+60+60")
br = mb.Bridge(root)
md = json.load(open(os.path.join(ROOT, "tests", "sample_matchday.json"), encoding="utf-8"))
md = {**md, "home": {**md["home"], "name": "Birmingham Legion", "short": "Birmingham", "human": False},
      "away": {**md["away"], "name": "Oldham Athletic", "short": "Oldham", "human": True}}
br.matchday = md
seen = []


def snap(tag):
    root.update()
    x, y, w, h = root.winfo_rootx(), root.winfo_rooty(), root.winfo_width(), root.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(
        os.path.join(ROOT, "research", "shots", f"bridge_{tag}.png"))


def poll():
    t = br.view.title_var.get()
    if not seen or seen[-1] != t:
        seen.append(t)
        OUT.write(f"{time.time() - T0:6.1f}s {t} | {br.view.body_var.get()[:120]} | {br.view.detail_var.get()[:120]}\n")
        OUT.flush()
        snap(f"{len(seen)}")
    if t in ("Your turn", "Pick the teams in SPFL26") or time.time() - T0 > 240:
        snap("final")
        OUT.write(f"END {t}\n")
        OUT.close()
        root.after(1500, root.destroy)
        return
    root.after(500, poll)


root.after(800, br.prompt)
root.after(4000, br.play)
root.after(1000, poll)
root.mainloop()
