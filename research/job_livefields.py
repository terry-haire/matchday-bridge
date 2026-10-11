"""Elevated: where each PES player field (Player.bin bit field) lives in the live edit-block player record:
the live bit offset whose value equals the Player.bin value for the most players. Output: research/live_fields.txt"""
import os
import struct
import sys

import numpy as np

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
from fl26db import getbits  # noqa: E402
from gen_structs import PES_PLAYER_FIELDS  # noqa: E402
from procmem import Proc  # noqa: E402
from spfl_db import PesDb  # noqa: E402

STRIDE, ID_OFF = 0x17c, 0x30
g = r"C:\Program Files (x86)\SP Football Life 2026"
sider = os.path.join(g, "SiderAddons", "livecpk")
db = PesDb.load(g, [os.path.join(sider, "matchday"), os.path.join(sider, "root")])
p = Proc("FL_2026.exe")
blk = p.u64(p.u64(0x143705e10) + 0x48)
n = p.u32(blk + 0xd0bce8)
raw = p.read(blk, n * STRIDE)
live = {struct.unpack_from("<I", raw, i * STRIDE + ID_OFF)[0]: i * STRIDE for i in range(n)}
pids = [pid for pid in list(db.player_index)[:6000] if pid in live]
L = np.frombuffer(b"".join(raw[live[pid]:live[pid] + STRIDE] for pid in pids), dtype=np.uint8).reshape(len(pids), STRIDE)
bits = np.unpackbits(L, axis=1, bitorder="little").astype(np.int32)      # bit k of the record = bits[:, k]
nb = bits.shape[1]
out = open(os.path.join(ROOT, "research", "live_fields.txt"), "w", encoding="utf-8")
out.write(f"{len(pids)} players\n")
for name, (bit, width, add) in PES_PLAYER_FIELDS.items():
    if name.startswith("pos:") or name in ("Registered Position", "Nationality", "Stronger Foot", "Weak Foot Usage",
                                            "Weak Foot Accuracy", "Form", "Injury Resistance", "Playing Style"):
        continue
    full = np.array([getbits(bytes(db.player_rec(pid)), bit, width) + add for pid in pids], dtype=np.int32)
    res = []
    for w in (6, 7, 8):
        for label, target in (("full", full), ("stored", full - add)):
            vals = np.zeros((len(pids), nb - w + 1), dtype=np.int32)
            for i in range(w):
                vals += bits[:, i:nb - w + 1 + i] << i
            eq = (vals == target[:, None]).sum(axis=0)
            b = int(np.argmax(eq))
            res.append((int(eq[b]), w, label, b))
    res.sort(reverse=True)
    out.write(f"{name:28} add {add:3}: " + "; ".join(f"{c} w{w} {lab} bit {b} (byte {b // 8:#x}.{b % 8})"
                                                     for c, w, lab, b in res[:3]) + "\n")
    out.flush()
out.close()
print("ok")
raise SystemExit
for name, (bit, width, add) in PES_PLAYER_FIELDS.items():
    target = np.array([getbits(bytes(db.player_rec(pid)), bit, width) for pid in pids], dtype=np.int32)
    if len(set(target.tolist())) < 2:
        out.write(f"{name:28} bin bit {bit:4} w{width}: constant, skipped\n")
        continue
    vals = np.zeros((len(pids), nb - width + 1), dtype=np.int32)
    for i in range(width):
        vals += bits[:, i:nb - width + 1 + i] << i
    eq = (vals == target[:, None]).sum(axis=0)
    order = np.argsort(-eq)[:3]
    out.write(f"{name:28} bin bit {bit:4} w{width} -> live bit " +
              ", ".join(f"{int(b)} (byte {int(b) // 8:#x}.{int(b) % 8}) {int(eq[b])}" for b in order) + "\n")
    out.flush()
out.close()
print("ok")
