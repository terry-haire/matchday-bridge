"""Elevated: SPFL26 running -> where a Player.bin record (312 B) sits inside the live edit-block player record
(stride 0x17c). Output: research/live_player.txt"""
import os
import struct
import sys

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
sys.path.insert(0, os.path.join(ROOT, "testkit"))
from fl26db import PLAYER_ID_OFF, PLAYER_REC  # noqa: E402
from procmem import Proc  # noqa: E402
from spfl_db import PesDb  # noqa: E402

out = open(os.path.join(ROOT, "research", "live_player.txt"), "w", encoding="utf-8")
if "--start" in sys.argv:
    import spfl
    spfl.start(None)
g = r"C:\Program Files (x86)\SP Football Life 2026"
sider = os.path.join(g, "SiderAddons", "livecpk")
db = PesDb.load(g, [os.path.join(sider, "matchday"), os.path.join(sider, "root")])
p = Proc("FL_2026.exe")
blk = p.u64(p.u64(0x143705e10) + 0x48)
n = p.u32(blk + 0xd0bce8)
STRIDE = 0x17c
raw = p.read(blk, n * STRIDE)
out.write(f"edit block {blk:#x}, {n} players\n")
# which offset of the live record holds the player id?
ids = set(db.player_index)
best = Counter = {}
for o in range(0, STRIDE - 3):
    hits = sum(1 for i in range(0, min(n, 3000)) if struct.unpack_from("<I", raw, i * STRIDE + o)[0] in ids)
    if hits > 2500:
        out.write(f"id candidate at live +{o:#x}: {hits}/3000\n")
for o in range(0, STRIDE - 3):
    hits = sum(1 for i in range(0, min(n, 3000)) if struct.unpack_from("<I", raw, i * STRIDE + o)[0] in ids)
    if hits > 2500:
        id_off = o
        break
live = {struct.unpack_from("<I", raw, i * STRIDE + id_off)[0]: i * STRIDE for i in range(n)}
out.write(f"live id offset {id_off:#x}; {len(set(live) & ids)} of {len(ids)} Player.bin ids live\n")
for pid in [r["player"] for r in db.assignments(199)][:3] + [r["player"] for r in db.assignments(101)][:2]:
    rec = bytes(db.player_rec(pid))
    lrec = raw[live[pid]:live[pid] + STRIDE]
    shift = id_off - PLAYER_ID_OFF
    same = sum(1 for k in range(PLAYER_REC) if 0 <= k + shift < STRIDE and rec[k] == lrec[k + shift])
    diff = [k for k in range(PLAYER_REC) if 0 <= k + shift < STRIDE and rec[k] != lrec[k + shift]]
    out.write(f"player {pid} {db.player_name(pid)!r}: Player.bin == live+{shift:#x} for {same}/{PLAYER_REC} bytes; "
              f"differing Player.bin offsets {[hex(k) for k in diff[:24]]}\n")
    out.write(f"  live head {lrec[:0x20].hex()}\n  bin  head {rec[:0x20].hex()}\n")
    out.write(f"  live name area {lrec[shift + 0x44:shift + 0x44 + 0x50]!r}\n")
out.close()
print(open(os.path.join(ROOT, "research", "live_player.txt"), encoding="utf-8").read())
