$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$d = "$MDB\research\pesdrive.ps1"
for ($i=30; $i -lt 50; $i++) {
  & $d -Cmds "scanmode on;key 0x28" -Wait 0 -Shot ("pesscan" + $i) | Out-Null
}
