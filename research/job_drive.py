"""Elevated: build Birmingham Legion v Oldham Athletic (both spare slots, user away), restart SPFL26 with the
bridge's proxy and let spfl_drive walk to the pre-match screen. Output: research/drive_test.txt"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import datetime
import json
import os
import subprocess
import sys
import time

ROOT = MDB
sys.path.insert(0, os.path.join(ROOT, "bridge"))
import install  # noqa: E402
import spfl_pad  # noqa: E402
from spfl_build import MatchBuilder, request_lines  # noqa: E402
from spfl_db import PesDb  # noqa: E402
from spfl_drive import DriveError, Driver  # noqa: E402

OUT = os.path.join(ROOT, "research", "drive_test.txt")
f = open(OUT, "w", encoding="utf-8")
T0 = time.time()


def log(s):
    line = f"{time.time() - T0:6.1f}s {s}"
    print(line, flush=True)
    f.write(line + "\n")
    f.flush()


HOME, AWAY = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("Birmingham Legion", "Oldham Athletic")
USER = sys.argv[3] if len(sys.argv) > 3 else "away"
game = install.find_spfl26()
sider = os.path.join(game, "SiderAddons")
md = json.load(open(os.path.join(ROOT, "tests", "sample_matchday.json"), encoding="utf-8"))
md = {**md, "home": {**md["home"], "name": HOME, "short": HOME.split()[0], "human": USER == "home"},
      "away": {**md["away"], "name": AWAY, "short": AWAY.split()[0], "human": USER == "away"}}
for exe in ("FL_2026.exe", "sider.exe"):
    subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True)
time.sleep(2)
install.install_spfl(game)
install.clear_match_root(game)
db = PesDb.load(game, [os.path.join(sider, "livecpk", "root")])
b = MatchBuilder(db)
plan = b.build(md, datetime.date(2032, 7, 15))
b.write_root(os.path.join(sider, "livecpk", "matchday"))
import fm_graphics  # noqa: E402
CLUB_IDS = {"Oldham Athletic": 694, "Atlanta United FC": 72047296}
for s in ("home", "away"):
    if plan[s]["spare_slot"]:
        png = fm_graphics.club_logo(install.find_fm24(), CLUB_IDS.get(plan[s]["fm_name"]))
        fm_graphics.write_crests(os.path.join(sider, "livecpk", "matchday"), plan[s]["spfl_team"],
                                 fm_graphics.crest_images(png, plan[s]["fm_name"], plan[s]["abbr"]))
        log(f"crest {plan[s]['fm_name']}: {'FM logo' if png else 'drawn'}")
open(os.path.join(sider, "matchday", "request.txt"), "w", encoding="utf-8").write(
    request_lines(md, plan, "FM24", "15 Jul 2032"))
for s in ("home", "away"):
    log(f"plan {s}: {plan[s]['spfl_name']} league={plan[s]['league']!r} tid={plan[s]['spfl_team']}")
spfl_pad.shm()
log(f"proxy install changed: {spfl_pad.install(game, os.path.join(ROOT, 'spfl', 'xinput', 'xinput1_3.dll'))}")
subprocess.Popen([os.path.join(game, "FL 2026 start.exe")], cwd=game, stdin=subprocess.DEVNULL,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x00000008 | 0x00000200)
d = Driver(plan, USER, status=lambda s: log(f"status: {s}"), log=log,
           shots=os.path.join(ROOT, "research", "shots", "drive"))
try:
    d.run()
    log("RESULT: pre-match screen reached")
except DriveError as e:
    log(f"RESULT: stopped: {e}")
    try:
        d.shot().save(os.path.join(ROOT, "research", "shots", "drive_fail.png"))
    except Exception:  # noqa: BLE001
        pass
finally:
    try:
        d.shot().save(os.path.join(ROOT, "research", "shots", "drive_end.png"))
    except Exception:  # noqa: BLE001
        pass
    d.close()
