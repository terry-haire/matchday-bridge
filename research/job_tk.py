import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, time
sys.path.insert(0, MDB + r"\testkit")
import spfl, win
u = win.user32
s = spfl.Spfl()
fm = u.FindWindowW(None, "Football Manager 2024")
for i in range(8):
    print("unfocused", spfl.clock(), spfl.game_state().get("ptr")); time.sleep(1)
win.untop("Football Manager 2024"); win.focus(s.h)
for i in range(5):
    print("focused", spfl.clock()); time.sleep(1)
img = s.shot(); img.save(MDB + r"\research\shots\spfl_state.png"); print(win.text_of(win.ocr(img))[:200])
