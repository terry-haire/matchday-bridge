"""Census of scoreline/goal/discipline classes in FM24 at full time."""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct, json
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
C = ["GAME_SCORELINE", "SCORELINE@db", "BASIC_SCORELINE@SCORELINE@db", "EXTERN_SCORELINE@db",
     "GAME_BASIC_GOAL_DESCRIPTION", "BASIC_GOAL_DESCRIPTION@db", "GOAL_DESCRIPTION@db", "EXTERN_BASIC_GOAL_DESCRIPTION@db",
     "GAME_DISCIPLINE", "DISCIPLINE@sicomps", "GAME_MATCH_PLAYER_STATS", "GAME_TEAM_COMP_STATS", "GAME_COMP_STATS",
     "FIXTURE_RESULT@sicomps", "GAME_FIXTURE_RECORD", "SCORELINE_TIMELINE_EVENT", "SCORELINE_WITH_PERSON_ARRAY_TIMELINE_EVENT",
     "INJURY@db", "GAME_MATCH", "MATCH@simatch", "ARCHIVED_MATCH_STATS"]
p = Proc("fm.exe")
vt = {}
for c in C:
    v = p.vtables(".?AV" + c + "@@")
    print(c, [hex(x) for x in v][:3])
    for x in v: vt[x] = c
hits = p.find_qwords(vt)
out = {c: [hex(a) for a in hits.get(c, [])] for c in C}
json.dump(out, open(MDB + r"\research\census_ft.json", "w"), indent=0)
for c in C: print(f"{len(out[c]):7d} {c}")
