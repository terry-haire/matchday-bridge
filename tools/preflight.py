"""Preflight: lay every sheet's rows and columns over each other and list what is unfinished.

Exit code 0 only when every cell is filled and verified and every cross-sheet reference resolves.
    python tools/preflight.py            -> full report
    python tools/preflight.py --summary  -> counts only
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEETS = os.path.join(ROOT, "sheets")
OPTIONAL = {"games": set(), "fm_structs": set(), "fm_attributes": set(), "pes_player_fields": set(),
            "ratings_map": set(), "positions_map": set(), "hooks": set(), "ui_text": set()}


def load_all():
    out = {}
    for f in sorted(os.listdir(SHEETS)):
        if f.endswith(".json"):
            out[f[:-5]] = json.load(open(os.path.join(SHEETS, f), encoding="utf-8"))
    return out


def main():
    sheets = load_all()
    problems = []
    ids = {name: {r["id"] for r in rows} for name, rows in sheets.items()}
    for name, rows in sheets.items():
        cols = sorted({k for r in rows for k in r})
        for r in rows:
            for c in cols:
                v = r.get(c, None)
                if c in OPTIONAL.get(name, set()):
                    continue
                if v is None or v == "" or v == [] or v == {}:
                    problems.append((name, r["id"], c, "empty" if c != "verified" else "UNVERIFIED"))
            if name == "hooks" and r.get("implemented") is False:
                problems.append((name, r["id"], "implemented", "NOT IMPLEMENTED"))
            ref = r.get("sheet_ref")
            if ref:
                sname, _, rid = ref.partition(":")
                if sname not in ids or rid not in ids[sname]:
                    problems.append((name, r["id"], "sheet_ref", f"dangling -> {ref}"))
    fm_names = {r["name"] for r in sheets.get("fm_attributes", [])}
    pes_names = {r["name"] for r in sheets.get("pes_player_fields", [])}
    for r in sheets.get("ratings_map", []):
        if r["pes_ability"] not in pes_names:
            problems.append(("ratings_map", r["id"], "pes_ability", f"unknown PES ability {r['pes_ability']}"))
        for k, w in r["weights"].items():
            if k not in fm_names:
                problems.append(("ratings_map", r["id"], "weights", f"unknown FM attribute {k}"))
        if abs(sum(r["weights"].values()) - 1.0) > 1e-6:
            problems.append(("ratings_map", r["id"], "weights", "weights do not sum to 1"))
    for r in sheets.get("positions_map", []):
        if "pos:" + r["pes_position"] not in pes_names:
            problems.append(("positions_map", r["id"], "pes_position", f"unknown PES position {r['pes_position']}"))
    total = sum(len(rows) * len({k for x in rows for k in x}) for rows in sheets.values())
    print(f"preflight: {len(sheets)} sheets, {sum(len(v) for v in sheets.values())} rows, {total} cells, "
          f"{len(problems)} open")
    if "--summary" not in sys.argv:
        for p in problems:
            print("  %-18s %-24s %-14s %s" % p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
