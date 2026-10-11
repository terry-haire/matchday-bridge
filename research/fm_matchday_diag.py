"""FM24 match-day detection, step by step (FM24 running at a match day; no elevation needed):
GAME_MATCH objects in memory (all, not just the first 32), the human club(s), which matches involve them, and
whether the reader builds a match day from each. Prints, and writes research/fm_matchday_diag.txt."""
import os
import sys
import time

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
from fm_reader import FmReader  # noqa: E402

out = open(os.path.join(ROOT, "research", "fm_matchday_diag.txt"), "w", encoding="utf-8")


def log(s):
    print(s, flush=True)
    out.write(s + "\n")


r = FmReader()
mine = r.human_teams()
log(f"human club TEAM*: {[hex(t) for t in mine]} = {[r.team(t)['name'] for t in mine]}")
t = time.time()
allgm = r.p.find_qword(r.vt_game_match)
log(f"GAME_MATCH objects: {len(allgm)} (scan {time.time() - t:.1f}s); first 32 = what the reader looks at")
for i, gm in enumerate(allgm):
    try:
        teams = r.side_teams(gm)
        names = [r.team(teams[k])["name"] for k in sorted(teams)]
        n = len(r.match_players(gm))
    except OSError as e:
        log(f"  {i:3d} {gm:#x}: unreadable ({e})")
        continue
    hit = bool(mine & set(teams.values()))
    md = None
    if hit:
        try:
            md = r._matchday(gm)
        except OSError as e:
            md = f"error {e}"
    if hit or i < 40:
        extra = ""
        if hit:
            extra = " <== HUMAN" + (f": match day {md['home']['name']} v {md['away']['name']} "
                                     f"({len(md['home']['players'])}+{len(md['away']['players'])} players)"
                                     if isinstance(md, dict) else f": no match day ({md})")
        log(f"  {i:3d} {gm:#x}: {' v '.join(names) or '-'} ({n} match players){extra}")
log(f"reader.matchday(): {(lambda m: m and (m['home']['name'], m['away']['name']))(r.matchday())}")
