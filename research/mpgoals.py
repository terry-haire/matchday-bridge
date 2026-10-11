import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct, json
sys.path.insert(0, MDB + r"\bridge")
sys.path.insert(0, MDB + r"\research")
from fmdump import p
from fm_reader import FmReader
r = FmReader()
gm = 0xe974d270
players = []
for side, off in (("H", 0xcea8), ("A", 0xcf38)):
    for i in range(18):
        mp = p.u64(gm + off + 8*i)
        nm = r.fm_string(p.u64(mp + 0x30))
        players.append((side, nm, mp, p.read(mp, 0x1880)))
json.dump([(s, n, hex(m), b.hex()) for s, n, m, b in players], open("mp_ft.json", "w"))
idx = {n: k for k, (s, n, m, b) in enumerate(players)}
def check(want, w):
    out = []
    for o in range(0, 0x1880 - w + 1):
        vals = [int.from_bytes(b[o:o+w], "little") for s, n, m, b in players]
        if all(vals[idx[n]] == v for n, v in want.items()) and all(vals[k] == 0 for k in range(len(players)) if players[k][1] not in want):
            out.append(o)
    return out
goals = {"Agostinho Santos": 2, "Nikola Raičević": 2}
for w in (1, 2, 4):
    print("goals w", w, [hex(o) for o in check(goals, w)])
yel = {"Agostinho Santos": 1, "Ryan Harris": 1}
for w in (1, 2, 4):
    print("yellow(S,H) w", w, [hex(o) for o in check(yel, w)][:20])
yel2 = {"Agostinho Santos": 1, "Ryan Harris": 1, "Marc Cucurella": 1}
for w in (1, 2, 4):
    print("yellow(S,H,C) w", w, [hex(o) for o in check(yel2, w)][:20])
ast = {"Agostinho Santos": 1, "Nikola Raičević": 1}
for w in (1, 2, 4):
    print("assist? w", w, [hex(o) for o in check(ast, w)][:20])
