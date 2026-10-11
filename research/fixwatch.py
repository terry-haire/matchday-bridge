"""Snapshot every object that holds the (home TEAM*, away TEAM*) pair of a fixture. Usage: fixwatch.py TAG"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct, json
sys.path.insert(0, MDB + r"\bridge")
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at
from fm_reader import FmReader
r = FmReader()
tag = sys.argv[1]
def find_team(name):
    vt = p.vtables(".?AVTEAM@db@@")[0]
    for a in p.find_qword(vt):
        try:
            if r.team(a)["name"] == name and p.u8(a + 0x8) != 0xff: return a
        except Exception: pass
cache = MDB + r"\research\fixwatch_teams.json"
try:
    t = json.load(open(cache)); H, A = int(t["H"], 16), int(t["A"], 16)
    assert r.team(H)["name"] == "Atlanta United FC" and r.team(A)["name"] == "Oldham Athletic"
except Exception:
    cands = {}
    vt = p.vtables(".?AVTEAM@db@@")[0]
    for a in p.find_qword(vt):
        try: nm = r.team(a)["name"]
        except Exception: continue
        if nm in ("Atlanta United FC", "Oldham Athletic"): cands.setdefault(nm, []).append(a)
    print({k: [hex(x) for x in v] for k, v in cands.items()})
    # first team = senior: pick the one referenced by most pairs
    best = None
    for h in cands["Atlanta United FC"]:
        for a in cands["Oldham Athletic"]:
            n = sum(1 for x in p.find_qword(h) if p.try_read(x + 8, 8) == struct.pack("<Q", a))
            if best is None or n > best[0]: best = (n, h, a)
    _, H, A = best
    json.dump({"H": hex(H), "A": hex(A)}, open(cache, "w"))
print("teams", hex(H), hex(A))
out = {}
for x in p.find_qword(H):
    if p.try_read(x + 8, 8) != struct.pack("<Q", A): continue
    owner = None
    for back in range(0, 0x400, 8):
        c = cls_at(x - back)
        if c: owner = (c, x - back); break
    base = owner[1] if owner else x - 0x40
    b = p.try_read(base, 0x200)
    out[hex(x)] = {"owner": owner[0] if owner else None, "base": hex(base), "data": b.hex() if b else None}
json.dump(out, open(MDB + rf"\research\fixwatch_{tag}.json", "w"), indent=0)
from collections import Counter
print(len(out), Counter(v["owner"] for v in out.values()))
