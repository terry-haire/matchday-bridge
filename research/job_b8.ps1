$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$d = "$MDB\research\pesdrive.ps1"
for ($i=0; $i -lt 36; $i++) { & $d -Cmds "scanmode on;key 0x28" -Wait 0 | Out-Null; Start-Sleep -Milliseconds 300 }
& $d -Shot pes32 -Wait 1
