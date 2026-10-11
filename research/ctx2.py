import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at, label
for a in (0xe2c6e406, 0x1031675c6, 0x1058a5806, 0xda1e50aa, 0x10362ca44, 0x112511a0f, 0x11cd77ed4, 0x28dbea3e):
    base = (a & ~0xf) - 0x40
    b = p.try_read(base, 0xa0)
    print("==", hex(a))
    if not b: continue
    for o in range(0, len(b), 16): print(f"  {base+o:#x} {b[o:o+16].hex(' ')}")
    for back in range(0, 0x1000, 8):
        c = cls_at((a & ~7) - back)
        if c: print("  owner", c, hex((a & ~7) - back), "off", hex(a - ((a & ~7) - back))); break
