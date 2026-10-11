param([string]$Keys, [int]$Wait=3, [string]$Shot="pesX")
$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$d = "$MDB\research\pesdrive.ps1"
foreach ($k in ($Keys -split ',')) {
  if ($k -match '^(\w+)x(\d+)$') { $name=$matches[1]; $n=[int]$matches[2] } else { $name=$k; $n=1 }
  $vk = @{enter='0x0D';down='0x28';up='0x26';left='0x25';right='0x27';esc='0x1B';back='0x08';space='0x20'}[$name]
  if (-not $vk -and $name.Length -eq 1) { $vk = '0x{0:X2}' -f [int][char]$name.ToUpper() }
  if (-not $vk) { continue }
  for ($i=0; $i -lt $n; $i++) { & $d -Cmds "scanmode on;key $vk" -Wait 0 | Out-Null; Start-Sleep -Milliseconds 350 }
}
& $d -Shot $Shot -Wait $Wait
