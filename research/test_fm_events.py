"""Test the FM writer on the lab save: play FM's match to full time, write a made-up SPFL result with MORE
events than FM produced (forces the remote-malloc path), leave the match, then read back what FM saved.

    python research/test_fm_events.py
"""
import os
import struct
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for d in ("testkit", "bridge"):
    sys.path.insert(0, os.path.join(ROOT, d))
import fm as F  # noqa: E402
from fm_reader import FmReader  # noqa: E402
from fm_writer import EV_GOAL, EV_PENALTY, EV_RED, FmResultWriter  # noqa: E402

if "--here" not in sys.argv:
    F.reload()
    F.to_match()
r = FmReader()
gm = r.find_game_match()
teams = r.side_teams(gm)
pid = {}
side_of = {}
for mp in r.match_players(gm):
    ap = r.complete_object(r.p.u64(mp + 0x28))
    if ap and r.p.u64(ap) == r.vt_actual_player:
        n = r.fm_string(r.p.u64(mp + 0x30))
        pid[n] = r.p.u32(ap + 0x280)
        side_of[n] = 0 if r.player_team(mp) == teams[0] else 1
home_players = [n for n, s in side_of.items() if s == 0]
print("home players with a person id:", home_players[:5])
w = FmResultWriter(teams[0], teams[1])
print("locked fixture date", hex(w.lock_fixture() or 0))
F.to_full_time()
fm_ev = w.fm_events()
print("FM's own events:", fm_ev)
S, T, H, N = pid["Agostinho Santos"], pid["Marc Cucurella"], pid[home_players[0]], pid[home_players[-1]]
events = [(S, 1, EV_GOAL, 5), (N, 0, EV_PENALTY, 12), (S, 1, EV_GOAL, 23), (T, 1, EV_RED, 40),
          (S, 1, EV_GOAL, 61), (S, 1, EV_GOAL, 70), (N, 0, EV_GOAL, 77), (S, 1, EV_GOAL, 88)]
home, away = 2, 5
print("score:", w.apply(home, away))
print("events:", w.apply_events(events))
runs = w.live_stats(set(pid.values()), fm_ev)
print("live stat runs:", [hex(r_[0]) for r_ in runs])
print("player stats:", w.apply_player_stats(runs, {S: 5, N: 2}, {H: 1, T: 1}))
time.sleep(0.5)
print(F.skip_match())
time.sleep(2)
for c in w.copies():
    if c["date"] == w.date:
        print(f"copy {c['addr']:#x} {c['home_goals']}-{c['away_goals']} state {c['state']:#x}", w.events_of(c)[1] == events)
fm = F.Fm()
fm.click_text("Schedule", region=(0, 0, 0.1, 1), exact=True)
time.sleep(2.5)
fm.read()
p = fm.find("16:00", region=(0.15, 0.25, 0.25, 0.35), exact=True)
if p:
    fm.click(*p)
    time.sleep(2)
fm.read()
fm.save("fm_events_test")
print("saved research/shots/fm_events_test.png")
