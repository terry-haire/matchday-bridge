"""Reads who scored from SP Football Life 2026's goal caption ("47 Ryan Harris / GOAL 1", bottom left).

SPFL26 keeps no player-keyed goal list that could be found in memory, but after every goal it shows the
scorer's shirt number and name for a few seconds. The game window is captured with Windows Graphics Capture
(works while other windows cover it; falls back to the screen pixels), the caption is read with the Windows OCR
engine, then matched to the squad the bridge built for this match: a unique name starting with the letters read
(the caption slides in), or a close fuzzy match, or the shirt number. Nothing is written to the game.
"""
from __future__ import annotations

import asyncio
import ctypes
import ctypes.wintypes as wt
import difflib
import glob
import io
import os
import re
import sys
import threading
import time
import unicodedata

TITLE = "SP Football Life 2026"
CAPTION = (40, 520, 560, 640)          # caption area in a 1280x720 frame (scaled to the real window size)
user32 = ctypes.windll.user32
_engine = None
_ocr_lock = threading.Lock()
_wgc = None


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def _wgc_native():
    """The native Windows Graphics Capture core of the windows-capture package, loaded without its Python
    wrapper (which pulls in OpenCV and numpy). Bundled under wgc/ in the release exe."""
    global _wgc
    if _wgc is None:
        _wgc = sys.modules.get("windows_capture.windows_capture")
    if _wgc is None:
        import importlib.machinery
        import importlib.util
        dirs = [os.path.join(getattr(sys, "_MEIPASS", ""), "wgc")]
        spec = importlib.util.find_spec("windows_capture")
        if spec and spec.submodule_search_locations:
            dirs += list(spec.submodule_search_locations)
        path = next((p for d in dirs for p in glob.glob(os.path.join(d, "windows_capture*.pyd"))), None)
        if not path:
            raise ImportError("windows-capture native module not found")
        loader = importlib.machinery.ExtensionFileLoader("windows_capture", path)
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("windows_capture", loader))
        loader.exec_module(mod)
        _wgc = mod
    return _wgc


class WindowFrames:
    """Windows Graphics Capture of one window while it runs: sees the game even when other windows cover it
    (not while minimized). Frames are only copied when someone asks for one."""

    def __init__(self, hwnd: int):
        n = _wgc_native()
        self.hwnd, self.frame, self.seq, self.want, self.closed = hwnd, None, 0, True, False
        self.frame_time = 0.0
        self.cond = threading.Condition()

        def on_frame(native, buf_len, width, height, stop_list, timespan):
            if self.closed:
                stop_list[0] = True
                return
            if not self.want:
                return
            data = bytes(native.buffer_view()[:buf_len])
            with self.cond:
                self.frame = (data, width, height, int(native.bytes_per_row))
                self.seq, self.want = self.seq + 1, False
                self.frame_time = time.time()
                self.cond.notify_all()

        def on_closed():
            self.closed = True
            with self.cond:
                self.cond.notify_all()

        try:        # no yellow capture border (Windows 11); Windows 10 refuses that setting
            self.control = n.NativeWindowsCapture(on_frame, on_closed, False, False, None, 100, None, None, None,
                                                  hwnd).start_free_threaded()
        except Exception:  # noqa: BLE001
            self.control = n.NativeWindowsCapture(on_frame, on_closed, False, None, None, 100, None, None, None,
                                                  hwnd).start_free_threaded()

    def age(self) -> float:
        """Seconds since the newest captured frame (a capture that stopped delivering frames grows old)."""
        return time.time() - self.frame_time if self.frame_time else 1e9

    def client_image(self, timeout: float = 0.6):
        """Newest frame (waits up to `timeout` for a fresh one), cropped to the client area; None if none yet."""
        from PIL import Image
        with self.cond:
            self.want, start = True, self.seq
            self.cond.wait_for(lambda: self.seq > start or self.closed, timeout)
            fr = self.frame
        if fr is None:
            return None
        data, w, h, row = fr
        img = Image.frombuffer("RGBA", (row // 4, h), data, "raw", "BGRA", 0, 1).crop((0, 0, w, h))
        ext = wt.RECT()
        ctypes.windll.dwmapi.DwmGetWindowAttribute(self.hwnd, 9, ctypes.byref(ext), ctypes.sizeof(ext))
        r = wt.RECT()
        user32.GetClientRect(self.hwnd, ctypes.byref(r))
        pt = wt.POINT(0, 0)
        user32.ClientToScreen(self.hwnd, ctypes.byref(pt))
        if r.right <= 0 or r.bottom <= 0 or ext.right <= ext.left:
            return img.convert("RGB")
        kx, ky = w / (ext.right - ext.left), h / (ext.bottom - ext.top)
        x0, y0 = (pt.x - ext.left) * kx, (pt.y - ext.top) * ky
        return img.crop((round(x0), round(y0), round(x0 + r.right * kx), round(y0 + r.bottom * ky))).convert("RGB")

    def stop(self):
        self.closed = True
        try:
            self.control.stop()
        except Exception:  # noqa: BLE001
            pass


def _window():
    user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))      # physical pixels on this thread
    h = user32.FindWindowW(None, TITLE)
    return h if h and not user32.IsIconic(h) else 0


def screen_image(h: int):
    """The window's client area as shown on screen (fallback when Windows Graphics Capture has no frame, e.g.
    exclusive fullscreen); only right while the game is on top."""
    from PIL import ImageGrab
    r = wt.RECT()
    user32.GetClientRect(h, ctypes.byref(r))
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(h, ctypes.byref(pt))
    if r.right < 320 or r.bottom < 180:
        return None
    return ImageGrab.grab(bbox=(pt.x, pt.y, pt.x + r.right, pt.y + r.bottom), all_screens=True)


def _grab_caption(frames: WindowFrames | None = None):
    """Pixels of the caption area of the SPFL26 window (captured, or from the screen if capture is
    unavailable), upscaled for OCR; None if the window is missing/minimized."""
    from PIL import ImageGrab
    h = _window()
    if not h:
        return None
    img = frames.client_image() if frames else None
    if img is not None and img.width >= 320:
        k = img.width / 1280
        img = img.crop((int(CAPTION[0] * k), int(CAPTION[1] * img.height / 720), int(CAPTION[2] * k),
                        int(CAPTION[3] * img.height / 720)))
    else:
        r = wt.RECT()
        user32.GetClientRect(h, ctypes.byref(r))
        pt = wt.POINT(0, 0)
        user32.ClientToScreen(h, ctypes.byref(pt))
        w, hh = r.right, r.bottom
        if w < 320 or hh < 180:
            return None
        kx, ky = w / 1280, hh / 720
        box = (pt.x + int(CAPTION[0] * kx), pt.y + int(CAPTION[1] * ky), pt.x + int(CAPTION[2] * kx),
               pt.y + int(CAPTION[3] * ky))
        img = ImageGrab.grab(bbox=box, all_screens=True)
    if img.width < 1000:                 # OCR wants ~30 px letters; the caption is ~15 px at 720p
        img = img.resize((img.width * 2, img.height * 2))
    return img


async def _recognize(png: bytes):
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
    global _engine
    if _engine is None:
        _engine = OcrEngine.try_create_from_user_profile_languages()
    stream = InMemoryRandomAccessStream()
    dw = DataWriter(stream)
    dw.write_bytes(png)
    await dw.store_async()
    stream.seek(0)
    bmp = await (await BitmapDecoder.create_async(stream)).get_software_bitmap_async()
    return await _engine.recognize_async(bmp)


def ocr_lines(img) -> list[str]:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    with _ocr_lock:
        res = asyncio.run(_recognize(buf.getvalue()))
    return [ln.text for ln in res.lines]


def ocr_words(img, box=None, scale: float = 1.0) -> list[list[tuple]]:
    """Lines of words (text, x, y, w, h) in the coordinates of `img`; `box` (x0, y0, x1, y1) crops first."""
    ox = oy = 0
    if box:
        img = img.crop(tuple(int(v) for v in box))
        ox, oy = box[0], box[1]
    if scale != 1.0:
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    with _ocr_lock:
        res = asyncio.run(_recognize(buf.getvalue()))
    out = []
    for ln in res.lines:
        words = []
        for wd in ln.words:
            r = wd.bounding_rect
            words.append((wd.text, ox + r.x / scale, oy + r.y / scale, r.width / scale, r.height / scale))
        if words:
            out.append(words)
    return out


def caption_lines(frames: WindowFrames | None = None) -> list[str]:
    img = _grab_caption(frames)
    return ocr_lines(img) if img is not None else []


class ScorerReader:
    """plan = MatchBuilder.build() result: plan[side]["players"] = [{name, shirt, fm_pid, ...}]."""

    def __init__(self, plan: dict):
        self.players = {0: plan["home"]["players"], 1: plan["away"]["players"]}
        self.team_names = {norm(plan[s][k]) for s in ("home", "away") for k in ("fm_name", "spfl_name")}

    def match(self, lines: list[str], side: int) -> dict | None:
        squad = self.players[side]
        names = {norm(p["name"]): p for p in squad}
        for t in lines:
            t = re.sub(r"(?i)\bown\s*goal\b", " ", t)
            m = re.match(r"\s*(\d{1,2})\b\s*(.*)", t)
            number, rest = (int(m.group(1)), m.group(2)) if m else (None, t)
            c = norm(rest)
            if not c or c in self.team_names or c.startswith("goal"):
                continue
            if len(c) >= 4:
                hit = difflib.get_close_matches(c, list(names), n=1, cutoff=0.8)
                if hit:
                    return names[hit[0]]
                pre = [n for n in names if n.startswith(c)]
                if len(pre) == 1:
                    return names[pre[0]]
            if number is not None:
                by_shirt = [p for p in squad if p["shirt"] == number]
                if len(by_shirt) == 1 and len(c) >= 2 and norm(by_shirt[0]["name"]).startswith(c[:2]):
                    return by_shirt[0]
        return None

    def read(self, side: int, timeout: float = 8.0) -> dict | None:
        """Watch the caption for up to `timeout` seconds after a goal of `side` (0 home, 1 away). An "OWN GOAL"
        caption names a player of the other side: the result then has own_goal=True (and no fm_pid if no name
        was readable)."""
        end = time.time() + timeout
        frames = None
        own = False
        try:
            h = _window()
            frames = WindowFrames(h) if h else None
        except Exception:  # noqa: BLE001 - no capture: read the screen instead
            frames = None
        try:
            while time.time() < end:
                try:
                    lines = caption_lines(frames)
                    own = own or any("owngoal" in norm(t) for t in lines)
                    hit = self.match(lines, 1 - side if own else side)
                except Exception:  # noqa: BLE001 - OCR/capture hiccup: try again
                    hit = None
                if hit:
                    return {**hit, "own_goal": True} if own else hit
                time.sleep(0.25)
            return {"own_goal": True} if own else None
        finally:
            if frames:
                frames.stop()
