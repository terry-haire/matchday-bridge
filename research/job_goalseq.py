"""Find SPFL26's goal list: play test matches until one has >= 2 goals, then search memory for the goal
minutes (from matchday_test.lua's goal log) laid out at a fixed stride, as u8/u16 minutes or u16/u32 seconds.
Elevated job. Writes research/spfl_goalseq_<n>.json with every hit and +-0x80 bytes of context.
"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import json
import os
import sys
import time

import numpy as np

ROOT = MDB
sys.path.insert(0, os.path.join(ROOT, "testkit"))
sys.path.insert(0, os.path.join(ROOT, "bridge"))
import spfl  # noqa: E402
from procmem import Proc  # noqa: E402

log = spfl.log
SCORERS = [int(x) for x in os.environ.get("GOALSEQ_SCORERS", "").split(",") if x]
SQUAD = set()
for _ln in open(os.path.join(spfl.MD, "build.log"), encoding="utf-8"):
    if " -> " in _ln:
        SQUAD.add(int(_ln.split(" -> ")[1].split()[0]))


def goal_log():
    g = spfl.game_state().get("goals", "")
    out = []
    for x in [x for x in g.split(",") if x]:
        side, mmss = x[0], x[1:]
        m, s = mmss.split(":")
        out.append((side, int(m), int(s)))
    return out


def search(goals, tag):
    p = Proc("FL_2026.exe")
    mins = [m for _, m, _ in goals]
    secs = [m * 60 + s for _, m, s in goals]
    hits = []
    CH = 32 << 20
    for base, size in p.regions():
        if size > 0x10000000:
            continue
        for off in range(0, size, CH):
            b = p.try_read(base + off, min(CH + 0x400, size - off))
            if not b:
                continue
            for kind, unit, dt, vals, tol in (("u8min", 1, np.uint8, mins, (0, 1)), ("u16min", 2, "<u2", mins, (0, 1)),
                                              ("u16sec", 2, "<u2", secs, (-3, 3)), ("u32sec", 4, "<u4", secs, (-3, 3))):
                a = np.frombuffer(b[: len(b) // unit * unit], dtype=dt)
                lo, hi = max(vals[0] + tol[0], 0), vals[0] + tol[1]
                idx = np.nonzero((a >= lo) & (a <= hi))[0]
                idx = idx[idx < CH // unit]
                if len(idx) == 0:
                    continue
                n = len(a)
                for s in range(1, 0x80 // unit + 1):
                    ok = np.ones(len(idx), dtype=bool)
                    for j in range(1, len(vals)):
                        pos = idx + j * s
                        good = pos < n
                        v = a[np.where(good, pos, 0)].astype(np.int64)
                        ok &= good & (v >= vals[j] + tol[0]) & (v <= vals[j] + tol[1])
                        if not ok.any():
                            break
                    for i in np.nonzero(ok)[0]:
                        addr = base + off + int(idx[i]) * unit
                        ctx = p.try_read(addr - 0x40, 0x80 + s * unit * len(vals)) or b""
                        c4 = np.frombuffer(ctx[: len(ctx) // 4 * 4], dtype="<u4")
                        who = [int(x) for x in c4 if int(x) in SQUAD]
                        if not who:
                            continue
                        if SCORERS:                # every entry must hold its own scorer within +-0x18 bytes
                            good = True
                            for j, sc in enumerate(SCORERS):
                                e = addr + j * s * unit
                                near = p.try_read(e - 0x18, 0x30) or b""
                                if not any(int.from_bytes(near[k:k + 4], "little") == sc for k in range(len(near) - 3)):
                                    good = False
                                    break
                            if not good:
                                continue
                        hits.append({"kind": kind, "stride": s * unit, "addr": hex(addr), "ids": who,
                                     "ctx": ctx.hex()})
    log(f"[{tag}] goals {goals}: {len(hits)} hits")
    for h in hits[:60]:
        log(f"   {h['kind']} stride {h['stride']:#x} at {h['addr']} ids {h['ids'][:6]}")
    json.dump({"goals": goals, "hits": hits}, open(os.path.join(ROOT, "research", f"spfl_goalseq_{tag}.json"), "w"))
    return hits


if "--here" in sys.argv or os.environ.get("GOALSEQ_HERE"):
    search(goal_log(), "here")
    sys.exit()
s = spfl.start(2)
spfl.to_team_select(s, "away")
spfl.select_teams(s, "Atlanta United FC", "Oldham Athletic", spfl.league_of("Atlanta United FC"),
                  spfl.league_of("Oldham Athletic"))
spfl.play_intro(s, time.time())
found = 0
for i in range(1, 7):
    if i > 1:
        spfl.rematch()
    spfl.skip_match(to_menu=False)
    g = goal_log()
    log(f"match {i}: goal log {g}")
    if len(g) >= 2:
        search(g, f"m{i}")
        found += 1
        if found >= 2:
            break
