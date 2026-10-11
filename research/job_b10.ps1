$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$d = "$MDB\research\pesdrive.ps1"
& $d -Shot pes34 -Wait 30
Get-Content "C:\Program Files (x86)\SP Football Life 2026\SiderAddons\sider.log" -Tail 400 | Select-String -Pattern "matchday|setting (HOME|AWAY)" | Select-Object -Last 8 | ForEach-Object { $_.Line }
