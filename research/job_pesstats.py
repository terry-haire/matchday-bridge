import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct, json
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
p = Proc("FL_2026.exe")
cands = {"away": [("0xa6a8b8",0x128),("0xa679b8",0x128),("0x6cf84950",0xf0),("0x6cf96f8c",0xd8),("0x7ff4f7dcbb50",0x48),("0x7ff4fbd6a9e8",0x188),("0x1e15e304",0x24),("0x4c928bc4",0x100),("0x706351b8",0x48),("0x7ff4fd00a2e8",0x380),("0x44aec68",0xd8),("0x44063d4",0x3f0),("0x7ff4fcf79190",0x380),("0x7ff4f7a53f38",0x3c),("0x5fe7ec28",0x380),("0x5ff21cec",0x380)],
         "home": [("0x44995c8",0x128),("0x6cf80f40",0xf0),("0x4c926478",0x100),("0x6cf94788",0xd8),("0x44ac464",0xd8),("0x70634678",0x48),("0x449c3e4",0x128),("0x44004bc",0x3f0),("0x1e15dd54",0x24),("0x7ff4fbd67140",0x188)]}
snap = {}
for side, lst in cands.items():
    for a, s in lst:
        a = int(a, 16)
        b = p.try_read(a - s, s * 20)
        snap[f"{side}:{a:#x}:{s:#x}"] = b.hex() if b else None
tag = sys.argv[1] if len(sys.argv) > 1 else "x"
res = open(r"C:\Program Files (x86)\SP Football Life 2026\SiderAddons\matchday\result.txt").read()
json.dump({"result": res, "snap": snap}, open(MDB + f"\\research\\pes_stats_{tag}.json", "w"))
print("ok", res.replace("\n", " "))
