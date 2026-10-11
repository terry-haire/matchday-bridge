import os, sys
ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "bridge"))
from spfl_drive import Driver, text_of
d = Driver({}, "home")
scr, lines = d.screen()
print(scr, "|", text_of(lines).replace("\n", " | ")[:300])
d.shot().save(os.path.join(ROOT, "research", "shots", "spfl_now.png"))
d.close()
