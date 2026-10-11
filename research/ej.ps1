param([Parameter(Mandatory=$true)][string]$File, [int]$Timeout=600)
$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$jobs="$MDB\research\jobs2"
$ext=[IO.Path]::GetExtension($File)
$name=(Get-Date -Format "HHmmssfff") + "_" + [IO.Path]::GetFileName($File)
Copy-Item $File "$jobs\$name"
$t=0; while(-not (Test-Path "$jobs\$name.out") -and $t -lt $Timeout){ Start-Sleep -Milliseconds 300; $t+=0.3 }
if (Test-Path "$jobs\$name.out") { Get-Content "$jobs\$name.out" -Encoding utf8 } else { "TIMEOUT" }
