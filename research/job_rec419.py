import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, json, struct
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
p = Proc("FL_2026.exe")
S = 0x419
out = {}
for a in (0xf4ac241c, 0x108c3ac38, 0x7ff4ebe72c0c):
    # find record start: search back for player id 55400 within one stride
    blk = p.try_read(a - S, S * 3)
    out[hex(a)] = {"pre": blk.hex() if blk else None}
    rows = []
    for i in range(-11, 24):
        r = p.try_read(a + i * S - 0x200, S)
        rows.append(r.hex() if r else None)
    out[hex(a)]["rows"] = rows
json.dump(out, open(MDB + r"\research\pes_rec419.json", "w"))
print("ok")
