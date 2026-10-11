$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$g = "C:\Program Files (x86)\SP Football Life 2026"
Get-Process -Name FL_2026,sider -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.Id -Force }
Start-Sleep 4
Start-Process -FilePath "$g\FL 2026 start.exe" -WorkingDirectory $g
Start-Sleep 75
Select-String -Path "$g\SiderAddons\sider.log" -Pattern "matchday" | ForEach-Object { $_.Line }
$d = "$MDB\research\pesdrive.ps1"
& $d -Cmds "scanmode on;key 0x0D" -Wait 25 | Out-Null
& $d -Cmds "scanmode on;key 0x0D" -Wait 4 | Out-Null
& $d -Cmds "scanmode on;key 0x0D" -Wait 8 | Out-Null
& $d -Cmds "scanmode on;key 0x0D" -Wait 8 -Shot pes09
