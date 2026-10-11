"""Search FM24's heap for the live match ratings stored as a strided array (any stride 4..0x800).

Ratings in team-sheet slot order (Oldham, half time of the lab match): Seimen 6.9, Luiz Alberto 7.0,
Vieira 7.0, Illa 6.7, Torres 7.5, Raicevic 8.9, Chukalov 8.5, Casartelli 6.6, Cucurella 6.8, Santos 6.8,
Ribeiro 7.4.
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bridge"))
from procmem import Proc  # noqa: E402

R = [6.9, 7.0, 7.0, 6.7, 7.5, 8.9, 8.5, 6.6, 6.8, 6.8, 7.4]
p = Proc("fm.exe")
TOL = 0.06
anchor = 5                                # Raicevic 8.9 is the rarest value
found = []
for base, size in p.regions():
    if size > 0x40000000:
        continue
    b = p.try_read(base, size)
    if not b:
        continue
    for kind in ("f32", "f64", "u8x10", "u16x10", "u16x100"):
        if kind == "f32":
            a = np.frombuffer(b[: len(b) // 4 * 4], dtype="<f4").astype(np.float64)
            unit, tol, val = 4, TOL, lambda x: x
        elif kind == "f64":
            a = np.frombuffer(b[: len(b) // 8 * 8], dtype="<f8")
            unit, tol, val = 8, TOL, lambda x: x
        elif kind == "u8x10":
            a = np.frombuffer(b, dtype=np.uint8).astype(np.float64)
            unit, tol, val = 1, 0.5, lambda x: round(x * 10)
        elif kind == "u16x10":
            a = np.frombuffer(b[: len(b) // 2 * 2], dtype="<u2").astype(np.float64)
            unit, tol, val = 2, 0.5, lambda x: round(x * 10)
        else:
            a = np.frombuffer(b[: len(b) // 2 * 2], dtype="<u2").astype(np.float64)
            unit, tol, val = 2, 6, lambda x: round(x * 100)
        idx = np.nonzero(np.abs(a - val(R[anchor])) <= tol)[0]
        if len(idx) == 0 or len(idx) > 2_000_000:
            continue
        n = len(a)
        for s_bytes in range(unit, 0x801, unit):
            s = s_bytes // unit
            ok = np.ones(len(idx), dtype=bool)
            for j, rv in enumerate(R):
                pos = idx + (j - anchor) * s
                good = (pos >= 0) & (pos < n)
                pos = np.where(good, pos, 0)
                ok &= good & (np.abs(a[pos] - val(rv)) <= tol)
                if not ok.any():
                    break
            for i in np.nonzero(ok)[0]:
                addr = base + int(idx[i] - anchor * s) * unit
                found.append((kind, s_bytes, addr))
                print(f"{kind} stride {s_bytes:#x} first@{addr:#x}", flush=True)
print("done", len(found))
