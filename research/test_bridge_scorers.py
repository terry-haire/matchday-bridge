"""End-to-end test of the bridge's result flow with SPFL scorers.

FM lab save at pre-match -> Bridge._play (builds the SPFL match and request.txt; SPFL is started by the elevated
testkit job instead of the UAC launch) -> a 2-minute SPFL match (User 1 idle on the away side, so the home side
scores) while Bridge._wait_result reads each scorer from SPFL's goal caption -> FM's match to full time -> the
bridge writes score, events and player goals -> leave the match -> check every fixture copy.

    python research/test_bridge_scorers.py [--here]     (--here: FM is already on the pre-match screen)
Needs research/elevated_runner.py running (admin).
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for d in ("testkit", "bridge"):
    sys.path.insert(0, os.path.join(ROOT, d))
import fm as F  # noqa: E402
import matchday_bridge as M  # noqa: E402
from fm_reader import FmReader  # noqa: E402

JOBS = os.path.join(ROOT, "research", "jobs2")
SPFL_JOB = r'''
import ctypes, os, shutil, sys, time
ROOT = r"{root}"
sys.path.insert(0, os.path.join(ROOT, "testkit"))
import spfl
shutil.copy2(os.path.join(ROOT, "spfl", "modules", "matchday.lua"), os.path.join(spfl.SIDER, "modules", "matchday.lua"))
s = spfl.start(2)
spfl.to_team_select(s, "away")
names = {names!r}
for side in ("home", "away"):
    spfl.pick(s, side, spfl.league_of(names[side][0]), "league")
    s.press("enter")
    time.sleep(0.5)
    try:
        spfl.pick(s, side, names[side][1], "team")
    except RuntimeError:
        spfl.pick(s, side, names[side][0], "team")
    s.press("enter")
    time.sleep(0.5)
spfl.play_intro(s, time.time())
spfl.skip_match(to_menu=True)
time.sleep(2)
print(open(os.path.join(spfl.MD, "result.txt")).read())
'''


class Var:
    def __init__(self, tag):
        self.tag = tag

    def set(self, s):
        print(f"[{self.tag}] {s}", flush=True)


class Root:
    def after(self, ms, f):
        f()


class TestBridge(M.Bridge):
    def __init__(self, md):
        self.root, self.msg, self.detail = Root(), Var("msg"), Var("detail")
        import games
        self.fm_dir, self.game = None, games.spfl26(M.install.find_spfl26())
        self.games = [self.game]
        self.setup_done = M.threading.Event()
        self.setup_done.set()
        self.matchday, self.busy, self.writer, self.plan = md, True, None, None
        self.reader = self.prompted_for = None


M.ctypes.windll.shell32.ShellExecuteW = lambda *a: 42        # SPFL is started by the elevated testkit job
M.stop_processes = lambda exes: None

if "--here" not in sys.argv:
    F.reload()
    F.to_match(until="prematch")
md = FmReader().matchday()
assert md, "no FM matchday"
b = TestBridge(md)
b._play()
assert b.plan and b.writer and b.writer.date, "bridge did not build the match / find the fixture"
job = os.path.join(JOBS, time.strftime("%H%M%S000") + "_job_bridge_spfl.py")
names = {s: (b.plan[s]["spfl_name"], b.plan[s]["fm_name"]) for s in ("home", "away")}
open(job, "w", encoding="utf-8").write(SPFL_JOB.format(root=ROOT, names=names))
print("SPFL job queued:", names, flush=True)

F.to_match()
F.to_full_time()
t0 = time.time()
while not os.path.exists(job + ".out") and time.time() - t0 < 900:
    time.sleep(2)
print("SPFL job:", open(job + ".out", encoding="utf-8").read()[-1500:] if os.path.exists(job + ".out") else "TIMEOUT")
res = dict(ln.split("=", 1) for ln in open(os.path.join(b.game.matchday, "result.txt")).read().split()
           if "=" in ln)
hg, ag = int(res["home"]), int(res["away"])
t0 = time.time()
while time.time() - t0 < 60:                                   # the bridge swaps the score in at FM's full time
    live = [c for c in b.writer.copies() if c["date"] == b.writer.date and c["state"]]
    if live and all((c["home_goals"], c["away_goals"]) == (hg, ag) for c in live):
        break
    time.sleep(1)
time.sleep(4)
print(F.skip_match())
t0 = time.time()
while b.busy and time.time() - t0 < 60:
    time.sleep(1)
print("bridge done:", not b.busy)
for c in b.writer.copies():
    if c["date"] == b.writer.date:
        print(f"copy {c['addr']:#x} {c['home_goals']}-{c['away_goals']} state {c['state']:#x} events {b.writer.events_of(c)[1]}")
fm = F.Fm()
fm.click_text("Schedule", region=(0, 0, 0.1, 1), exact=True)
time.sleep(2.5)
fm.read()
p = fm.find("16:00", region=(0.15, 0.25, 0.25, 0.35), exact=True)
if p:
    fm.click(*p)
    time.sleep(2.5)
fm.read()
fm.save("fm_bridge_scorers")
print("saved research/shots/fm_bridge_scorers.png")
