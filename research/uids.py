import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\bridge")
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at
from fm_reader import FmReader
r = FmReader()
gm = 0xe974d270
for side, off in (("H", 0xcea8), ("A", 0xcf38)):
    for i in range(18):
        mp = p.u64(gm + off + 8*i)
        nm = r.fm_string(p.u64(mp + 0x30))
        ap = r.complete_object(p.u64(mp + 0x28))
        b = p.read(ap, 0x30)
        mb = p.read(mp, 0x28)
        print(side, i, f"{nm:24s}", cls_at(ap), b[8:0x30].hex(" "), "| MP", mb[8:0x28].hex(" "))
