import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import sys, json
sys.path.insert(0, MDB + r"\research")
from fmx import p
tag = sys.argv[1]
gm = int(sys.argv[2], 16)
c = json.load(open(MDB + r"\research\census_teamnews.json"))["instances"]
out = {"gm": p.try_read(gm, 0x40000) or b""}
mps = [int(x,16) for x in c["MATCH_PLAYER@simatch"]]
blob = b"".join((p.try_read(m, 0x1880) or b"\0"*0x1880) for m in mps)
import pickle
pickle.dump({"gm_addr": gm, "gm": out["gm"], "mps": mps, "mpblob": blob}, open(MDB + rf"\research\dumps_snap_{tag}.pkl","wb"))
print("snap", tag, len(out["gm"]), len(blob))
