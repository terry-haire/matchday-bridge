import ctypes, ctypes.wintypes as w, time
u = ctypes.windll.user32
def who(h):
    pid = w.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    t = ctypes.create_unicode_buffer(200); u.GetWindowTextW(h, t, 200)
    return pid.value, t.value
h = u.FindWindowW(None, "SP Football Life 2026")
u.ShowWindow(h, 9); time.sleep(0.5); u.SetForegroundWindow(h)
for i in range(2):
    time.sleep(0.5)
    print(round(i*0.5,1), "fg", who(u.GetForegroundWindow()), "spfl iconic", u.IsIconic(h))
