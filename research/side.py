import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\bridge")
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at, label
from fm_reader import FmReader
r = FmReader()
gm = 0xeabe1020
mps = [p.u64(gm + 0xcea8 + 8 * i) for i in range(35)]
recs = [p.read(m, 0x1880) for m in mps]
side = [0] * 17 + [1] * 18
for o in range(0, 0x1880):
    v = [b[o] for b in recs]
    h = set(v[:17]); a = set(v[17:])
    if len(h) == 1 and len(a) == 1 and h != a:
        print("byte side flag +", hex(o), h, a)
for o in range(0, 0x1880 - 8, 8):
    v = [struct.unpack_from("<Q", b, o)[0] for b in recs]
    h = set(v[:17]); a = set(v[17:])
    if len(h) == 1 and len(a) == 1 and h != a:
        print("qword +", hex(o), [label(x) or hex(x) for x in (list(h)[0], list(a)[0])])
# team pointers inside GAME_MATCH
OLD = 0x1023d41f0
b = p.read(gm, 0x40000)
for o in range(0, len(b) - 8, 8):
    q = struct.unpack_from("<Q", b, o)[0]
    if q == OLD: print("GAME_MATCH + ", hex(o), "Oldham TEAM; neighbors", label(struct.unpack_from("<Q", b, o - 8)[0]), "|", label(struct.unpack_from("<Q", b, o + 8)[0]))
