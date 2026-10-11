import ctypes, time
u = ctypes.windll.user32
h = u.FindWindowW(None, "SP Football Life 2026")
u.ShowWindow(h, 9); time.sleep(1); u.SetForegroundWindow(h); time.sleep(2)
print("iconic", u.IsIconic(h), "fg", u.GetForegroundWindow() == h)
