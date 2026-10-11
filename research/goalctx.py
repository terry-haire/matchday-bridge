import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\research")
from fmdump import p, label
for a in (0x104622b60, 0x1209448e0, 0x1d9e759f0):
    base = a - 0x80
    b = p.read(base, 0x140)
    print("== ref", hex(a))
    for o in range(0, len(b), 8):
        q = struct.unpack_from("<Q", b, o)[0]
        extra = ""
        if 0x10000 < q < 0x7fffffffffff:
            extra = label(q)
            if not extra:
                d = p.try_read(q, 16)
                if d: extra = "data " + d.hex(" ")
        print(f"  {base+o:#x} {'*' if base+o==a else ' '} {b[o:o+8].hex(' ')}  {extra}")
