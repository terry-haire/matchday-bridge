import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\bridge")
sys.path.insert(0, MDB + r"\research")
from fmdump import p, dump, cls_at, label
from fm_reader import FmReader
r = FmReader()
gm = r.find_game_match(); print("GAME_MATCH", hex(gm))
def team_of(off):
    for i in range(18):
        mp = p.u64(gm + off + 8*i)
        sub = p.u64(mp + 0x28)
        full = r.complete_object(sub)
        if full and cls_at(full) == "ACTUAL_PLAYER@db":
            t = p.u64(full + 0x130)
            if t: return t
home = team_of(0xcea8); away = team_of(0xcf38)
print("home team", hex(home), r.team(home)); print("away team", hex(away), r.team(away))
open("teams.txt","w").write(f"{home:#x} {away:#x} {gm:#x}\n")
refs = p.find_qword(home)
print("refs to home team", len(refs))
pairs = [a for a in refs if p.try_read(a+8, 8) == struct.pack("<Q", away)]
print("home,away pairs", len(pairs))
for a in pairs[:60]:
    b = p.try_read(a + 0x10, 0x10)
    print(hex(a), b.hex(" ") if b else None)
