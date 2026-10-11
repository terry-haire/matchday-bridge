import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at, label
objs = {"GAME_MATCH": (0xe974d270, open("dumps_GAME_MATCH_ft.bin","rb").read()), "MATCH": (0x8187f20, open("dumps_MATCH_ft.bin","rb").read())}
for name, (base, b) in objs.items():
    print("==", name)
    n = 0
    for o in range(0, len(b) - 24, 8):
        beg, end, cap = struct.unpack_from("<QQQ", b, o)
        if not (0x10000 < beg < end <= cap < 0x7fffffffffff): continue
        size = end - beg
        if size > 0x10000 or (cap - beg) > 0x40000: continue
        # element count guesses
        for stride in (0x8, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0x40, 0x48, 0x50, 0x58, 0x60, 0x68, 0x70, 0x78, 0x80, 0x90, 0xa0, 0xb0, 0xc0):
            if size % stride == 0 and 3 <= size // stride <= 12:
                pass
        first = p.try_read(beg, min(size, 0x40))
        print(f"  +{o:05x} vec beg={beg:#x} size={size:#x} cap={cap-beg:#x} first={first[:0x20].hex(' ') if first else None} {label(struct.unpack_from('<Q', first)[0]) if first and len(first)>=8 else ''}")
        n += 1
        if n > 150: break
