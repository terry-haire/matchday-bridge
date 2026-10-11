"""Find heap windows that hold many pointers to one club's players (candidate line-up arrays)."""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import json
import struct
import sys

sys.path.insert(0, MDB + r"\research")
from fmx import p, rtti_name, VT  # noqa: E402

TEAM = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0xF36AC710
AP0 = VT["ACTUAL_PLAYER@db"][0]
players = [a for a in p.find_qword(AP0) if p.u64(a + 0x130) == TEAM or p.u64(a + 0x138) == TEAM]


def pname(a):
    fn, sn, cn = struct.unpack("<QQQ", p.read(a + 0x2D0, 24))

    def ns(x):
        if not x:
            return ""
        sp = p.u64(x)
        return p.read(sp + 4, p.u32(sp)).decode("utf-8", "replace")
    return ns(cn) or (ns(fn) + " " + ns(sn))


names = {a: pname(a) for a in players}
print("players on team", len(players))
hits = p.find_qwords({a: names[a] for a in players})
refs = sorted((addr, nm) for nm, lst in hits.items() for addr in lst)
# cluster
clusters = []
cur = []
for addr, nm in refs:
    if cur and addr - cur[-1][0] > 0x40:
        clusters.append(cur)
        cur = []
    cur.append((addr, nm))
if cur:
    clusters.append(cur)
big = [c for c in clusters if len({n for _, n in c}) >= 11]
print("clusters with >=11 distinct players:", len(big))
for c in big[:40]:
    start = c[0][0]
    own = None
    for back in range(0, 0x400, 8):
        q = p.try_read(start - back, 8)
        if q and p.base <= struct.unpack("<Q", q)[0] < p.base + p.size:
            n = rtti_name(struct.unpack("<Q", q)[0])
            if n:
                own = (hex(start - back), n)
                break
    stride = (c[1][0] - c[0][0]) if len(c) > 1 else 0
    print(hex(start), "n", len(c), "stride", hex(stride), "owner", own)
    print("    ", ", ".join(n for _, n in c[:24]))
