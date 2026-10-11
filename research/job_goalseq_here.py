import os as _mdb_os
MDB = _mdb_os.environ.get("MDB_ROOT") or _mdb_os.path.abspath(__file__).split(_mdb_os.sep + "research" + _mdb_os.sep)[0]  # repo root
import os, runpy, sys
os.environ['GOALSEQ_HERE'] = '1'
os.environ['GOALSEQ_SCORERS'] = '110210,160819,148550'
sys.argv = ['job_goalseq.py']
runpy.run_path(MDB + r'\research\job_goalseq.py', run_name='__main__')
