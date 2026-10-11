"""Find SPFL26's per-player match stats (goals, cards): run CPU-vs-CPU test matches with the testkit, and at
full time look for byte offsets near each player-id occurrence whose per-team sums equal the score.

Player ids are the ones the bridge gave the FM squads (SiderAddons/matchday/build.log). Runs elevated.
"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import json
import os
import re
import struct
import sys
import time

import numpy as np

ROOT = MDB
sys.path.insert(0, os.path.join(ROOT, "testkit"))
sys.path.insert(0, os.path.join(ROOT, "bridge"))
import spfl  # noqa: E402
from procmem import Proc  # noqa: E402

log = spfl.log
ids = {"home": [], "away": []}
for ln in open(os.path.join(spfl.MD, "build.log"), encoding="utf-8"):
    m = re.match(r"(.+?): #\d+ .+ -> (\d+)", ln)
    if m:
        ids["home" if m.group(1).startswith("Atlanta") else "away"].append(int(m.group(2)))
side_of = {pid: 0 for pid in ids["home"]} | {pid: 1 for pid in ids["away"]}
ARR = np.array(sorted(side_of), dtype=np.uint32)


def scan(tag):
    st = spfl.game_state()
    hs, as_ = int(st.get("home", 0)), int(st.get("away", 0))
    log(f"[{tag}] scanning at {hs}-{as_}, goals log {st.get('goals')}")
    p = Proc("FL_2026.exe")
    occ = []
    for base, size in p.regions():
        if size > 0x10000000:
            continue
        b = p.try_read(base, size)
        if not b:
            continue
        a4 = np.frombuffer(b[: len(b) // 4 * 4], dtype="<u4")
        for j in np.nonzero(np.isin(a4, ARR))[0]:
            occ.append((base + int(j) * 4, int(a4[j])))
    occ.sort()
    log(f"[{tag}] {len(occ)} id occurrences")
    # clusters: runs of id occurrences no more than 0x1000 apart holding >= 20 distinct ids of both teams
    clusters, cur = [], [occ[0]]
    for o in occ[1:]:
        if o[0] - cur[-1][0] <= 0x1000:
            cur.append(o)
        else:
            clusters.append(cur)
            cur = [o]
    clusters.append(cur)
    out = []
    for cl in clusters:
        first = {}
        for a, pid in cl:
            first.setdefault(pid, a)
        if len(first) < 20 or not {0, 1} <= {side_of[x] for x in first}:
            continue
        addrs = sorted(first.values())
        strides = sorted({b - a for a, b in zip(addrs, addrs[1:])})
        blk = {pid: p.try_read(a - 0x200, 0x800) for pid, a in first.items()}
        if not all(blk.values()):
            continue
        cands = []
        for d in range(0x800):
            v = {pid: blk[pid][d] for pid in first}
            h = sum(x for pid, x in v.items() if side_of[pid] == 0)
            w = sum(x for pid, x in v.items() if side_of[pid] == 1)
            if (h, w) == (hs, as_) and max(v.values()) <= 6 and (hs + as_ == 0 or any(v.values())):
                cands.append(d - 0x200)
        out.append({"start": hex(addrs[0]), "n": len(first), "strides": [hex(s) for s in strides[:4]],
                    "cands": cands, "blk": {str(pid): b.hex() for pid, b in blk.items()}})
        log(f"[{tag}] cluster {addrs[0]:#x} ids={len(first)} strides={[hex(s) for s in strides[:3]]} "
            f"goal-offset candidates={[hex(c) for c in cands][:30]}")
    json.dump({"score": [hs, as_], "goals": st.get("goals"), "clusters": out},
              open(os.path.join(ROOT, "research", f"spfl_stats_{tag}.json"), "w"))


s = spfl.start(2)
spfl.to_team_select(s, "away")
spfl.select_teams(s, "Atlanta United FC", "Oldham Athletic", spfl.league_of("Atlanta United FC"),
                  spfl.league_of("Oldham Athletic"))
spfl.play_intro(s, time.time())
spfl.skip_match(to_menu=False)
scan("m1")
for i in (2, 3, 4):
    spfl.rematch()
    spfl.skip_match(to_menu=False)
    scan(f"m{i}")
