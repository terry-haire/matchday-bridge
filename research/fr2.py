import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys
sys.path.insert(0, MDB + r"\bridge")
from fm_reader import FmReader
r = FmReader()
print(r.team(0x1027f7478), r.team(0x2367f7478 if False else 0x1027f7478))
for t in (0x1027f7478,):
    pass
from fmdump import p
print(r.team(p.u64(0x1072b10c0 + 8)), r.team(p.u64(0x1072b10c0 + 0x10)))
