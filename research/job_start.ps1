$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$g = "C:\Program Files (x86)\SP Football Life 2026"
Start-Process -FilePath "$g\FL 2026 start.exe" -WorkingDirectory $g
Start-Sleep 75
& "$MDB\research\pesdrive.ps1" -Shot pesA0 -Wait 0
