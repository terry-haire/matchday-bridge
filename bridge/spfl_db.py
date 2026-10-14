"""Read SPFL26's effective pesdb tables from the player's own install (nothing is shipped)."""
from __future__ import annotations

import os
import re
import struct

from fl26db import (ASSIGN_REC, ORDER_MASK, ORDER_SHIFT, PLAYER_ID_OFF, PLAYER_NAME_LEN, PLAYER_NAME_OFF,
                    PLAYER_REC, SHIRT_MASK, TEAM_ID_OFF, TEAM_NAME_LEN, TEAM_NAME_OFF, TEAM_REC, cpk_names,
                    cpk_read, cstr, wesys_unpack)

PESDB = "common/etc/pesdb/"
TEAM_POOL_OFF = 0x4f           # Team.bin: high nibble = the Select Team group of a club that is in no league
POOL_GROUPS = {1: "Classic Teams", 2: "Other European Leagues", 3: "Other Clubs (Asia)",
               6: "Other Latin American Teams", 7: "Other Clubs (Africa)"}
COMP_REC, REG_REC, ENTRY_REC = 36, 2352, 12


def cpk_priority(game_dir: str) -> list[str]:
    """CPK file names of the game's download list, highest precedence first. SP Football Life 2026 reads
    download/spFileList.bin, PES 2021 download/DpFileList.bin; in both a later entry overrides the earlier ones
    (Data Pack 7.0 after 1.0; SPFL's own order numbers count down the same way). Entries are 0x30 bytes from +8:
    u32, u32, name."""
    for name in ("spFileList.bin", "DpFileList.bin"):
        p = os.path.join(game_dir, "download", name)
        if os.path.exists(p):
            break
    d = open(p, "rb").read()
    return [m.group(1).decode() for m in re.finditer(rb"([0-9A-Za-z_\-]+\.cpk)", d)][::-1]


def effective_table(game_dir: str, table: str, livecpk_roots: list[str] | None = None) -> tuple[bytes, str]:
    """Decompressed bytes of the table the game actually loads, plus where it came from."""
    inner = PESDB + table + ".bin"
    for root in livecpk_roots or []:
        p = os.path.join(root, inner.replace("/", os.sep))
        if os.path.exists(p):
            return wesys_unpack(open(p, "rb").read()), p
    for name in cpk_priority(game_dir):
        cp = os.path.join(game_dir, "download", name)
        if not os.path.exists(cp):
            continue
        if inner in cpk_names(cp):
            return wesys_unpack(cpk_read(cp, inner)), cp
    for cp in sorted(os.listdir(os.path.join(game_dir, "Data")), reverse=True):
        full = os.path.join(game_dir, "Data", cp)
        if cp.endswith(".cpk") and inner in cpk_names(full):
            return wesys_unpack(cpk_read(full, inner)), full
    raise FileNotFoundError(inner)


def load_leagues(game_dir: str, roots: list[str] | None = None) -> dict[int, str]:
    """{team id: league name as SPFL26's Select Team list shows it}.
    Competition.bin (36 B): +0x03 region (8 = continental club cups), +0x05 competition id, +0x08 code.
    CompetitionRegulation.bin (2352 B): +0x08 competition id, +0x14 English name; a competition's first row
    is its overall name ("Major League Soccer"), later rows are phases ("MLS First Round").
    CompetitionEntry.bin (12 B): +0x00 team id, +0x08 competition id (Matozanato/FootballLife-new-leagues
    tools/mkleague.py)."""
    comp, _ = effective_table(game_dir, "Competition", roots)
    reg, _ = effective_table(game_dir, "CompetitionRegulation", roots)
    ent, _ = effective_table(game_dir, "CompetitionEntry", roots)
    league = set()
    for i in range(0, len(comp) - COMP_REC + 1, COMP_REC):
        code = comp[i + 8:i + COMP_REC].split(b"\0")[0]
        if code.endswith(b"_LEAGUE") and comp[i + 3] != 8:
            league.add(comp[i + 5])
    names: dict[int, str] = {}
    for i in range(0, len(reg) - REG_REC + 1, REG_REC):
        names.setdefault(reg[i + 8], cstr(reg[i + 0x14:i + 0x14 + 0x73]))
    out: dict[int, str] = {}
    for i in range(0, len(ent) - ENTRY_REC + 1, ENTRY_REC):
        tid, cid = struct.unpack_from("<I", ent, i)[0], ent[i + 8]
        if cid in league and names.get(cid) and tid not in out:
            out[tid] = names[cid]
    return out


class PesDb:
    def __init__(self, player: bytes, assign: bytes, team: bytes):
        self.player = bytearray(player)
        self.assign = bytearray(assign)
        self.team = bytearray(team)
        self.player_index = {struct.unpack_from("<I", self.player, i + PLAYER_ID_OFF)[0]: i
                             for i in range(0, len(self.player), PLAYER_REC)}
        self.team_index = {struct.unpack_from("<I", self.team, i + TEAM_ID_OFF)[0]: i
                           for i in range(0, len(self.team), TEAM_REC)}
        self.leagues: dict[int, str] = {}

    @classmethod
    def load(cls, game_dir: str, roots: list[str] | None = None) -> "PesDb":
        p, _ = effective_table(game_dir, "Player", roots)
        a, _ = effective_table(game_dir, "PlayerAssignment", roots)
        t, _ = effective_table(game_dir, "Team", roots)
        db = cls(p, a, t)
        try:
            db.leagues = load_leagues(game_dir, roots)
        except (OSError, ValueError, IndexError):
            db.leagues = {}
        return db

    def menu_league(self, tid: int) -> str:
        """The entry of SPFL26's Select Team league list the club is filed under: its league, or for a club in
        no league the "Other ..." group of its Team.bin record."""
        if tid in self.leagues:
            return self.leagues[tid]
        i = self.team_index.get(tid)
        return POOL_GROUPS.get(self.team[i + TEAM_POOL_OFF] >> 4, "") if i is not None else ""

    def team_name(self, tid: int) -> str:
        i = self.team_index[tid]
        return cstr(self.team[i + TEAM_NAME_OFF:i + TEAM_NAME_OFF + TEAM_NAME_LEN])

    def player_name(self, pid: int) -> str:
        i = self.player_index[pid]
        return cstr(self.player[i + PLAYER_NAME_OFF:i + PLAYER_NAME_OFF + PLAYER_NAME_LEN])

    def player_rec(self, pid: int) -> bytearray:
        i = self.player_index[pid]
        return self.player[i:i + PLAYER_REC]

    def assignments(self, tid: int) -> list[dict]:
        out = []
        for i in range(0, len(self.assign), ASSIGN_REC):
            rid, pid, t, pack = struct.unpack_from("<IIII", self.assign, i)
            if t == tid:
                out.append({"off": i, "row": rid, "player": pid, "team": t, "pack": pack,
                            "shirt": (pack & SHIRT_MASK) + 1, "order": (pack & ORDER_MASK) >> ORDER_SHIFT})
        out.sort(key=lambda r: r["order"])
        return out
