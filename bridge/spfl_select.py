"""Select Team without scrolling, through matchday.lua's hook on the game's list cursor (PES 2021 / SPFL26).

matchday.lua detours FL_2026.exe+C95D7B (PES2021.exe+B8A58B), the cursor store of the game's list widget (every menu
list moves its cursor there: [r8] = old index +/- 1, rbx = the list), into a cave that records the list that moved
last and, when armed for one list, stores our index instead. Idea and site from forceselection.lua 2.0 (the project
author's Sider module).

A Select Team column is one list widget:
  +0x100/+0x108  vector of leagues, 0x70 bytes each; cursor +0x118 (+ offset +0x11c, 0 here)
  +0x9b          0 while the league list is active, 1 once a league is confirmed (club list)
  league +0x08/+0x10  vector of clubs, 0x50 bytes each, +0x00 = encoded team id ((v >> 14) & 0x1ffff);
                       cursor +0x64 (+ offset +0x68, 0 here)
Every club is in exactly one of the 36 lists (728 clubs, research/job_selprobe.py), so the club's team id gives
both indices, whatever order the game sorts the lists in. PES 2021 LITE has one list (its five clubs) that starts
confirmed: the club cursor is the first to move.
"""
from __future__ import annotations

import os
import re
import struct
import time

from procmem import Proc

CODE = bytes.fromhex("48891d41000000")       # the cave's first instruction: mov [rec_list],rbx
LIST, CELL, TARGET, VALUE, MOVES, FLAG = 72, 80, 88, 96, 100, 104
W_LEAGUES, W_CURSOR, W_CURSOR_OFF, W_MODE = 0x100, 0x118, 0x11C, 0x9B
L_SIZE, L_CLUBS, L_CURSOR, L_CURSOR_OFF = 0x70, 0x08, 0x64, 0x68
C_SIZE = 0x50


class SelectHook:
    def __init__(self, sider_dir: str, exe: str = "FL_2026.exe"):
        try:
            text = open(os.path.join(sider_dir, "matchday", "hooks.txt"), encoding="utf-8").read()
        except OSError:
            raise RuntimeError("matchday.lua wrote no hooks.txt (older version running?)") from None
        kv = dict(re.findall(r"(\w+)=(\S+)", text))
        if "select_cave" not in kv or "select_at" not in kv:
            raise RuntimeError("matchday.lua has no Select Team hook in this game")
        self.cave, self.at = int(kv["select_cave"], 16), int(kv["select_at"], 16)
        self.p = Proc(exe, write=True)
        # hooks.txt may be from an earlier run: the detour must jump to this cave and the cave hold our code
        if self.p.try_read(self.at, 14) != b"\xff\x25\0\0\0\0" + struct.pack("<Q", self.cave) or \
                self.p.try_read(self.cave, len(CODE)) != CODE:
            self.p.close()
            raise RuntimeError("the Select Team hook in hooks.txt is not installed in this game")
        self.disarm()

    def close(self):
        try:
            self.disarm()
        finally:
            self.p.close()

    def moves(self) -> int:
        return self.p.u32(self.cave + MOVES)

    def last_list(self) -> tuple[int, int]:
        """(list widget, cursor cell) of the last list whose cursor moved."""
        return self.p.u64(self.cave + LIST), self.p.u64(self.cave + CELL)

    def arm(self, widget: int, value: int):
        self.p.write(self.cave + TARGET, struct.pack("<Q", widget))
        self.p.write(self.cave + VALUE, struct.pack("<I", value))
        self.p.write(self.cave + FLAG, b"\x01")

    def disarm(self):
        self.p.write(self.cave + FLAG, b"\x00")

    # ---- the column widget
    def leagues(self, w: int) -> list[int]:
        b, e = struct.unpack("<QQ", self.p.read(w + W_LEAGUES, 16))
        n = (e - b) // L_SIZE
        if not 1 <= n <= 200:
            raise RuntimeError(f"not a Select Team list ({n} leagues)")
        return [b + i * L_SIZE for i in range(n)]

    def clubs(self, league: int) -> list[int]:
        b, e = struct.unpack("<QQ", self.p.read(league + L_CLUBS, 16))
        n = (e - b) // C_SIZE
        if not 0 <= n <= 400:
            raise RuntimeError(f"unexpected club list size {n}")
        raw = self.p.read(b, n * C_SIZE) if n else b""
        return [(struct.unpack_from("<I", raw, k * C_SIZE)[0] >> 14) & 0x1FFFF for k in range(n)]

    def find(self, w: int, team_id: int) -> tuple[int, int]:
        """(league index, club index) of the club in this column."""
        for i, lg in enumerate(self.leagues(w)):
            clubs = self.clubs(lg)
            if team_id in clubs:
                return i, clubs.index(team_id)
        raise RuntimeError(f"team {team_id} is in none of the Select Team lists")

    def league_cursor(self, w: int) -> int:
        return self.p.u32(w + W_CURSOR) + self.p.u32(w + W_CURSOR_OFF)

    def club_cursor(self, w: int, league_index: int) -> int:
        lg = self.leagues(w)[league_index]
        return self.p.u32(lg + L_CURSOR) + self.p.u32(lg + L_CURSOR_OFF)

    def club_mode(self, w: int) -> bool:
        return self.p.u8(w + W_MODE) != 0

    def wait(self, cond, timeout: float = 2.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.02)
        return cond()
