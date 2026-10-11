"""Find FM24's goal-event records: a structure that holds the scorer (pointer or person id) and the minute.

Goals of the committed lab match (Atlanta 2-5 Oldham): Chukalov 11, 33; Ribeiro 19, 69; Luiz Alberto 85;
Aaronson 62, 64 (pen). For every reference to a scorer, test every nearby offset/encoding; report the
(reference kind, offset, encoding) combinations that explain the most distinct goals.
"""
import os
import struct
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bridge"))
from fm_reader import FmReader  # noqa: E402

GOALS = {"Aleksandar Chukalov": (11, 33), "Rodrigo Ribeiro": (19, 69), "Luiz Alberto": (85,),
         "Paxten Aaronson": (62, 64)}
r = FmReader()
p = r.p

# find the ACTUAL_PLAYERs by name through today's (finished) GAME_MATCH if still there, else by id scan
refs = {}          # value -> (scorer, kind, size)
gm = r.find_game_match()
players = {}
if gm:
    for mp in r.match_players(gm):
        n = r.fm_string(p.u64(mp + 0x30))
        if n in GOALS:
            sub = p.u64(mp + 0x28)
            ap = r.complete_object(sub)
            players[n] = {"MP": mp, "SUB": sub, "AP": ap, "ID": p.u32(ap + 0x280)}
print({n: {k: hex(v) for k, v in d.items()} for n, d in players.items()})
if not players:                       # match already left: find the scorers among all ACTUAL_PLAYERs
    want = {89734: "Aleksandar Chukalov", 26970: "Rodrigo Ribeiro", 100949: "Luiz Alberto"}
    for ap in p.find_qword(r.vt_actual_player):
        try:
            pid = p.u32(ap + 0x280)
        except OSError:
            continue
        if pid in want:
            players[want[pid]] = {"AP": ap, "ID": pid}
    print("by id:", {n: hex(d["AP"]) for n, d in players.items()})
qwords = {}
for n, d in players.items():
    for k in ("MP", "SUB", "AP"):
        if k in d:
            qwords[d[k]] = (n, k)
ids = {d["ID"]: n for n, d in players.items()}

occ = []           # (addr, scorer, kind)
idarr = np.array(sorted(ids), dtype=np.uint32)
qarr = np.array(sorted(qwords), dtype=np.uint64)
for base, size in p.regions():
    b = p.try_read(base, size)
    if not b:
        continue
    a8 = np.frombuffer(b[: len(b) // 8 * 8], dtype=np.uint64)
    for j in np.nonzero(np.isin(a8, qarr))[0]:
        n, k = qwords[int(a8[j])]
        occ.append((base + int(j) * 8, n, k, b, int(j) * 8))
    a4 = np.frombuffer(b[: len(b) // 4 * 4], dtype=np.uint32)
    for j in np.nonzero(np.isin(a4, idarr))[0]:
        occ.append((base + int(j) * 4, ids[int(a4[j])], "ID", b, int(j) * 4))
print(len(occ), "references")

score = defaultdict(set)
where = defaultdict(list)
for addr, n, k, b, off in occ:
    mins = GOALS[n]
    for d in range(-0x80, 0x80):
        o = off + d
        if o < 0 or o + 4 > len(b):
            continue
        v8 = b[o]
        v16 = struct.unpack_from("<H", b, o)[0]
        v32 = struct.unpack_from("<I", b, o)[0]
        for enc, val in (("u8min", v8), ("u16min", v16), ("u16sec/60", v16 // 60 if v16 < 7200 else -1),
                         ("u32sec/60", v32 // 60 if v32 < 7200 else -1), ("u8min-1", v8 + 1)):
            if val in mins:
                key = (k, d, enc)
                score[key].add((n, val))
                where[key].append(addr)
best = sorted(score.items(), key=lambda kv: -len(kv[1]))
hits = []
for key, goals in best:
    if len(goals) < 5:
        break
    pts = []
    for addr, n, k, b, off in occ:
        pass
    # rebuild (addr, goal) for this key and look for a compact window holding all 5 goals
    recs = []
    kk, d, enc = key
    for addr, n, k, b, off in occ:
        if k != kk:
            continue
        o = off + d
        if o < 0 or o + 4 > len(b):
            continue
        v8, v16, v32 = b[o], struct.unpack_from("<H", b, o)[0], struct.unpack_from("<I", b, o)[0]
        val = {"u8min": v8, "u16min": v16, "u16sec/60": v16 // 60 if v16 < 7200 else -1,
               "u32sec/60": v32 // 60 if v32 < 7200 else -1, "u8min-1": v8 + 1}[enc]
        if val in GOALS[n]:
            recs.append((addr, (n, val)))
    recs.sort()
    for i in range(len(recs)):
        win = [g for a, g in recs[i:] if a - recs[i][0] < 0x800]
        if len(set(win)) >= 5:
            hits.append((key, hex(recs[i][0]), sorted(set(win))))
            break
for h in hits[:30]:
    print("COMPACT", h)
print(len(hits), "compact candidates")
