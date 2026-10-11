"""Interactive helpers for exploring FM24 objects (research only)."""
from __future__ import annotations
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root

import json
import struct
import sys

sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc  # noqa: E402

p = Proc("fm.exe")
VT = {k: [int(x, 16) for x in v] for k, v in json.load(open(MDB + r"\research\fm_vtables.json")).items()}
VTN = {}
for k, v in VT.items():
    for i, x in enumerate(v):
        VTN[x] = f"{k}#{i}"


def printable(b: bytes) -> str:
    return "".join(chr(c) if 32 <= c < 127 else "." for c in b)


def rtti_name(vt: int) -> str | None:
    """Class name for any vtable via COL -> TypeDescriptor."""
    col = p.try_read(vt - 8, 8)
    if not col:
        return None
    col = struct.unpack("<Q", col)[0]
    if not (p.base <= col < p.base + p.size):
        return None
    d = p.try_read(col, 24)
    if not d:
        return None
    sig, off, cdoff, td = struct.unpack_from("<IIII", d)
    if sig != 1:
        return None
    nm = p.try_read(p.base + td + 0x10, 96)
    if not nm:
        return None
    return nm.split(b"\0")[0].decode(errors="replace")


def describe_ptr(v: int) -> str:
    if v < 0x10000 or v > 0x7FFFFFFFFFFF:
        return ""
    if p.base <= v < p.base + p.size:
        n = rtti_name(v)
        return f"[vtable {n}]" if n else "[image]"
    d = p.try_read(v, 32)
    if not d:
        return ""
    q = struct.unpack("<Q", d[:8])[0]
    if p.base <= q < p.base + p.size:
        n = rtti_name(q)
        if n:
            return f"-> obj {n}"
    return f"-> '{printable(d)}'"


def dump(addr: int, n: int = 0x100, skip_zero: bool = True):
    b = p.read(addr, n)
    for off in range(0, n, 8):
        q = struct.unpack_from("<Q", b, off)[0]
        if skip_zero and q == 0:
            continue
        print(f"+{off:03x}: {b[off:off+8].hex(' ')}  {q:#x} {describe_ptr(q)}")


def cstr(addr: int, n: int = 64) -> str:
    b = p.try_read(addr, n) or b""
    return b.split(b"\0")[0].decode("utf-8", errors="replace")


if __name__ == "__main__":
    a = int(sys.argv[1], 16)
    n = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x100
    dump(a, n)
