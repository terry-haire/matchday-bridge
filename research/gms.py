import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, struct
sys.path.insert(0, MDB + r"\bridge")
sys.path.insert(0, MDB + r"\research")
from fmdump import p, cls_at, label
from fm_reader import FmReader
r = FmReader()
gms = p.find_qword(r.vt_game_match)
print("GAME_MATCH count", len(gms))
for gm in gms:
    try:
        ht, h = r.roster(gm, 0xcea8); at, a = r.roster(gm, 0xcf38)
        print(hex(gm), ht.get("name"), "v", at.get("name"), len(h), len(a), "teamptrs", hex(ht.get("team_ptr") or 0), hex(at.get("team_ptr") or 0))
    except Exception as e:
        print(hex(gm), "err", e)
mt = p.find_qword(p.vtables(".?AVMATCH@simatch@@")[0])
print("MATCH", [hex(x) for x in mt])
for m in mt:
    refs = p.find_qword(m)
    for x in refs:
        for gm in gms:
            if gm <= x < gm + 0x40000: print("  MATCH ref inside GAME_MATCH", hex(gm), "+", hex(x - gm))
hum = p.find_qword(p.vtables(".?AVHUMAN_NON_PLAYER@db@@")[0])
print("HUMAN_NON_PLAYER", [hex(x) for x in hum])
for h in hum[:3]:
    b = p.read(h, 0x400)
    for o in range(0, 0x400, 8):
        q = struct.unpack_from("<Q", b, o)[0]
        lb = label(q)
        if "CLUB" in lb or "TEAM" in lb or "JOB" in lb or "CONTRACT" in lb:
            print("   +", hex(o), lb, hex(q))
