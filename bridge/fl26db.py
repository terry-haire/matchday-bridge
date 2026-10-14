"""CRI .cpk reading, WESYS pack/unpack and FL26 pesdb record layouts.

Adapted from Matozanato/FootballLife-new-leagues (tools/cpkread.py, tools/pesdb.py,
tools/playeredit.py, docs/player-record.md), MIT License, Copyright (c) 2026 Matozanato.
See THIRD_PARTY_NOTICES.md.
"""
from __future__ import annotations

import os
import struct
import zlib

# ---------------------------------------------------------------- CPK


def _read_val(b, p, typ, gstr):
    fmt = {0: (">B", 1), 1: (">b", 1), 2: (">H", 2), 3: (">h", 2), 4: (">I", 4), 5: (">i", 4),
           6: (">Q", 8), 7: (">q", 8), 8: (">f", 4)}
    if typ in fmt:
        f, n = fmt[typ]
        return struct.unpack(f, b[p:p + n])[0], p + n
    if typ == 0xA:
        return gstr(struct.unpack(">I", b[p:p + 4])[0]), p + 4
    if typ == 0xB:
        o, s = struct.unpack(">QI", b[p:p + 12])
        return ("DATA", o, s), p + 12
    raise ValueError("@UTF column type %x" % typ)


_UTF_KEY = b""


def _utf_unscramble(data: bytes) -> bytes:
    """CRI's table scrambling (Konami's official PES 2021 .cpk files): XOR with the low bytes of the LCG
    m = 0x655F * 0x4115^i (mod 2^32); the key stream is the same for every table, so it is built once."""
    global _UTF_KEY
    import numpy as np
    if len(_UTF_KEY) < len(data):
        p = np.full(max(len(data), 1 << 16), 0x4115, dtype=np.uint64)
        p[0] = 1
        _UTF_KEY = ((np.cumprod(p) * np.uint64(0x655F)) & np.uint64(0xFF)).astype(np.uint8).tobytes()
    return (np.frombuffer(data, np.uint8) ^ np.frombuffer(_UTF_KEY, np.uint8, len(data))).tobytes()


def _utf_parse(data):
    if data[:4] != b"@UTF" and _utf_unscramble(data[:4]) == b"@UTF":
        data = _utf_unscramble(data)
    if data[:4] != b"@UTF":
        raise ValueError("not a CRI table: %r" % data[:4])
    size, = struct.unpack(">I", data[4:8])
    b = data[8:8 + size]
    rows_off, strings_off, _data_off, _name, n_cols, row_len, n_rows = struct.unpack(">IIIIHHI", b[:24])

    def gstr(o):
        e = b.index(b"\0", strings_off + o)
        return b[strings_off + o:e].decode("utf-8", "replace")
    cols, p = [], 24
    for _ in range(n_cols):
        flags = b[p]
        noff, = struct.unpack(">I", b[p + 1:p + 5])
        p += 5
        storage, typ, const = flags & 0xF0, flags & 0x0F, None
        if storage == 0x30:
            const, p = _read_val(b, p, typ, gstr)
        cols.append((gstr(noff), storage, typ, const))
    rows = []
    for r in range(n_rows):
        p, row = rows_off + r * row_len, {}
        for name, storage, typ, const in cols:
            if storage == 0x30:
                row[name] = const
            elif storage == 0x10:
                row[name] = None
            else:
                row[name], p = _read_val(b, p, typ, gstr)
        rows.append(row)
    return rows


def _crilayla(src):
    usize, hsize = struct.unpack("<II", src[8:16])
    head = src[16 + hsize:16 + hsize + 0x100]
    dest = bytearray(usize)
    data = src[16:16 + hsize]
    st = {"pos": len(data) - 1, "pool": 0, "count": 0}

    def bits(n):
        v = 0
        while n > 0:
            if st["count"] == 0:
                st["pool"], st["count"] = data[st["pos"]], 8
                st["pos"] -= 1
            t = min(n, st["count"])
            v = (v << t) | ((st["pool"] >> (st["count"] - t)) & ((1 << t) - 1))
            st["count"] -= t
            n -= t
        return v
    out, vle = usize - 1, (2, 3, 5, 8)
    while out >= 0:
        if bits(1):
            ref, lvl, ln = bits(13) + 3, 0, 3
            while True:
                v = bits(vle[lvl] if lvl < 4 else 8)
                ln += v
                if lvl < 3:
                    if v != (1 << vle[lvl]) - 1:
                        break
                    lvl += 1
                elif v != 255:
                    break
            for _ in range(ln):
                dest[out] = dest[out + ref]
                out -= 1
        else:
            dest[out] = bits(8)
            out -= 1
    return bytes(head) + bytes(dest)


def cpk_toc(f):
    hdr = f.read(16)
    cpk = _utf_parse(f.read(struct.unpack("<Q", hdr[8:16])[0] + 8))[0]
    t_off, ca = cpk["TocOffset"], cpk.get("ContentOffset", 0)
    f.seek(t_off)
    t = f.read(16)
    return (min(t_off, ca) if ca else t_off), _utf_parse(f.read(struct.unpack("<Q", t[8:16])[0] + 8))


def cpk_path(r):
    return (r["DirName"] + "/" + r["FileName"]) if r["DirName"] else r["FileName"]


def cpk_names(path):
    with open(path, "rb") as f:
        return [cpk_path(r) for r in cpk_toc(f)[1]]


def cpk_read(path, inner):
    """Bytes of one file inside a .cpk (inner path with forward slashes), or None."""
    with open(path, "rb") as f:
        base, rows = cpk_toc(f)
        for r in rows:
            if cpk_path(r).lower() == inner.lower():
                return cpk_row_data(f, base, r)
    return None


def cpk_row_data(f, base, r) -> bytes:
    """Bytes of one table-of-contents row of an open .cpk (from cpk_toc)."""
    f.seek(base + r["FileOffset"])
    d = f.read(r["FileSize"])
    if r["ExtractSize"] > r["FileSize"] and d[:8] == b"CRILAYLA":
        d = _crilayla(d)
    return d

# ---------------------------------------------------------------- WESYS


def wesys_unpack(d: bytes) -> bytes:
    if d[3:8] != b"WESYS":
        return d
    csz, usz = struct.unpack("<II", d[8:16])
    out = zlib.decompress(d[16:16 + csz])
    if len(out) != usz:
        raise ValueError("WESYS size mismatch")
    return out


def wesys_pack(raw: bytes, hdr: bytes = b"\xff\x10\x81") -> bytes:
    c = zlib.compress(raw, 9)
    return hdr + b"WESYS" + struct.pack("<II", len(c), len(raw)) + c

# ---------------------------------------------------------------- records

PLAYER_REC = 312
PLAYER_ID_OFF = 0x08
PLAYER_NAME_OFF, PLAYER_NAME_LEN = 0x44, 0x3D
ASSIGN_REC = 16
TEAM_REC = 1532
TEAM_ID_OFF = 0x08
TEAM_NAME_OFF, TEAM_NAME_LEN = 0x170, 0x46
SHIRT_MASK = 0x3FF
ORDER_SHIFT, ORDER_MASK = 10, 0xFC00
POSITIONS = ["GK", "CB", "LB", "RB", "DMF", "CMF", "LMF", "RMF", "AMF", "LWF", "RWF", "SS", "CF"]


def cstr(b: bytes) -> str:
    return b.split(b"\0", 1)[0].decode("utf-8", "replace")


def name_slot(s: str) -> bytes:
    b = s.encode("utf-8")[:PLAYER_NAME_LEN - 1]
    return b.decode("utf-8", "ignore").encode("utf-8").ljust(PLAYER_NAME_LEN, b"\0")


def name_slots(name: str, shirt: str | None = None) -> bytes:
    """full name, shirt name x2, full name (the order FL26's own players use)."""
    name = name.strip()
    if shirt is None:
        shirt = (name.split(" ", 1)[1] if " " in name else name).upper()
    return name_slot(name) + name_slot(shirt) * 2 + name_slot(name)


def getbits(rec: bytes, bit: int, width: int) -> int:
    return (int.from_bytes(rec, "little") >> bit) & ((1 << width) - 1)


def setbits(rec: bytearray, bit: int, width: int, value: int):
    v = int.from_bytes(rec, "little")
    mask = ((1 << width) - 1) << bit
    v = (v & ~mask) | ((value << bit) & mask)
    rec[:] = v.to_bytes(len(rec), "little")
