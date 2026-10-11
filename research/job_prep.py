import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import os, subprocess, sys, time, json, datetime
sys.path.insert(0, MDB + r"\bridge")
import install
from spfl_db import PesDb
from spfl_build import MatchBuilder, request_lines
g = install.find_spfl26()
for name in ("FL_2026.exe", "sider.exe"):
    subprocess.run(["taskkill", "/F", "/IM", name], capture_output=True)
time.sleep(4)
install.install_spfl(g)
install.clear_match_root(g)
db = PesDb.load(g, [os.path.join(g, "SiderAddons", "livecpk", "root")])
md = json.load(open(MDB + r"\tests\sample_matchday.json", encoding="utf-8"))
b = MatchBuilder(db); plan = b.build(md, datetime.date(2032, 7, 10))
b.write_root(os.path.join(g, "SiderAddons", "livecpk", "matchday"))
open(os.path.join(g, "SiderAddons", "matchday", "request.txt"), "w", encoding="utf-8").write(
    request_lines(md, plan, "Friendly", "10 Jul 2032"))
print("prepared")
