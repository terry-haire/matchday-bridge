"""Elevated end-to-end test of two FM24 match days in a row with the real bridge (lab save: Atlanta v Oldham, then
Birmingham Legion v Oldham). Per match: Pep Talk -> Match Preview -> choice over FM -> Play in SPFL26 -> SPFL26 set
up (first cold, then into the running game) -> wait until FM's background match is at full time (as when a player
takes longer than FM) -> a 2-minute SPFL match (testkit) -> score in FM -> FM's match screen left by the bridge.
Output: research/e2e_two.txt and research/shots/e2e2_*.png"""
import ctypes
import os
import sys
import threading
import time
import tkinter as tk

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
for d in ("testkit", "bridge"):
    sys.path.insert(0, os.path.join(ROOT, d))
import fm as F  # noqa: E402
import spfl  # noqa: E402
from PIL import ImageGrab  # noqa: E402

import matchday_bridge as M  # noqa: E402

OUT = open(os.path.join(ROOT, "research", "e2e_two.txt"), "w", encoding="utf-8")
T0 = time.time()


def log(s):
    line = f"{time.time() - T0:7.1f}s {s}"
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


def snap(tag):
    ImageGrab.grab(all_screens=True).save(os.path.join(ROOT, "research", "shots", f"e2e2_{tag}.png"))


ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
spfl.set_test(match_minutes=2, extra_time=0, penalties=0)
u32 = ctypes.windll.user32
h_fm = u32.FindWindowW(None, "Football Manager 2024")
if h_fm and u32.IsIconic(h_fm):
    u32.ShowWindow(h_fm, 9)                     # a minimized FM can't be captured
F.start()
F.reload()
F.to_match(until="teamtalk")
log("FM on match 1 Pep Talk")
root = tk.Tk()
br = M.Bridge(root)
br.game = next(g for g in br.games if g.key == "spfl26")   # a Football Life job (PES 2021 is games[0])


def one_match(n):
    while "waiting for Match Preview" not in br.view._pill[0]:
        time.sleep(0.5)
    log(f"match {n}: bridge armed for {br.matchday['home']['name']} v {br.matchday['away']['name']}")
    fm = F.Fm()
    end = time.time() + 90
    while not br.choosing and time.time() < end:
        fm.key("space")
        for _ in range(10):
            if br.choosing:
                break
            time.sleep(0.3)
    if not br.choosing:
        raise TimeoutError(f"match {n}: no choice over FM")
    log(f"match {n}: choice shown")
    time.sleep(2)
    snap(f"{n}_choice")
    root.after(0, lambda: br.dialog._play(br.games.index(br.game)))
    t = time.time()
    while br.view.title_var.get() not in ("Your turn", "Pick the teams in Football Life 2026"):
        time.sleep(1)
    log(f"match {n}: SPFL26 ready in {time.time() - t:.0f}s ({br.view.title_var.get()}), live load: {br.live is not None}")
    if br.view.title_var.get() != "Your turn":
        raise RuntimeError(f"match {n}: automatic SPFL26 setup failed: {br.view.detail_var.get()}")
    br.fm_done.wait(1500)
    log(f"match {n}: FM24 at full time (auto-sim ok: {br.fm_ok}); minimizing FM24, playing the SPFL match now")
    ctypes.windll.user32.ShowWindow(ctypes.windll.user32.FindWindowW(None, "Football Manager 2024"), 6)
    s = spfl.Spfl()
    spfl.play_intro(s, time.time())
    spfl.skip_match(to_menu=True)
    res = os.path.join(spfl.MD, "result.txt")
    t_final = os.path.getmtime(res) if "final=1" in open(res).read() else time.time()
    log(f"match {n}: SPFL match over")
    while not br.view.title_var.get().startswith("Saved in FM24"):
        time.sleep(0.5)
        if time.time() - t_final > 600:
            raise TimeoutError("not saved")
    log(f"match {n}: SAVED {time.time() - t_final:.0f}s after SPFL26 wrote its final score | {br.view.title_var.get()}")
    while br.busy:
        time.sleep(1)


def harness():
    try:
        one_match(1)
        time.sleep(5)
        F.to_match(until="teamtalk")
        log("FM on match 2 Pep Talk")
        one_match(2)
        snap("done")
    except Exception as e:  # noqa: BLE001
        log(f"FAILED: {e!r}")
        snap("fail")
    finally:
        spfl.set_test(match_minutes=None)
        root.after(0, root.destroy)


threading.Thread(target=harness, daemon=True).start()
root.mainloop()
log("done")
