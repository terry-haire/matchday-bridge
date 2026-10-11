import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\bridge")
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at, label
from fm_reader import FmReader
r = FmReader()
gm = 0xe974d270
want = {"Agostinho Santos", "Nikola Raičević", "Marc Cucurella", "Ryan Harris"}
found = {}
for off in (0xcea8, 0xcf38):
    for i in range(18):
        mp = p.u64(gm + off + 8*i)
        nm = r.fm_string(p.u64(mp + 0x30))
        if nm in want:
            found[nm] = (mp, r.complete_object(p.u64(mp + 0x28)))
for nm, (mp, ap) in found.items():
    print("#", nm, "MP", hex(mp), "AP", hex(ap))
    for tag, val in (("MP", mp), ("AP", ap), ("SUB", p.u64(mp+0x28))):
        refs = p.find_qword(val)
        print("  refs to", tag, len(refs))
        for a in refs[:40]:
            start = None
            for back in range(0, 0x800, 8):
                c = cls_at(a - back)
                if c: start = (a - back, c); break
            ctx = p.try_read(a - 0x10, 0x30)
            s = f"{hex(start[0])}+{a-start[0]:#x} {start[1]}" if start else "-"
            print(f"    {a:#x} in {s}  {ctx.hex(' ') if ctx else ''}")
