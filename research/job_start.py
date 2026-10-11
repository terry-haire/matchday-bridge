import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, time, os
sys.path.insert(0, MDB + r"\testkit")
import spfl, win, pad
log = spfl.log
T0 = time.time()
s = spfl.start(1)
spfl.to_team_select(s, "away")
spfl.select_teams(s, "Atlanta United FC", "Oldham Athletic", spfl.league_of("Atlanta United FC"), spfl.league_of("Oldham Athletic"))
t_team = time.time()
log(f"teams picked after {t_team - T0:.1f}s")

# find the first Skip prompt and test P, then O
tested = False
end = time.time() + 120
while time.time() < end and not tested:
    scr, lines = s.screen()
    if spfl.has_skip(lines):
        for k in (spfl.START_KEY, spfl.SELECT_KEY):
            s.press(k)
            time.sleep(1.2)
            _, l2 = s.screen()
            log(f"skip prompt -> key {k}: prompt {'GONE' if not spfl.has_skip(l2) else 'still there'} | {win.text_of(l2)[:60]!r}")
            if not spfl.has_skip(l2):
                break
        tested = True
        break
    st = spfl.game_state()
    if not spfl.live(st):
        s.press("enter")
    time.sleep(0.4)
spfl.play_intro(s, t_team)
log(f"kick-off {time.time() - T0:.1f}s after start")
spfl.skip_match(to_menu=False, verbose=True)
log(f"full time {time.time() - T0:.1f}s after start")
t1 = time.time()
spfl.rematch()
spfl.skip_match(to_menu=False, verbose=False)
log(f"rematch to full time {time.time() - t1:.1f}s")
