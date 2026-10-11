import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, time, os
sys.path.insert(0, MDB + r"\testkit")
import spfl, win, pad
from PIL import ImageChops, ImageStat
FILM = MDB + r"\research\shots\film"
os.makedirs(FILM, exist_ok=True)
for f in os.listdir(FILM):
    os.remove(os.path.join(FILM, f))
log = spfl.log
s = spfl.Spfl()
n = 0
T0 = time.time()

def film(tag):
    global n
    n += 1
    img = s.shot().convert("RGB").resize((480, 270))
    st = spfl.game_state()
    img.save(os.path.join(FILM, f"{n:03d}_{int(time.time()-T0):03d}s_{tag}.jpg"), quality=70)
    return img, st

def diff(a, b):
    return round(sum(ImageStat.Stat(ImageChops.difference(a, b).convert("L")).mean), 1)

def do(inp):
    if inp == "enter":
        s.press("enter")
    else:
        s.btn(inp)

# 1) back to the pre-match screen: highlights/fulltime -> Rematch
for _ in range(40):
    scr, lines = s.screen()
    if scr == "prematch":
        break
    log("screen", scr, "| ", win.text_of(lines)[:100].replace("\n", " / "))
    s.press("enter")
    time.sleep(1.0)
log("prematch")
s.advance("enter", "prematch", 20)
t_ko = time.time()

# 2) intro: 20 s no input, then pad A, pad START, pad B, keyboard Enter (10 s each), filming the effect
plan = [(None, 20), ("A", 10), ("START", 10), ("B", 10), ("enter", 30), ("A", 30)]
for inp, dur in plan:
    end = time.time() + dur
    while time.time() < end:
        st = spfl.game_state()
        if st.get("ptr", "0") not in ("0", "") and st.get("running") == "1":
            break
        a, st = film(f"intro_{inp}")
        if inp:
            do(inp)
            time.sleep(0.6)
            b, _ = film(f"after_{inp}")
            log(f"intro {inp}: diff {diff(a, b)} ptr={st.get('ptr')} stage={st.get('stage')} paused={st.get('paused')}")
        time.sleep(1.2)
    else:
        continue
    break
log(f"ball in play {time.time() - t_ko:.1f}s after Kick Off", spfl.game_state())

# 3) match: film every stall; paused=0 -> pad A; paused=1 -> rotate inputs
moved, last, k = time.time(), None, 0
rot = ["A", "START", "enter", "B"]
while time.time() - T0 < 600:
    st = spfl.game_state()
    c = (st.get("period"), st.get("minute"), st.get("second"))
    if c != last:
        last, moved = c, time.time()
    if time.time() - moved < 0.8:
        time.sleep(0.1)
        continue
    scr, lines = s.screen()
    if scr == "fulltime":
        log("FULL TIME", st); break
    if scr in ("halftime", "highlights", "fulltimestats"):
        film(scr)
        log("menu", scr, "-> enter"); s.press("enter"); time.sleep(0.5); moved = time.time(); continue
    a, st = film(f"stall_p{st.get('paused')}_r{st.get('running')}_s{st.get('stage')}")
    inp = "A" if st.get("paused") == "0" else rot[k % len(rot)]
    k += 1 if st.get("paused") == "1" else 0
    do(inp)
    time.sleep(0.6)
    b, st2 = film(f"after_{inp}")
    log(f"stall {scr} period={st.get('period')} {st.get('minute')}:{st.get('second')} paused={st.get('paused')} "
        f"running={st.get('running')} stage={st.get('stage')} -> {inp}: diff {diff(a, b)} -> paused={st2.get('paused')} "
        f"running={st2.get('running')} stage={st2.get('stage')} | {win.text_of(lines)[:60]!r}")
    moved = time.time() - 0.3
log("end", spfl.game_state(), f"{time.time() - T0:.1f}s")
