"""Clock scan: clockscan.py first MM SS | next MM SS"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, pickle
import numpy as np
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
p = Proc("fm.exe")
ST = MDB + r"\research\dumps_clock.pkl"
mode, mm, ss = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
secs = mm * 60 + ss
def vals():
    return {"u16s": (np.uint16, secs), "u32s": (np.uint32, secs), "f32s": (np.float32, float(secs)),
            "u32ds": (np.uint32, secs * 10), "u32cs": (np.uint32, secs * 100), "u32ms": (np.uint32, secs * 1000)}
if mode == "first":
    out = {k: [] for k in vals()}
    for base, size in p.regions():
        for off in range(0, size, 64 << 20):
            n = min(64 << 20, size - off)
            b = p.try_read(base + off, n)
            if not b: continue
            for k, (dt, v) in vals().items():
                w = np.dtype(dt).itemsize
                a = np.frombuffer(b[: len(b) // w * w], dtype=dt)
                if dt == np.float32:
                    idx = np.nonzero(np.abs(a - v) < 1.0)[0]
                else:
                    idx = np.nonzero((a >= v - 1) & (a <= v + 1))[0] if k == "u16s" or k == "u32s" else np.nonzero(np.abs(a.astype(np.int64) - v) <= (10 if k=="u32ds" else 100 if k=="u32cs" else 1000))[0]
                out[k].extend((base + off + idx * w).tolist())
    pickle.dump(out, open(ST, "wb"))
    print({k: len(v) for k, v in out.items()})
else:
    import struct
    out = pickle.load(open(ST, "rb"))
    keep = {}
    for k, lst in out.items():
        dt, v = vals()[k]
        w = np.dtype(dt).itemsize
        tol = 1.0 if dt == np.float32 else (1 if k in ("u16s", "u32s") else 10 if k == "u32ds" else 100 if k == "u32cs" else 1000)
        kk = []
        for a in lst:
            b = p.try_read(a, w)
            if not b: continue
            x = np.frombuffer(b, dtype=dt)[0]
            if abs(float(x) - v) <= tol: kk.append(a)
        keep[k] = kk
    pickle.dump(keep, open(ST, "wb"))
    print({k: len(v) for k, v in keep.items()})
    for k, v in keep.items():
        if len(v) <= 30: print(k, [hex(x) for x in v])
