"""Elevated experiment: which roster entry empties SPFL26's pre-match line-ups. matchday.lua is pointed at another
fixture so Liverpool/Galatasaray are left alone; their live rosters are written directly (original roster with some
positions replaced by the face-aware plan's records), the teams picked, the pre-match screen read.
Report research/bisect.txt."""
import datetime
import os
import struct
import sys
import time

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
sys.path.insert(1, os.path.join(ROOT, "testkit"))
import install  # noqa: E402
import spfl  # noqa: E402
from fm_reader import FmReader  # noqa: E402
from gen_structs import SPFL_EDIT_BLOCK as EB, SPFL_TEAM_REC as TR  # noqa: E402
from procmem import Proc  # noqa: E402
from spfl_build import MatchBuilder  # noqa: E402
from spfl_db import PesDb  # noqa: E402
from spfl_drive import Driver, fold, text_of  # noqa: E402
from spfl_faces import real_face_ids  # noqa: E402

OUT = open(os.path.join(ROOT, "research", "bisect.txt"), "w", encoding="utf-8")
T0 = time.time()


def log(s):
    line = f"{time.time() - T0:6.1f}s {s}"
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


game = install.find_spfl26()
sider = os.path.join(game, "SiderAddons")
md = FmReader().matchday()
db = PesDb.load(game, [os.path.join(sider, "livecpk", "root")])
b = MatchBuilder(db, real_face_ids(game))
plan = b.build(md, datetime.date(2026, 10, 11))
how = {line.split(" -> ")[1].split(" ")[0]: line for line in b.log}
ORIG = {t: [r["player"] for r in db.assignments(t)] for t in (103, 130)}
SHIRTS = {t: [r["shirt"] for r in db.assignments(t)] for t in (103, 130)}

req = {"home": "Atlanta United FC", "away": "Zalgiris Vilnius", "home_tid": 5736, "away_tid": 199}
text = "".join(f"{k}={v}\n" for k, v in req.items())
for side in ("home", "away"):
    rows = db.assignments(req[side + "_tid"])
    text += f"{side}_ids={','.join(str(r['player']) for r in rows)}\n{side}_shirts={','.join(str(r['shirt']) for r in rows)}\n"
rq = os.path.join(sider, "matchday", "request.txt")
open(rq + ".tmp", "w", encoding="utf-8").write(text)
os.replace(rq + ".tmp", rq)


def ensure_game():
    import subprocess
    for exe in ("FL_2026.exe", "sider.exe"):                 # a broken line-up stays broken: fresh game per try
        subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True)
    time.sleep(3)
    install.clear_match_root(game)
    spfl.start(match_minutes=None)
    time.sleep(3)


def team_addr(p, blk, tid):
    n = p.u32(blk + EB.TEAM_COUNT)
    raw = p.read(blk + EB.TEAMS, n * 0x690)
    return blk + EB.TEAMS + 0x690 * next(i for i in range(n)
                                          if (struct.unpack_from("<I", raw, i * 0x690)[0] >> 14) & 0x1ffff == tid)


def write_roster(p, a, ids, shirts):
    n = len(ids)
    for k in range(40):
        p.write(a + TR.ROSTER + k * 8, struct.pack("<IHH", ids[k] if k < n else 0, 0xffff if k >= n - 1 else 0, 0))
        p.write(a + TR.SHIRTS + k * 2, struct.pack("<H", shirts[k] if k < n else 0))
    p.write(a + TR.CAPTAIN_INDEX, struct.pack("<H", 0))


def try_rosters(tag, rosters):
    ensure_game()
    p = Proc("FL_2026.exe", write=True)
    try:
        blk = p.u64(p.u64(EB.OWNER_GLOBAL) + 0x48)
        for t, ids in rosters.items():
            write_roster(p, team_addr(p, blk, t), ids, list(range(1, len(ids) + 1)))
    finally:
        p.close()
    pl = {"home": {**plan["home"], "ids": rosters[103]}, "away": {**plan["away"], "ids": rosters[130]}}
    d = Driver(pl, "home", log=lambda s: None, sider=sider)
    try:
        d.run(from_anywhere=True)
        time.sleep(2.0)
        img, lines = d.read()
        img.save(os.path.join(ROOT, "research", "shots", f"bisect_{len(os.listdir(os.path.join(ROOT, 'research', 'shots')))}.png"))
        t = fold(text_of(lines))
        filled = "asaray" in t or "verpoo" in t
    except Exception as e:  # noqa: BLE001
        log(f"{tag}: drive failed ({e}); counted as empty")
        filled = False
    finally:
        d.close()
    log(f"{tag}: {'filled' if filled else 'EMPTY'}")
    return filled


def mixed(t, idx):
    ids = list(ORIG[t])
    for i in idx:
        pid = plan["home" if t == 103 else "away"]["ids"][i]
        if pid in ids:                                   # his own record elsewhere in the roster: swap, no duplicate
            j = ids.index(pid)
            ids[j] = ids[i]
        ids[i] = pid
    return ids


ok_orig = try_rosters("original both", {103: ORIG[103], 130: ORIG[130]})
for t in (103, 130):
    side = "home" if t == 103 else "away"
    full = list(range(len(plan[side]["ids"])))
    other = 130 if t == 103 else 103
    if try_rosters(f"{side} = plan", {t: mixed(t, full), other: ORIG[other]}):
        continue
    cand = full
    while len(cand) > 1:
        half = cand[:len(cand) // 2]
        if not try_rosters(f"{side} plan at {half}", {t: mixed(t, half), other: ORIG[other]}):
            cand = half
        else:
            cand = cand[len(cand) // 2:]
    pid = plan[side]["ids"][cand[0]]
    log(f"{side}: index {cand[0]} breaks it: {pid} | {how.get(str(pid))}")
OUT.close()

