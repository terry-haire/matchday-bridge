$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$g = "C:\Program Files (x86)\SP Football Life 2026"
Copy-Item "$MDB\spfl\modules\matchday.lua" "$g\SiderAddons\modules\matchday.lua" -Force
Remove-Item "$g\SiderAddons\modules\matchday_gen.lua" -ErrorAction SilentlyContinue
& "$MDB\research\pesdrive.ps1" -Cmds "scanmode on;key 0x10 down;key 0x52;key 0x10 up" -Shot pes07 -Wait 4
Select-String -Path "$g\SiderAddons\sider.log" -Pattern "matchday" | Select-Object -Last 6 | ForEach-Object { $_.Line }
