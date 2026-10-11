"""Annotated hex dumps of FM24 objects: each qword is labelled with the RTTI class it points to (if any)."""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct, json
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
p = Proc("fm.exe")
_cache = {}
def cls_of_vt(vt):
    if vt in _cache: return _cache[vt]
    name = None
    try:
        if p.base <= vt < p.base + p.size:
            col = p.u64(vt - 8)
            if p.base <= col < p.base + p.size and p.u32(col) == 1:
                td = p.base + p.u32(col + 0xC)
                raw = p.read(td + 0x10, 120).split(b"\0")[0].decode("ascii", "replace")
                name = raw[4:-2] if raw.startswith(".?AV") else raw
    except OSError:
        pass
    _cache[vt] = name
    return name
def cls_at(ptr):
    try:
        return cls_of_vt(p.u64(ptr))
    except OSError:
        return None
def fmstr(ptr):
    try:
        n = p.u32(ptr)
        if 0 < n < 200:
            s = p.read(ptr + 4, n)
            if all(32 <= c < 127 or c >= 0x80 for c in s): return s.decode("utf-8", "replace")
    except OSError: pass
    return None
def label(q):
    if q < 0x10000 or q > 0x7fffffffffff: return ""
    c = cls_at(q)
    if c: return "-> " + c
    s = fmstr(q)
    if s: return f'-> str "{s}"'
    try:
        q2 = p.u64(q); s = fmstr(q2)
        if s: return f'-> ->str "{s}"'
        c = cls_at(q2)
        if c: return "-> -> " + c
    except OSError: pass
    return ""
def dump(addr, n=0x100, title=""):
    print(f"== {title} {hex(addr)} {cls_at(addr)}")
    b = p.try_read(addr, n)
    if b is None: print("  unreadable"); return
    for o in range(0, len(b), 8):
        q = struct.unpack_from("<Q", b, o)[0]
        if q == 0: continue
        print(f"  +{o:04x} {b[o:o+8].hex(' ')}  {label(q)}")
if __name__ == "__main__":
    c = json.load(open(MDB + r"\research\census_ft.json"))
    for k in sys.argv[1:]:
        name, _, n = k.partition(":")
        for a in c[name][:int(n or 4)]:
            dump(int(a, 16), 0x100, name)
