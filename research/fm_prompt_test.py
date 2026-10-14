"""Live test of the FM side: lab save -> pre-match; the bridge's detector, the choice dialog over FM (screenshot),
then FM's match played to full time in the background and the match screen left. Output: research/fm_prompt_test.txt"""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import ctypes
import ctypes.wintypes
import io
import os
import sys
import threading
import time
import tkinter as tk

ROOT = MDB
sys.path.insert(0, os.path.join(ROOT, "testkit"))
sys.path.insert(0, os.path.join(ROOT, "bridge"))
import fm as F  # noqa: E402
from PIL import Image, ImageGrab  # noqa: E402

import fm_graphics  # noqa: E402
import install  # noqa: E402
from fm_drive import FmUi  # noqa: E402
from fm_reader import FmReader  # noqa: E402
from ui import ChoiceDialog  # noqa: E402

OUT = open(os.path.join(ROOT, "research", "fm_prompt_test.txt"), "w", encoding="utf-8")
T0 = time.time()


def log(s):
    line = f"{time.time() - T0:6.1f}s {s}"
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
if "--here" not in sys.argv:
    F.reload()
    F.to_match(until="teamtalk")
ui = FmUi()
t = time.time()
log(f"at_prematch on pep talk: {ui.at_prematch()} ({time.time() - t:.2f}s)")
md = FmReader().matchday()
log(f"matchday: {md['home']['name']} ({md['home'].get('club_id')}) v {md['away']['name']} ({md['away'].get('club_id')}), "
    f"human home={md['home'].get('human')} away={md['away'].get('human')}")
ui.key("space")                     # Match Preview
for _ in range(20):
    t = time.time()
    hit = ui.at_prematch()
    log(f"at_prematch: {hit} ({time.time() - t:.2f}s)")
    if hit:
        break
    time.sleep(0.5)

root = tk.Tk()
root.withdraw()
fm_dir = install.find_fm24()
teams = []
for side in ("home", "away"):
    png = fm_graphics.club_logo(fm_dir, md[side].get("club_id"))
    teams.append({"name": md[side]["name"], "human": md[side].get("human"),
                  "logo": Image.open(io.BytesIO(png)).convert("RGBA") if png else None})
r = ctypes.wintypes.RECT()
ctypes.windll.user32.GetWindowRect(ui.window(), ctypes.byref(r))
ui.enable(False)
chosen = []
d = ChoiceDialog(root, (r.left, r.top, r.right, r.bottom), teams, "FM24", ["PES 2021", "Football Life 2026"],
                 lambda i: chosen.append(("pes", "spfl")[i]),
                 lambda: chosen.append("fm"))


def snap():
    ImageGrab.grab(all_screens=True).save(os.path.join(ROOT, "research", "shots", "fm_choice.png"))
    log(f"FM enabled while asking: {bool(ctypes.windll.user32.IsWindowEnabled(ui.h))}")
    d._play()
    root.after(300, root.quit)


root.after(2500, snap)
root.mainloop()
ui.enable(True)
log(f"chosen: {chosen}")
t = time.time()
ui.play_to_full_time(status=lambda s: None, log=log)
log(f"FM full time after {time.time() - t:.1f}s")
ui.img.save(os.path.join(ROOT, "research", "shots", "fm_ft_auto.png"))
time.sleep(3)
t = time.time()
ui.leave_match(log=log)
log(f"left the match after {time.time() - t:.1f}s; screen now {ui.screen()} button {ui.button()!r}")
