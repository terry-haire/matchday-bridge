$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
& "$MDB\research\pesdrive.ps1" -Cmds "scanmode on;key 0x1B" -Wait 1 | Out-Null
cd "$MDB"
@"
import sys, struct
sys.path.insert(0, 'bridge')
from procmem import Proc
p = Proc('FL_2026.exe')
blk = p.u64(p.u64(0x143705e10) + 0x48)
print('block', hex(blk), 'counts', [p.u32(blk+o) for o in (0xd0bce8,0xd0bcec)])
TB = blk + 0xadf4bc
idx = None
for i in range(760):
    enc = p.u32(TB + i*0x690)
    if (enc >> 14) & 0x1ffff == 5736: idx = i; break
rec = p.read(TB + idx*0x690, 0x690)
print('atlanta slot', idx, rec[4:0x4a].split(b'\0')[0])
# find u32 values that are player ids present in Player table: scan for ascending small ints
ids = [struct.unpack_from('<I', rec, o)[0] for o in range(0, 0x690, 4)]
print([ (hex(o*4), v) for o, v in enumerate(ids) if 1000 < v < 300000][:60])
import pickle; pickle.dump(rec, open('research/dumps_pes_atl_team.bin','wb'))
"@ | .\.venv\Scripts\python.exe -
