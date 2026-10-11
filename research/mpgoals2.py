import json
players = [(s, n, int(m, 16), bytes.fromhex(b)) for s, n, m, b in json.load(open("mp_ft.json"))]
idx = {n: k for k, (s, n, m, b) in enumerate(players)}
def check(want, w, strict=True):
    out = []
    for o in range(0, 0x1880 - w + 1):
        vals = [int.from_bytes(b[o:o+w], "little") for s, n, m, b in players]
        if all(vals[idx[n]] == v for n, v in want.items()) and (not strict or all(vals[k] == 0 for k in range(len(players)) if players[k][1] not in want)):
            out.append(o)
    return out
tests = {"goals": {"Agostinho Santos": 1, "Nikola Raičević": 2, "Marc Cucurella": 1},
         "assists": {"Agostinho Santos": 1, "Nikola Raičević": 1, "Chris Rigg": 1},
         "yellows": {"Agostinho Santos": 1, "Ryan Harris": 1},
         "pens": {"Nikola Raičević": 1}}
for t, want in tests.items():
    for w in (1, 2, 4):
        r = check(want, w)
        if r: print(t, "w", w, [hex(o) for o in r][:20])
