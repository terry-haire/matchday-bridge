"""The games an FM24 match can be played in: eFootball PES 2021 (Steam; the free LITE edition included) and
SP Football Life 2026 (a standalone game on the PES 2021 engine). Both run the same Sider module (matchday.lua)
and keep their edit data in the same layout; what differs is listed here.

PES 2021 LITE's Local Match offers only five clubs (Manchester United, Arsenal, Bayern, Barcelona, Juventus), so
there every FM24 club plays in one of those slots (SPARE_SLOTS["pes2021"]) under its FM24 name, crest and squad;
SP Football Life 2026 has most clubs and lends three plain-kit slots to the clubs it lacks.
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass

from gen_structs import GAME_EXES, SPARE_SLOTS

PES_APPID = "1259970"


@dataclass(frozen=True)
class Game:
    key: str                # "pes2021" | "spfl26"
    name: str               # "eFootball PES 2021"
    short: str              # "PES 2021"
    exe: str                # the game's process
    dir: str                # install folder
    sider_sub: str          # Sider's folder inside it
    age_year: int           # database season: Player.bin age + birth year
    upper_names: bool       # the game's own club names are in capitals
    hosts_only: bool        # only the spare slots can be picked in Local Match

    @property
    def sider(self) -> str:
        return os.path.join(self.dir, self.sider_sub)

    @property
    def root(self) -> str:
        """The LiveCPK root the bridge writes each match's database, crests and faces to."""
        return os.path.join(self.sider, "livecpk", "matchday")

    @property
    def matchday(self) -> str:
        """request.txt / result.txt / hooks.txt, shared with matchday.lua."""
        return os.path.join(self.sider, "matchday")

    @property
    def spare_slots(self) -> list[int]:
        return SPARE_SLOTS[self.key]

    @property
    def extra_roots(self) -> list[str]:
        """Other LiveCPK roots whose database files the game loads (SPFL26's own root)."""
        return [os.path.join(self.sider, "livecpk", "root")] if self.key == "spfl26" else []


def pes2021(path: str) -> Game:
    return Game("pes2021", "eFootball PES 2021", "PES 2021", "PES2021.exe", path, "sider", 2021, True, True)


def spfl26(path: str) -> Game:
    return Game("spfl26", "SP Football Life 2026", "Football Life 2026", "FL_2026.exe", path, "SiderAddons", 2025,
                False, False)


def find_games() -> list[Game]:
    """Installed games, PES 2021 first."""
    import install
    out = []
    d = install.find_pes2021()
    if d:
        out.append(pes2021(d))
    d = install.find_spfl26()
    if d:
        out.append(spfl26(d))
    return out


def owner_global(proc) -> tuple[str, int]:
    """(game, edit block owner global) of a running game exe, from the link time in its PE header."""
    e = proc.u32(proc.base + 0x3C)
    stamp = struct.unpack("<I", proc.read(proc.base + e + 8, 4))[0]
    if stamp not in GAME_EXES:
        raise RuntimeError(f"{proc.exe} is a version Matchday Bridge does not know (link time {stamp})")
    return GAME_EXES[stamp]
