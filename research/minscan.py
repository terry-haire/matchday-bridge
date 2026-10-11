import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys
import numpy as np
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
p = Proc("fm.exe")
seqs = {"all": [2, 7, 19, 21, 31, 34, 53], "goals": [2, 19, 31, 53], "goals+inj": [2, 19, 31, 34, 53]}
found = []
for base, size in p.regions():
    if size > 0x40000000: continue
    b = p.try_read(base, size)
    if not b: continue
    for dt, w in (("u1", 1), ("<u2", 2), ("<u4", 4)):
        n = len(b) // w
        a = np.frombuffer(b[:n * w], dtype=dt)
        starts = np.nonzero(a == 2)[0]
        if len(starts) == 0: continue
        for name, seq in seqs.items():
            for s in range(1, 0x200 // w):
                ok = starts[starts + s * (len(seq) - 1) < n]
                m = np.ones(len(ok), dtype=bool)
                for k, v in enumerate(seq[1:], 1):
                    m &= a[ok + k * s] == v
                    if not m.any(): break
                for i in ok[m]:
                    found.append((name, hex(base + int(i) * w), w, s * w))
print(len(found))
for f in found[:60]: print(f)
