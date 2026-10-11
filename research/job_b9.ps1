$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$d = "$MDB\research\pesdrive.ps1"
& $d -Cmds "scanmode on;key 0x0D" -Wait 2 | Out-Null
& $d -Cmds "scanmode on;key 0x0D" -Wait 40 -Shot pes33
Get-Content "C:\Program Files (x86)\SP Football Life 2026\SiderAddons\sider.log" -Tail 200 | Select-String -Pattern "matchday" | Select-Object -Last 6 | ForEach-Object { $_.Line }
