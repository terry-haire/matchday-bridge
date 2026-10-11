"""Count live instances of match-related FM24 classes (research)."""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import json
import sys

sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc  # noqa: E402

CLASSES = ["MATCH@simatch", "MATCH_MANAGER@simatch", "MATCH_PLAYER@simatch", "MATCH_PLAYER_STATS@simatchshared",
           "GAME_MATCH_PLAYER_STATS", "STATS_MANAGER@simatchshared", "MATCH_STATS_MANAGER", "MATCH_TEAM_SELECTOR@simatch",
           "PRE_MATCH_TEAM_SELECTOR@simatch", "TEAM_SELECTOR@simatch", "INJURE_PLAYER@simatch", "SEND_OFF_PLAYER@simatch",
           "INJURY_INFO@siquickmatch", "MATCH_RECORD", "FIXTURE@simatchshared", "BASE_FIXTURE@simatchshared",
           "MATCH_SYSTEM@simatch", "TACTICS_CREATOR_ARRAY@simatch", "PREPARED_TACTICS_CREATOR_ARRAY@simatch",
           "MATCHDAY_MANAGER", "FIXTURE@sicomps", "FIXTURE_RESULT@sicomps", "INJURY@db", "MATCH_REFEREE@simatch",
           "SUBSTITUTION@simatch", "GOAL_DESCRIPTION@db", "BASIC_GOAL_DESCRIPTION@db", "MATCH_PLAYER_RATINGS_MANAGER@simatch",
           "XG_SHOT_DATA@simatchshared", "QME_STAT_MANAGER@simatchshared", "MATCH_PERSON@simatch"]

if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "census"
    p = Proc("fm.exe")
    vt = {}
    for c in CLASSES:
        v = p.vtables(".?AV" + c + "@@")
        if v:
            vt[v[0]] = c
    hits = p.find_qwords(vt)
    res = {c: [hex(a) for a in hits.get(c, [])] for c in CLASSES}
    json.dump({"vtables": {c: hex(a) for a, c in vt.items()}, "instances": res},
              open(MDB + rf"\research\census_{tag}.json", "w"), indent=0)
    for c in CLASSES:
        print(f"{len(res[c]):6d}  {c}")
