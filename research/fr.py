import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at, label
a = 0x1072b1128 - 0x68
b = p.read(a, 0x100)
for o in range(0, 0x100, 16):
    q1 = struct.unpack_from("<Q", b, o)[0]; q2 = struct.unpack_from("<Q", b, o + 8)[0]
    print(f"+{o:03x} {b[o:o+16].hex(' ')}  {label(q1)} | {label(q2)}")
print("refs to this FIXTURE_RESULT:", [hex(x) for x in p.find_qword(a, limit=20)])
