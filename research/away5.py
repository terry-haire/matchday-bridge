import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, pickle, json
from collections import Counter
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at
st = pickle.load(open("dumps_single.pkl", "rb"))
W = {"u8": 1, "u16": 2, "u32": 4}
gm = 0x6857f80
addrs = []
for (s, k), v in st.items():
    if s != "a": continue
    for base, idx in v:
        for i in idx: addrs.append((k, base + int(i) * W[k]))
json.dump([(k, hex(a)) for k, a in addrs], open("away5_cands.json", "w"))
own = Counter(); rows = []
for k, a in addrs:
    owner = None
    for back in range(0, 0x4000, 8):
        c = cls_at((a & ~7) - back)
        if c: owner = (c, (a & ~7) - back); break
    tag = owner[0] if owner else None
    if gm <= a < gm + 0x40000: tag = "GAME_MATCH"
    own[tag] += 1
    rows.append((k, hex(a), tag, hex(a - owner[1]) if owner else "", (hex(a - gm) if gm <= a < gm + 0x40000 else "")))
for t, n in own.most_common(40): print(n, t)
json.dump(rows, open("away5_owners.json", "w"))
for r in rows:
    if r[2] in ("GAME_MATCH", "MATCH@simatch", "FIXTURE@sicomps", "FIXTURE_RESULT@sicomps", "GAME_TEAM_COMP_STATS", "BASIC_SCORELINE@SCORELINE@db", "GAME_SCORELINE", "TEAM_MATCH_STATS@simatchshared"):
        print(r)
