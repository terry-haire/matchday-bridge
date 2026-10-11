"""Elevated research: the Select Team list widgets via matchday.lua's cursor-store cave.
Starts SPFL26 (testkit), goes to Select Team, presses DOWN in the home league list and dumps the moved widget: its
league vector (0x70 per entry) and each league's team vector (0x50 per entry) -> research/selprobe.json. Then A
(league confirmed) + DOWN in the team list, and DOWN in the away league list after the home club is confirmed."""
import json
import os
import shutil
import struct
import sys
import time

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
sys.path.insert(1, os.path.join(ROOT, "testkit"))
import spfl  # noqa: E402
from procmem import Proc  # noqa: E402

shutil.copy2(os.path.join(ROOT, "spfl", "modules", "matchday.lua"), os.path.join(spfl.SIDER, "modules", "matchday.lua"))
s = spfl.start(match_minutes=None)
spfl.to_team_select(s, "away")
time.sleep(1.5)
hooks = spfl.read_kv(os.path.join(spfl.MD, "hooks.txt"))
print("hooks.txt", hooks)
cave = int(hooks["select_cave"], 16)
p = Proc("FL_2026.exe", write=True)
out = {"cave": cave}


def moved(button):
    n0 = p.u32(cave + 100)
    s.press(button)
    end = time.time() + 3
    while p.u32(cave + 100) == n0 and time.time() < end:
        time.sleep(0.02)
    time.sleep(0.4)
    return {"moves": p.u32(cave + 100) - n0, "list": p.u64(cave + 72), "cell": p.u64(cave + 80)}


def widget(w, items=True):
    d = {"addr": w, "head": p.read(w + 0x80, 0xb0).hex(), "mode_9b": p.u8(w + 0x9b),
         "i118": p.u32(w + 0x118), "i11c": p.u32(w + 0x11c)}
    b, e = p.u64(w + 0x100), p.u64(w + 0x108)
    d["n"] = (e - b) // 0x70
    d["entries"] = []
    for i in range(min(d["n"], 64)):
        a = b + i * 0x70
        raw = p.read(a, 0x70)
        ib, ie = struct.unpack_from("<QQ", raw, 8)
        ent = {"addr": a, "raw": raw.hex(), "n": (ie - ib) // 0x50 if ie >= ib else -1,
               "i64": struct.unpack_from("<I", raw, 0x64)[0], "i68": struct.unpack_from("<I", raw, 0x68)[0]}
        if items and 0 <= ent["n"] <= 200:
            ent["items"] = [p.read(ib + k * 0x50, 0x50).hex() for k in range(ent["n"])]
        d["entries"].append(ent)
    return d


def col(side):
    return spfl.column(s, side)


out["home_league_col_before"] = col("home")
m = moved("DOWN")
out["home_league_move"] = m
out["home_league_col"] = col("home")
out["home_widget"] = widget(m["list"])
print("home league move", m, "n leagues", out["home_widget"]["n"], "i118", out["home_widget"]["i118"])
s.press("A")
time.sleep(1.0)
m2 = moved("DOWN")
out["home_team_move"] = m2
out["home_team_col"] = col("home")
out["home_widget_after"] = widget(m2["list"], items=False)
print("home team move", m2, "mode", out["home_widget_after"]["mode_9b"])
s.press("A")
time.sleep(1.0)
m3 = moved("DOWN")
out["away_league_move"] = m3
out["away_league_col"] = col("away")
out["away_widget"] = widget(m3["list"], items=False)
print("away league move", m3)
json.dump(out, open(os.path.join(ROOT, "research", "selprobe.json"), "w"), indent=1)
s.shot().save(os.path.join(ROOT, "research", "shots", "selprobe.png"))
print("cols", out["home_league_col"], out["home_team_col"], out["away_league_col"])
