import os, sys, time
ROOT = os.path.abspath(__file__).split(os.sep + "research" + os.sep)[0]
sys.path.insert(0, os.path.join(ROOT, "testkit"))
import spfl
spfl.set_test(match_minutes=2, extra_time=0, penalties=0)
time.sleep(2)
s = spfl.Spfl()
spfl.play_intro(s, time.time())
spfl.skip_match(to_menu=True)
time.sleep(3)
spfl.set_test(match_minutes=None)
print(open(os.path.join(spfl.MD, "result.txt")).read())
print(open(os.path.join(spfl.MD, "request.txt")).read())
