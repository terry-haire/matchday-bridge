"""Single-value narrowing: singlescan.py first HV AV | next HV AV  (u8/u16/u32 per side)"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, pickle
import numpy as np
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
p = Proc("fm.exe")
ST = MDB + r"\research\dumps_single.pkl"
mode, hv, av = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
W = {"u8": np.uint8, "u16": np.uint16, "u32": np.uint32}
if mode == "first":
    out = {}
    for base, size in p.regions():
        if size > 0x40000000: continue
        b = p.try_read(base, size)
        if not b: continue
        for k, dt in W.items():
            w = np.dtype(dt).itemsize
            a = np.frombuffer(b[: len(b) // w * w], dtype=dt)
            for side, v in (("h", hv), ("a", av)):
                idx = np.nonzero(a == v)[0].astype(np.uint32)
                if len(idx): out.setdefault((side, k), []).append((base, idx))
    pickle.dump(out, open(ST, "wb"), protocol=4)
    print({f"{s}{k}": sum(len(i) for _, i in v) for (s, k), v in out.items()})
else:
    out = pickle.load(open(ST, "rb"))
    keep = {}
    regions = {}
    for (side, k), lst in out.items():
        dt = W[k]; w = np.dtype(dt).itemsize; v = hv if side == "h" else av
        nl = []
        for base, idx in lst:
            if base not in regions:
                regions[base] = None
            b = regions.get(base)
            if b is None:
                if not hasattr(p, "_regmap"):
                    p._regmap = dict(p.regions())
                size = p._regmap.get(base, 0)
                b = p.try_read(base, size) if size else None
                regions[base] = b
            if not b: continue
            a = np.frombuffer(b[: len(b) // w * w], dtype=dt)
            idx = idx[idx < len(a)]
            m = a[idx] == v
            if m.any(): nl.append((base, idx[m]))
        keep[(side, k)] = nl
    pickle.dump(keep, open(ST, "wb"), protocol=4)
    print({f"{s}{k}": sum(len(i) for _, i in v) for (s, k), v in keep.items()})
    for (s, k), v in keep.items():
        n = sum(len(i) for _, i in v)
        if n <= 40:
            w = np.dtype(W[k]).itemsize
            print(s, k, [hex(b + int(i) * w) for b, ii in v for i in ii])
