import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
p = Proc("FL_2026.exe")
owner = p.u64(0x143705e10); print("owner", hex(owner))
blk = p.u64(owner + 0x48); print("block", hex(blk))
print("counts players/teams/coaches/regs", [p.u32(blk+o) for o in (0xd0bce8,0xd0bcec,0xd0bcf0,0xd0bcf4)])
TB = blk + 0xadf4bc
def cs(b): return b.split(b"\0")[0].decode("utf-8","replace")
found = {}
for i in range(750):
    rec = p.read(TB + i*0x690, 0x50)
    enc = struct.unpack_from("<I", rec, 0)[0]
    tid = (enc >> 14) & 0x1ffff
    nm = cs(rec[4:4+0x46])
    if i < 3 or tid in (103, 5736, 101, 900): print(i, hex(enc), tid, nm)
    found[tid] = i
print("teams in table", len(found))
# player array: check record for Salah id 57123?
PB = blk
for i in range(30001):
    b = p.read(PB + i*0x17c + 0x30, 0x10)
    if b is None: break
