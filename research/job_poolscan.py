"""Elevated: find the edit-block TEAM_REC byte that holds the Select Team "Other ..." group (Team.bin +0x4f high
nibble). Output: research/pool_scan.txt"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import os
import struct
import sys
from collections import Counter

ROOT = MDB
sys.path.insert(0, os.path.join(ROOT, "bridge"))
from procmem import Proc  # noqa: E402
from spfl_db import PesDb  # noqa: E402

out = open(os.path.join(ROOT, "research", "pool_scan.txt"), "w", encoding="utf-8")
g = r"C:\Program Files (x86)\SP Football Life 2026"
db = PesDb.load(g, [os.path.join(g, "SiderAddons", "livecpk", "root")])
pool = {t: db.team[db.team_index[t] + 0x4f] >> 4 for t in db.team_index}
p = Proc("FL_2026.exe")
owner = p.u64(0x143705e10)
blk = p.u64(owner + 0x48)
n = p.u32(blk + 0xd0bcec)
raw = p.read(blk + 0xadf4bc, n * 0x690)
recs = {}
for i in range(n):
    r = raw[i * 0x690:(i + 1) * 0x690]
    tid = (struct.unpack_from("<I", r, 0)[0] >> 14) & 0x1FFFF
    recs[tid] = r
common = [t for t in recs if t in pool]
out.write(f"{n} edit teams, {len(common)} in Team.bin\n")
for t in (199, 200, 899, 1695):
    if t in recs:
        out.write(f"{t}: pool {pool.get(t)}\n")
best = []
others = [t for t in common if pool[t]]
for o in range(0x690):
    for shift, mask in ((4, 0xF), (0, 0xF), (0, 0x7), (5, 0x7), (2, 0x7), (3, 0x7), (1, 0x7), (0, 0xFF)):
        fn, bad = {}, 0
        for t in others:
            v = (recs[t][o] >> shift) & mask
            if fn.setdefault(pool[t], v) != v:
                bad += 1
        if bad <= 2 and len(set(fn.values())) == len(fn) and len(fn) >= 4:
            best.append((-bad, o, shift, mask, dict(fn)))
best.sort(reverse=True)
out.write(f"{len(others)} clubs in an Other group\n")
for nb, o, shift, mask, fn in best[:20]:
    out.write(f"+{o:#x} >>{shift} &{mask:#x}: mismatches {-nb}  map {fn}  "
              f"199={recs[199][o]:#x} 200={recs[200][o]:#x} 899={recs[899][o]:#x}\n")
out.close()
print(open(os.path.join(ROOT, "research", "pool_scan.txt")).read())
