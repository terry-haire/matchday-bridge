"""Full-time write experiment: does FM commit edited injuries, cards and goal events?

Run while FM's live match is on (any state); plays to the FULL TIME screen, then edits the live data:
  * Ribeiro: injury type/minute copied from an in-match injury (stats +0x7c/+0xa4), or type 13 at 60'
  * Santos: one yellow card (stats +0x9a)
  * goal list: every goal re-attributed to Santos (same minutes) in the live copy's vector
Then leaves the match (fm.skip_match) and reports what FM saved.
"""
import os
import struct
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for d in ("testkit", "bridge", "research"):
    sys.path.insert(0, os.path.join(ROOT, d))
import fm as F  # noqa: E402
import fm_livestats as L  # noqa: E402
from fm_reader import FmReader  # noqa: E402
from procmem import Proc  # noqa: E402

F.to_full_time()
r = FmReader()
r.p = Proc("fm.exe", write=True)
p = r.p
arrays, ids = L.live_arrays(r)
by = {v: k for k, v in ids.items()}
SAN = by["Agostinho Santos"]
RIB = by["Rodrigo Ribeiro"]

# live stats copy = the one whose records carry ratings
live = [base for base, recs in arrays.items() if any(p.u16(a + 0x78) for _, _, a in recs)]
print("stats copies", [hex(b) for b in arrays], "with ratings", [hex(b) for b in live])
inj = None
for base in live:
    for _, pid, a in arrays[base]:
        if p.u8(a + 0x7c) != 255:
            inj = (ids[pid], p.u8(a + 0x7c), p.u8(a + 0xa4))
print("in-match injury:", inj)
typ = inj[1] if inj else 13
for base in live:
    for _, pid, a in arrays[base]:
        if pid == RIB:
            p.write(a + 0x7c, bytes([typ]))
            p.write(a + 0xa4, bytes([60]))
        if pid == SAN:
            p.write(a + 0x9a, bytes([p.u8(a + 0x9a) + 1]))
print("Ribeiro injured (type", typ, "at 60'), Santos +1 yellow")

# goal vectors of today's fixture
gm = r.find_game_match()
teams = r.side_teams(gm)
vt_fr = p.vtables(".?AVFIXTURE_RESULT@sicomps@@")[0]
date = None
for ref in p.find_qword(teams[0]):
    a = ref - 0x8
    try:
        if p.u64(a) != vt_fr or p.u64(a + 0x10) != teams[1]:
            continue
        q = p.u64(a + 0x70)
        beg, end, cap = struct.unpack_from("<QQQ", p.read(q, 0x18)) if q else (0, 0, 0)
        st = p.u16(a + 0x6c)
        d = p.read(beg, end - beg) if beg and end > beg else b""
        ents = [struct.unpack_from("<IBBH", d, i) for i in range(0, len(d), 8)]
        print(f"FR {a:#x} date {p.u32(a + 0x4c):#x} score {p.u8(a + 0x64)}-{p.u8(a + 0x68)} state {st:#x} "
              f"n={len(ents)} cap={(cap - beg) // 8 if beg else 0} {ents}")
        if st and beg and ents:
            for i, (pid, side, typ_, minute) in enumerate(ents):
                if typ_ in (0, 2):
                    p.write(beg + i * 8, struct.pack("<IBBH", SAN, 1, typ_, minute))
            print("   -> rewrote goals to Santos (side 1)")
    except OSError as e:
        print("err", e)
time.sleep(1)
print(F.skip_match())
