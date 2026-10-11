import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct, json, collections
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
p = Proc("FL_2026.exe")
blk = p.u64(p.u64(0x143705e10) + 0x48)
lo, hi = blk, blk + 0xd10000
away = list(range(55400, 55418))
home = [170214,41270,130462,144870,118361,148991,148550,160819,135943,175607,110210,116633,168625,143565,133281,148557,148561,182280]
ids = set(away + home)
hits = collections.defaultdict(list)
for base, size in p.regions():
    if lo <= base < hi: continue
    if size > 0x20000000: continue
    b = p.try_read(base, size)
    if not b: continue
    import numpy as np
    a = np.frombuffer(b[: len(b) // 4 * 4], dtype="<u4")
    m = np.isin(a, np.array(sorted(ids), dtype=np.uint32))
    for i in np.nonzero(m)[0]:
        addr = base + int(i) * 4
        if lo <= addr < hi: continue
        hits[int(a[i])].append(addr)
# group by 64KB page to find dense structures
pages = collections.Counter()
for pid, lst in hits.items():
    for a in lst: pages[a >> 12] += 1
dense = [(pg << 12, n) for pg, n in pages.most_common(40)]
print("total hits", sum(len(v) for v in hits.values()))
for a, n in dense: print(hex(a), n)
json.dump({str(k): [hex(x) for x in v] for k, v in hits.items()}, open("pes_idhits_1.json", "w"))
