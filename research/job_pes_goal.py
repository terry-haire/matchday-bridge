"""PES 2021 goal captions (dev research): from the pre-match screen, kick off and keep the match going (A every 2 s
for set pieces and help popups, paused after a goal), and for every goal save frames and the OCR of the caption
area the bridge reads (spfl_scorers.CAPTION) -> research/shots/pesgoal_*.png, research/pes_goals.txt.

    python research/job_pes_goal.py [MINUTES]
"""
import ctypes
import os
import sys
import time

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
import spfl_pad  # noqa: E402
import spfl_scorers as sc  # noqa: E402

ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
sc.use_game("PES2021.exe")
RES = r"C:\Program Files (x86)\Steam\steamapps\common\eFootball PES 2021\sider\matchday\result.txt"
LIMIT = float(sys.argv[1]) if len(sys.argv) > 1 else 12
OUT = open(os.path.join(ROOT, "research", "pes_goals.txt"), "w", encoding="utf-8")
T0 = time.time()


def log(s):
    line = f"{time.time() - T0:6.1f}s {s}"
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


def result():
    try:
        return dict(l.split("=", 1) for l in open(RES).read().split() if "=" in l)
    except OSError:
        return {}


spfl_pad.shm()
frames = sc.WindowFrames(sc._window())
spfl_pad.press("A")                       # Kick Off
log("kick off pressed")
last_goals, quiet_until, n_goal, last_press = "", 0.0, 0, 0.0
while time.time() - T0 < LIMIT * 60:
    r = result()
    goals = r.get("goals", "")
    if r and goals != last_goals:
        n_goal += 1
        log(f"goal mark {goals!r} score {r.get('home')}-{r.get('away')} minute {r.get('minute')}")
        end = time.time() + 10
        k = 0
        while time.time() < end:
            img = frames.client_image(1.0)
            if img is not None:
                if k % 3 == 0:
                    img.save(os.path.join(ROOT, "research", "shots", f"pesgoal_{n_goal}_{k:02d}.png"))
                log(f"   caption ocr: {sc.caption_lines(frames)}")
            k += 1
            time.sleep(0.4)
        quiet_until = time.time() + 6
    last_goals = goals
    if r.get("final") == "1":
        log(f"final: {r}")
        break
    if time.time() > quiet_until and time.time() - last_press > 2.0:
        spfl_pad.press("A")
        last_press = time.time()
    time.sleep(0.3)
log(f"stopped: {result()}")
frames.stop()
OUT.close()
