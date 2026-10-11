import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, time
sys.path.insert(0, MDB + r"\bridge")
from procmem import Proc
p = Proc("fm.exe")
FR = 0x1072b10c0
last = None; t0 = time.time()
log = open(MDB + r"\research\frwatch.log", "w")
while time.time() - t0 < 240:
    b = p.try_read(FR, 0x70)
    v = b[0x60:0x70].hex(" ") if b else None
    if v != last:
        line = f"{time.time()-t0:7.1f} {v}"
        print(line); log.write(line + "\n"); log.flush(); last = v
    time.sleep(0.25)
