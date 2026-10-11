"""Keep SPFL focused (it pauses otherwise) until result.txt says the 2nd half reached 90' or stalls; skip replays/half time with Enter."""
import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import ctypes, time, re, subprocess
u = ctypes.windll.user32
R = r"C:\Program Files (x86)\SP Football Life 2026\SiderAddons\matchday\result.txt"
h = u.FindWindowW(None, "SP Football Life 2026")
def focus():
    if u.GetForegroundWindow() != h:
        if u.IsIconic(h): u.ShowWindow(h, 9)
        u.keybd_event(0x12, 0, 0, 0); u.keybd_event(0x12, 0, 2, 0); u.SetForegroundWindow(h)
def enter():
    focus(); time.sleep(0.2)
    subprocess.run(["powershell", "-NoProfile", "-File", MDB + r"\research\pesdrive.ps1", "-Cmds", "scanmode on;key 0x0D", "-Shot", "", "-Wait", "0"], capture_output=True)
last, since, t0 = "", time.time(), time.time()
while time.time() - t0 < 1500:
    focus(); time.sleep(5)
    c = open(R).read()
    m = dict(re.findall(r"(\w+)=(\d+)", c))
    if c != last:
        last, since = c, time.time()
        print(time.strftime("%H:%M:%S"), c.replace("\n", " "), flush=True)
    if int(m.get("period", 0)) >= 3 or (int(m.get("period", 0)) == 2 and int(m.get("minute", 0)) >= 90 and time.time() - since > 20):
        print("full time"); break
    if time.time() - since > 25:
        enter(); since = time.time()
