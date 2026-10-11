import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\bridge"); sys.path.insert(0, MDB + r"\research")
from procmem import Proc
from pesx import decode_player
p = Proc("FL_2026.exe")
print("base", hex(p.base), hex(p.size))
for nm in (b"Mohamed Salah\x00", b"M. SALAH\x00", b"SALAH\x00", b"Virgil van Dijk\x00"):
    hits = p.find_bytes(nm, limit=12)
    print(nm, [hex(h) for h in hits])
    for h in hits[:12]:
        rec = p.try_read(h-54, 312)
        if not rec: continue
        d = decode_player(rec)
        print("   rec@", hex(h-54), "id", d["Id"], "name", d["Name"], "/", d["ShirtName"], "h", d["Height"], "w", d["Weight"], "age", d["Age"], "spd", d["Speed"], "fin", d["Finishing"], "pos", d["RegisteredPosition"])
