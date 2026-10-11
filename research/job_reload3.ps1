$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$g = "C:\Program Files (x86)\SP Football Life 2026"
Copy-Item "$MDB\spfl\modules\matchday.lua" "$g\SiderAddons\modules\matchday.lua" -Force
& "$MDB\research\pesdrive.ps1" -Cmds "scanmode off;key 0x10 down;key 0x52 down;key 0x52 up;key 0x10 up" -Wait 4 | Out-Null
Get-Content "$g\SiderAddons\sider.log" -Tail 400 | Select-String -Pattern "matchday|Reloaded" | Select-Object -Last 8 | ForEach-Object { $_.Line.Substring(0,[Math]::Min(200,$_.Line.Length)) }
