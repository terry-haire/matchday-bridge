import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys
sys.path.insert(0, MDB + r"\research")
from fmdump import p, label
for a in (0x116a74a18, 0xea8665c8):
    b = p.read(a, 0x180)
    print("==", hex(a))
    for o in range(0, len(b), 16):
        q1 = int.from_bytes(b[o:o+8], "little"); q2 = int.from_bytes(b[o+8:o+16], "little")
        print(f"+{o:03x} {b[o:o+16].hex(' ')}  {label(q1)} | {label(q2)}")
