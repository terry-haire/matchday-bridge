"""FM24 full-time experiment 2: which GAME_MATCH_PLAYER_STATS copy is live, and are injury / yellow edits kept?

Plays the lab match to FULL TIME, lists every stats-record run of today's squads, picks the runs whose goals
agree with FM's own goal list, then (unless --dry) gives Casartelli an injury (type 13 at 60') and Cucurella
a yellow card in those runs, leaves the match and checks for an INJURY object on Casartelli.
"""
import json
import os
import struct
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for d in ("testkit", "bridge", "research"):
    sys.path.insert(0, os.path.join(ROOT, d))
import fm as F  # noqa: E402
from fm_reader import FmReader  # noqa: E402
from procmem import Proc  # noqa: E402

DRY = "--dry" in sys.argv
if "--here" not in sys.argv:
    F.reload()
    F.to_match()
F.to_full_time()
r = FmReader()
r.p = Proc("fm.exe", write=True)
p = r.p
gm = r.find_game_match()
teams = r.side_teams(gm)
ids, aps = {}, {}
for mp in r.match_players(gm):
    ap = r.complete_object(p.u64(mp + 0x28))
    if ap and p.u64(ap) == r.vt_actual_player:
        pid = p.u32(ap + 0x280)
        ids[pid] = r.fm_string(p.u64(mp + 0x30))
        aps[pid] = ap

# FM's own goal list (finished copy)
vt_fr = p.vtables(".?AVFIXTURE_RESULT@sicomps@@")[0]
fm_goals = None
for ref in p.find_qword(teams[0]):
    a = ref - 8
    try:
        if p.u64(a) == vt_fr and p.u64(a + 0x10) == teams[1] and p.u16(a + 0x6c):
            q = p.u64(a + 0x70)
            beg, end, _ = struct.unpack_from("<QQQ", p.read(q, 0x18))
            d = p.read(beg, end - beg) if end > beg else b""
            fm_goals = [struct.unpack_from("<IBBH", d, i) for i in range(0, len(d), 8)]
            break
    except OSError:
        pass
print("FM goal list:", [(ids.get(g[0], g[0]), g[1], g[2], g[3]) for g in fm_goals or []])
want = Counter(g[0] for g in fm_goals or [] if g[2] in (0, 2))

vt = p.vtables(".?AVGAME_MATCH_PLAYER_STATS@@")[0]
recs = sorted(a for a in p.find_qword(vt) if p.u32(a + 0x10) in ids)
runs, cur = [], []
for a in recs:
    if cur and a != cur[-1] + 0x100:
        runs.append(cur)
        cur = []
    cur.append(a)
if cur:
    runs.append(cur)
dump = []
good = []
for run in runs:
    rows = [(a, p.read(a, 0x100)) for a in run]
    goals = Counter({struct.unpack_from("<I", b, 0x10)[0]: b[0x7f] for _, b in rows if b[0x7f]})
    rated = sum(1 for _, b in rows if struct.unpack_from("<H", b, 0x78)[0])
    ok = goals == +want
    if ok and rated:
        good.append(run)
    print(f"run {run[0]:#x} n={len(run)} rated={rated} goals_match={ok} "
          + " ".join(f"{ids[struct.unpack_from('<I', b, 0x10)[0]].split()[-1]}:{b[0x7f]}g/{b[0x9a]}y/{b[0x7c]}i{b[0xa4]}"
                     for _, b in rows))
    dump.append({"run": hex(run[0]), "rows": [b.hex() for _, b in rows]})
json.dump(dump, open(os.path.join(ROOT, "research", "ft_runs.json"), "w"))
print("live runs:", [hex(r_[0]) for r_ in good])
if DRY or not good:
    sys.exit()

by = {v: k for k, v in ids.items()}
CAS, CUC = by["Facundo Casartelli"], by["Marc Cucurella"]
for run in good:
    for a in run:
        pid = p.u32(a + 0x10)
        if pid == CAS:
            p.write(a + 0x7c, bytes([13]))
            p.write(a + 0xa4, bytes([60]))
        if pid == CUC:
            p.write(a + 0x9a, bytes([p.u8(a + 0x9a) + 1]))
print("edited: Casartelli injury 13 @60', Cucurella +1 yellow")
time.sleep(0.5)
print(F.skip_match())
time.sleep(2)
vt_inj = p.vtables(".?AVINJURY@db@@")[0]
injs = p.find_qword(vt_inj)
hit = [a for a in injs if any(p.u64(a + o) == aps[CAS] for o in range(8, 0x60, 8))]
print("INJURY objects:", len(injs), "on Casartelli:", [hex(a) for a in hit])
for a in hit:
    print("  ", p.read(a, 0x60).hex(" "))
