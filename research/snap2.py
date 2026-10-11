import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, pickle
sys.path.insert(0, MDB + r"\research")
from fmx import p
tag = sys.argv[1]
def rd(a, n):
    out = bytearray()
    step = 0x1000
    for o in range(0, n, step):
        b = p.try_read(a+o, step)
        if b is None: break
        out += b
    return bytes(out)
regions = {"match": (0x8187f20, 0x40000), "gm": (0xe974d270, 0x40000)}
out = {k: (a, rd(a, n)) for k,(a,n) in regions.items()}
pickle.dump(out, open(MDB + rf"\research\dumps_ms_{tag}.pkl","wb"))
print(tag, {k: len(v[1]) for k,v in out.items()})
