$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$d = "$MDB\research\pesdrive.ps1"
& $d -Cmds "scanmode on;key 0x28" -Wait 1 | Out-Null
for ($i=0; $i -lt 6; $i++) { & $d -Cmds "scanmode on;key 0x28" -Wait 1 -Shot ("pes_l" + $i) | Out-Null }
& $d -Shot pes10 -Wait 1
