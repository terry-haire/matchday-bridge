"""Elevated: a Liverpool v Galatasaray match day (research/lfc_gs_starters.json: the save's 26 + 22 names and birth dates on sample attributes) through the real bridge, as a player would: 1 into a freshly
started SPFL26, a 2-minute match, 2 into the running game. Each time the live rosters against the plan and the
pre-match line-ups (OCR: FM24 starters' surnames). Then the team sheet. Report research/faces5.txt, shots
research/shots/faces5_*.png. SPFL26 ends at its main menu, borrowed players restored."""
import ctypes
import os
import subprocess
import sys
import time
import tkinter as tk

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
sys.path.insert(1, os.path.join(ROOT, "testkit"))
import fm_writer  # noqa: E402
import matchday_bridge as mb  # noqa: E402
import spfl  # noqa: E402
import win  # noqa: E402
from fm_reader import FmReader  # noqa: E402
from spfl_drive import fold  # noqa: E402
from spfl_live import live_rosters  # noqa: E402


class NoFm:
    def __init__(self, *a, **k):
        raise RuntimeError("FM24 is not written in this test")


fm_writer.FmResultWriter = NoFm
mb.Bridge.watch = lambda self: None
mb.Bridge._fm_sim = lambda self: None
SHOTS = os.path.join(ROOT, "research", "shots")
OUT = open(os.path.join(ROOT, "research", "faces5.txt"), "w", encoding="utf-8")
T0 = time.time()


def log(s):
    line = f"{time.time() - T0:6.1f}s {s}"
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


def check(n):
    plan = br.plan
    have = live_rosters({plan[s]["spfl_team"] for s in plan})
    ok = all(have.get(plan[s]["spfl_team"]) == plan[s]["ids"] for s in ("home", "away"))
    log(f"  live rosters == plan before the pick: {ok} (SPFL26 rebuilds them from the registered players on the pick)")
    ok = True
    lent = os.path.join(spfl.SIDER, "livecpk", "matchday", "Asset", "model", "character", "face", "real")
    log(f"  lent face folders: {sorted(os.listdir(lent)) if os.path.isdir(lent) else []}")
    s = spfl.Spfl()
    time.sleep(1.0)
    img, lines = s.read()
    img.save(os.path.join(SHOTS, f"faces5_{n}_prematch.png"))
    text = fold(win.text_of(lines))
    for side in ("home", "away"):
        xi = [p["name"].split()[-1] for p in plan[side]["players"] if p["starter"]]
        seen = [x for x in xi if fold(x)[:5] in text]
        log(f"  pre-match {side}: {len(seen)}/{len(xi)} FM24 starters read ({', '.join(seen)})")
        ok &= len(seen) >= 7
    return ok


def run(n):
    state = {"t": time.time()}
    br.matchday = md
    root.after(300, br.play)

    def poll():
        t = br.view.title_var.get()
        if (t in ("Your turn", "Pick the teams in Football Life 2026") and time.time() - state["t"] > 3) or \
                time.time() - state["t"] > 420:
            state["title"] = t
            root.after(300, root.quit)
            return
        root.after(500, poll)

    root.after(1500, poll)
    root.mainloop()
    log(f"run {n}: {state.get('title')} in {time.time() - state['t']:.0f}s | into the running game: {br.live is not None}")
    return state.get("title") == "Your turn" and check(n)


def team_sheet():
    s = spfl.Spfl()
    s.press("RIGHT")                                   # Kick Off -> Game Plan
    time.sleep(0.6)
    s.press("A")
    t = time.time()
    while time.time() - t < 20:
        time.sleep(1)
        scr, lines = s.screen()
        if scr == "teamsheet":
            break
    time.sleep(2)
    s.shot().save(os.path.join(SHOTS, "faces5_teamsheet.png"))
    log(f"team sheet: {scr} after {time.time() - t:.0f}s")
    s.press("B")
    time.sleep(2)
    s.press("LEFT")
    time.sleep(0.6)


def CHECK_FACES():
    """sider.log: which hidden ids were rewritten, and whether SPFL26 still loaded a hidden id's real face."""
    import re
    hidden = set()
    for side in ("home", "away"):
        hidden |= set((br.plan or {}).get(side, {}).get("noface", []))
    text = open(SIDER_LOG, encoding="utf-8", errors="replace").read()
    rewritten = sorted(set(re.findall(r"real face of (\d+) hidden", text)))
    loaded = sorted({m for m in re.findall(r"face\\real\\(\d+)\\", text) if int(m) in hidden})
    log(f"hidden ids {sorted(hidden)} | rewritten by matchday.lua {rewritten} | real face files still loaded for {loaded}")
    log(f"matchday_noface loads: {text.count('matchday_noface')}")


def RESTORE_SPFL():
    import install
    install.clear_match_root(os.path.dirname(spfl.SIDER))
    open(os.path.join(spfl.MD, "request.txt"), "w", encoding="utf-8").write("done=1\n")
    for n in ("test.txt", "result.txt"):
        try:
            os.remove(os.path.join(spfl.MD, n))
        except OSError:
            pass
    log("SPFL26 put back to its own data (match root cleared, request done, test settings removed)")

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
import json
md = json.load(open(os.path.join(ROOT, "research", "lfc_gs_starters.json"), encoding="utf-8"))
log(f"FM24 match day: {md['home']['name']} v {md['away']['name']}")
SIDER_LOG = os.path.join(spfl.SIDER, "sider.log")
for exe in ("FL_2026.exe", "sider.exe"):
    subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True)
time.sleep(3)
spfl.set_test(match_minutes=2, extra_time=0, penalties=0)
root = tk.Tk()
br = mb.Bridge(root)
br.game = next(g for g in br.games if g.key == "spfl26")   # a Football Life job (PES 2021 is games[0])
results = []
try:
    results.append(run(1))
    s = spfl.Spfl()
    spfl.play_intro(s, time.time())
    spfl.skip_match(to_menu=True)
    end = time.time() + 60
    while br.busy and time.time() < end:
        root.update()
        time.sleep(0.5)
    log(f"match 1 over; bridge idle: {not br.busy}")
    results.append(run(2))
    team_sheet()
    s = spfl.Spfl()
    spfl.play_intro(s, time.time())
    time.sleep(2)
    s.shot().save(os.path.join(SHOTS, "faces5_in_play_2.png"))
    spfl.skip_match(to_menu=True)
    log("match 2 over")
finally:
    spfl.set_test(match_minutes=None)
    CHECK_FACES()
    br._restore_live()
    log(f"RESULT {'PASS' if len(results) == 2 and all(results) else 'FAIL'} {results}")
    RESTORE_SPFL()
    root.destroy()
    OUT.close()
