"""Narrowing scan for the live score. Usage: scorescan.py first H A  |  scorescan.py next H A"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import json
import pickle
import sys

import numpy as np

sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc  # noqa: E402

STATE = MDB + r"\research\dumps_scorescan.pkl"
p = Proc("fm.exe")
mode, h, a = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])

if mode == "first":
    cands = {"u8": [], "u16": [], "u32": []}
    for base, size in p.regions():
        for off in range(0, size, 64 << 20):
            n = min(64 << 20, size - off)
            b = p.try_read(base + off, n)
            if not b:
                continue
            arr = np.frombuffer(b, dtype=np.uint8)
            m = (arr[:-1] == h) & (arr[1:] == a)
            cands["u8"].extend((base + off + np.nonzero(m)[0]).tolist())
            a16 = np.frombuffer(b[: len(b) // 2 * 2], dtype=np.uint16)
            m = (a16[:-1] == h) & (a16[1:] == a)
            cands["u16"].extend((base + off + np.nonzero(m)[0] * 2).tolist())
            a32 = np.frombuffer(b[: len(b) // 4 * 4], dtype=np.uint32)
            m = (a32[:-1] == h) & (a32[1:] == a)
            cands["u32"].extend((base + off + np.nonzero(m)[0] * 4).tolist())
    pickle.dump(cands, open(STATE, "wb"))
    print({k: len(v) for k, v in cands.items()})
else:
    cands = pickle.load(open(STATE, "rb"))
    out = {}
    for k, lst in cands.items():
        w = {"u8": 1, "u16": 2, "u32": 4}[k]
        fmt = {"u8": "<BB", "u16": "<HH", "u32": "<II"}[k]
        keep = []
        import struct
        for addr in lst:
            bb = p.try_read(addr, 2 * w)
            if bb and struct.unpack(fmt, bb) == (h, a):
                keep.append(addr)
        out[k] = keep
    pickle.dump(out, open(STATE, "wb"))
    print({k: len(v) for k, v in out.items()})
    for k, v in out.items():
        if len(v) <= 40:
            print(k, [hex(x) for x in v])
