"""Intersect SPFL per-player goal-offset candidates across the spfl_stats_m*.json dumps (job_stats.py).
A real goals field must sum to each team's score in every match. Prints, per record layout (cluster
strides), the offsets (relative to the player id) that survive, with each scorer's value per match."""
import glob
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dumps = []
for f in sorted(glob.glob(os.path.join(ROOT, "research", "spfl_stats_m*.json"))):
    d = json.load(open(f))
    dumps.append((os.path.basename(f), d))
    print(os.path.basename(f), "score", d["score"], "goals", d.get("goals"))

layouts = defaultdict(list)          # key -> [(file, score, cluster)]
for name, d in dumps:
    for cl in d["clusters"]:
        key = (cl["n"], tuple(cl["strides"][:2]))
        layouts[key].append((name, d["score"], cl))

for key, rows in layouts.items():
    scored = [r for r in rows if sum(r[1])]
    if not scored:
        continue
    surv = set(scored[0][2]["cands"])
    for _, _, cl in scored[1:]:
        surv &= set(cl["cands"])
    zero = [r for r in rows if not sum(r[1])]
    for _, _, cl in zero:                       # 0-0 matches: the field must be 0 for everyone
        surv &= set(cl["cands"])
    print(f"\nlayout n={key[0]} strides={key[1]}: {len(scored)} scoring matches, {len(surv)} offsets survive")
    for off in sorted(surv)[:12]:
        line = []
        for name, score, cl in scored:
            vals = {pid: bytes.fromhex(b)[0x200 + off] for pid, b in cl["blk"].items()}
            line.append(f"{name}:{score} " + ",".join(f"{pid}={v}" for pid, v in vals.items() if v))
        print(f"   {off:+#06x}  " + " | ".join(line))
