"""Elevated: what SPFL26's in-match scoreboard shows for clubs in spare slots.
python job_scoreboard.py HOME AWAY [stay] [cold]: the real Bridge._play with a sample match day (FM24 not used), then the
edit-block team records and every copy of the FM names in SPFL26's memory (with the bytes after them), kick off,
screenshots of the scoreboard -> research/shots/sb_<tag>_*.png, report research/sb_<tag>.txt. Leaves SPFL26 at the
main menu unless 'stay' is given."""
import ctypes
import json
import os
import shutil
import struct
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
from gen_structs import SPFL_EDIT_BLOCK as EB  # noqa: E402
from procmem import Proc  # noqa: E402


class NoFm:
    def __init__(self, *a, **k):
        raise RuntimeError("FM24 not used in this test")


fm_writer.FmResultWriter = NoFm
mb.Bridge.watch = lambda self: None
mb.Bridge._fm_sim = lambda self: None
HOME, AWAY = sys.argv[1], sys.argv[2]
STAY = "stay" in sys.argv[3:]
if "cold" in sys.argv[3:]:
    import subprocess
    for exe in ("FL_2026.exe", "sider.exe"):
        subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True)
    time.sleep(3)
TAG = f"{HOME.split()[0].lower()}_{AWAY.split()[0].lower()}"
CLUB_IDS = {"Oldham Athletic": 694, "Atlanta United FC": 72047296, "Birmingham Legion": 20046409}
SHORT = {"Oldham Athletic": "Oldham", "Atlanta United FC": "Atlanta", "Birmingham Legion": "Birmingham"}
SHOTS = os.path.join(ROOT, "research", "shots")
OUT = open(os.path.join(ROOT, "research", f"sb_{TAG}.txt"), "w", encoding="utf-8")
T0 = time.time()


def log(s):
    OUT.write(f"{time.time() - T0:6.1f}s {s}\n")
    OUT.flush()


def printable(b: bytes) -> str:
    return "".join(chr(c) if 32 <= c < 127 else "." for c in b)


def team_recs(p: Proc, tids):
    owner = p.u64(EB.OWNER_GLOBAL)
    blk = p.u64(owner + 0x48)
    n = p.u32(blk + EB.TEAM_COUNT)
    raw = p.read(blk + EB.TEAMS, n * 0x690)
    out = {}
    for i in range(n):
        tid = (struct.unpack_from("<I", raw, i * 0x690)[0] >> 14) & 0x1ffff
        if tid in tids:
            out[tid] = (blk + EB.TEAMS + i * 0x690, raw[i * 0x690:(i + 1) * 0x690])
    return out


def dump_memory(label: str, names):
    p = Proc("FL_2026.exe")
    try:
        plan = br.plan or {}
        tids = {plan[s]["spfl_team"] for s in plan}
        for tid, (a, rec) in sorted(team_recs(p, tids).items()):
            name = rec[4:0x4a].split(b"\x00")[0]
            log(f"[{label}] edit team {tid} @{a:#x}: name={name!r} "
                f"abbr={rec[0x4a:0x4e]!r} head={rec[:0x60].hex()}")
        for nm in names:
            for enc, pat in (("utf8", nm.encode() + b"\0"), ("utf16", nm.encode("utf-16-le") + b"\0\0")):
                hits = p.find_bytes(pat, limit=40)
                log(f"[{label}] {nm!r} {enc}: {len(hits)} copies")
                for h in hits:
                    pre = p.try_read(h - 0x20, 0x20) or b""
                    post = p.try_read(h, 0xa0) or b""
                    log(f"    @{h:#x} before={printable(pre)!r} after={printable(post)!r}")
    finally:
        p.close()


ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
spfl.set_test(match_minutes=2, extra_time=0, penalties=0)
root = tk.Tk()
br = mb.Bridge(root)
md = json.load(open(os.path.join(ROOT, "tests", "sample_matchday.json"), encoding="utf-8"))
md = {**md, "home": {**md["home"], "name": HOME, "short": SHORT.get(HOME, HOME.split()[0]), "human": False,
                     "club_id": CLUB_IDS.get(HOME)},
      "away": {**md["away"], "name": AWAY, "short": SHORT.get(AWAY, AWAY.split()[0]), "human": True,
               "club_id": CLUB_IDS.get(AWAY)}}
br.matchday = md
log(f"SPFL26 running before: {mb.is_running('FL_2026.exe')}")
root.after(500, br.play)
state = {}


def poll():
    t = br.view.title_var.get()
    if t in ("Your turn", "Pick the teams in SPFL26") or time.time() - T0 > 600:
        state["title"] = t
        log(f"{t} | {br.view.body_var.get()[:100]} | {br.view.detail_var.get()[:160]}")
        log(f"loaded live: {br.live is not None}")
        root.after(300, root.destroy)
        return
    root.after(500, poll)


root.after(1000, poll)
root.mainloop()

names = [md["home"]["name"], md["away"]["name"]]
for side in ("home", "away"):
    pl = (br.plan or {}).get(side) or {}
    log(f"plan {side}: tid={pl.get('spfl_team')} spfl_name={pl.get('spfl_name')!r} spare={pl.get('spare_slot')} "
        f"abbr={pl.get('abbr')!r}")
    if pl.get("spare_slot") and pl.get("spfl_name"):
        names.append(pl["spfl_name"])
try:
    req = open(os.path.join(spfl.MD, "request.txt"), encoding="utf-8").read()
    log("request.txt: " + req.replace("\n", " | ")[:600])
except OSError as e:
    log(f"request.txt: {e}")
dump_memory("pre-match", names)

if state.get("title") == "Your turn":
    s = spfl.Spfl()
    spfl.play_intro(s, time.time())
    for k in range(8):
        img = s.shot()
        path = os.path.join(SHOTS, f"sb_{TAG}_{k}.png")
        img.save(path)
        top = img.crop((0, 0, img.width, int(img.height * 0.16)))
        log(f"shot {k}: {path} top OCR: {win.text_of(win.ocr(top, scale=2.0))!r}")
        time.sleep(1.5)
    dump_memory("in-match", names)
    if not STAY:
        spfl.skip_match(to_menu=True)
spfl.set_test(match_minutes=None)
shots = os.path.join(os.environ["LOCALAPPDATA"], "MatchdayBridge", "last_match")
for n in os.listdir(shots):
    shutil.copy2(os.path.join(shots, n), os.path.join(SHOTS, f"sb_{TAG}_{n}"))
log("done")
OUT.close()
print(open(os.path.join(ROOT, "research", f"sb_{TAG}.txt"), encoding="utf-8").read())
