$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
cd "$MDB"
.\.venv\Scripts\python.exe research\pes_nav.py 11 0 13 33
& "$MDB\research\pesdrive.ps1" -Shot pes23 -Wait 1
