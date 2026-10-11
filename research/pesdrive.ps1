param([string]$Cmds="", [string]$Shot="pes", [int]$Wait=3)
$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$env:UM_FFMPEG_WIN="$env:LOCALAPPDATA\universal-modder\ffmpeg\bin\ffmpeg.exe"
$um="$env:USERPROFILE\Tools\universal-modder\.venv\Scripts\um.exe"
if ($Cmds) { [string[]]$list = $Cmds -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ }; & $um win drive --proc FL_2026 @list 2>&1 | Select-Object -Last 3 }
Start-Sleep -Seconds $Wait
if ($Shot) { & $um win shot --exe FL_2026.exe "$MDB\research\shots\$Shot.png" --scale 0.5 2>&1 | Select-Object -Last 1 }
