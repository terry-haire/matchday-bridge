import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at, label
gm, match = 0xe974d270, 0x8187f20
for arr in (0xe2c6e400, 0x1031675c0, 0x1058a5800, 0x10362ca40, 0x11cd77ed0, 0xe2c6e3c0):
    refs = p.find_qword(arr)
    print("== array", hex(arr), "refs", len(refs))
    for a in refs[:10]:
        nxt = p.try_read(a, 0x18)
        beg, end, cap = struct.unpack_from("<QQQ", nxt)
        owner = None
        for back in range(0, 0x20000, 8):
            c = cls_at(a - back)
            if c: owner = (c, hex(a - back), hex(back)); break
        print("  ref", hex(a), "beg/end/cap", hex(beg), hex(end), hex(cap), "n8", (end-beg)//8, "cap8", (cap-beg)//8, "owner", owner,
              "inGM" if gm <= a < gm + 0x40000 else "", "inMATCH" if match <= a < match + 0x40000 else "")
