import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
import numpy as np
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
p = Proc("fm.exe")
pairs = {"shots": (5, 25), "ontarget": (1, 11), "corners": (6, 12), "fouls": (15, 9)}
found = []
for base, size in p.regions():
    if size > 0x40000000: continue
    b = p.try_read(base, size)
    if not b: continue
    for dt, w in (("<u4", 4), ("<u2", 2), ("u1", 1)):
        n = len(b) // w
        a = np.frombuffer(b[: n * w], dtype=dt)
        # interleaved pairs (h,a) adjacent
        def pairpos(h, aw):
            return set(np.nonzero((a[:-1] == h) & (a[1:] == aw))[0].tolist())
        s = pairpos(5, 25)
        if not s: continue
        o = pairpos(1, 11); c = pairpos(6, 12); f = pairpos(15, 9)
        for i in s:
            win = range(i - 64, i + 64)
            hits = sum(1 for st in (o, c, f) if any(j in st for j in win))
            if hits >= 2:
                found.append((base + i * w, w, hits))
print(len(found))
for addr, w, h in found[:50]:
    print(hex(addr), w, h)
