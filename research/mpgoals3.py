import json
players = [(s, n, int(m, 16), bytes.fromhex(b)) for s, n, m, b in json.load(open("mp_ft.json"))]
idx = {n: k for k, (s, n, m, b) in enumerate(players)}
tests = {"goals": {"Agostinho Santos": 1, "Nikola Raičević": 2, "Marc Cucurella": 1},
         "assists": {"Agostinho Santos": 1, "Nikola Raičević": 1, "Chris Rigg": 1},
         "yellows": {"Agostinho Santos": 1, "Ryan Harris": 1}}
for t, want in tests.items():
    for w in (1, 2, 4):
        hits = []
        for o in range(0, 0x1880 - w + 1):
            vals = [int.from_bytes(b[o:o+w], "little") for s, n, m, b in players]
            if all(vals[idx[n]] == v for n, v in want.items()):
                others = [vals[k] for k in range(len(players)) if players[k][1] not in want]
                nz = sum(1 for v in others if v)
                if nz <= 3 and max(others) <= 3:
                    hits.append((hex(o), nz, [ (players[k][1][:10], vals[k]) for k in range(len(players)) if players[k][1] not in want and vals[k]]))
        for h in hits[:10]: print(t, w, h)
