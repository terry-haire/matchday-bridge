import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, json
sys.path.insert(0, MDB + r"\research")
from fmdump import p
tag = sys.argv[1]
addrs = [0xd96c2b70, 0xd96c46f0, 0xd96c5400, 0xd96c5610, 0xf69979f0, 0xf6f43b38, 0xf6f44110, 0x104341bc0, 0x104341d40, 0x104341dc0,
         0x10436b5c0, 0x10436b6c0, 0x10436b740, 0x10436b7c0, 0x10436b840, 0x10436b8c0, 0x10436b940, 0x10436b9c0, 0x117a6c398,
         0x117a71358, 0x11e726000, 0xf4e20200, 0x116a74e48]
snap = {}
for a in addrs:
    b = p.try_read(a, 0x300)
    snap[hex(a)] = b.hex() if b else None
json.dump(snap, open(f"fixsnap_{tag}.json", "w"))
print("saved", len(snap))
