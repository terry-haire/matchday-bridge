"""Diff references to every match player before/after the next goal in FM's live match.

The match must be on screen (paused or running). Resumes it, waits for the score to change, pauses,
then prints references that appeared for exactly the players involved, with the surrounding bytes.
"""
import json
import os
import re
import struct
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "testkit"))
sys.path.insert(0, os.path.join(ROOT, "bridge"))
sys.path.insert(0, os.path.join(ROOT, "research"))
import fm as F  # noqa: E402
from fm_reader import FmReader  # noqa: E402
from fmdump import cls_at  # noqa: E402

r = FmReader()
p = r.p
gm = r.find_game_match()
keys = {}
for mp in r.match_players(gm):
    n = r.fm_string(p.u64(mp + 0x30))
    sub = p.u64(mp + 0x28)
    keys[mp] = n + ":MP"
    keys[sub] = n + ":SUB"
    ap = r.complete_object(sub)
    if ap and ap != sub:
        keys[ap] = n + ":AP"


def snap():
    return {k: set(v) for k, v in p.find_qwords(keys).items()}


def score(fm):
    m = re.search(r"\b(\d{1,2})\s*-\s*(\d{1,2})\b", fm.top())
    return m.group(0) if m else None


fm = F.Fm()
fm.read()
s0 = None
for _ in range(10):
    fm.screen()
    s0 = score(fm) or s0
    if s0:
        break
print("score before", s0)
before = snap()
print("snapshot 1 done", sum(len(v) for v in before.values()))
fm.click_at(F.PLAY)                   # resume (tactics view / paused)
time.sleep(2)
t0 = time.time()
while time.time() - t0 < 400:
    fm.screen()
    s = score(fm)
    if s and s0 and s != s0:
        break
    if fm.screen() == "fulltime":
        print("full time before another goal")
        break
    time.sleep(0.7)
fm.key("space")                       # pause
time.sleep(1.5)
fm.read()
print("score after", score(fm), "clock", fm.clock())
fm.save("fm_goaldiff")
after = snap()
new = {k: sorted(after.get(k, set()) - before.get(k, set())) for k in after}
new = {k: v for k, v in new.items() if v}
print("new refs:", {k: len(v) for k, v in new.items()})
out = {}
for k, v in new.items():
    for a in v[:12]:
        b = p.try_read(a - 0x40, 0x90) or b""
        own = None
        for back in range(0, 0x4000, 8):
            c = cls_at(a - back)
            if c:
                own = f"{c}+{back:#x}"
                break
        print(f"{k:30} {a:#x} {own}")
        print("   " + b[:0x40].hex(" "))
        print(" * " + b[0x40:0x48].hex(" ") + " | " + b[0x48:].hex(" "))
        out.setdefault(k, []).append({"addr": hex(a), "owner": own, "ctx": b.hex()})
json.dump(out, open(os.path.join(ROOT, "research", "goal_diff.json"), "w"), indent=1)
