$MDB = if ($env:MDB_ROOT) { $env:MDB_ROOT } else { ($PSScriptRoot -split '\\research')[0] }  # repo root
cd "$MDB"
$env:PYTHONIOENCODING = "utf-8"
@"
import sys, struct, numpy as np
sys.path.insert(0, 'bridge'); sys.path.insert(0, 'research')
from procmem import Proc
from pesx import decode_player
p = Proc('FL_2026.exe')
blk = p.u64(p.u64(0x143705e10) + 0x48)
n = p.u32(blk + 0xd0bce8)
raw = p.read(blk, n * 0x17c)
arr = np.frombuffer(raw[: len(raw)//4*4], dtype=np.uint32)
for pid in (184462, 106339, 110210, 184476):
    hits = np.nonzero(arr == pid)[0]
    offs = [int(h)*4 for h in hits]
    print(pid, [(o // 0x17c, hex(o % 0x17c)) for o in offs][:6])
    if offs:
        i = offs[0] // 0x17c; rec = raw[i*0x17c:(i+1)*0x17c]
        print('   rec', rec[:0x50].hex(' '))
        nm = rec.find(b'\0', 0x40)
        print('   text', [s for s in rec.split(b'\0') if len(s) > 3][:4])
"@ | .\.venv\Scripts\python.exe -
