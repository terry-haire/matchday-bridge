param([string]$Proc="fm", [string]$Shot="", [string]$Cmds="", [int]$Wait=2, [double]$Scale=0.4)
$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$env:UM_FFMPEG_WIN="$env:LOCALAPPDATA\universal-modder\ffmpeg\bin\ffmpeg.exe"
$um="$env:USERPROFILE\Tools\universal-modder\.venv\Scripts\um.exe"
if ($Cmds) { [string[]]$list = $Cmds -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ }; & $um win drive --proc $Proc focus @list 2>&1 | Out-String | Write-Output }
if ($Shot) { Start-Sleep -Seconds $Wait; & $um win shot --exe "$Proc.exe" "$MDB\research\shots\$Shot.png" --scale $Scale 2>&1 | Select-Object -Last 1 }

