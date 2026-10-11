import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct, json
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at
tag = sys.argv[1]
FN, H, A = 0x115d2eb50, 0xf3abfd98, 0xf36ac710
hits = p.find_qword(H)
out = []
for a in hits:
    b = p.try_read(a - 8, 0x30)
    if not b: continue
    fn, h, aw = struct.unpack_from("<QQQ", b, 0)
    if aw != A: continue
    date, x, hg, ag = struct.unpack_from("<IIBB", b, 0x18)
    start = None
    for back in range(8, 0x400, 8):
        c = cls_at(a - back)
        if c: start = (a - back, c); break
    out.append({"rec": hex(a - 8), "fn": hex(fn), "date": hex(date), "x": hex(x), "hg": hg, "ag": ag,
                "tail": b[0x20:0x30].hex(" "), "owner": f"{start[1]}@{hex(start[0])}+{hex(a-8-start[0])}" if start else None})
json.dump(out, open(f"fixblocks_{tag}.json", "w"), indent=1)
for o in out: print(o)
