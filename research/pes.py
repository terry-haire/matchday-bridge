"""PES 2021 research helper (dev only).

    python research/pes.py look [--save NAME]     # OCR of the game window (background capture)
    python research/pes.py taps "DOWN*3,A" [--look] [--save NAME]
    python research/pes.py hold                   # keep the pad's shared memory alive (run in the background)
    python research/pes.py title                  # window title / size
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "testkit"))
sys.path.insert(0, os.path.join(HERE, "..", "bridge"))
import win  # noqa: E402
import spfl_pad  # noqa: E402

user32 = ctypes.windll.user32
EXE = "PES2021.exe"


def pids(exe: str = EXE) -> set[int]:
    import subprocess
    out = subprocess.run(["tasklist", "/fo", "csv", "/nh", "/fi", f"imagename eq {exe}"],
                         capture_output=True, text=True).stdout
    return {int(l.split('","')[1]) for l in out.splitlines() if l.startswith('"')}


def window(exe: str = EXE) -> int:
    want = pids(exe)
    best = [0, 0]
    proto = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(h, _):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in want and user32.IsWindowVisible(h):
            r = wt.RECT()
            user32.GetClientRect(h, ctypes.byref(r))
            area = r.right * r.bottom
            if area > best[1]:
                best[:] = [h, area]
        return True

    user32.EnumWindows(proto(cb), 0)
    return best[0]


def title(h: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(h, buf, 256)
    return buf.value


def look(save: str | None = None):
    user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    h = window()
    if not h:
        print("no PES2021 window")
        return
    img = win.capture(h, 2.0)
    lines = win.ocr(img)
    print(f"title {title(h)!r} size {img.size}")
    for ln in lines:
        print(f"  ({int(ln[0].x)},{int(ln[0].y)}) " + " ".join(w.text for w in ln))
    if save:
        d = os.path.join(HERE, "shots")
        os.makedirs(d, exist_ok=True)
        img.save(os.path.join(d, save + ".png"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("op", choices=["look", "taps", "hold", "title"])
    ap.add_argument("seq", nargs="?")
    ap.add_argument("--save")
    ap.add_argument("--look", action="store_true")
    ap.add_argument("--wait", type=float, default=1.0)
    a = ap.parse_args()
    if a.op == "look":
        look(a.save)
    elif a.op == "taps":
        spfl_pad.shm()
        spfl_pad.taps(a.seq, 120)
        if a.look or a.save:
            time.sleep(a.wait)
            look(a.save)
    elif a.op == "hold":
        s = spfl_pad.shm()
        print("holding", spfl_pad.NAME, flush=True)
        while True:
            time.sleep(5)
    elif a.op == "title":
        h = window()
        r = wt.RECT()
        user32.GetClientRect(h, ctypes.byref(r))
        print(hex(h), repr(title(h)), r.right, r.bottom)
