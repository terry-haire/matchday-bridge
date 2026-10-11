param([int]$Max=60)
$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$d = "$MDB\research\d.ps1"
for ($i=0; $i -lt $Max; $i++) {
  & $d -Cmds "focus;click 1645 22" -Wait 0 | Out-Null
  Start-Sleep 5
  $gm = & "$MDB\.venv\Scripts\python.exe" -c "import sys;sys.path.insert(0,r'$MDB\bridge');from fm_reader import FmReader;print(bool(FmReader().find_game_match()))"
  if ($gm -eq "True") { "GAME_MATCH at iter $i"; break }
}
& $d -Shot fmAdv -Wait 0 -Scale 0.3
