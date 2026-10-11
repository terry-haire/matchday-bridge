import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
p = Proc("FL_2026.exe")
blk = p.u64(p.u64(0x143705e10) + 0x48)
TB = blk + 0xadf4bc
for i in range(750):
    a = TB + i*0x690
    enc = p.u32(a); tid = (enc >> 14) & 0x1ffff
    if tid in (199, 5736):
        r = p.read(a, 0x60)
        print(tid, hex(a), r[4:0x4a].split(b"\0")[0], r[0x4a:0x52])
for pat in (b"ZLG\0", b"Zalgiris", b"OLD\0", b"Oldham Athletic"):
    hits = p.find_bytes(pat, limit=40)
    print(pat, len(hits))
    for h in hits[:40]:
        ctx = p.try_read(h-0x10, 0x40)
        print("  ", hex(h), ctx)
