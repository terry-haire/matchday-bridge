import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
p = Proc("FL_2026.exe")
def pr(b): return "".join(chr(c) if 32<=c<127 else "." for c in b)
for h in (0x7ff4e4a4b27c, 0x7ff4e49c9164):
    a = h - 0x180
    b = p.read(a, 0x300)
    for off in range(0, 0x300, 16):
        print(hex(a+off), b[off:off+16].hex(" "), pr(b[off:off+16]))
    print()
