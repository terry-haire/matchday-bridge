"""Find the per-match player stats in FM24's MATCH_PLAYER objects.

Pauses FM's live match, reads the tactics table (player, GLS, RAT) by OCR, dumps every MATCH_PLAYER of the
match and reports offsets whose value equals each player's rating / goals (float or scaled ints).
Run with FM in a live match (fm.py to-match first). Writes research/mp_stats_dump.json.
"""
import json
import os
import re
import struct
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "testkit"))
sys.path.insert(0, os.path.join(ROOT, "bridge"))
import fm as F  # noqa: E402
import win  # noqa: E402
from fm_reader import FmReader  # noqa: E402

MP_SIZE = 0x1880


def table(fm: F.Fm) -> dict:
    """{player name: (goals, rating)} from the paused match's tactics table."""
    k = fm.k()
    rows: dict[int, list] = {}
    for ln in fm.lines:
        for w in ln:
            rows.setdefault(round((w.y + w.h / 2) / (14 * k)), []).append(w)
    out = {}
    for _, words in sorted(rows.items()):
        words.sort(key=lambda w: w.x)
        name = " ".join(w.text for w in words if 560 * k <= w.x < 860 * k).strip()
        rat = [w.text for w in words if w.x >= 1840 * k]
        gls = [w.text for w in words if 1800 * k <= w.x < 1840 * k]
        if name and rat and re.fullmatch(r"\d+\.\d\d", rat[-1]):
            g = gls[0] if gls else "-"
            out[name] = (int(g) if g.isdigit() else 0, float(rat[-1]))
    return out


def main():
    fm = F.Fm()
    if not any(fm.screen() == "match" or time.sleep(1) for _ in range(8)):
        raise SystemExit("no live match on screen")
    while (fm.clock() or 0) < int(sys.argv[1] if len(sys.argv) > 1 else 30) * 60:
        time.sleep(2)
        fm.screen()
    fm.key("space")                       # pause
    time.sleep(1.5)
    if not fm.click_text("TACTICS & SUBS"):
        fm.click_text("TACTICS")
    time.sleep(2.0)
    fm.read()
    fm.save("fm_mpstats_table")
    tab = table(fm)
    print("table:", tab)

    r = FmReader()
    gm = r.find_game_match()
    out = {"table": tab, "players": []}
    for mp in r.match_players(gm):
        name = r.fm_string(r.p.u64(mp + 0x30))
        blk = r.p.read(mp, MP_SIZE)
        out["players"].append({"mp": hex(mp), "name": name, "team": hex(r.player_team(mp)), "hex": blk.hex()})
    json.dump(out, open(os.path.join(ROOT, "research", "mp_stats_dump.json"), "w"))

    def key(n):
        return win.norm(n)
    known = []
    for pl in out["players"]:
        hit = next((v for n, v in tab.items() if key(n) == key(pl["name"]) or key(pl["name"]).endswith(key(n).split()[-1] if n.split() else "x")), None)
        if hit:
            known.append((pl, hit))
    print(f"{len(known)} players matched to the table")
    blks = [(bytes.fromhex(pl["hex"]), g, rt) for pl, (g, rt) in known]
    for off in range(0, MP_SIZE - 4):
        for kind in ("f32", "u8x10", "u16x10", "u16x100", "u8x20"):
            ok = 0
            for b, g, rt in blks:
                if kind == "f32":
                    v = struct.unpack_from("<f", b, off)[0]
                    good = abs(v - rt) < 0.051
                elif kind == "u8x10":
                    good = b[off] == round(rt * 10)
                elif kind == "u8x20":
                    good = b[off] == round(rt * 20)
                elif kind == "u16x10":
                    good = struct.unpack_from("<H", b, off)[0] == round(rt * 10)
                else:
                    good = struct.unpack_from("<H", b, off)[0] == round(rt * 100)
                ok += good
            if ok >= max(3, len(blks) - 1):
                print(f"rating candidate +{off:#x} {kind}: {ok}/{len(blks)}")
    goals = [g for _, g, _ in blks]
    if any(goals):
        for off in range(0, MP_SIZE):
            if all(b[off] == g for b, g, _ in blks):
                print(f"goals candidate +{off:#x} u8")


if __name__ == "__main__":
    main()
