"""Live per-player match stats in FM24 (GAME_MATCH_PLAYER_STATS, 0x100 bytes each, arrays of 18 per team).

    python research/fm_livestats.py show            # print the live records of the human club's match
    python research/fm_livestats.py move A B        # move A's goals to B (all live copies) - experiment

Found 2026-10-10 on the lab save: rating x100 u16 at +0x76/+0x78, goals u8 +0x7f, assists u8 +0x89 (probable),
yellow cards u8 +0x9a (probable), index in team sheet u8 +0x8c, person id u32 +0x10 (= ACTUAL_PLAYER +0x280).
FM keeps several copies of the arrays (live, UI caches): every copy is edited.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bridge"))
from fm_reader import FmReader  # noqa: E402

REC = 0x100
F = {"goals": 0x7f, "assists": 0x89, "yellow": 0x9a, "index": 0x8c}


def squad_ids(r: FmReader):
    """{person id: name} and {person id: team ptr} for every player in today's match."""
    gm = r.find_game_match()
    ids, team = {}, {}
    for mp in r.match_players(gm):
        sub = r.p.u64(mp + 0x28)
        ap = r.complete_object(sub)
        if ap and r.p.u64(ap) == r.vt_actual_player:
            pid = r.p.u32(ap + 0x280)
            ids[pid] = r.fm_string(r.p.u64(mp + 0x30))
            team[pid] = r.player_team(mp)
    return ids, team


def live_arrays(r: FmReader):
    """Copies of the stats records of today's match: {array base: [(index, person id, record addr)]}.
    A copy = records at base + i*0x100 whose index field is i and whose ids are all in today's squads."""
    ids, _ = squad_ids(r)
    vt = r.p.vtables(".?AVGAME_MATCH_PLAYER_STATS@@")[0]
    recs = r.p.find_qword(vt)
    arrays: dict[int, list] = {}
    for a in recs:
        b = r.p.try_read(a, REC)
        if not b:
            continue
        pid = struct.unpack_from("<I", b, 0x10)[0]
        idx = b[F["index"]]
        if pid in ids and idx < 18:
            arrays.setdefault(a - idx * REC, []).append((idx, pid, a))
    # a live copy has a full starting XI (indices 0-10) of one club
    return {base: sorted(v) for base, v in arrays.items() if {i for i, _, _ in v} >= set(range(11))}, ids


def show():
    r = FmReader()
    arrays, ids = live_arrays(r)
    for base, recs in arrays.items():
        print(f"copy {base:#x}: {len(recs)} records")
        for idx, pid, a in recs:
            b = r.p.read(a, REC)
            print(f"   {idx:2} {ids[pid][:22]:22} rating={struct.unpack_from('<H', b, 0x78)[0] / 100:.2f} "
                  f"goals={b[F['goals']]} assists={b[F['assists']]} yellow={b[F['yellow']]}")
    return r, arrays, ids


def move(src: str, dst: str):
    r = FmReader()
    r.p.close()
    from procmem import Proc
    r.p = Proc("fm.exe", write=True)
    arrays, ids = live_arrays(r)
    by_name = {v: k for k, v in ids.items()}
    s = next(k for n, k in by_name.items() if src.lower() in n.lower())
    d = next(k for n, k in by_name.items() if dst.lower() in n.lower())
    for base, recs in arrays.items():
        ra = next(a for _, pid, a in recs if pid == s)
        rb = next(a for _, pid, a in recs if pid == d)
        g = r.p.u8(ra + F["goals"])
        r.p.write(rb + F["goals"], bytes([r.p.u8(rb + F["goals"]) + g]))
        r.p.write(ra + F["goals"], bytes([0]))
        print(f"copy {base:#x}: moved {g} goals {ids[s]} -> {ids[d]}")


if __name__ == "__main__":
    if sys.argv[1] == "show":
        show()
    elif sys.argv[1] == "move":
        move(sys.argv[2], sys.argv[3])
