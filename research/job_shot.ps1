$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$env:UM_FFMPEG_WIN="$env:LOCALAPPDATA\universal-modder\ffmpeg\bin\ffmpeg.exe"
& "$env:USERPROFILE\Tools\universal-modder\.venv\Scripts\um.exe" win shot --exe FL_2026.exe "$MDB\research\shots\pes01.png" --scale 0.5 2>&1 | Select-Object -Last 1
& "$env:USERPROFILE\Tools\universal-modder\.venv\Scripts\um.exe" win drive --proc FL_2026 rect 2>&1 | Select-Object -Last 1
