"""Elevated: SPFL26's scoreboard after a bridge match ends (Rematch) and the restore before the next match.
1 cold: Birmingham v Oldham (slots 199/200) to full time, back to the menu.
2 hot: Atlanta v Oldham (199) to full time, then SPFL26's Rematch: the scoreboard must still say OLD (it said ZLG when
  matchday.lua restored the slot at the end of the match).
3 hot: Birmingham v Oldham again: the bridge restores match 2's players first (Atlanta's own SPFL26 players back),
  matchday.lua the team records, then BIR / OLD.
FM24 is not used. Report research/rematch.txt, scoreboard crops research/shots/rematch_*.png. Run detached (>30 min
possible): job_rematch_detached.py."""
import ctypes
import json
import os
import struct
import subprocess
import sys
import threading
import time
import tkinter as tk

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
sys.path.insert(1, os.path.join(ROOT, "testkit"))
import fm_writer  # noqa: E402
import matchday_bridge as mb  # noqa: E402
import spfl  # noqa: E402
import win  # noqa: E402
from gen_structs import SPFL_EDIT_BLOCK as EB, SPFL_LIVE_PLAYER as LP  # noqa: E402
from procmem import Proc  # noqa: E402


class NoFm:
    def __init__(self, *a, **k):
        raise RuntimeError("FM24 not used in this test")


fm_writer.FmResultWriter = NoFm
mb.Bridge.watch = lambda self: None
mb.Bridge._fm_sim = lambda self: None
CLUB_IDS = {"Oldham Athletic": 694, "Atlanta United FC": 72047296, "Birmingham Legion": 20046409}
SHORT = {"Oldham Athletic": "Oldham", "Atlanta United FC": "Atlanta", "Birmingham Legion": "Birmingham"}
SHOTS = os.path.join(ROOT, "research", "shots")
OUT = open(os.path.join(ROOT, "research", "rematch.txt"), "w", encoding="utf-8")
T0 = time.time()
BRIDGE_LOG = os.path.join(os.environ["LOCALAPPDATA"], "MatchdayBridge", "bridge.log")
SIDER_LOG = os.path.join(spfl.SIDER, "sider.log")


def log(s):
    line = f"{time.time() - T0:7.1f}s {s}"
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


def edit_teams(tids):
    p = Proc("FL_2026.exe")
    try:
        blk = p.u64(p.u64(EB.OWNER_GLOBAL) + 0x48)
        n = p.u32(blk + EB.TEAM_COUNT)
        raw = p.read(blk + EB.TEAMS, n * 0x690)
        out = {}
        for i in range(n):
            tid = (struct.unpack_from("<I", raw, i * 0x690)[0] >> 14) & 0x1ffff
            if tid in tids:
                r = raw[i * 0x690:(i + 1) * 0x690]
                out[tid] = (r[4:0x4a].split(b"\x00")[0].decode("utf-8", "replace"),
                            r[0x4a:0x4d].split(b"\x00")[0].decode())
        return out
    finally:
        p.close()


def live_names(pids):
    p = Proc("FL_2026.exe")
    try:
        blk = p.u64(p.u64(EB.OWNER_GLOBAL) + 0x48)
        n = p.u32(blk + EB.PLAYER_COUNT)
        raw = p.read(blk, n * LP.STRIDE)
        want, out = set(pids), {}
        for i in range(n):
            pid = struct.unpack_from("<I", raw, i * LP.STRIDE + LP.PLAYER_ID)[0]
            if pid in want:
                out[pid] = raw[i * LP.STRIDE + LP.NAMES:i * LP.STRIDE + LP.NAMES + 0x3d].split(b"\x00")[0].decode(
                    "utf-8", "replace")
        return out
    finally:
        p.close()


def scoreboard(tag):
    s = spfl.Spfl()
    words = []
    for k in range(4):
        img = s.shot()
        box = img.crop((int(img.width * 0.04), int(img.height * 0.05), int(img.width * 0.2), int(img.height * 0.15)))
        box.save(os.path.join(SHOTS, f"rematch_{tag}_{k}.png"))
        words.append(win.text_of(win.ocr(box, scale=3.0)).replace("\n", " "))
        time.sleep(1.5)
    img.save(os.path.join(SHOTS, f"rematch_{tag}_full.png"))
    log(f"{tag}: scoreboard OCR {words}")
    return words


def tail(path, since_marker):
    text = open(path, encoding="utf-8", errors="replace").read()
    i = text.rfind(since_marker)
    return text[i:] if i >= 0 else ""


def md_for(home, away):
    md = json.load(open(os.path.join(ROOT, "tests", "sample_matchday.json"), encoding="utf-8"))
    return {**md,
            "home": {**md["home"], "name": home, "short": SHORT[home], "human": False, "club_id": CLUB_IDS[home]},
            "away": {**md["away"], "name": away, "short": SHORT[away], "human": True, "club_id": CLUB_IDS[away]}}


def setup(n, home, away):
    while br.busy:
        time.sleep(1)
    br.matchday = md_for(home, away)
    t = time.time()
    root.after(0, br.play)
    time.sleep(3)
    while br.view.title_var.get() not in ("Your turn", "Pick the teams in SPFL26"):
        time.sleep(1)
        if time.time() - t > 400:
            raise TimeoutError(f"match {n}: SPFL26 not ready")
    plan = br.plan
    log(f"match {n}: {home} v {away} ready in {time.time() - t:.0f}s ({br.view.title_var.get()}), live load: "
        f"{br.live is not None}, slots {plan['home']['spfl_team']}/{plan['away']['spfl_team']}")
    if br.view.title_var.get() != "Your turn":
        raise RuntimeError(f"match {n}: automatic setup failed: {br.view.detail_var.get()}")
    log(f"match {n}: edit data {edit_teams({plan['home']['spfl_team'], plan['away']['spfl_team']})}")
    return plan


def harness():
    ok = True
    try:
        for exe in ("FL_2026.exe", "sider.exe"):
            subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True)
        time.sleep(3)
        setup(1, "Birmingham Legion", "Oldham Athletic")
        s = spfl.Spfl()
        spfl.play_intro(s, time.time())
        scoreboard("m1")
        spfl.skip_match(to_menu=True)
        log("match 1 over")

        plan2 = setup(2, "Atlanta United FC", "Oldham Athletic")
        atl = [(p["spfl_id"], p["name"]) for p in plan2["home"]["players"]][:6]
        log(f"match 2: Atlanta records now {live_names([a for a, _ in atl])}")
        s = spfl.Spfl()
        spfl.play_intro(s, time.time())
        scoreboard("m2")
        spfl.skip_match(to_menu=False)
        log("match 2 full time; Rematch")
        spfl.rematch()
        time.sleep(2)
        w2r = scoreboard("m2_rematch")
        log(f"match 2 rematch: edit data {edit_teams({5736, 199})}")
        ok &= any("OLD" in w for w in w2r) and not any("ZLG" in w for w in w2r)
        spfl.skip_match(to_menu=True)
        log("rematch over")

        plan3 = setup(3, "Birmingham Legion", "Oldham Athletic")
        del plan3
        restored = live_names([a for a, _ in atl])
        log(f"match 3: match 2's Atlanta records now {restored} (FM24 names were {dict(atl)})")
        ok &= all(restored.get(a) != nm for a, nm in atl)
        blog = [ln for ln in open(BRIDGE_LOG, encoding="utf-8", errors="replace").read().splitlines()[-40:]
                if "restored" in ln or "wrote" in ln]
        log(f"match 3: bridge.log {blog}")
        slog = [ln for ln in tail(SIDER_LOG, "new FM24 fixture Birmingham").splitlines() if "matchday:" in ln][:6]
        log(f"match 3: sider.log {slog}")
        s = spfl.Spfl()
        spfl.play_intro(s, time.time())
        w3 = scoreboard("m3")
        ok &= any("BIR" in w for w in w3) and any("OLD" in w for w in w3)
        spfl.skip_match(to_menu=True)
        log(f"RESULT {'PASS' if ok else 'FAIL'}")
    except Exception as e:  # noqa: BLE001
        log(f"FAILED: {e!r}")
    finally:
        spfl.set_test(match_minutes=None)
        root.after(0, root.destroy)


ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
spfl.set_test(match_minutes=2, extra_time=0, penalties=0)
root = tk.Tk()
br = mb.Bridge(root)
threading.Thread(target=harness, daemon=True).start()
root.mainloop()
log("done")
OUT.close()
