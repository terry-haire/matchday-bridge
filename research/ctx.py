import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at
for a in (0x10843b45b, 0x1a907dc5e):
    base = a - 0x60
    b = p.read(base, 0xc0)
    print("==", hex(a))
    for o in range(0, 0xc0, 16): print(f"  {base+o:#x} {b[o:o+16].hex(' ')}")
    for back in range(0, 0x2000, 8):
        c = cls_at((a & ~7) - back)
        if c: print("  owner", c, hex((a & ~7) - back), "off", hex(a - ((a & ~7) - back))); break
