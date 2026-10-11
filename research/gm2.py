import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys
sys.path.insert(0, MDB + r"\bridge")
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at
from fm_reader import FmReader
r = FmReader()
gm = 0xeabe1020
for off in (0xcea8, 0xcf38):
    t, pl = r.roster(gm, off)
    print(hex(off), t["name"], [(x["name"], x["kind"], x["slot"]) for x in pl][:18])
    for i in range(3):
        mp = p.u64(gm + off + 8 * i)
        sub = p.u64(mp + 0x28); full = r.complete_object(sub)
        print("   ", r.fm_string(p.u64(mp + 0x30)), cls_at(full) if full else None, hex(p.u64(full + 0x130)) if full else None)
