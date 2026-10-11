param([string]$Keys, [int]$Wait=3, [string]$Shot="")
$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$py = "$MDB\.venv\Scripts\python.exe"
$r = "$MDB\research"
$t0 = Get-Date; while ($true) { $g = & $py "$r\guard.py"; if ($LASTEXITCODE -ne 3) { break }; if (((Get-Date) - $t0).TotalSeconds -gt 900) { "gave up: user active"; exit 3 }; Start-Sleep 5 }
$d = "$r\pesdrive.ps1"
if ($Keys) {
  & $py "$r\focus.py" grab | Out-Null
  foreach ($k in ($Keys -split ',')) {
    if (-not $k) { continue }
    if ($k -match '^(\w+)x(\d+)$') { $name=$matches[1]; $n=[int]$matches[2] } else { $name=$k; $n=1 }
    $vk = @{enter='0x0D';down='0x28';up='0x26';left='0x25';right='0x27';esc='0x1B';back='0x08';space='0x20'}[$name]
    if (-not $vk -and $name.Length -eq 1) { $vk = '0x{0:X2}' -f [int][char]$name.ToUpper() }
    if (-not $vk) { continue }
    for ($i=0; $i -lt $n; $i++) { & $d -Cmds "scanmode on;key $vk" -Wait 0 -Shot "" 2>&1 | Out-Null; Start-Sleep -Milliseconds 300 }
  }
  & $py "$r\guard.py" stamp
  & $py "$r\focus.py" back | Out-Null
}
Start-Sleep -Seconds $Wait
if ($Shot) {
  $env:UM_FFMPEG_WIN = "$env:LOCALAPPDATA\universal-modder\ffmpeg\bin\ffmpeg.exe"
  & "$env:USERPROFILE\Tools\universal-modder\.venv\Scripts\um.exe" win shot --exe FL_2026.exe "$r\shots\$Shot.png" --scale 0.75 2>&1 | Select-Object -Last 1
}
