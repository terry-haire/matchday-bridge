"""At SPFL full time, search memory for a strided per-player array matching a known goals vector (elevated job).
Truth (match 3 of job_scorers): Atlanta goals by Tim Penfold, Brooks Lennon, Ryan Harris (1 each), Oldham 0.
Orders tried: build.log roster order, and the order of the in-match 22-player array (stride 0xa0 id cluster).
"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import os
import re
import sys

import numpy as np

ROOT = MDB
sys.path.insert(0, os.path.join(ROOT, "testkit"))
sys.path.insert(0, os.path.join(ROOT, "bridge"))
import spfl  # noqa: E402
from procmem import Proc  # noqa: E402

log = spfl.log
TRUTH = {"Tim Penfold": 1, "Brooks Lennon": 1, "Ryan Harris": 1}
roster = {"home": [], "away": []}
names = {}
for ln in open(os.path.join(spfl.MD, "build.log"), encoding="utf-8"):
    m = re.match(r"(.+?): #(\d+) (.+) -> (\d+)", ln)
    if m:
        pid = int(m.group(4))
        roster["home" if m.group(1).startswith("Atlanta") else "away"].append(pid)
        names[pid] = m.group(3)
truth = {pid: TRUTH.get(names[pid], 0) for pid in names}
p = Proc("FL_2026.exe")

# the in-match 22-player array: 22 squad ids at a constant stride
arr = np.array(sorted(names), dtype=np.uint32)
occ = []
for base, size in p.regions():
    if size > 0x10000000:
        continue
    for off in range(0, size, 32 << 20):
        b = p.try_read(base + off, min(32 << 20, size - off))
        if b:
            a4 = np.frombuffer(b[: len(b) // 4 * 4], dtype="<u4")
            occ += [(base + off + int(j) * 4, int(a4[j])) for j in np.nonzero(np.isin(a4, arr))[0]]
occ.sort()
orders = {"roster_home11": roster["home"][:11], "roster_home18": roster["home"],
          "roster_22": roster["home"][:11] + roster["away"][:11]}
for i in range(len(occ)):
    run = [occ[i]]
    for j in range(i + 1, min(i + 40, len(occ))):
        if occ[j][0] - run[-1][0] == 0xa0:
            run.append(occ[j])
    if len(run) >= 20 and len({x[1] for x in run}) == len(run):
        orders.setdefault(f"pitch_{occ[i][0]:#x}", [x[1] for x in run])
log("orders:", {k: [names[x].split()[-1] for x in v] for k, v in list(orders.items())[:6]})

hits = []
for oname, order in orders.items():
    T = [truth[x] for x in order]
    nz = [j for j, v in enumerate(T) if v]
    if not nz:
        continue
    for base, size in p.regions():
        if size > 0x10000000:
            continue
        for off in range(0, size, 32 << 20):
            b = p.try_read(base + off, min((32 << 20) + 0x9000, size - off))
            if not b:
                continue
            a = np.frombuffer(b, dtype=np.uint8)
            n = len(a)
            idx = np.nonzero(a[: min(n, 32 << 20)] == T[nz[0]])[0]
            for s in range(1, 0x800):
                ok = idx.copy()
                for j in nz[1:] + [k for k in range(len(T)) if k not in nz]:
                    pos = ok + (j - nz[0]) * s
                    good = (pos >= 0) & (pos < n)
                    ok = ok[good]
                    pos = pos[good]
                    ok = ok[a[pos] == T[j]]
                    if len(ok) == 0:
                        break
                for x in ok:
                    first = base + off + int(x) - nz[0] * s
                    hits.append((oname, s, first))
                    log(f"HIT {oname} stride {s:#x} first {first:#x}")
log(f"{len(hits)} hits")
