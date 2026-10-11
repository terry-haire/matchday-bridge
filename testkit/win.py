"""Fast Windows helpers for driving FM24 and SPFL26 in tests: focus, keys, clicks, screen grabs, OCR.

Everything works in PHYSICAL pixels (the process is made per-monitor DPI aware), so OCR boxes from a grab
can be clicked directly. Run elevated when talking to SP Football Life 2026 (it runs as admin).
"""
from __future__ import annotations

import asyncio
import ctypes
import ctypes.wintypes as wt
import io
import re
import time
import unicodedata

from PIL import Image, ImageGrab

user32 = ctypes.windll.user32
try:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
except (AttributeError, OSError):
    user32.SetProcessDPIAware()

# ------------------------------------------------------------------ windows

def find_window(title: str) -> int:
    h = user32.FindWindowW(None, title)
    if not h:
        raise RuntimeError(f"window not found: {title}")
    return h


def is_foreground(hwnd: int) -> bool:
    return user32.GetForegroundWindow() == hwnd


def focus(hwnd: int, timeout: float = 2.0) -> bool:
    if is_foreground(hwnd):
        return True
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
    end = time.time() + timeout
    while time.time() < end:
        user32.keybd_event(0x12, 0, 0, 0)  # a key event lets SetForegroundWindow succeed
        user32.keybd_event(0x12, 0, 2, 0)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.05)
        if is_foreground(hwnd):
            return True
    return False


def untop(title: str):
    """Clear another window's always-on-top flag (FM24 sets it in borderless fullscreen)."""
    h = user32.FindWindowW(None, title)
    if h and user32.GetWindowLongW(h, -20) & 0x8 and not user32.IsIconic(h):
        user32.SetWindowPos(h, ctypes.c_void_p(-2), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # HWND_NOTOPMOST
        if user32.GetWindowLongW(h, -20) & 0x8:
            user32.ShowWindow(h, 6)  # still on top: minimize it


def client_rect(hwnd: int) -> tuple[int, int, int, int]:
    """(left, top, width, height) of the client area in screen pixels."""
    r = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, r.right, r.bottom


def grab_screen(hwnd: int) -> Image.Image:
    """Client area copied from the screen: the window must be on top (focus it first)."""
    x, y, w, h = client_rect(hwnd)
    return ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)


class WindowCapture:
    """Windows Graphics Capture of one window: works while the window is covered by others and never touches
    focus or the game process (PrintWindow crashed Sider). Not while minimized: WGC gets no frames then."""

    _all: dict[int, "WindowCapture"] = {}

    @classmethod
    def of(cls, hwnd: int) -> "WindowCapture":
        c = cls._all.get(hwnd)
        if c is None or c.closed:
            c = cls._all[hwnd] = cls(hwnd)
        return c

    def __init__(self, hwnd: int):
        import threading
        from windows_capture import WindowsCapture
        self.hwnd, self.closed = hwnd, False
        self.frame, self.frame_t, self.want = None, 0.0, 0.0
        self.cond = threading.Condition()
        try:
            cap = WindowsCapture(cursor_capture=False, draw_border=False, window_hwnd=hwnd, minimum_update_interval=30)
        except Exception:                                   # border control needs Windows 11
            cap = WindowsCapture(cursor_capture=False, window_hwnd=hwnd, minimum_update_interval=30)

        @cap.event
        def on_frame_arrived(frame, control):
            if self.closed:
                control.stop()
                return
            now = time.time()
            if self.want and (self.frame is None or now >= self.want):   # copy only frames someone waits for
                buf = frame.frame_buffer.copy()
                with self.cond:
                    self.frame, self.frame_t, self.want = buf, now, 0.0
                    self.cond.notify_all()

        @cap.event
        def on_closed():
            self.closed = True
            with self.cond:
                self.cond.notify_all()

        self.want = time.time()
        self.control = cap.start_free_threaded()

    def image(self, timeout: float = 1.0) -> Image.Image:
        """A frame rendered after this call (or the newest one if the window stops presenting), client area only."""
        t = time.time()
        with self.cond:
            self.want = t
            self.cond.wait_for(lambda: self.frame_t >= t or self.closed, timeout)
            arr = self.frame
        if arr is None:
            raise OSError("no frame captured (window minimized or closed?)")
        h, w = arr.shape[:2]
        img = Image.frombuffer("RGBA", (w, h), arr.tobytes(), "raw", "BGRA", 0, 1).convert("RGB")
        ext = wt.RECT()
        ctypes.windll.dwmapi.DwmGetWindowAttribute(self.hwnd, 9, ctypes.byref(ext), ctypes.sizeof(ext))
        cx, cy, cw, ch = client_rect(self.hwnd)
        if cw <= 0 or ch <= 0 or ext.right <= ext.left:
            return img
        kx, ky = w / (ext.right - ext.left), h / (ext.bottom - ext.top)
        x0, y0 = (cx - ext.left) * kx, (cy - ext.top) * ky
        return img.crop((round(x0), round(y0), round(x0 + cw * kx), round(y0 + ch * ky)))

    def stop(self):
        self.closed = True
        try:
            self.control.stop()
        except Exception:
            pass


def capture(hwnd: int, timeout: float = 1.0) -> Image.Image:
    """A current frame; a capture that stopped delivering frames (e.g. after a minimize) is restarted."""
    c = WindowCapture.of(hwnd)
    img = c.image(timeout)
    if time.time() - c.frame_t > 4:
        c.stop()
        img = WindowCapture.of(hwnd).image(max(timeout, 2.0))
    return img


def grab(hwnd: int) -> Image.Image:
    """Client-area screenshot via PrintWindow(PW_RENDERFULLCONTENT): works when the window is covered.
    NOT for SP Football Life 2026: printing its Sider-hooked D3D window crashed the game (sider.dll+0x2ff8)."""
    _, _, w, h = client_rect(hwnd)
    gdi = ctypes.windll.gdi32
    hdc = user32.GetDC(hwnd)
    mem = gdi.CreateCompatibleDC(hdc)
    bmp = gdi.CreateCompatibleBitmap(hdc, w, h)
    old = gdi.SelectObject(mem, bmp)
    ok = user32.PrintWindow(hwnd, mem, 3)  # PW_CLIENTONLY | PW_RENDERFULLCONTENT
    buf = ctypes.create_string_buffer(w * h * 4)
    bi = (ctypes.c_uint32 * 10)(40, w, ctypes.c_uint32(-h).value, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
    gdi.GetDIBits(mem, bmp, 0, h, buf, bi, 0)
    gdi.SelectObject(mem, old)
    gdi.DeleteObject(bmp)
    gdi.DeleteDC(mem)
    user32.ReleaseDC(hwnd, hdc)
    if not ok:
        x, y, _, _ = client_rect(hwnd)
        return ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
    return Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1)

def pid_of(hwnd: int) -> int:
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def suspend(pid: int, on: bool = True):
    """Freeze/unfreeze a whole process (NtSuspendProcess). Used to read game memory at a fixed instant."""
    k32, nt = ctypes.windll.kernel32, ctypes.windll.ntdll
    h = k32.OpenProcess(0x0800, False, pid)  # PROCESS_SUSPEND_RESUME
    try:
        (nt.NtSuspendProcess if on else nt.NtResumeProcess)(h)
    finally:
        k32.CloseHandle(h)


# ------------------------------------------------------------------ input

class _KI(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _MI(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _U(ctypes.Union):
    _fields_ = [("ki", _KI), ("mi", _MI), ("pad", ctypes.c_byte * 32)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def _send(*inputs):
    arr = (_INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), arr, ctypes.sizeof(_INPUT))


VK = {"enter": 0x0D, "esc": 0x1B, "back": 0x08, "space": 0x20, "tab": 0x09, "left": 0x25, "up": 0x26,
      "right": 0x27, "down": 0x28, "pgup": 0x21, "pgdn": 0x22, "home": 0x24, "end": 0x23, "ins": 0x2D,
      "del": 0x2E, **{f"f{i}": 0x6F + i for i in range(1, 13)}, **{f"num{i}": 0x60 + i for i in range(10)}}
EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E}


def vk_of(name: str) -> int:
    name = name.lower()
    if name in VK:
        return VK[name]
    if len(name) == 1:
        return ord(name.upper())
    raise ValueError(name)


def key(name: str, hold: float = 0.04):
    """Hardware scan-code key press (PES/Fox Engine ignores virtual-key-only input)."""
    vk = vk_of(name)
    sc = user32.MapVirtualKeyW(vk, 0)
    flags = 0x0008 | (0x0001 if vk in EXTENDED else 0)
    _send(_INPUT(1, _U(ki=_KI(0, sc, flags, 0, 0))))
    time.sleep(hold)
    _send(_INPUT(1, _U(ki=_KI(0, sc, flags | 0x0002, 0, 0))))


def keys(seq: str, gap: float = 0.12):
    """'down*11,enter' style sequences."""
    for part in [p.strip() for p in seq.split(",") if p.strip()]:
        m = re.fullmatch(r"(\w+)(?:\*(\d+))?", part)
        for _ in range(int(m.group(2) or 1)):
            key(m.group(1))
            time.sleep(gap)


def click(hwnd: int, x: float, y: float, settle: float = 0.05):
    """Left click at client pixel (x, y)."""
    cx, cy, _, _ = client_rect(hwnd)
    user32.SetCursorPos(cx + int(x), cy + int(y))
    time.sleep(settle)
    _send(_INPUT(0, _U(mi=_MI(0, 0, 0, 0x0002, 0, 0))))
    time.sleep(0.03)
    _send(_INPUT(0, _U(mi=_MI(0, 0, 0, 0x0004, 0, 0))))

# ------------------------------------------------------------------ OCR (Windows.Media.Ocr)

_engine = None
_ocr_lock = __import__("threading").Lock()


def _ocr_engine():
    global _engine
    if _engine is None:
        from winrt.windows.media.ocr import OcrEngine
        _engine = OcrEngine.try_create_from_user_profile_languages()
    return _engine


async def _ocr_async(png: bytes):
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
    stream = InMemoryRandomAccessStream()
    w = DataWriter(stream)
    w.write_bytes(png)
    await w.store_async()
    stream.seek(0)
    dec = await BitmapDecoder.create_async(stream)
    bmp = await dec.get_software_bitmap_async()
    return await _ocr_engine().recognize_async(bmp)


class Word:
    def __init__(self, text, x, y, w, h):
        self.text, self.x, self.y, self.w, self.h = text, x, y, w, h

    def __repr__(self):
        return f"{self.text!r}@{int(self.x)},{int(self.y)}"


def ocr(img: Image.Image, box: tuple[int, int, int, int] | None = None, scale: float = 1.0) -> list[list[Word]]:
    """Lines of words with boxes in the coordinates of `img`. `box` crops first (x0, y0, x1, y1)."""
    ox = oy = 0
    if box:
        img = img.crop(tuple(int(v) for v in box))
        ox, oy = box[0], box[1]
    if scale != 1.0:
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    with _ocr_lock:                       # one RecognizeAsync at a time per engine
        res = asyncio.run(_ocr_async(buf.getvalue()))
    lines = []
    for ln in res.lines:
        words = []
        for wd in ln.words:
            r = wd.bounding_rect
            words.append(Word(wd.text, ox + r.x / scale, oy + r.y / scale, r.width / scale, r.height / scale))
        lines.append(words)
    return lines


def text_of(lines) -> str:
    return "\n".join(" ".join(w.text for w in ln) for ln in lines)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def find_text(lines, phrase: str):
    """Center (x, y) of the first run of words matching `phrase` (accent/case-insensitive prefix match)."""
    want = [norm(t) for t in phrase.split()]
    for ln in lines:
        toks = [norm(w.text) for w in ln]
        for i in range(len(toks) - len(want) + 1):
            if all(toks[i + k].startswith(want[k]) for k in range(len(want)) if want[k]):
                first, last = ln[i], ln[i + len(want) - 1]
                return (first.x + last.x + last.w) / 2, first.y + first.h / 2
    return None
