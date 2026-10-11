"""SPFL26 scorer ground truth + memory search (elevated job).

Plays test matches (User 1 on Oldham, CPU Atlanta scores). On every score change it OCRs SPFL's scorer caption
("47 Ryan Harris / GOAL 1", bottom left) for a few seconds and maps it to the squad (build.log names). Every
3 s it also OCRs that corner and logs any other caption (cards, injuries). At full time it searches memory for
a byte offset next to squad-player-id occurrences that equals each scorer's goal count and is 0 for the other
players in the same structure.
"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import difflib
import json
import os
import re
import sys
import threading
import time
from collections import Counter, defaultdict

import numpy as np

ROOT = MDB
sys.path.insert(0, os.path.join(ROOT, "testkit"))
sys.path.insert(0, os.path.join(ROOT, "bridge"))
import spfl  # noqa: E402
import win  # noqa: E402
from procmem import Proc  # noqa: E402

log = spfl.log
squad = {}                                   # pid -> (side, shirt, name)
for ln in open(os.path.join(spfl.MD, "build.log"), encoding="utf-8"):
    m = re.match(r"(.+?): #(\d+) (.+) -> (\d+)", ln)
    if m:
        squad[int(m.group(4))] = (0 if m.group(1).startswith("Atlanta") else 1, int(m.group(2)), m.group(3))
by_name = {win.norm(n): pid for pid, (_, _, n) in squad.items()}


def caption(s):
    """Text of the bottom-left caption area (1280x720 basis)."""
    img = s.shot()
    k = img.width / 1280
    lines = win.ocr(img, box=(40 * k, 520 * k, 560 * k, 640 * k), scale=2.0)
    return [" ".join(w.text for w in ln) for ln in lines]


def who(texts):
    """Squad player named in OCR text: fuzzy match, or a unique squad name starting with the (>= 4 letters)
    text (the caption slides in, so OCR often catches only the first letters)."""
    names = list(by_name)
    for t in texts:
        for cand in (t, re.sub(r"^\d+\s*", "", t)):
            c = win.norm(cand)
            if len(c) < 4 or c in ("atlantaunitedfc", "oldhamathletic"):
                continue
            m = difflib.get_close_matches(c, names, n=1, cutoff=0.8)
            if m:
                return by_name[m[0]]
            pre = [n for n in names if n.startswith(c)]
            if len(pre) == 1:
                return by_name[pre[0]]
    return None


def search(truth, tag):
    """truth: {pid: goals}. Offsets d (rel. to a squad-id occurrence) where the scorers' occurrences hold their
    goal counts and all other squad-id occurrences within the same 0x4000-byte window hold 0."""
    p = Proc("FL_2026.exe")
    arr = np.array(sorted(squad), dtype=np.uint32)
    occ = []
    for base, size in p.regions():
        if size > 0x10000000:
            continue
        for off in range(0, size, 32 << 20):
            b = p.try_read(base + off, min(32 << 20, size - off))
            if not b:
                continue
            a4 = np.frombuffer(b[: len(b) // 4 * 4], dtype="<u4")
            for j in np.nonzero(np.isin(a4, arr))[0]:
                occ.append((base + off + int(j) * 4, int(a4[j])))
    occ.sort()
    win_ = {a: p.try_read(a - 0x300, 0x600) for a, _ in occ}
    scorers = [pid for pid, g in truth.items() if g]
    found = defaultdict(set)
    for a, pid in occ:
        if pid not in scorers or not win_[a]:
            continue
        blk = win_[a]
        for d in range(-0x300, 0x300):
            if blk[0x300 + d] != truth[pid]:
                continue
            nb = [(a2, p2) for a2, p2 in occ if abs(a2 - a) <= 0x4000 and win_.get(a2)]
            others = [win_[a2][0x300 + d] for a2, p2 in nb if p2 not in scorers]
            same = [win_[a2][0x300 + d] for a2, p2 in nb if p2 in scorers]
            if len(others) >= 8 and not any(others) and len({p2 for _, p2 in nb if p2 in scorers}) == len(scorers):
                if all(v == truth[p2] for (a2, p2), v in zip([x for x in nb if x[1] in scorers], same)):
                    found[d].add(hex(a))
    log(f"[{tag}] truth {[(squad[p][2], g) for p, g in truth.items() if g]}: offsets {sorted(found)[:20]}")
    for d, addrs in sorted(found.items())[:20]:
        log(f"    d={d:+#06x} at {sorted(addrs)[:4]}")
    json.dump({"truth": {str(k): v for k, v in truth.items()}, "found": {str(d): sorted(a) for d, a in found.items()}},
              open(os.path.join(ROOT, "research", f"spfl_scorers_{tag}.json"), "w"))


s = spfl.start(2)
spfl.to_team_select(s, "away")
spfl.select_teams(s, "Atlanta United FC", "Oldham Athletic", spfl.league_of("Atlanta United FC"),
                  spfl.league_of("Oldham Athletic"))
spfl.play_intro(s, time.time())
for match in range(1, 4):
    if match > 1:
        spfl.rematch()
    done = threading.Event()
    threading.Thread(target=lambda: (spfl.skip_match(to_menu=False), done.set()), daemon=True).start()
    score, goals, last_cap = (0, 0), [], 0.0
    while not done.is_set():
        st = spfl.game_state()
        if st.get("ptr", "0") in ("0", ""):
            time.sleep(0.3)
            continue
        sc = (int(st.get("home", 0) or 0), int(st.get("away", 0) or 0))
        if sum(sc) > sum(score):
            side = 0 if sc[0] > score[0] else 1
            seen = []
            pid = None
            t_end = time.time() + 7
            while time.time() < t_end and pid is None:
                txt = caption(s)
                seen += txt
                pid = who([t for t in txt if t and "GOAL" not in t.upper()])
                time.sleep(0.4)
            goals.append((side, st.get("minute"), pid))
            log(f"GOAL {sc} side {side} {st.get('minute')}': scorer {squad[pid][2] if pid else '?'} | {seen[:6]}")
        elif sum(sc) < sum(score):
            goals = []
        score = sc
        if time.time() - last_cap > 3:
            txt = [t for t in caption(s) if len(t) > 3]
            if txt:
                log(f"   caption: {txt[:4]}")
            last_cap = time.time()
        time.sleep(0.2)
    truth = Counter(pid for _, _, pid in goals if pid)
    log(f"match {match} over {score}: {goals}")
    if truth:
        search(dict(truth), f"m{match}")
