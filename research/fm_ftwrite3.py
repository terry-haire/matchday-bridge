"""FM24 full-time experiment 3: real injury + red card through the match objects.

Plays the lab match to FULL TIME and, unless --dry, for Casartelli writes the in-match injury markers seen on
an engine-injured player (MATCH_PLAYER +0x2d5 injury type (14 seen), stats record +0x7c type-1, +0xa4 minute),
leaves the match, continues one day and checks the Medical Center / INJURY history for him.
Also dumps the stats records + MATCH_PLAYERs at full time to research/ft3.json for card offsets.
"""
import json
import os
import struct
import sys
import time

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
mps = {}
for mp in r.match_players(gm):
    ap = r.complete_object(p.u64(mp + 0x28))
    pid = p.u32(ap + 0x280) if ap and p.u64(ap) == r.vt_actual_player else 0
    mps[r.fm_string(p.u64(mp + 0x30))] = (mp, pid)
vt = p.vtables(".?AVGAME_MATCH_PLAYER_STATS@@")[0]
pids = {pid: n for n, (_, pid) in mps.items() if pid}
recs = [a for a in p.find_qword(vt) if p.u32(a + 0x10) in pids]
live = [a for a in recs if p.u16(a + 0x78)]
json.dump({"mp": {n: [hex(mp), pid, p.read(mp, 0x1880).hex()] for n, (mp, pid) in mps.items()},
           "stats": {hex(a): [pids[p.u32(a + 0x10)], p.read(a, 0x100).hex()] for a in recs}},
          open(os.path.join(ROOT, "research", "ft3.json"), "w"))
print("dumped", len(mps), "match players,", len(recs), "stats records,", len(live), "rated")
for n, (mp, pid) in mps.items():
    if p.u8(mp + 0x2d5) != 255:
        print("engine injury:", n, "MP+0x2d5 =", p.u8(mp + 0x2d5))
if DRY:
    sys.exit()
mp, pid = mps["Facundo Casartelli"]
p.write(mp + 0x2d5, bytes([14]))
for a in live:
    if p.u32(a + 0x10) == pid:
        p.write(a + 0x7c, bytes([13]))
        p.write(a + 0xa4, bytes([60]))
print("Casartelli: MP+0x2d5=14, stats +0x7c=13 +0xa4=60")
print(F.skip_match())
fm = F.Fm()
for _ in range(6):                     # move on to the next day so the physio processes injuries
    fm.read()
    if fm.has("Sun") or fm.has("11 Jul"):
        break
    b = fm.button()
    if b in ("CONTINUE", "NEXT UNREAD", "MATCHES"):
        fm.key("space")
    time.sleep(2.5)
fm.click_at((100, 415))               # Medical Center
time.sleep(3)
fm.read()
fm.save("fm_medical3")
print([" ".join(w.text for w in ln) for ln in fm.lines if "Casartelli" in " ".join(w.text for w in ln)])
