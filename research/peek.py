import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import pickle, sys, struct
from collections import Counter
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
p = Proc("fm.exe")
c = pickle.load(open(MDB + r"\research\dumps_scorescan.pkl", "rb"))
for k in ("u32", "u16", "u8"):
    w = {"u8": 1, "u16": 2, "u32": 4}[k]; fmt = {"u8": "<BB", "u16": "<HH", "u32": "<II"}[k]
    cnt = Counter()
    for a in c[k][:200000]:
        b = p.try_read(a, 2 * w)
        if b: cnt[struct.unpack(fmt, b)] += 1
    print(k, [x for x in cnt.most_common(12) if max(x[0]) <= 9])
