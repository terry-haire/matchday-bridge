import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, time, os, subprocess
sys.path.insert(0, MDB + r"\testkit")
import spfl, win, pad
out = subprocess.run(["tasklist", "/m", "/fi", "imagename eq FL_2026.exe"], capture_output=True, text=True).stdout
mods = out.replace("\n", " ").replace(",", " ").split()
print("input modules:", [m for m in mods if any(k in m.lower() for k in ("xinput", "dinput", "hid", "steam", "sider"))])
pad.ensure()
s = spfl.Spfl()
print("screen", s.screen()[0])
for btn, ms in (("A", 300), ("START", 300), ("A", 600)):
    win.untop("Football Manager 2024"); win.focus(s.h)
    time.sleep(0.3)
    pad.hold(btn, ms)
    time.sleep(1.5)
    print(btn, ms, "->", s.screen()[0])
