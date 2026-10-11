import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import ctypes, ctypes.wintypes as w
from PIL import ImageGrab
u = ctypes.windll.user32
u.SetProcessDPIAware()
h = u.FindWindowW(None, "SP Football Life 2026")
r = w.RECT(); u.GetWindowRect(h, ctypes.byref(r))
print(h, r.left, r.top, r.right, r.bottom, "fg", u.GetForegroundWindow() == h, "iconic", u.IsIconic(h))
ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom), all_screens=True).resize((960, 540)).save(MDB + r"\research\shots\pesE3.png")
