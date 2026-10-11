$g = "C:\Program Files (x86)\SP Football Life 2026\SiderAddons\sider.log"
Select-String -Path $g -Pattern "matchday|setting HOME|setting AWAY|tournament_id" | Select-Object -Last 20 | ForEach-Object { $_.Line.Substring(0,[Math]::Min(200,$_.Line.Length)) }
