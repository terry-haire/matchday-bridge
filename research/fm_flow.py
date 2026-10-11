"""Step through FM24's match day on the lab save and log, per step: screen, main button, and whether the
bridge's FmReader sees today's match (GAME_MATCH). Output: research/fm_flow.txt"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import os
import sys
import time

ROOT = MDB
sys.path.insert(0, os.path.join(ROOT, "testkit"))
sys.path.insert(0, os.path.join(ROOT, "bridge"))
import fm as F  # noqa: E402
from fm_reader import FmReader  # noqa: E402

OUT = open(os.path.join(ROOT, "research", "fm_flow.txt"), "w", encoding="utf-8")
T0 = time.time()


def log(s):
    line = f"{time.time() - T0:6.1f}s {s}"
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


F.reload()
fm = F.Fm()
r = FmReader()
last = None
for step in range(40):
    scr = fm.screen()
    b = fm.button()
    t = time.time()
    try:
        md = r.matchday()
    except Exception as e:  # noqa: BLE001
        md = f"err {e}"
    dt = time.time() - t
    seen = (md["home"]["name"], md["away"]["name"]) if isinstance(md, dict) else md
    log(f"step {step}: screen={scr} button={b!r} top={fm.top()[:60]!r} matchday={seen} ({dt:.2f}s)")
    fm.save(f"fmflow_{step:02d}")
    if scr == "match":
        break
    if scr == "confirm":
        fm.click_text("Yes", reread=False, exact=True) or fm.click_text("Ok", reread=False, exact=True)
    elif b == "SUBMIT TEAM":
        fm.click_text("Quick Pick", reread=False, exact=True)
        time.sleep(1.0)
        fm.key("space")
    elif b:
        fm.key("space")
    time.sleep(2.5)
log("done")
