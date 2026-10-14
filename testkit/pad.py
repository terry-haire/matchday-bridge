"""Test input for SP Football Life 2026 as controller "User 1", without focusing the game (dev testkit only).

The input path is the one the bridge ships: spfl/xinput/xinput_proxy.c is a proxy xinput1_3.dll for the game
folder that merges the buttons written by bridge/spfl_pad.py (shared memory "Local\\MatchdayBridgePad") into
slot 0, on top of a real pad if one is plugged in. This file adds the build and a command line.

    python testkit/pad.py build              # compile spfl/xinput/xinput1_3.dll (clang)
    python testkit/pad.py install            # put the proxy into the game folder (game closed; run elevated)
    python testkit/pad.py uninstall          # restore the game's own xinput1_3.dll
    python testkit/pad.py status             # proxy installed? game polling the pad?
    python testkit/pad.py tap START          # A B X Y LB RB LT RT START BACK LS RS UP DOWN LEFT RIGHT
    python testkit/pad.py taps "DOWN*3,A"    # sequence
    python testkit/pad.py hold A 1500        # hold for ms
    python testkit/pad.py stick L 0 1 500    # left stick up for 500 ms

Do not press LT and RT together: that toggles the Sider overlay (gamepad.ini).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bridge"))
import spfl_pad  # noqa: E402
from spfl_pad import polled, press, release, shm, taps  # noqa: E402,F401

SRC = os.path.join(HERE, "..", "spfl", "xinput")
DLL = os.path.join(SRC, "xinput1_3.dll")
GAME = r"C:\Program Files (x86)\SP Football Life 2026"
tap = press


def hold(names: str, ms: float = 1000):
    press(names, ms)


def stick(side: str, x: float, y: float, ms: float = 300):
    v = lambda f: int(max(-1.0, min(1.0, f)) * 32767)
    if side.upper() == "L":
        spfl_pad.write(lx=v(x), ly=v(y), ms=ms)
    else:
        spfl_pad.write(rx=v(x), ry=v(y), ms=ms)
    time.sleep(ms / 1000)
    release()


def ensure():
    """Create the shared block before the game starts (the proxy finds it within 0.5 s otherwise)."""
    shm()


def build() -> str:
    c, d = os.path.join(SRC, "xinput_proxy.c"), os.path.join(SRC, "xinput1_3.def")
    if os.path.exists(DLL) and os.path.getmtime(DLL) >= max(os.path.getmtime(c), os.path.getmtime(d)):
        return DLL
    cmd = ["clang", "-shared", "-O2", "-Wall", "-ffreestanding", "-nostdlib", "-fno-stack-protector",
           "-o", DLL, c, f"-Wl,/DEF:{d}", "-Wl,/ENTRY:DllMain", "-lkernel32"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"clang failed:\n{r.stdout}{r.stderr}")
    for ext in (".lib", ".exp"):
        try:
            os.remove(DLL[:-4] + ext)
        except OSError:
            pass
    return DLL


def installed() -> bool:
    return spfl_pad.installed(GAME, DLL)


def install() -> bool:
    return spfl_pad.install(GAME, build())


def uninstall():
    spfl_pad.uninstall(GAME)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    op, args = sys.argv[1].lower(), sys.argv[2:]
    if op == "build":
        print(build())
    elif op == "install":
        print("installed" if install() else "already installed")
    elif op == "uninstall":
        uninstall()
        print("restored the game's xinput1_3.dll")
    elif op == "status":
        s = shm()
        print(f"proxy installed: {installed()}  game polling: {polled()}  pid={s.pid}  real pad in slot 0: {bool(s.real_ok)}")
    elif op in ("tap", "press", "hold"):
        press(args[0], float(args[1]) if len(args) > 1 else (80 if op != "hold" else 1000))
    elif op == "taps":
        taps(args[0], float(args[1]) if len(args) > 1 else 90)
    elif op == "stick":
        stick(args[0], float(args[1]), float(args[2]), float(args[3]) if len(args) > 3 else 300)
    elif op == "release":
        release()
    else:
        raise SystemExit(__doc__)
