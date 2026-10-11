"""Elevated job: start research/job_e2e_two.py as a detached process (the runner stops jobs after 30 minutes,
the two-match test takes longer). Its output goes to research/e2e_two.log."""
import os
import subprocess
import sys

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
log = open(os.path.join(ROOT, "research", "e2e_two.log"), "w", encoding="utf-8")
p = subprocess.Popen([sys.executable, os.path.join(ROOT, "research", "job_e2e_two.py")], stdout=log,
                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=os.path.join(ROOT, "research"),
                     creationflags=0x00000008 | 0x00000200)
print("started", p.pid)
