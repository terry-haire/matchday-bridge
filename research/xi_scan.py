"""Find an ordered pointer array matching the XI shown on FM's Team Selection screen."""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import json
import struct
import sys

sys.path.insert(0, MDB + r"\research")
from fmx import p, rtti_name, VT, dump  # noqa: E402

TEAM = 0xF36AC710
XI = ["Dennis Seimen", "Gary De León", "Emili Illa", "Luiz Alberto", "Juan Cruz Torres", "Facundo Casartelli",
      "Facundo Quintana", "Marquinhos", "Test Player", "Nikola Raičević", "Agostinho Santos"]
SUBS = ["Márcio", "Chris Rigg", "Rasmus Kristensen", "Lucien Agoumé", "Gerardo Chan", "Samuel Iling",
        "Rodrigo Ribeiro", "Mikhail Salov", "Marc Cucurella"]
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


by_name = {pname(a): a for a in players}
missing = [n for n in XI + SUBS if n not in by_name]
print("missing", missing)
ptr = {by_name[n]: n for n in XI + SUBS if n in by_name}
first = by_name[XI[0]]
hits = p.find_qword(first)
print("refs to GK", len(hits))
res = []
for h in hits:
    for stride in (8, 16, 24, 32, 40, 48, 56, 64, 0x48, 0x50, 0x58, 0x60, 0x68, 0x70, 0x78, 0x80):
        ok = 0
        for i, n in enumerate(XI):
            q = p.try_read(h + i * stride, 8)
            if q and struct.unpack("<Q", q)[0] == by_name.get(n):
                ok += 1
        if ok >= 9:
            res.append((h, stride, ok))
for h, s, ok in res:
    own = None
    for back in range(0, 0x2000, 8):
        q = p.try_read(h - back, 8)
        if q and p.base <= struct.unpack("<Q", q)[0] < p.base + p.size:
            n = rtti_name(struct.unpack("<Q", q)[0])
            if n:
                own = (hex(h - back), hex(back), n)
                break
    subs = []
    for i in range(11, 24):
        q = p.try_read(h + i * s, 8)
        v = struct.unpack("<Q", q)[0] if q else 0
        subs.append(ptr.get(v, hex(v) if v else "0"))
    print(hex(h), "stride", hex(s), "ok", ok, "owner", own, "after:", subs)
json.dump({"by_name": {k: hex(v) for k, v in by_name.items()}, "hits": [[hex(h), s, ok] for h, s, ok in res]},
          open(MDB + r"\research\xi_hits.json", "w"), ensure_ascii=False, indent=1)
