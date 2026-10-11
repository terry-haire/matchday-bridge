$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$d = "$MDB\research\pesdrive.ps1"
& $d -Cmds "scanmode on;key 0x27" -Wait 1 | Out-Null
& $d -Cmds "scanmode on;key 0x0D" -Wait 4 -Shot pes26
