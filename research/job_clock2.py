import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, time, struct
import numpy as np
sys.path.insert(0, MDB + r"\testkit")
sys.path.insert(0, MDB + r"\bridge")
import spfl, win
from procmem import Proc
s = spfl.Spfl(); pid = win.pid_of(s.h)
p = Proc("FL_2026.exe")
def display(pt):
    b = p.read(pt, 0x150); mm, ss = struct.unpack_from("<II", b, 0x12c); return mm * 60 + ss, b[0x22]
# need a running match
for _ in range(240):
    st = spfl.game_state(); scr = s.screen()[0]
    if scr in ("highlights", "halftime"): s.press("enter")
    pt = int(st.get("ptr", "0"), 16)
    if pt and scr == "match":
        T, run = display(pt)
        if run and 3 * 60 < T < 40 * 60: break
        if not run: s.press("x")
    if scr in ("fulltime", "mainmenu", "teams", "prematch", "sides", "matchmenu", "title"):
        print("not in a match:", scr); sys.exit()
    time.sleep(0.5)
sci2 = p.u64(pt + 0x38)
print("ptr", hex(pt), "sci2", hex(sci2))
ranges = []
for c in (pt, sci2):
    ranges.append((max(c - 0x200000, 0) & ~0xfff, 0x400000))
img = 0x140000000
ranges += [(img + 0x339b000, 0x72a000), (img + 0x3c98000, 0x9000), (img + 0x3ca1000, 0x73000)]
def snap():
    out = []
    for a, n in ranges:
        b = bytearray()
        for off in range(0, n, 0x1000):
            pg = p.try_read(a + off, 0x1000)
            b += pg if pg else b"\0" * 0x1000
        out.append(bytes(b))
    return out
snaps, Ts = [], []
for i in range(4):
    win.suspend(pid, True); time.sleep(0.15)
    Ts.append(display(pt)[0]); snaps.append(snap())
    win.suspend(pid, False); time.sleep(0.5 if i < 3 else 0)
print("T", Ts)
dT = np.diff(np.array(Ts, dtype=np.float64))
for (a, n), *ss in zip(ranges, *snaps):
    for dt, w in ((np.float32, 4), (np.float64, 8), (np.uint32, 4), (np.uint64, 8)):
        arrs = [np.frombuffer(x[: len(x) // w * w], dtype=dt).astype(np.float64) for x in ss]
        d = [arrs[i + 1] - arrs[i] for i in range(3)]
        with np.errstate(all="ignore"):
            r = [d[i] / dT[i] for i in range(3)]
            ok = np.isfinite(r[0]) & (np.abs(r[0]) > 1e-6) & (np.abs(r[0] - r[1]) <= 0.02 * np.abs(r[0]) + 1e-9) & (np.abs(r[0] - r[2]) <= 0.02 * np.abs(r[0]) + 1e-9)
        for i in np.nonzero(ok)[0][:20]:
            ratio = r[0][i]; c = arrs[0][i] - ratio * Ts[0]
            print(f"{dt.__name__:8s} {hex(a + i * w)} vals {[round(x[i], 3) for x in arrs]} ratio {ratio:.5f} offset {c:.2f}")
