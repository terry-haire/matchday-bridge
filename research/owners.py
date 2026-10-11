import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, pickle
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at
from fm_reader import FmReader
r = FmReader()
gm = r.find_game_match()
mt = p.find_qword(p.vtables(".?AVMATCH@simatch@@")[0], limit=4)
print("GAME_MATCH", hex(gm), "MATCH", [hex(x) for x in mt])
c = pickle.load(open("dumps_scorescan.pkl", "rb"))
for k, lst in c.items():
    for a in lst:
        owner = None
        for back in range(0, 0x20000, 8):
            cl = cls_at((a & ~7) - back)
            if cl: owner = (cl, (a & ~7) - back); break
        rel = ""
        if gm and gm <= a < gm + 0x40000: rel = f"GAME_MATCH+{a-gm:#x}"
        for m in mt:
            if m <= a < m + 0x40000: rel = f"MATCH+{a-m:#x}"
        print(k, hex(a), owner[0] if owner else None, hex(a - owner[1]) if owner else "", rel)
