$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$d = "$MDB\research\pesdrive.ps1"
& $d -Shot pes19 -Wait 25
