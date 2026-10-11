$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
& "$MDB\research\pesdrive.ps1" -Shot pes21 -Wait 0
