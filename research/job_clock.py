import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, time, struct, json
import numpy as np
sys.path.insert(0, MDB + r"\testkit")
sys.path.insert(0, MDB + r"\bridge")
import spfl, win
from procmem import Proc
s = spfl.Spfl(); pid = win.pid_of(s.h)
p = Proc("FL_2026.exe")
def display():
    pt = int(spfl.game_state()["ptr"], 16); b = p.read(pt, 0x150)
    mm, ss = struct.unpack_from("<II", b, 0x12c); return mm * 60 + ss, b[0x22]
# get into a running 2nd half
t0 = time.time(); last = None; still = 0
while time.time() - t0 < 120:
    scr = s.screen()[0]
    if scr in ("highlights", "halftime"): s.press("enter"); time.sleep(0.5); continue
    T, run = display()
    if scr == "match" and T > 47 * 60 and T < 80 * 60 and T != last: break
    still = still + 1 if T == last else 0; last = T
    if still > 3: s.press("x"); s.press("enter"); still = 0
    time.sleep(0.5)
win.suspend(pid, True); time.sleep(0.2)
T, run = display(); print("suspended at", T, "running", run)
kinds = {"f32": (np.float32, 1.0), "f64": (np.float64, 1.0), "u32s": (np.uint32, 0), "u32ms": (np.uint32, 1000), "f32min": (np.float32, 0.02)}
def targets(k, T):
    base = [T, T - 2700]
    return [ {"f32": x, "f64": x, "u32s": x, "u32ms": x * 1000, "f32min": x / 60}[k] for x in base ]
cands = {k: [] for k in kinds}
t1 = time.time()
for base, size in p.regions():
    if size > 0x40000000: continue
    b = p.try_read(base, size)
    if not b: continue
    for k, (dt, tol) in kinds.items():
        w = np.dtype(dt).itemsize
        a = np.frombuffer(b[: len(b) // w * w], dtype=dt).astype(np.float64)
        with np.errstate(invalid="ignore"):
            m = np.zeros(len(a), bool)
            for tg in targets(k, T): m |= np.abs(a - tg) <= tol
        cands[k].extend((base + np.nonzero(m)[0] * w).tolist())
print("scan", round(time.time() - t1, 1), {k: len(v) for k, v in cands.items()})
for rnd in range(5):
    win.suspend(pid, False); time.sleep(0.6); win.suspend(pid, True); time.sleep(0.1)
    T2, run = display()
    for k, (dt, tol) in kinds.items():
        w = np.dtype(dt).itemsize; keep = []
        for a in cands[k]:
            bb = p.try_read(a, w)
            if not bb: continue
            v = float(np.frombuffer(bb, dtype=dt)[0])
            if any(abs(v - tg) <= tol + (1.0 if k != "u32ms" else 1000) for tg in targets(k, T2)): keep.append(a)
        cands[k] = keep
    print("round", rnd, "T", T2, "running", run, {k: len(v) for k, v in cands.items()})
win.suspend(pid, False)
res = {}
for k, v in cands.items():
    dt = kinds[k][0]; w = np.dtype(dt).itemsize
    res[k] = [(hex(a), float(np.frombuffer(p.read(a, w), dtype=dt)[0])) for a in v[:40]]
    for a, val in res[k][:15]: print(k, a, val)
json.dump(res, open(MDB + r"\research\spfl_clock_cands.json", "w"), indent=0)
