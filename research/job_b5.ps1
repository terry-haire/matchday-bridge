$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$d = "$MDB\research\pesdrive.ps1"
& $d -Cmds "scanmode on;key 0x28;key 0x28;key 0x28" -Wait 1 | Out-Null
& $d -Cmds "scanmode on;key 0x0D" -Wait 2 | Out-Null
for ($i=0; $i -lt 34; $i++) { & $d -Cmds "scanmode on;key 0x28" -Wait 0 | Out-Null; Start-Sleep -Milliseconds 250 }
& $d -Shot pes29 -Wait 1
