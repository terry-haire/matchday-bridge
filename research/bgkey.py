import ctypes, time, sys
u = ctypes.windll.user32
h = u.FindWindowW(None, "SP Football Life 2026")
vk = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x0D
sc = u.MapVirtualKeyW(vk, 0)
ext = 1 if vk in (0x25, 0x26, 0x27, 0x28) else 0
down = 1 | (sc << 16) | (ext << 24)
up = down | (1 << 30) | (1 << 31)
print("fg is spfl", u.GetForegroundWindow() == h)
u.PostMessageW(h, 0x0100, vk, down); time.sleep(0.08); u.PostMessageW(h, 0x0101, vk, up)
print("posted", hex(vk))
