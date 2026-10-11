import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys
sys.path.insert(0, MDB + r"\bridge")
from fm_reader import FmReader
from gen_structs import MATCH_PLAYER, MATCH_TEAM
r = FmReader()
for gm in r.find_game_matches():
    mps = r.match_players(gm)
    print("GM", hex(gm), len(mps), {k: r.team(v)["name"] if v else None for k, v in r.side_teams(gm).items()})
    for mp in mps[:2] + mps[-2:]:
        mt = r.p.u64(mp + MATCH_PLAYER.MATCH_TEAM); opp = r.p.u64(mp + MATCH_PLAYER.MATCH_TEAM + 8)
        print("  ", r.fm_string(r.p.u64(mp + 0x30)), "side", r.p.u8(mp + 0x1ec), "mt", r.team(r.p.u64(mt + 0x48))["name"] if mt else None,
              "opp", r.team(r.p.u64(opp + 0x48))["name"] if opp else None, "slot", r.p.u8(mp + 0x6bb))
