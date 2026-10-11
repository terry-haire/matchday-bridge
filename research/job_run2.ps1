$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$ErrorActionPreference = "Continue"
$g = "C:\Program Files (x86)\SP Football Life 2026"
Get-Process -Name FL_2026,sider -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.Id -Force; "killed $($_.Name)" }
Start-Sleep 4
cd "$MDB"
$env:PYTHONIOENCODING = "utf-8"
@"
import sys, json, datetime, os
sys.path.insert(0, 'bridge')
import install
from spfl_db import PesDb
from spfl_build import MatchBuilder, request_lines
g = install.find_spfl26()
print(install.install_spfl(g))
install.clear_match_root(g)
db = PesDb.load(g, [os.path.join(g,'SiderAddons','livecpk','root')])
md = json.load(open('tests/sample_matchday.json', encoding='utf-8'))
b = MatchBuilder(db); plan = b.build(md, datetime.date(2032,7,10))
b.write_root(os.path.join(g,'SiderAddons','livecpk','matchday'))
open(os.path.join(g,'SiderAddons','matchday','request.txt'),'w',encoding='utf-8').write(request_lines(md, plan, 'Friendly', '10 Jul 2032'))
print(open(os.path.join(g,'SiderAddons','matchday','request.txt'),encoding='utf-8').read())
"@ | .\.venv\Scripts\python.exe -
Start-Process -FilePath "$g\FL 2026 start.exe" -WorkingDirectory $g
Start-Sleep 80
Select-String -Path "$g\SiderAddons\sider.log" -Pattern "matchday" | ForEach-Object { $_.Line }
