import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\bridge")
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at, label
from fm_reader import FmReader
r = FmReader()
gm = 0xe974d270
mps = {}
for side, off in (("H", 0xcea8), ("A", 0xcf38)):
    for i in range(18):
        mp = p.u64(gm + off + 8*i)
        mps[mp] = side + ":" + r.fm_string(p.u64(mp + 0x30))
want = [m for m, n in mps.items() if any(x in n for x in ("Santos", "Ra", "Cucurella", "Rigg", "Harris"))]
for mp in want:
    print("#", mps[mp], hex(mp))
    for a in p.find_qword(mp):
        if 0xe974d270 <= a < 0xe974d270 + 0xd000: continue
        b = p.try_read(a - 0x40, 0x80)
        print(f"  ref {a:#x}")
        if b:
            for o in range(0, 0x80, 16):
                q1 = int.from_bytes(b[o:o+8], "little"); q2 = int.from_bytes(b[o+8:o+16], "little")
                l1 = mps.get(q1) or label(q1); l2 = mps.get(q2) or label(q2)
                print(f"    {o-0x40:+04x} {b[o:o+16].hex(' ')}  {l1} | {l2}")
