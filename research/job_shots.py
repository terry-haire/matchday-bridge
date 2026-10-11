import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, json, time
import numpy as np
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
p = Proc("FL_2026.exe")
# away roster order: shots by index (0..10) and targets
seqs = {"shots": [0, 1, 0, 1, 0, 1, 1, 1, 3, 6, 8], "ontgt": [0, 0, 0, 1, 0, 1, 0, 1, 3, 4, 6], "goals": [0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 1]}
t0 = time.time(); found = []
for base, size in p.regions():
    if size > 0x10000000: continue
    b = p.try_read(base, size)
    if not b: continue
    for dt, w in (("u1", 1), ("<u2", 2), ("<u4", 4)):
        n = len(b) // w
        a = np.frombuffer(b[: n * w], dtype=dt)
        i8 = np.nonzero(a == 8)[0]
        if len(i8) == 0: continue
        for s in range(1, 0x600 // w + 1):
            c = i8[i8 >= 10 * s]
            m = a[c - s] == 6
            c = c[m]
            if len(c) == 0: continue
            c = c[a[c - 2 * s] == 3]
            if len(c) == 0: continue
            seq = seqs["shots"]
            for k in range(3, 11):
                c = c[a[c - k * s] == seq[10 - k]]
                if len(c) == 0: break
            for x in c:
                found.append((hex(base + int(x - 10 * s) * w), w, hex(s * w)))
print("time", round(time.time() - t0), "found", len(found))
for f in found[:40]: print(f)
json.dump(found, open(MDB + r"\research\pes_shots_found.json", "w"))
