"""Elevated end-to-end test of the real bridge: FM lab save -> Pep Talk -> Match Preview -> the choice over FM
(Play in SPFL26) -> SPFL26 set up by the bridge while FM24 sims -> a 2-minute SPFL match (testkit) -> score and
scorers written at FM's full time, FM's match screen left by the bridge. Output: research/e2e_fm.txt and
research/shots/e2e_*.png"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import ctypes
import os
import sys
import threading
import time
import tkinter as tk

ROOT = MDB
for d in ("testkit", "bridge"):
    sys.path.insert(0, os.path.join(ROOT, d))
import fm as F  # noqa: E402
import spfl  # noqa: E402
from PIL import ImageGrab  # noqa: E402

import matchday_bridge as M  # noqa: E402

OUT = open(os.path.join(ROOT, "research", "e2e_fm.txt"), "w", encoding="utf-8")
T0 = time.time()


def log(s):
    line = f"{time.time() - T0:7.1f}s {s}"
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


def snap(tag):
    ImageGrab.grab(all_screens=True).save(os.path.join(ROOT, "research", "shots", f"e2e_{tag}.png"))


ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
spfl.set_test(match_minutes=2, extra_time=0, penalties=0)
F.reload()
F.to_match(until="teamtalk")
log("FM on Pep Talk")

root = tk.Tk()
br = M.Bridge(root)
br.game = next(g for g in br.games if g.key == "spfl26")   # a Football Life job (PES 2021 is games[0])
state = {"phase": "wait-arm"}


def harness():
    try:
        while "waiting for Match Preview" not in br.view._pill[0]:
            time.sleep(0.5)
            if time.time() - T0 > 240:
                raise TimeoutError("bridge never armed")
        log("bridge armed; pressing Match Preview in FM")
        fm = F.Fm()
        end = time.time() + 60
        while not br.choosing and time.time() < end:
            fm.key("space")
            for _ in range(10):
                if br.choosing:
                    break
                time.sleep(0.3)
        if not br.choosing:
            raise TimeoutError("no choice dialog")
        log(f"choice dialog open; FM input enabled = {bool(ctypes.windll.user32.IsWindowEnabled(br.fm_ui.h))}")
        time.sleep(2)
        snap("1_choice")
        root.after(0, lambda: br.dialog._play(br.games.index(br.game)))
        while br.view.title_var.get() not in ("Your turn", "Pick the teams in Football Life 2026"):
            time.sleep(1)
            if time.time() - T0 > 900:
                raise TimeoutError("SPFL setup did not finish")
        log(f"SPFL setup: {br.view.title_var.get()} | {br.view.detail_var.get()}")
        snap("2_ready")
        s = spfl.Spfl()
        spfl.play_intro(s, time.time())
        log("SPFL ball in play")
        spfl.skip_match(to_menu=True)
        log("SPFL match over")
        snap("3_spfl_done")
        while not br.view.title_var.get().startswith("Saved in FM24"):
            time.sleep(2)
            if time.time() - T0 > 2400:
                raise TimeoutError("not saved in FM24")
        log(f"bridge: {br.view.title_var.get()} | {br.view.body_var.get()}")
        time.sleep(8)
        snap("4_saved")
        for c in br.writer.copies():
            if c["date"] == br.writer.date:
                log(f"copy {c['addr']:#x} {c['home_goals']}-{c['away_goals']} state {c['state']:#x} "
                    f"events {br.writer.events_of(c)[1]}")
        log(f"FM screen now: {br.fm_ui.screen()} button {br.fm_ui.button()!r}")
    except Exception as e:  # noqa: BLE001
        log(f"FAILED: {e!r}")
        snap("fail")
    finally:
        root.after(0, root.destroy)


threading.Thread(target=harness, daemon=True).start()
root.mainloop()
log("done")
