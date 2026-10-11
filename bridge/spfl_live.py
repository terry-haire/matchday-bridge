"""Puts the FM24 match squads into a running SP Football Life 2026, so it does not have to restart per match.

SPFL26 reads its database files (served from the bridge's LiveCPK root) only at boot and then plays from its
edit block in memory: [[0x143705e10]+0x48], player_count records of 0x17c bytes from its start. A live player
record holds the same name slots as Player.bin and the same fields at other bit positions, as full values
(sheets/pes_player_fields.json live_bit/live_width, mapped on 29,492 players). The bridge writes the players it
built; matchday.lua writes the team names, rosters and shirt numbers from request.txt. The original records are
kept and written back when the next match is loaded or the bridge closes (a Rematch keeps the FM24 teams).
"""
from __future__ import annotations

import struct

from gen_structs import SPFL_EDIT_BLOCK as EB, SPFL_LIVE_PLAYER as LP, SPFL_TEAM_REC as TR
from procmem import Proc
from spfl_build import write_live_player


def live_rosters(team_ids) -> dict[int, list[int]]:
    """{team id: player ids of its live roster, in order} from the running SPFL26's edit block."""
    p = Proc("FL_2026.exe")
    try:
        owner = p.u64(EB.OWNER_GLOBAL)
        blk = p.u64(owner + 0x48) if owner else 0
        if not blk:
            return {}
        n = p.u32(blk + EB.TEAM_COUNT)
        raw = p.read(blk + EB.TEAMS, n * 0x690)
        out = {}
        for i in range(n):
            tid = (struct.unpack_from("<I", raw, i * 0x690)[0] >> 14) & 0x1FFFF
            if tid in team_ids:
                ids = [struct.unpack_from("<I", raw, i * 0x690 + TR.ROSTER + k * 8)[0] for k in range(40)]
                out[tid] = ids[:ids.index(0)] if 0 in ids else ids
        return out
    finally:
        p.close()


class LiveDb:
    def __init__(self):
        self.p = Proc("FL_2026.exe", write=True)
        owner = self.p.u64(EB.OWNER_GLOBAL)
        self.blk = self.p.u64(owner + 0x48) if owner else 0
        if not self.blk:
            raise RuntimeError("SPFL26's database is not loaded yet")
        n = self.p.u32(self.blk + EB.PLAYER_COUNT)
        if not 1000 < n < 200000:
            raise RuntimeError(f"unexpected SPFL26 player count {n}")
        raw = self.p.read(self.blk, n * LP.STRIDE)
        self.addr = {struct.unpack_from("<I", raw, i * LP.STRIDE + LP.PLAYER_ID)[0]: self.blk + i * LP.STRIDE
                     for i in range(n)}
        self.saved: dict[int, bytes] = {}

    def write_players(self, assigned) -> int:
        """assigned: [(SPFL player id, FM player, match date)] from MatchBuilder. Returns players written."""
        done = 0
        for pid, pl, match_date in assigned:
            a = self.addr.get(pid)
            if a is None:
                raise RuntimeError(f"player {pid} is not in the running SPFL26")
            old = self.p.read(a, LP.STRIDE)
            if struct.unpack_from("<I", old, LP.PLAYER_ID)[0] != pid:
                raise RuntimeError(f"player {pid} moved in SPFL26's memory")
            self.saved.setdefault(pid, old)
            rec = bytearray(old)
            write_live_player(rec, pl, match_date)
            self.p.write(a, bytes(rec))
            if self.p.read(a, LP.STRIDE) != bytes(rec):
                raise RuntimeError(f"player {pid} could not be written")
            done += 1
        return done

    def restore(self) -> int:
        n = 0
        for pid, old in self.saved.items():
            a = self.addr[pid]
            if struct.unpack_from("<I", self.p.read(a, LP.STRIDE), LP.PLAYER_ID)[0] == pid:
                self.p.write(a, old)
                n += 1
        self.saved.clear()
        return n
