$g = "C:\Program Files (x86)\SP Football Life 2026"
Start-Process -FilePath "$g\FL 2026 start.exe" -WorkingDirectory $g
Start-Sleep 70
Get-Process -Name FL_2026,sider -ErrorAction SilentlyContinue | Select-Object Id,Name,MainWindowTitle | Format-Table | Out-String
Select-String -Path "$g\SiderAddons\sider.log" -Pattern "matchday|error|Error|pesdb\\(Player|Team|PlayerAssignment)" | Select-Object -First 25 | ForEach-Object { $_.Line.Substring(0, [Math]::Min(200, $_.Line.Length)) }
