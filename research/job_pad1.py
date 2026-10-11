import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, time, os
sys.path.insert(0, MDB + r"\testkit")
import spfl, win, pad
SH = MDB + r"\research\shots"
pad.ensure()
print("pad up")
s = spfl.start(1)
t0 = time.time()
# title: tap A until it leaves the title screen
while True:
    win.untop("Football Manager 2024"); win.focus(s.h)
    pad.tap("A")
    scr, _ = s.screen()
    if scr != "title":
        print(f"left title via pad A after {time.time()-t0:.1f}s ->", scr); break
    time.sleep(0.5)
for want in ("mainmenu", "matchmenu"):
    scr, _ = s.wait(["mainmenu", "matchmenu", "sides", "teams"], 60)
    if scr == want:
        t = time.time()
        while s.screen()[0] == want:
            win.focus(s.h); pad.tap("A"); time.sleep(1.0)
        print(f"{want} -> next via pad in {time.time()-t:.1f}s")
scr, lines = s.wait(["sides", "teams"], 60)
print("now", scr)
img = s.shot(); img.save(os.path.join(SH, "pad_sides.png"))
print(win.text_of(lines)[:400])
