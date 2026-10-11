$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$py = "$MDB\.venv\Scripts\python.exe"
& $py "$MDB\research\job_fg.py"
"--- after pesdrive focus"
& "$MDB\research\pesdrive.ps1" -Cmds "focus" -Shot "" -Wait 0
& $py -c "import ctypes,time;u=ctypes.windll.user32;h=u.FindWindowW(None,'SP Football Life 2026');[print(i, u.GetForegroundWindow()==h, u.IsIconic(h)) or time.sleep(0.5) for i in range(8)]"
"--- after key"
& "$MDB\research\pesdrive.ps1" -Cmds "scanmode on;key 0x26" -Shot "" -Wait 0
& $py -c "import ctypes,time;u=ctypes.windll.user32;h=u.FindWindowW(None,'SP Football Life 2026');[print(i, u.GetForegroundWindow()==h, u.IsIconic(h)) or time.sleep(0.5) for i in range(8)]"
