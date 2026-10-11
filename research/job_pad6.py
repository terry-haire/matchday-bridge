import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, time, os
sys.path.insert(0, MDB + r"\testkit")
import spfl, win, pad
log = spfl.log
spfl.HIGHLIGHT_KEYS = ["esc", "back", "tab", "ins", "del", "home", "end", "q", "e", "f1", "num0", "enter"]
s = spfl.Spfl()
scr, _ = s.screen()
log("screen", scr)
t0 = time.time()
if scr != "fulltime":
    spfl.skip_match(to_menu=False)
spfl.rematch()
spfl.skip_match(to_menu=False, verbose=True)
log(f"rematch + match {time.time() - t0:.1f}s")
