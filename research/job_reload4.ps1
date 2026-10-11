$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$g = "C:\Program Files (x86)\SP Football Life 2026"
Copy-Item "$MDB\spfl\modules\matchday.lua" "$g\SiderAddons\modules\matchday.lua" -Force
$d = "$MDB\research\pesdrive.ps1"
& $d -Cmds "scanmode off;key 0x10 down;key 0x52 down;key 0x52 up;key 0x10 up" -Wait 4 | Out-Null
& $d -Cmds "scanmode on;key 0x08" -Wait 4 -Shot pes24
Get-Content "$g\SiderAddons\sider.log" -Tail 300 | Select-String -Pattern "matchday|Reloaded|ERROR" | Select-Object -Last 8 | ForEach-Object { $_.Line.Substring(0,[Math]::Min(200,$_.Line.Length)) }
