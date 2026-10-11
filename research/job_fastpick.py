"""Elevated: Select Team through matchday.lua's hook (spfl_select) in three drives in one SPFL26 session.
1 cold: Birmingham Legion v Oldham Athletic (user away), 2 hot from the pre-match screen: Atlanta United FC v Oldham
Athletic (user away), 3 hot: Oldham Athletic v Atlanta United FC (user home). Each: time per step, what the hook did
(bridge driver log), pre-match names by OCR. Report research/fastpick.txt, shots research/shots/fastpick_*."""
import datetime
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
import install  # noqa: E402
import spfl_pad  # noqa: E402
from spfl_build import MatchBuilder, request_lines  # noqa: E402
from spfl_db import PesDb  # noqa: E402
from spfl_drive import DriveError, Driver, similarity  # noqa: E402

f = open(os.path.join(ROOT, "research", "fastpick.txt"), "w", encoding="utf-8")
T0 = time.time()


def log(s):
    line = f"{time.time() - T0:6.1f}s {s}"
    print(line, flush=True)
    f.write(line + "\n")
    f.flush()


game = install.find_spfl26()
sider = os.path.join(game, "SiderAddons")
SAMPLE = json.load(open(os.path.join(ROOT, "tests", "sample_matchday.json"), encoding="utf-8"))


def md_for(home, away, user):
    return {**SAMPLE, "home": {**SAMPLE["home"], "name": home, "short": home.split()[0], "human": user == "home"},
            "away": {**SAMPLE["away"], "name": away, "short": away.split()[0], "human": user == "away"}}


def build(md):
    install.clear_match_root(game)
    db = PesDb.load(game, [os.path.join(sider, "livecpk", "root")])
    b = MatchBuilder(db)
    plan = b.build(md, datetime.date(2032, 7, 15))
    b.write_root(os.path.join(sider, "livecpk", "matchday"))
    open(os.path.join(sider, "matchday", "request.txt"), "w", encoding="utf-8").write(
        request_lines(md, plan, "FM24", "15 Jul 2032"))
    return plan


def drive(n, home, away, user, cold, hook=True):
    md = md_for(home, away, user)
    plan = build(md)
    log(f"drive {n}: {home} v {away} (user {user}), slots {plan['home']['spfl_team']}/{plan['away']['spfl_team']}, "
        f"{'cold' if cold else 'hot'}{'' if hook else ', hook unavailable (OCR scroll)'}")
    if cold:
        subprocess.Popen([os.path.join(game, "FL 2026 start.exe")], cwd=game, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x00000008 | 0x00000200)
    shots = os.path.join(ROOT, "research", "shots", f"fastpick_{n}")
    d = Driver(plan, user, status=lambda s: log(f"  status: {s}"), log=lambda s: log(f"  {s}"), shots=shots,
               sider=sider if hook else os.path.join(ROOT, "research"))
    t = time.time()
    try:
        d.run(from_anywhere=not cold)
        took = time.time() - t
        time.sleep(1.0)
        _, lines = d.screen()
        seen = [" ".join(w[0] for w in ln) for ln in lines]
        ok = all(any(similarity(plan[s]["spfl_name"], x) >= 0.82 for x in seen) for s in ("home", "away"))
        log(f"drive {n}: pre-match in {took:.1f}s, names on screen: {ok} {seen[:6]}")
        return ok
    except DriveError as e:
        log(f"drive {n}: FAILED {e}")
        return False
    finally:
        d.close()


for exe in ("FL_2026.exe", "sider.exe"):
    subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True)
time.sleep(2)
install.install_spfl(game)
spfl_pad.shm()
spfl_pad.install(game, os.path.join(ROOT, "spfl", "xinput", "xinput1_3.dll"))
results = [drive(1, "Birmingham Legion", "Oldham Athletic", "away", True),
           drive(2, "Atlanta United FC", "Oldham Athletic", "away", False),
           drive(3, "Oldham Athletic", "Atlanta United FC", "home", False),
           drive(4, "Birmingham Legion", "Oldham Athletic", "away", False, hook=False)]
log(f"RESULT {'PASS' if all(results) else 'FAIL'} {results}")
shutil.copy2(os.path.join(sider, "sider.log"), os.path.join(ROOT, "research", "fastpick_sider.log"))
