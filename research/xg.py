import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\research")
from fmdump import p, label, cls_at
vt = p.vtables(".?AVXG_SHOT_DATA@simatchshared@@")[0]
hits = p.find_qword(vt)
print("XG_SHOT_DATA", len(hits))
for a in hits[:40]:
    b = p.read(a, 0x60)
    owner = None
    print(hex(a), b.hex(" "))
