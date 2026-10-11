"""Offline checks of own-goal handling: SPFL26's caption -> scorer reader -> FM event list (no game needed)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bridge"))

import spfl_scorers  # noqa: E402
from fm_writer import EV_GOAL, EV_OWN_GOAL, merge_events  # noqa: E402

PLAN = {"home": {"fm_name": "Atlanta United FC", "spfl_name": "Atlanta United FC",
                 "players": [{"name": "Juan Torres", "shirt": 5, "fm_pid": 105},
                             {"name": "Tim Penfold", "shirt": 9, "fm_pid": 109}]},
        "away": {"fm_name": "Oldham Athletic", "spfl_name": "Oldham Athletic",
                 "players": [{"name": "Ryan Harris", "shirt": 47, "fm_pid": 247},
                             {"name": "Emili Illa", "shirt": 4, "fm_pid": 204}]}}


def read_with_caption(lines, side):
    spfl_scorers._window = lambda: 0
    spfl_scorers.caption_lines = lambda frames=None: lines
    return spfl_scorers.ScorerReader(PLAN).read(side, timeout=0.6)


def test_caption_reader():
    assert read_with_caption(["47 Ryan Harris", "GOAL 1"], 1)["fm_pid"] == 247
    og = read_with_caption(["5 Juan Torres", "OWN GOAL"], 1)          # away goal, home player's own goal
    assert og["own_goal"] and og["fm_pid"] == 105, og
    og = read_with_caption(["4 Emili Illa OWN GOAL"], 0)
    assert og["own_goal"] and og["fm_pid"] == 204, og
    assert read_with_caption(["OWN GOAL"], 0) == {"own_goal": True}
    assert read_with_caption(["QATAR AIRWAYS"], 0) is None


def test_event_list():
    goals = [{"side": 0, "minute": 10, "pid": 109, "own": False},
             {"side": 0, "minute": 20, "pid": 204, "own": True},
             {"side": 1, "minute": 30, "pid": None, "own": True},
             {"side": 1, "minute": 40, "pid": 247}]
    ev = merge_events(goals, [(999, 0, 3, 50)], {0: [109], 1: [247]}, {0: [111], 1: [222]})
    assert ev == [(109, 0, EV_GOAL, 10), (204, 0, EV_OWN_GOAL, 20), (111, 1, EV_OWN_GOAL, 30),
                  (247, 1, EV_GOAL, 40), (999, 0, 3, 50)], ev


def test_own_goal_fallback():
    import matchday_bridge as mb
    md = {"home": {"players": [{"slot": 0, "pid": 1, "positions": {"GK": 20}, "attrs": {}},
                               {"slot": 1, "pid": 2, "positions": {"ST": 20}, "attrs": {}},
                               {"slot": 2, "pid": 3, "positions": {"DC": 20}, "attrs": {}},
                               {"slot": 12, "pid": 4, "positions": {"DC": 20}, "attrs": {}}]},
          "away": {"players": []}}
    assert mb.own_goal_fallback(md) == {0: [3, 2], 1: []}


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
