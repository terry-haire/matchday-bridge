"""Find PES 2021's live edit block (dev research): team records by name, the block base, the owner global.

    python research/pes_find_edit.py
"""
from __future__ import annotations

import struct
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bridge"))
from procmem import Proc  # noqa: E402

TEAM_REC, PLAYER_REC = 0x690, 0x17C
SPFL = dict(teams=0xADF4BC, team_count=0xD0BCEC, player_count=0xD0BCE8)

p = Proc("PES2021.exe")
print(f"PES2021.exe base {p.base:#x} size {p.size:#x}")

hits = p.find_bytes(b"ARSENAL\x00" + b"\x00" * 8, 40)
recs = []
for h in hits:
    rec = h - 4
    raw = p.try_read(rec, TEAM_REC)
    if not raw:
        continue
    abbr = raw[0x4A:0x4E]
    enc = struct.unpack_from("<I", raw, 0)[0]
    tid = (enc >> 14) & 0x1FFFF
    print(f"  'Arsenal' at {h:#x}: abbr {abbr!r} enc {enc:#x} tid {tid}")
    if abbr[:3] == b"ARS":
        recs.append((rec, tid))

for rec, tid in recs:
    # walk back to the first team record
    first = rec
    while True:
        prev = first - TEAM_REC
        raw = p.try_read(prev, 0x50)
        if not raw:
            break
        name = raw[4:0x4A].split(b"\0")[0]
        enc = struct.unpack_from("<I", raw, 0)[0]
        if not name or not all(32 <= c < 127 or c >= 0xC0 for c in name[:3]) or enc == 0:
            break
        first = prev
    n = 0
    while True:
        raw = p.try_read(first + n * TEAM_REC, 0x50)
        if not raw or not raw[4:0x4A].split(b"\0")[0]:
            break
        n += 1
    print(f"team array {first:#x}: {n} records; Arsenal index {(rec - first) // TEAM_REC}")
    for i in (0, 1, 2, n - 1):
        raw = p.read(first + i * TEAM_REC, 0x50)
        enc = struct.unpack_from("<I", raw, 0)[0]
        nm = raw[4:0x4A].split(b"\0")[0].decode("utf-8", "replace")
        ab = raw[0x4A:0x4E].split(b"\0")[0].decode("latin-1")
        print(f"    [{i}] tid {(enc >> 14) & 0x1FFFF} {nm!r} {ab!r}")
    blk = first - SPFL["teams"]
    print(f"  block if SPFL layout: {blk:#x}; team_count {p.u32(blk + SPFL['team_count']) if p.try_read(blk + SPFL['team_count'], 4) else None} "
          f"player_count {p.u32(blk + SPFL['player_count']) if p.try_read(blk + SPFL['player_count'], 4) else None}")
    # players before the teams: ids at +0x30 stride 0x17c
    for k in (0, 1, 2):
        raw = p.try_read(blk + k * PLAYER_REC, PLAYER_REC)
        if raw:
            pid = struct.unpack_from("<I", raw, 0x30)[0]
            nm = raw[0x38:0x38 + 0x3D].split(b"\0")[0].decode("utf-8", "replace")
            print(f"    player[{k}] id {pid} {nm!r}")
    holders = p.find_qword(blk, 20)
    print(f"  qwords pointing at the block: {[hex(h) for h in holders]}")
    img = p.image()
    import numpy as np
    q = np.frombuffer(img[: len(img) // 8 * 8], dtype=np.uint64)
    for h in holders:
        owner = h - 0x48
        for j in np.nonzero(q == np.uint64(owner))[0][:5]:
            print(f"    owner {owner:#x} held by exe global {p.base + int(j) * 8:#x}")
    break
