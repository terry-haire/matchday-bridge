import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at, label
import struct
for a in (0x6329bfe, 0x1c92c87cc, 0xf131ab32):
    base = (a & ~0xf) - 0x80
    b = p.read(base, 0x100)
    print("==", hex(a))
    for o in range(0, 0x100, 16):
        q1 = struct.unpack_from("<Q", b, o)[0]; q2 = struct.unpack_from("<Q", b, o + 8)[0]
        print(f"  {base+o:#x} {b[o:o+16].hex(' ')}  {label(q1)} | {label(q2)}")
    refs = p.find_qword(a & ~0xfff, limit=5)
