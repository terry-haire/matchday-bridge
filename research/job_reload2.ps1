$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$g = "C:\Program Files (x86)\SP Football Life 2026"
& "$MDB\research\pesdrive.ps1" -Cmds "scanmode off;key 0x10 down;key 0x52 down;key 0x52 up;key 0x10 up" -Shot pes08 -Wait 5
Get-Content "$g\SiderAddons\sider.log" -Tail 30 | Select-String -Pattern "matchday|reload|Reload|PROBLEM" | ForEach-Object { $_.Line }
