"""PES 2021 / SPFL26 record helpers (research). Layouts from the4chancup/4cc-studio (MIT/Apache-2.0)."""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import json
import struct
import sys

sys.path.insert(0, MDB + r"\bridge")

SCHEMA = json.load(open(MDB + r"\research\pes21_schema.json"))
PLAYER_FIELDS = {n: (o, w) for n, o, w in SCHEMA["PLAYER"]["fields"]}
TEAM_FIELDS = {n: (o, w) for n, o, w in SCHEMA["TEAM_21"]["fields"]}


def getbits(b: bytes, off: int, width: int) -> int:
    v = int.from_bytes(b[off // 8: (off + width + 7) // 8 + 1], "little")
    return (v >> (off % 8)) & ((1 << width) - 1)


def setbits(b: bytearray, off: int, width: int, value: int):
    start = off // 8
    end = (off + width + 7) // 8 + 1
    end = min(end, len(b))
    v = int.from_bytes(b[start:end], "little")
    mask = ((1 << width) - 1) << (off % 8)
    v = (v & ~mask) | ((value << (off % 8)) & mask)
    b[start:end] = v.to_bytes(end - start, "little")


def decode_player(rec: bytes) -> dict:
    d = {n: getbits(rec, o, w) for n, (o, w) in PLAYER_FIELDS.items() if o + w <= len(rec) * 8}
    d["Name"] = rec[54:115].split(b"\0")[0].decode("utf-8", "replace")
    d["ShirtName"] = rec[115:176].split(b"\0")[0].decode("utf-8", "replace")
    return d


def decode_team(rec: bytes) -> dict:
    d = {n: getbits(rec, o, w) for n, (o, w) in TEAM_FIELDS.items()}
    d["Name"] = rec[104:174].split(b"\0")[0].decode("utf-8", "replace")
    d["ShortName"] = rec[174:178].split(b"\0")[0].decode("utf-8", "replace")
    return d
