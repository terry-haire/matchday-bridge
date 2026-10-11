import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, time, os
sys.path.insert(0, MDB + r"\testkit")
import spfl, win, pad
from PIL import ImageChops
SH = MDB + r"\research\shots"
pad.ensure()
s = spfl.Spfl()
scr, _ = s.screen()
if scr == "title":
    s.advance("enter", "title", 60)
scr, _ = s.wait(["mainmenu"], 30)
time.sleep(1.5)
a = s.shot(); a.save(os.path.join(SH, "pad_mm_before.png"))
win.focus(s.h); pad.taps("DOWN*2", 250); time.sleep(0.8)
b = s.shot(); b.save(os.path.join(SH, "pad_mm_after.png"))
print("main menu changed after pad DOWN*2:", ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox())
s.press("enter")
scr, _ = s.wait(["matchmenu", "sides"], 30)
time.sleep(1.0)
win.focus(s.h); pad.hold("A", 200); time.sleep(1.5)
print("after pad A on", scr, "->", s.screen()[0])
s.wait(["matchmenu", "sides"], 10)
if s.screen()[0] == "matchmenu":
    s.advance("enter", "matchmenu", 30)
s.wait("sides", 30)
time.sleep(1.0)
s.shot().save(os.path.join(SH, "pad_sides.png"))
win.focus(s.h); pad.taps("RIGHT", 200); time.sleep(0.8)
s.shot().save(os.path.join(SH, "pad_sides2.png"))
print("done")
