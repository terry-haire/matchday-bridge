"""Controller "User 1" input for SP Football Life 2026 without focusing its window.

SPFL26 reads its pads through XInput even when the window is in the background, and only User 1 (the keyboard
plus the pad in XInput slot 0) may use the menus. spfl/xinput/xinput_proxy.c is a small proxy xinput1_3.dll for
the game folder: it merges the buttons written here (shared memory "Local\\MatchdayBridgePad") into slot 0, on
top of a real pad if one is plugged in. The bridge uses it to walk the menus to the pre-match screen; the dev
testkit (testkit/pad.py) uses it to play. Held buttons expire after a second, so a crash never leaves one down.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import filecmp
import os
import shutil
import time

NAME = "Local\\MatchdayBridgePad"
MAGIC = 0x3150424D
DLL_NAME, ORIG_NAME = "xinput1_3.dll", "xinput1_3_orig.dll"
BUTTONS = {
    "UP": 0x0001, "DOWN": 0x0002, "LEFT": 0x0004, "RIGHT": 0x0008, "START": 0x0010, "BACK": 0x0020,
    "LS": 0x0040, "RS": 0x0080, "LB": 0x0100, "RB": 0x0200, "GUIDE": 0x0400,
    "A": 0x1000, "B": 0x2000, "X": 0x4000, "Y": 0x8000,
}


class _Pad(ctypes.Structure):
    _fields_ = [("buttons", ctypes.c_uint16), ("lt", ctypes.c_uint8), ("rt", ctypes.c_uint8),
                ("lx", ctypes.c_int16), ("ly", ctypes.c_int16), ("rx", ctypes.c_int16), ("ry", ctypes.c_int16)]


class _Shm(ctypes.Structure):       # keep in sync with SHM in spfl/xinput/xinput_proxy.c
    _fields_ = [("magic", ctypes.c_uint32), ("seq", ctypes.c_uint32), ("slot", ctypes.c_uint32),
                ("connect", ctypes.c_uint32), ("reads", ctypes.c_uint32), ("pid", ctypes.c_uint32),
                ("real_ok", ctypes.c_uint32), ("reserved", ctypes.c_uint32), ("expires", ctypes.c_uint64),
                ("pad", _Pad)]


k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileMappingW.restype = wt.HANDLE
k32.CreateFileMappingW.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.DWORD, wt.LPCWSTR]
k32.MapViewOfFile.restype = ctypes.c_void_p
k32.MapViewOfFile.argtypes = [wt.HANDLE, wt.DWORD, wt.DWORD, wt.DWORD, ctypes.c_size_t]
k32.GetTickCount64.restype = ctypes.c_uint64
_shm: _Shm | None = None
_handle = None


def shm() -> _Shm:
    """Create (or open) the shared block. Everyone-access DACL + low integrity label, so the elevated game and a
    non-elevated tool can both open it whichever starts first. The game keeps it alive once open."""
    global _shm, _handle
    if _shm is not None:
        return _shm

    class SA(ctypes.Structure):
        _fields_ = [("nLength", wt.DWORD), ("sd", ctypes.c_void_p), ("inherit", wt.BOOL)]

    sd = ctypes.c_void_p()
    if not ctypes.windll.advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            "D:(A;;GA;;;WD)S:(ML;;NW;;;LW)", 1, ctypes.byref(sd), None):
        raise ctypes.WinError(ctypes.get_last_error())
    sa = SA(ctypes.sizeof(SA), sd, False)
    _handle = k32.CreateFileMappingW(wt.HANDLE(-1), ctypes.byref(sa), 0x04, 0, 64, NAME)
    if not _handle:
        raise ctypes.WinError(ctypes.get_last_error())
    addr = k32.MapViewOfFile(_handle, 0x0002 | 0x0004, 0, 0, 64)     # FILE_MAP_WRITE | FILE_MAP_READ
    if not addr:
        raise ctypes.WinError(ctypes.get_last_error())
    _shm = _Shm.from_address(addr)
    if _shm.magic != MAGIC:
        _shm.slot, _shm.connect, _shm.expires = 0, 1, 0
        _shm.magic = MAGIC
    return _shm


def write(buttons: int = 0, lt: int = 0, rt: int = 0, lx: int = 0, ly: int = 0, rx: int = 0, ry: int = 0,
          ms: float = 0):
    s = shm()
    s.pad.buttons, s.pad.lt, s.pad.rt = buttons, lt, rt
    s.pad.lx, s.pad.ly, s.pad.rx, s.pad.ry = lx, ly, rx, ry
    s.expires = k32.GetTickCount64() + int(ms) + 1000 if (buttons or lt or rt or lx or ly or rx or ry) else 0
    s.seq = (s.seq + 1) & 0x7FFFFFFF        # last: the proxy bumps the packet number from it


def mask(names: list[str]) -> tuple[int, int, int]:
    b = lt = rt = 0
    for n in names:
        n = n.upper()
        if n == "LT":
            lt = 255
        elif n == "RT":
            rt = 255
        elif n in BUTTONS:
            b |= BUTTONS[n]
        else:
            raise ValueError(f"unknown pad button {n!r}")
    return b, lt, rt


def press(names: str, ms: float = 80):
    """Press 'A' or 'LB+RB' for `ms` and release."""
    b, lt, rt = mask(names.split("+"))
    write(b, lt, rt, ms=ms)
    time.sleep(ms / 1000)
    release()


def taps(seq: str, gap_ms: float = 90, ms: float = 70):
    """'DOWN*3,A' style sequences."""
    for part in [p.strip() for p in seq.replace(" ", "").split(",") if p.strip()]:
        name, _, n = part.partition("*")
        for _ in range(int(n or 1)):
            press(name, ms)
            time.sleep(gap_ms / 1000)


def release():
    write()


def polled(within: float = 1.5) -> bool:
    """True if a game with the proxy is reading the pad right now."""
    s = shm()
    n = s.reads
    end = time.time() + within
    while time.time() < end:
        if s.reads != n:
            return True
        time.sleep(0.05)
    return False


# ------------------------------------------------------------------ proxy dll in the game folder
def installed(game: str, dll: str) -> bool:
    dst = os.path.join(game, DLL_NAME)
    return os.path.exists(dst) and filecmp.cmp(dll, dst, shallow=False)


def install(game: str, dll: str) -> bool:
    """Game folder: xinput1_3.dll (Microsoft's) -> xinput1_3_orig.dll, proxy -> xinput1_3.dll. The game must be
    closed. Returns True if something was changed."""
    dst, orig = os.path.join(game, DLL_NAME), os.path.join(game, ORIG_NAME)
    if installed(game, dll):
        return False
    if os.path.exists(dst) and not os.path.exists(orig) and os.path.getsize(dst) > 32 * 1024:
        os.replace(dst, orig)                      # the proxy is ~6 KB; Microsoft's dll is ~100 KB
    shutil.copy2(dll, dst)
    return True


def uninstall(game: str) -> bool:
    dst, orig = os.path.join(game, DLL_NAME), os.path.join(game, ORIG_NAME)
    if os.path.exists(orig):
        os.replace(orig, dst)
        return True
    if os.path.exists(dst) and os.path.getsize(dst) < 32 * 1024:
        os.remove(dst)                             # ours, and the game had no copy of its own
        return True
    return False
