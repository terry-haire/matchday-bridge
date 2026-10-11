$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
$ErrorActionPreference = "Continue"
Get-Process -Name FL_2026,sider -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.Id -Force; "killed $($_.Id) $($_.Name)" }
Start-Sleep 3
cd "$MDB"
$env:PYTHONIOENCODING = "utf-8"
@"
import sys, json, datetime
sys.path.insert(0, 'bridge')
import install
from spfl_db import PesDb
from spfl_build import MatchBuilder
g = install.find_spfl26(); print('spfl', g, 'fm', install.find_fm24())
print(install.install_spfl(g))
import os
db = PesDb.load(g, [os.path.join(g,'SiderAddons','livecpk','root')])
md = json.load(open('tests/sample_matchday.json', encoding='utf-8'))
b = MatchBuilder(db); plan = b.build(md, datetime.date(2032,7,10))
b.write_root(os.path.join(g,'SiderAddons','livecpk','matchday'))
req = {'home': md['home']['name'], 'away': md['away']['name'], 'home_spfl': plan['home']['spfl_name'], 'away_spfl': plan['away']['spfl_name'], 'comp': 'Friendly', 'date': '10 Jul 2032', 'fm_installed': '1'}
open(os.path.join(g,'SiderAddons','matchday','request.txt'),'w',encoding='utf-8').write(''.join(f'{k}={v}\n' for k,v in req.items()))
print(json.dumps(plan, ensure_ascii=False))
"@ | .\.venv\Scripts\python.exe -
Select-String -Path "C:\Program Files (x86)\SP Football Life 2026\SiderAddons\sider.ini" -Pattern "matchday"
