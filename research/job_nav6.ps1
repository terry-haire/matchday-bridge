$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$d = "$MDB\research\pesdrive.ps1"
for ($i=0; $i -lt 12; $i++) { & $d -Cmds "scanmode on;key 0x26" -Wait 1 | Out-Null }
& $d -Shot pes15 -Wait 1
