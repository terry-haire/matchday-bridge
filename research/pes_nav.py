"""Drives SPFL26's menus from the title screen to kickoff of a Local Match with two given teams.

Uses SendInput keyboard events (scan codes) only while FL_2026 is the foreground window.
Team rows are found by reading the team-select cursor? No: by stepping through the lists and
OCR-free matching on the menu order computed from the game's own tables (see spfl_menu.py).
This research version takes the number of Down presses for each list.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

WINDRIVE = os.path.join(os.environ.get("LOCALAPPDATA", ""), "universal-modder", "tools", "WinDrive.ps1")
VK = {"enter": 0x0D, "down": 0x28, "up": 0x26, "right": 0x27, "left": 0x25, "esc": 0x1B}


class Driver:
    def __init__(self, proc="FL_2026"):
        self.p = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", WINDRIVE,
                                   "-Proc", proc], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.p.stdout.readline()
        self.cmd("focus")
        self.cmd("scanmode on")

    def cmd(self, line):
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()
        return self.p.stdout.readline().strip()

    def key(self, name, n=1, gap=0.35):
        for _ in range(n):
            self.cmd(f"key {VK[name]:#x}")
            time.sleep(gap)

    def close(self):
        self.p.stdin.close()


def to_kickoff(home_league_down, home_team_down, away_league_up, away_team_down):
    d = Driver()
    d.key("enter"); time.sleep(20)            # title -> main menu
    d.key("enter"); time.sleep(3)             # Match
    d.key("enter"); time.sleep(6)             # Local match -> side select
    d.key("enter"); time.sleep(6)             # side select -> team select
    d.key("down", home_league_down)
    d.key("enter"); time.sleep(2)
    d.key("down", home_team_down)
    d.key("enter"); time.sleep(2)
    d.key("up", away_league_up)
    d.key("enter"); time.sleep(2)
    d.key("down", away_team_down)
    d.key("enter"); time.sleep(2)
    d.close()


if __name__ == "__main__":
    to_kickoff(*[int(x) for x in sys.argv[1:5]])
