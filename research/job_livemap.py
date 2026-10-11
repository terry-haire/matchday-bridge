"""Elevated: byte map Player.bin record (312 B) -> live edit-block player record (0x17c B), by agreement across
players; plus a dump of one live record. Output: research/live_map.txt"""
import os
import struct
import sys

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
from fl26db import PLAYER_REC  # noqa: E402
from procmem import Proc  # noqa: E402
from spfl_db import PesDb  # noqa: E402

STRIDE, ID_OFF = 0x17c, 0x30
out = open(os.path.join(ROOT, "research", "live_map.txt"), "w", encoding="utf-8")
g = r"C:\Program Files (x86)\SP Football Life 2026"
sider = os.path.join(g, "SiderAddons", "livecpk")
db = PesDb.load(g, [os.path.join(sider, "matchday"), os.path.join(sider, "root")])
p = Proc("FL_2026.exe")
blk = p.u64(p.u64(0x143705e10) + 0x48)
n = p.u32(blk + 0xd0bce8)
raw = p.read(blk, n * STRIDE)
live = {struct.unpack_from("<I", raw, i * STRIDE + ID_OFF)[0]: i * STRIDE for i in range(n)}
pids = [pid for pid in list(db.player_index)[:4000] if pid in live]
bins = [bytes(db.player_rec(pid)) for pid in pids]
lives = [raw[live[pid]:live[pid] + STRIDE] for pid in pids]
out.write(f"{len(pids)} players compared\n")
for k in range(PLAYER_REC):
    col = [b[k] for b in bins]
    if len(set(col)) < 4:
        continue                      # (almost) constant byte: no information
    best, bj = 0, None
    for j in range(STRIDE):
        same = sum(1 for b, l in zip(col, lives) if b == l[j])
        if same > best:
            best, bj = same, j
    out.write(f"bin+{k:#05x} -> live+{bj:#05x}  {best}/{len(pids)}  distinct {len(set(col))}\n")
pid = pids[0]
out.write(f"\nplayer {pid} {db.player_name(pid)!r}\n")
for name, rec in (("bin", bins[0]), ("live", lives[0])):
    out.write(f"-- {name}\n")
    for o in range(0, len(rec), 16):
        chunk = rec[o:o + 16]
        out.write(f"{o:04x} {chunk.hex(' ')}  {''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)}\n")
out.close()
print("ok")
