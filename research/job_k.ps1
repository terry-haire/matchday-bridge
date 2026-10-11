Get-Process FL_2026,sider -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.Id -Force; "stopped $($_.ProcessName)" }
