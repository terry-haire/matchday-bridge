import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\bridge")
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at, label
from fm_reader import FmReader
r = FmReader()
OLD = 0x1023d41f0
oldclub = p.u64(OLD + 0x30)
print("Oldham club", hex(oldclub))
for h in (0x112841460, 0x112841a20):
    print("== HUMAN", hex(h), cls_at(h))
    b = p.read(h, 0x600)
    for o in range(0, 0x600, 8):
        q = struct.unpack_from("<Q", b, o)[0]
        if q in (OLD, oldclub): print("   direct +", hex(o), "Oldham" if q == OLD else "OldhamCLUB")
        if 0x10000 < q < 0x7fffffffffff:
            sub = p.try_read(q, 0x100)
            if sub:
                for o2 in range(0, 0x100, 8):
                    q2 = struct.unpack_from("<Q", sub, o2)[0]
                    if q2 in (OLD, oldclub):
                        print("   +", hex(o), "->", cls_at(q) or label(q), "+", hex(o2), "Oldham" if q2 == OLD else "OldhamCLUB")
# side flag search in MATCH_PLAYER
gm = 0xeabe1020
mps = [p.u64(gm + 0xcea8 + 8 * i) for i in range(36)]
names = [r.fm_string(p.u64(m + 0x30)) if m else None for m in mps]
print([ (i, n) for i, n in enumerate(names)])
