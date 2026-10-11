import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, time, os
sys.path.insert(0, MDB + r"\testkit")
import spfl, win, pad
SH = MDB + r"\research\shots"
log = spfl.log

s = spfl.Spfl()
if s.screen()[0] != "teams":
    s = spfl.start(1)
    spfl.to_team_select(s, "away")
s.shot().save(os.path.join(SH, "probe_teams.png"))
spfl.select_teams(s, "Atlanta United FC", "Oldham Athletic", spfl.league_of("Atlanta United FC"), spfl.league_of("Oldham Athletic"))

KEYS = ("ptr", "period", "minute", "second", "paused", "running", "stage", "home", "away")
def st():
    g = spfl.game_state()
    return {k: g.get(k) for k in KEYS}

t0 = time.time()
shots = set()
last_sig, last_clock, moved = None, None, time.time()
tries = 0
order = ["padA", "padA", "padB", "padSTART", "enter"]
while time.time() - t0 < 480:
    g = st()
    sig = (g["ptr"] != "0", g["period"], g["paused"], g["running"], g["stage"])
    if sig != last_sig:
        log("state", g)
        last_sig = sig
    c = (g["minute"], g["second"])
    if c != last_clock:
        last_clock, moved = c, time.time()
        if tries:
            log(f"  clock moving again after {tries} press(es), last={order[min(tries, len(order)) - 1]}")
        tries = 0
    if time.time() - moved > 1.2:
        scr, lines = s.screen()
        if scr == "fulltime":
            log("FULL TIME", g); break
        if scr in ("teams", "prematch", "halftime", "highlights", "fulltimestats", "sides"):
            log("menu", scr, "-> enter"); s.press("enter"); time.sleep(0.6); moved = time.time(); continue
        key = (scr, g["stage"], g["paused"], g["running"])
        if key not in shots:
            shots.add(key)
            fn = f"probe_stall_{len(shots)}_{scr}_{g['stage']}.png"
            s.shot().save(os.path.join(SH, fn))
            log("stall", key, "shot", fn, "|", win.text_of(lines)[:120].replace("\n", " / "))
        how = order[min(tries, len(order) - 1)]
        tries += 1
        log("  press", how)
        if how == "enter":
            s.press("enter")
        else:
            s.btn(how[3:])
        moved = time.time() - 0.2   # re-evaluate ~1 s later
    time.sleep(0.1)
log("end", st(), f"{time.time() - t0:.1f}s")
