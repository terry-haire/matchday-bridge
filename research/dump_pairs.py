import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys
sys.path.insert(0, MDB + r"\research")
from fmdump import p, dump, cls_at
for a in (0x116a74f18, 0xf4e20240, 0x116a74ac8, 0xea866678):
    # walk back to the nearest qword that is a vtable of a class
    start = None
    for back in range(0, 0x400, 8):
        if cls_at(a - back):
            start = a - back; break
    print("pair at", hex(a), "object start", hex(start) if start else None, cls_at(start) if start else None, "pair offset", hex(a - start) if start else None)
    dump(start if start else a - 0x40, (a - start + 0x60) if start else 0xa0)
