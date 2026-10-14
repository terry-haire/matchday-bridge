"""Render the bridge window in several states and save screenshots (research/shots/ui_*.png)."""
import ctypes
import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bridge"))
from PIL import ImageGrab  # noqa: E402

import ui  # noqa: E402

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))   # like the app: physical pixels
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
root = tk.Tk()
v = ui.View(root, "Matchday Bridge", ["PES 2021", "Football Life 2026"], lambda i: None, lambda: None)
v.footer("Log  " + os.path.join(os.environ.get("LOCALAPPDATA", ""), "MatchdayBridge", "bridge.log"))
root.geometry("+80+80")
H = {"name": "Birmingham Legion", "abbr": "BIR"}
A = {"name": "Oldham Athletic", "abbr": "OLD", "human": True}


def shot(name):
    for _ in range(10):
        root.update()
        time.sleep(0.05)
    root.lift()
    root.attributes("-topmost", True)
    root.update()
    time.sleep(0.3)
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(os.path.join(OUT, f"ui_{name}.png"))


v.status("Watching FM24", "ok")
v.idle("Waiting for match day", "Play FM24 as normal. This window wakes up at Team News.")
v.message("Waiting for match day", "Play FM24 as normal. When your club reaches Team News, this window asks whether "
          "you want to play the match yourself in SP Football Life 2026.", "copied matchday.lua; sider.ini already set up")
shot("1_waiting")
v.fixture(H, A, "FM24  ·  Match day")
v.status("Match day", "warn")
v.buttons(True, True)
v.message("Match day: Birmingham Legion v Oldham Athletic",
          "Play this match in SP Football Life 2026, or let FM24 simulate it?",
          "FM24 match squads ready: Birmingham Legion 18 players, Oldham Athletic 18 players (team sheet order). "
          "You'll control Oldham Athletic.")
shot("2_prompt")
v.buttons(False, False)
v.fixture(H, A, "FM24  ·  15 Jul 2032")
v.step(2)
v.status("Picking teams", "busy")
v.message("Setting up the match", "SPFL26 is starting. Matchday Bridge walks its menus for you: Local Match, "
          "Birmingham Legion v Oldham Athletic, controller 1 on Oldham Athletic. It works in the background; you "
          "don't need to touch the game yet.", "Selecting Oldham Athletic (away)")
shot("3_teams")
v.step(3)
v.status("Live in SPFL26", "ok")
v.score(1, 2, "LIVE  63'", "live")
v.message("Live in SP Football Life 2026", "Birmingham Legion: Dan Sweeney 12'\nOldham Athletic: James Norman 30', "
          "Mike Fondop 58'")
shot("4_live")
v.step(5)
v.status("Saved in FM24", "ok")
v.score(1, 2, "SAVED IN FM24", "ok")
v.message("Saved in FM24: Birmingham Legion 1-2 Oldham Athletic.", "Birmingham Legion: Dan Sweeney 12'\n"
          "Oldham Athletic: James Norman 30', Mike Fondop 58'", "Waiting for the next match day...")
shot("5_saved")
v.step(2, True)
v.status("Pick the teams yourself", "warn")
v.score(None, None)
v.message("Pick the teams in Football Life 2026", "Pick Birmingham Legion (Other European Leagues) as home and Oldham Athletic "
          "(Other European Leagues) as away in Match > Local Match. FM24 squads and ratings are loaded. Put controller "
          "1 on Oldham Athletic (away).", "Automatic setup stopped: SPFL26 stayed on the unknown screen.")
shot("6_manual")
rx, ry = root.winfo_rootx(), root.winfo_rooty()
dlg = ui.ChoiceDialog(root, (rx, ry, rx + root.winfo_width(), ry + root.winfo_height()),
                      [dict(H), dict(A)], "FM24  ·  15 Jul 2032", ["PES 2021", "Football Life 2026"], lambda i: None,
                      lambda: None)
for _ in range(10):
    root.update()
    time.sleep(0.05)
time.sleep(0.3)
b = dlg.win
ImageGrab.grab(bbox=(b.winfo_rootx(), b.winfo_rooty(), b.winfo_rootx() + b.winfo_width(),
                     b.winfo_rooty() + b.winfo_height()), all_screens=True).save(os.path.join(OUT, "ui_7_choice.png"))
dlg.close()
root.destroy()
print("ok")
