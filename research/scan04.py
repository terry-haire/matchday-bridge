import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct, json
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at
gm = 0xe974d270
m = p.find_qword(p.vtables(".?AVMATCH@simatch@@")[0], limit=4)
print("MATCH objs", [hex(x) for x in m])
objs = {"GAME_MATCH": gm}
if m: objs["MATCH"] = m[0]
out = {}
for name, base in objs.items():
    size = 0x40000
    b = None
    while size >= 0x1000 and b is None:
        b = p.try_read(base, size)
        if b is None: size //= 2
    open(f"dumps_{name}_ft.bin", "wb").write(b)
    print(name, hex(base), "read", hex(size))
    for fmt, w in (("<II", 8), ("<HH", 4), ("BB", 2)):
        hits = [o for o in range(0, len(b) - w, w // 2) if struct.unpack_from(fmt, b, o) == (0, 4)]
        print(f"  {fmt} (0,4) at", [hex(o) for o in hits][:60], len(hits))
