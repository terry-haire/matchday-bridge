import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, time, os, threading, ctypes
sys.path.insert(0, MDB + r"\testkit")
import spfl, win, pad
log = spfl.log
u = ctypes.windll.user32

steals = []
stop = False


def watch():
    """Record every time the game window is the foreground window (it should never be, after start)."""
    was = False
    while not stop:
        try:
            h = win.find_window(spfl.TITLE)
            fg = u.GetForegroundWindow() == h
        except RuntimeError:
            fg = False
        if fg and not was:
            steals.append(time.strftime("%H:%M:%S"))
        was = fg
        time.sleep(0.05)


T0 = time.time()
s = spfl.start(1)
threading.Thread(target=watch, daemon=True).start()
st = pad.shm()
log(f"pad polled={pad.polled()} pid={st.pid} real pad in slot 0={bool(st.real_ok)} game foreground={win.is_foreground(s.h)}")
spfl.to_team_select(s, "away")
spfl.select_teams(s, "Atlanta United FC", "Oldham Athletic", spfl.league_of("Atlanta United FC"), spfl.league_of("Oldham Athletic"))
t_team = time.time()
log(f"teams picked after {t_team - T0:.1f}s")
spfl.play_intro(s, t_team, verbose=True)
log(f"kick-off {time.time() - T0:.1f}s after start")
t1 = time.time()
spfl.skip_match(to_menu=False, verbose=True)
log(f"match skipped in {time.time() - t1:.1f}s")
t1 = time.time()
spfl.rematch()
spfl.skip_match(to_menu=False, verbose=False)
log(f"rematch to full time {time.time() - t1:.1f}s")
stop = True
log(f"game window became foreground after start: {steals or 'never'}")
for ln in open(os.path.join(spfl.SIDER, "sider.log"), encoding="utf-8", errors="replace"):
    if "matchday_test:" in ln:
        log("sider:", ln.strip())
log("state:", spfl.game_state())
