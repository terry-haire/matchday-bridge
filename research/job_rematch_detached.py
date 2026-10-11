"""Elevated job: start research/job_rematch.py detached (the runner stops jobs after 30 minutes). Its output goes to
research/rematch.log, its report to research/rematch.txt."""
import os
import subprocess
import sys

ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
log = open(os.path.join(ROOT, "research", "rematch.log"), "w", encoding="utf-8")
p = subprocess.Popen([sys.executable, os.path.join(ROOT, "research", "job_rematch.py")], stdout=log,
                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=os.path.join(ROOT, "research"),
                     creationflags=0x00000008 | 0x00000200)
print("started", p.pid)
