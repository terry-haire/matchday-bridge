"""Scan SPFL26's Select Team league list (home column) and the teams of a few leagues -> research/leaguescan.txt"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, time, os
sys.path.insert(0, MDB + r"\testkit")
import spfl, win
OUT = MDB + r"\research\leaguescan.txt"
f = open(OUT, "w", encoding="utf-8")


def out(*a):
    s = " ".join(str(x) for x in a)
    spfl.log(s)
    f.write(s + "\n")
    f.flush()


def scan(s, side, limit=140):
    seen, first, last = [], None, None
    for _ in range(limit):
        col = spfl.column(s, side)
        c = dict(col).get(0, "")
        if c and c == first and len(seen) > 2:
            out("  (wrapped)")
            break
        if c == last:
            out("  (end)")
            break
        if first is None:
            first = c
        seen.append(c)
        out(f"  {len(seen):3} {c}   | {[n for o, n in col if o != 0]}")
        last = c
        s.press("down")
        time.sleep(0.25)
    return seen


s = spfl.start(None)
spfl.to_team_select(s, "home")
time.sleep(1)
scr, lines = s.screen()
out("screen", scr, win.text_of(lines)[:300])
s.shot().save(MDB + r"\research\shots\teamselect.png")
out("LEAGUES (home column)")
leagues = scan(s, "home")
for lg in ("Other European Leagues", "Major League Soccer"):
    spfl.pick(s, "home", lg, "league")
    s.press("enter")
    time.sleep(0.8)
    s.shot().save(MDB + r"\research\shots\teamselect_%s.png" % lg.split()[0])
    out("TEAMS of", lg)
    scan(s, "home", 60)
    s.press("B")
    time.sleep(0.8)
out("done")
