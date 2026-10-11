"""Diff SPFL26 memory around every squad player-id occurrence across goals (elevated job).

Starts a test match (User 1 on Oldham, so Atlanta scores), plays it out in a background thread with the
testkit, and on every score change reports: (1) id occurrences that appeared/vanished since the last full
scan (event entries), (2) bytes within +-0x100 of existing occurrences that changed by +1.
"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import json
import os
import re
import sys
import threading
import time

import numpy as np

ROOT = MDB
sys.path.insert(0, os.path.join(ROOT, "testkit"))
sys.path.insert(0, os.path.join(ROOT, "bridge"))
import spfl  # noqa: E402
from procmem import Proc  # noqa: E402

log = spfl.log
ids, names = {}, {}
for ln in open(os.path.join(spfl.MD, "build.log"), encoding="utf-8"):
    m = re.match(r"(.+?): #(\d+) (.+) -> (\d+)", ln)
    if m:
        pid = int(m.group(4))
        ids[pid] = 0 if m.group(1).startswith("Atlanta") else 1
        names[pid] = m.group(3)
ARR = np.array(sorted(ids), dtype=np.uint32)
W = 0x100


def full_scan(p):
    occ = {}
    for base, size in p.regions():
        if size > 0x10000000:
            continue
        b = p.try_read(base, size)
        if not b:
            continue
        a4 = np.frombuffer(b[: len(b) // 4 * 4], dtype="<u4")
        for j in np.nonzero(np.isin(a4, ARR))[0]:
            occ[base + int(j) * 4] = int(a4[j])
    return occ


def windows(p, occ):
    return {a: p.try_read(a - W, 2 * W) for a in occ}


s = spfl.start(2)
spfl.to_team_select(s, "away")
spfl.select_teams(s, "Atlanta United FC", "Oldham Athletic", spfl.league_of("Atlanta United FC"),
                  spfl.league_of("Oldham Athletic"))
spfl.play_intro(s, time.time())
done = threading.Event()
th = threading.Thread(target=lambda: (spfl.skip_match(to_menu=False), done.set()), daemon=True)
th.start()

p = Proc("FL_2026.exe")
occ = full_scan(p)
log(f"{len(occ)} occurrences at kick-off")
prev_w = windows(p, occ)
prev_t = time.time()
st = spfl.game_state()
score = (int(st.get("home", 0)), int(st.get("away", 0)))
report = []
while not done.is_set():
    st = spfl.game_state()
    sc = (int(st.get("home", 0) or 0), int(st.get("away", 0) or 0))
    if sc != score and sc[0] + sc[1] > score[0] + score[1]:
        minute = st.get("minute")
        side = 0 if sc[0] > score[0] else 1
        now_w = windows(p, occ)
        occ2 = full_scan(p)
        new = {a: pid for a, pid in occ2.items() if a not in occ}
        gone = {a: pid for a, pid in occ.items() if a not in occ2}
        incs = []
        for a, b0 in prev_w.items():
            b1 = now_w.get(a)
            if not b0 or not b1:
                continue
            d0 = np.frombuffer(b0, dtype=np.uint8).astype(int)
            d1 = np.frombuffer(b1, dtype=np.uint8).astype(int)
            for o in np.nonzero(d1 - d0 == 1)[0]:
                incs.append((a, occ[a], int(o) - W))
        log(f"GOAL side {side} at {minute}' -> {sc}; {len(new)} new occurrences, {len(gone)} gone, "
            f"{len(incs)} +1 bytes (windows {time.time() - prev_t:.1f}s old)")
        side_new = [(a, pid) for a, pid in new.items() if ids[pid] == side]
        for a, pid in side_new[:15]:
            ctx = p.try_read(a - 0x20, 0x60) or b""
            log(f"   new {a:#x} {names[pid]} ({pid}): {ctx.hex(' ')}")
        from collections import Counter
        log("   +1 offsets (rel. to id) by count: " + str(Counter(o for _, _, o in incs).most_common(12)))
        report.append({"side": side, "minute": minute, "score": sc,
                       "new": [(hex(a), pid, (p.try_read(a - 0x40, 0xc0) or b"").hex()) for a, pid in new.items()],
                       "incs": [(hex(a), pid, o) for a, pid, o in incs]})
        json.dump(report, open(os.path.join(ROOT, "research", "spfl_goaldiff.json"), "w"))
        occ = occ2
        score = sc
        prev_w = windows(p, occ)
        prev_t = time.time()
        continue
    score = sc if sc[0] + sc[1] >= score[0] + score[1] else sc
    if time.time() - prev_t > 1.5:
        prev_w = windows(p, occ)
        prev_t = time.time()
    time.sleep(0.15)
log("match over", score)
