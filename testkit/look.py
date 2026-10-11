"""Print what's on screen: python testkit/look.py spfl|fm [--save NAME]"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import win  # noqa: E402

TITLES = {"spfl": "SP Football Life 2026", "fm": "Football Manager 2024"}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("game", choices=TITLES)
    ap.add_argument("--save")
    a = ap.parse_args()
    h = win.find_window(TITLES[a.game])
    img = win.capture(h, 2.0)          # background capture: no focus change
    t = time.time()
    lines = win.ocr(img)
    print(f"size {img.size} ocr {time.time() - t:.2f}s")
    for ln in lines:
        print(f"  ({int(ln[0].x)},{int(ln[0].y)}) " + " ".join(w.text for w in ln))
    if a.save:
        img.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "research", "shots", a.save + ".png"))
