$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
& "$MDB\research\pesdrive.ps1" -Cmds "scanmode on;key 0x0D" -Shot pes05 -Wait 8
