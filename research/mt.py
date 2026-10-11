import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\bridge")
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at, label
from fm_reader import FmReader
r = FmReader()
for t in (0x106da6620, 0x106da6040):
    print("==", hex(t), cls_at(t))
    b = p.read(t, 0x200)
    for o in range(0, 0x200, 8):
        q = struct.unpack_from("<Q", b, o)[0]
        lb = label(q)
        if lb: print("  +", hex(o), lb, hex(q))
        if "TEAM@db" in lb:
            print("     ->", r.team(q))
