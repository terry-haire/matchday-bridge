$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
cd "$MDB"
$env:PYTHONIOENCODING = "utf-8"
@"
import sys, struct
sys.path.insert(0, 'bridge')
from procmem import Proc
p = Proc('FL_2026.exe')
blk = p.u64(p.u64(0x143705e10) + 0x48)
TB = blk + 0xadf4bc
for tid in (199, 5736):
    for i in range(760):
        enc = p.u32(TB + i*0x690)
        if (enc >> 14) & 0x1ffff == tid: break
    rec = p.read(TB + i*0x690, 0x690)
    print('== team', tid, 'slot', i, 'enc', hex(enc), 'name', rec[4:0x4a].split(b'\0')[0], 'abbr', rec[0x4a:0x4e])
    for o in range(0x140, 0x300, 16):
        print('  +%03x' % o, rec[o:o+16].hex(' '))
"@ | .\.venv\Scripts\python.exe -
