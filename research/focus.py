"""focus.py grab  -> remember the current foreground window, bring SPFL forward
   focus.py back  -> give the remembered window its focus back"""
import ctypes, os, sys, time
u = ctypes.windll.user32
ST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prev_fg.txt")
h = u.FindWindowW(None, "SP Football Life 2026")
if sys.argv[1] == "grab":
    prev = u.GetForegroundWindow()
    open(ST, "w").write(str(prev if prev != h else 0))
    if u.IsIconic(h): u.ShowWindow(h, 9)
    u.keybd_event(0x12, 0, 0, 0); u.keybd_event(0x12, 0, 2, 0)  # lets SetForegroundWindow succeed
    u.SetForegroundWindow(h); time.sleep(0.4)
    print("spfl fg", u.GetForegroundWindow() == h)
else:
    prev = int(open(ST).read() or 0) if os.path.exists(ST) else 0
    if prev and u.IsWindow(prev):
        u.keybd_event(0x12, 0, 0, 0); u.keybd_event(0x12, 0, 2, 0)
        u.SetForegroundWindow(prev)
    print("restored", bool(prev))
