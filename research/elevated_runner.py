"""Elevated job runner for research: executes jobs2/*.py (or *.ps1) and writes *.out next to them.

Started once with admin rights so scripts can read the elevated SPFL26 process and send it input.
Output goes to a file (not a pipe): a game launched by a job may inherit handles and must never block us.
Stops when jobs2/STOP exists.
"""
import os
import subprocess
import sys
import time

JOBS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs2")
PY = sys.executable
os.makedirs(JOBS, exist_ok=True)

while not os.path.exists(os.path.join(JOBS, "STOP")):
    for name in sorted(os.listdir(JOBS)):
        path = os.path.join(JOBS, name)
        if not (name.endswith(".py") or name.endswith(".ps1")) or os.path.exists(path + ".out") or os.path.exists(path + ".run"):
            continue
        open(path + ".run", "w").close()
        cmd = [PY, path] if name.endswith(".py") else ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path]
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        log = path + ".log"
        with open(log, "w", encoding="utf-8") as f:
            p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                 cwd=os.path.dirname(JOBS), env=env)
            try:
                rc = p.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                p.kill()
                rc = "timeout"
        out = open(log, encoding="utf-8", errors="replace").read()
        with open(path + ".out", "w", encoding="utf-8") as f:
            f.write(out + f"\n[exit {rc}]")
    time.sleep(0.2)
