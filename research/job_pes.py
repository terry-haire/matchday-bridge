"""The real Bridge._play/_drive in PES 2021 with a sample match day (FM24 not read or written, FM's background match
off): python research/job_pes.py HOME AWAY [GAME]. GAME: pes2021 (default) or spfl26. Logs the plan, whether the game
was restarted or loaded live and the time to the pre-match screen -> research/pes_<home>.txt; game screenshots in
%LOCALAPPDATA%\\MatchdayBridge\\last_match (copied to research/shots/pes_<home>_*.png)."""
import ctypes
import json
import os
import shutil
import sys
import time
import tkinter as tk

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
import fm_writer  # noqa: E402
import matchday_bridge as mb  # noqa: E402


class NoFm:
    def __init__(self, *a, **k):
        raise RuntimeError("FM24 not used in this test")


fm_writer.FmResultWriter = NoFm
mb.Bridge.watch = lambda self: None
mb.Bridge._fm_sim = lambda self: None
HOME, AWAY = sys.argv[1], sys.argv[2]
GAME = sys.argv[3] if len(sys.argv) > 3 else "pes2021"
CLUB_IDS = {"Oldham Athletic": 694, "Atlanta United FC": 72047296}
TAG = HOME.split()[0].lower()
OUT = open(os.path.join(ROOT, "research", f"pes_{TAG}.txt"), "w", encoding="utf-8")
T0 = time.time()


def log(s):
    OUT.write(f"{time.time() - T0:6.1f}s {s}\n")
    OUT.flush()


ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
root = tk.Tk()
br = mb.Bridge(root)
md = json.load(open(os.path.join(ROOT, "tests", "sample_matchday.json"), encoding="utf-8"))
md = {**md, "home": {**md["home"], "name": HOME, "short": HOME.split()[0], "human": False,
                     "club_id": CLUB_IDS.get(HOME)},
      "away": {**md["away"], "name": AWAY, "short": AWAY.split()[0], "human": True, "club_id": CLUB_IDS.get(AWAY)}}
br.matchday = md
game = next(i for i, g in enumerate(br.games) if g.key == GAME)
log(f"games {[g.short for g in br.games]}; playing in {br.games[game].name}; running before: "
    f"{mb.is_running(br.games[game].exe)}")
root.after(500, lambda: br.choose(game))


def poll():
    t = br.view.title_var.get()
    if t == "Your turn" or t.startswith(("Pick the teams in", "Could not build")) or time.time() - T0 > 420:
        log(f"{t} | {br.view.body_var.get()[:160]} | {br.view.detail_var.get()[:160]}")
        log(f"loaded live: {getattr(br, 'live', None) is not None}")
        if br.plan:
            for s in ("home", "away"):
                p = br.plan[s]
                log(f"{s}: {p['fm_name']} -> team {p['spfl_team']} {p['spfl_name']!r} (slot of {p.get('slot_name')!r}), "
                    f"{len(p['ids'])} players, noface {len(p['noface'])}")
        shots = os.path.join(os.environ["LOCALAPPDATA"], "MatchdayBridge", "last_match")
        for n in os.listdir(shots) if os.path.isdir(shots) else []:
            shutil.copy2(os.path.join(shots, n), os.path.join(ROOT, "research", "shots", f"pes_{TAG}_{n}"))
        root.after(500, root.destroy)
        return
    root.after(500, poll)


root.after(1000, poll)
root.mainloop()
OUT.close()
print(open(os.path.join(ROOT, "research", f"pes_{TAG}.txt"), encoding="utf-8").read())
