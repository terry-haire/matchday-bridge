import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys
sys.path.insert(0, MDB + r"\bridge"); sys.path.insert(0, MDB + r"\research")
from procmem import Proc
from pesx import decode_player
p = Proc("FL_2026.exe")
for nm, h, (hmin,hmax) in (("Salah",0x7ff4e4a4b27c,(170,178)),("VVD",0x7ff4e49c9164,(190,196))):
    R = h - 8
    buf = p.read(R-0x200, 0x600)
    for k in range(0, 0x600-312):
        rec = buf[k:k+312]
        d = decode_player(rec)
        if hmin <= d["Height"] <= hmax and 60 <= d["Weight"] <= 100 and 25 <= d["Age"] <= 40 and 40 <= d["Speed"] <= 99 and 40<=d["Finishing"]<=99:
            print(nm, "base R%+#x" % (k-0x200), {x:d[x] for x in ("Id","Height","Weight","Age","Speed","Finishing","AttackingProwess","BallControl","RegisteredPosition","Stamina","Nationality")})
