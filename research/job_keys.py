"""Interactive key test: runs the actions in research/keys_todo.txt and logs the screen after each.
Lines: 'key esc' | 'pad START' | 'shot name' | 'wait 1.5' | 'state'"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, time, os
sys.path.insert(0, MDB + r"\testkit")
import spfl, win, pad
SH = MDB + r"\research\shots"
log = spfl.log
pad.ensure()
s = spfl.Spfl()
todo = open(MDB + r"\research\keys_todo.txt").read().splitlines()

def show(tag=""):
    scr, lines = s.screen()
    st = spfl.game_state()
    log(f"{tag:>14} -> {scr:12} p={st.get('period')} {st.get('minute')}:{st.get('second')} paused={st.get('paused')} "
        f"run={st.get('running')} stage={st.get('stage')} | {win.text_of(lines)[:110]!r}")

show("start")
for line in todo:
    if not line.strip() or line.startswith(("#", "!")):
        continue
    op, _, arg = line.strip().partition(" ")
    if op == "key":
        s.press(arg)
    elif op == "pad":
        s.btn(arg)
    elif op == "wait":
        time.sleep(float(arg)); continue
    elif op == "shot":
        s.shot().save(os.path.join(SH, f"k_{arg}.png")); continue
    elif op == "state":
        show("state"); continue
    time.sleep(0.8)
    show(line.strip())
    gone = os.environ.get("UNTIL_GONE") or (todo[0][1:].strip() if todo and todo[0].startswith("!") else "")
    if gone and gone not in win.norm(win.text_of(s.read()[1])):
        log(f"*** '{gone}' gone after: {line.strip()}")
        break
