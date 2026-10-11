"""Exit 3 if a human used keyboard/mouse since our last injected input (yield to the user)."""
import ctypes, os, sys
class L(ctypes.Structure): _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
STAMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "my_last_input.txt")
l = L(); l.cbSize = 8; ctypes.windll.user32.GetLastInputInfo(ctypes.byref(l))
now = ctypes.windll.kernel32.GetTickCount()
mine = int(open(STAMP).read()) if os.path.exists(STAMP) else 0
if sys.argv[1:] == ["stamp"]:
    open(STAMP, "w").write(str(now)); sys.exit(0)
idle = (now - l.dwTime) / 1000
if l.dwTime > mine + 1500 and idle < 30:
    print(f"USER_ACTIVE idle={idle:.1f}s"); sys.exit(3)
print(f"ok idle={idle:.1f}s")
