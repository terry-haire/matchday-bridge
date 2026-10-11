"""Read-only: every played FIXTURE_RESULT in FM24's memory -> event type census, and for fixtures with type-1
events, whether the event's side is the side the goal counted for (score check). Output: research/og_census.txt"""
import os
import struct
import sys
from collections import Counter

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
from gen_structs import FIXTURE, FIXTURE_RESULT  # noqa: E402
from procmem import Proc  # noqa: E402

p = Proc("fm.exe")
vt = p.vtables(".?AVFIXTURE_RESULT@sicomps@@")[0]
objs = p.find_qword(vt, limit=400000)
types, checked, ok_benefit, ok_player = Counter(), 0, 0, 0
samples = []
seen = set()
for base in objs:
    b = p.try_read(base, FIXTURE_RESULT.STATE + 4)
    if not b:
        continue
    home, away = struct.unpack_from("<QQ", b, 8)
    key = (home, away, struct.unpack_from("<I", b, FIXTURE.DATE)[0])
    if key in seen or not b[FIXTURE_RESULT.STATE]:
        continue
    seen.add(key)
    hg, ag = b[FIXTURE_RESULT.HOME_GOALS], b[FIXTURE_RESULT.AWAY_GOALS]
    vec = p.u64(base + FIXTURE_RESULT.EVENTS)
    if not vec:
        continue
    try:
        beg, end, cap = struct.unpack_from("<QQQ", p.read(vec, 24))
        if not beg or not beg <= end <= cap or end - beg > 0x800:
            continue
        d = p.read(beg, end - beg) if end > beg else b""
    except OSError:
        continue
    ev = [struct.unpack_from("<IBBH", d, i) for i in range(0, len(d) - 7, 8)]
    for e in ev:
        types[e[2]] += 1
    if any(e[2] == 1 for e in ev):
        checked += 1
        # side = team the goal counted for?
        b0 = sum(1 for e in ev if e[2] in (0, 1, 2) and e[1] == 0)
        b1 = sum(1 for e in ev if e[2] in (0, 1, 2) and e[1] == 1)
        # side = the player's own team (own goals count for the other side)?
        p0 = sum(1 for e in ev if (e[2] in (0, 2) and e[1] == 0) or (e[2] == 1 and e[1] == 1))
        p1 = sum(1 for e in ev if (e[2] in (0, 2) and e[1] == 1) or (e[2] == 1 and e[1] == 0))
        ok_benefit += (b0, b1) == (hg, ag)
        ok_player += (p0, p1) == (hg, ag)
        if len(samples) < 12:
            samples.append(f"{hg}-{ag} events {ev}")
out = open(os.path.join(ROOT, "research", "og_census.txt"), "w", encoding="utf-8")
out.write(f"{len(objs)} FIXTURE_RESULT objects, {len(seen)} played fixtures\ntypes {dict(types)}\n")
out.write(f"fixtures with type 1: {checked}; score matches if side = team credited: {ok_benefit}; "
          f"if side = player's own team: {ok_player}\n")
out.write("\n".join(samples) + "\n")
out.close()
print(open(os.path.join(ROOT, "research", "og_census.txt"), encoding="utf-8").read())
