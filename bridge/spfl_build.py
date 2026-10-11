"""Builds the per-match SPFL26 database from an FM24 match day and writes it to a LiveCPK root.

Nothing from either game is shipped: the tables are read from the player's SPFL26 install and rewritten
with the FM24 squads the bridge just read from FM24's memory.
"""
from __future__ import annotations

import datetime
import os
import re
import struct
import unicodedata

from fl26db import (ASSIGN_REC, ORDER_SHIFT, PLAYER_ID_OFF, PLAYER_NAME_OFF, PLAYER_REC, POSITIONS, TEAM_NAME_LEN,
                    TEAM_NAME_OFF, TEAM_REC, getbits, name_slots, setbits, wesys_pack)
from gen_structs import (FM_POSITION_SLOTS, PES_LIVE_FIELDS, PES_PLAYER_FIELDS, RATINGS_MAP, SPARE_SLOTS,
                         SPFL_LIVE_PLAYER)
from spfl_db import PesDb

TEAM_ABBR_OFF, TEAM_ABBR_LEN = 0x372, 3
PLAYER_CAP = 30001  # unpatched FL26 player array (Matozanato/FootballLife-new-leagues docs)
SPFL_AGE_YEAR = 2025  # SPFL26 2.2 ages: birth year + age = 2025 for 32 of 38 FM24 players checked (2024 for the rest)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(fc|cf|afc|sc|ac|club|de|the)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# FM24 and SPFL26 write some clubs differently: "Galatasaray A.Ş." / "Galatasaray SK", "Almería" / "UD Almería",
# "Reggiana" / "AC Reggiana 1919". The second matching pass compares names without legal forms, club-type words and
# SPFL26's founding years, and accepts a club only when exactly one SPFL26 club has that name and the type words
# do not disagree ("VfL Freiburg" is not "SC Freiburg", "Malmö IK" is not "Malmö FF"). FM24's own years stay
# ("Porto 2005" is not FC Porto); reserve markers (B, II, U21) stay, so a reserve side never matches the first team.
TYPE_WORDS = {"fc", "fk", "cf", "afc", "sc", "ac", "club", "sk", "jk", "as", "sv", "tsv", "vfb", "vfl", "fsv", "if",
              "ik", "bk", "ff", "cd", "ud", "sd", "rcd", "ca", "sl", "ssc", "ss", "us", "calcio", "kulubu"}
SAME_TYPE = {"fk": "fc", "cf": "fc"}                   # one word in different languages
LEGAL = re.compile(r"\b(a s|s a d|s a|e v|s p a|sad|spa)\b")
YEAR = re.compile(r"\b(18|19|20)\d\d\b")


def club_words(s: str, drop_years: bool = False) -> tuple[str, frozenset]:
    """(name without legal forms and club-type words, the club-type words)."""
    t = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    t = LEGAL.sub(" ", re.sub(r"[^a-z0-9]+", " ", t))
    if drop_years:
        t = YEAR.sub(" ", t)
    words = t.split()
    return (" ".join(w for w in words if w not in TYPE_WORDS and w not in ("de", "the")),
            frozenset(SAME_TYPE.get(w, w) for w in words if w in TYPE_WORDS))


def fm_to_pes(v: float) -> int:
    return max(40, min(99, round(40 + (v - 5) / 95 * 59)))


def ability(attrs: dict, pes_name: str) -> int:
    return fm_to_pes(sum(attrs[k] * w for k, w in RATINGS_MAP[pes_name]))


def best_positions(pl: dict) -> tuple[int, dict]:
    """PES registered position + playable ratings (0/1/2) from FM's 15 position ratings."""
    ratings = {p: 0 for p in POSITIONS}
    fm = pl.get("positions")
    if not fm:  # FM virtual player: infer from attributes
        a = pl["attrs"]
        if a["Handling"] >= 30 and a["Reflexes"] >= 30:
            fm = {"GK": 20}
        else:
            score = {"DC": a["Marking"] + a["Tackling"] + a["Heading"], "MC": a["Passing"] + a["Vision"] + a["Decisions"],
                     "ST": a["Finishing"] + a["Off The Ball"] + a["Composure"]}
            fm = {max(score, key=score.get): 20}
    reg, reg_val = "CMF", -1
    for code, pes in FM_POSITION_SLOTS:
        v = fm.get(code, 0) or 0
        r = 2 if v >= 18 else 1 if v >= 13 else 0
        ratings[pes] = max(ratings[pes], r)
        if v > reg_val:
            reg, reg_val = pes, v
    ratings[reg] = 2
    return POSITIONS.index(reg), ratings


def player_fields(pl: dict, match_date: datetime.date) -> tuple[dict[str, int], bytes]:
    """The FM24 player as PES values ({field: full value}, e.g. abilities 40-99, height in cm) and the four name
    slots. Values are kept inside what Player.bin can hold, so the file and the live game agree."""
    f: dict[str, int] = {}

    def setf(name, value):
        _, width, add = PES_PLAYER_FIELDS[name]
        f[name] = add + max(0, min((1 << width) - 1, int(value) - add))

    a = pl["attrs"]
    for pes_name in RATINGS_MAP:
        setf(pes_name, ability(a, pes_name))
    if pl.get("height"):
        setf("Height", pl["height"])
    if pl.get("weight"):
        setf("Weight", pl["weight"])
    if pl.get("dob"):
        dob = datetime.date.fromisoformat(pl["dob"])
        age = match_date.year - dob.year - ((match_date.month, match_date.day) < (dob.month, dob.day))
        setf("Age", max(15, min(78, age)))
    left, right = a["Left Foot"], a["Right Foot"]
    setf("Stronger Foot", 1 if left > right else 0)
    weak = min(left, right)
    weak_level = 3 if weak >= 75 else 2 if weak >= 55 else 1 if weak >= 35 else 0
    setf("Weak Foot Usage", weak_level)
    setf("Weak Foot Accuracy", weak_level)
    reg, ratings = best_positions(pl)
    setf("Registered Position", reg)
    for pos, r in ratings.items():
        setf("pos:" + pos, r)
    full = pl["name"]
    shirt = (pl.get("last") or full.split(" ")[-1]).upper()
    return f, name_slots(full, shirt)


def write_player(rec: bytearray, pl: dict, match_date: datetime.date):
    """Player.bin record (fields stored minus their offset)."""
    fields, names = player_fields(pl, match_date)
    for name, value in fields.items():
        bit, width, add = PES_PLAYER_FIELDS[name]
        setbits(rec, bit, width, value - add)
    rec[PLAYER_NAME_OFF:PLAYER_NAME_OFF + 4 * 0x3D] = names


def write_live_player(rec: bytearray, pl: dict, match_date: datetime.date):
    """Live edit-block player record of a running SPFL26 (fields hold the full value)."""
    fields, names = player_fields(pl, match_date)
    for name, value in fields.items():
        bit, width = PES_LIVE_FIELDS[name]
        setbits(rec, bit, width, max(0, min((1 << width) - 1, value)))
    rec[SPFL_LIVE_PLAYER.NAMES:SPFL_LIVE_PLAYER.NAMES + 4 * 0x3D] = names


class MatchBuilder:
    def __init__(self, db: PesDb, real_faces: set[int] | None = None):
        """real_faces: SPFL26 player ids with a real head (spfl_faces); None = unknown (records are lent as before)."""
        self.db = db
        self.real_faces = real_faces
        self.by_name: dict[str, list[int]] = {}
        for pid, i in db.player_index.items():
            nm = db.player[i + PLAYER_NAME_OFF:i + PLAYER_NAME_OFF + 0x3D].split(b"\0")[0].decode("utf-8", "replace")
            self.by_name.setdefault(norm(nm), []).append(pid)
        self.teams_of: dict[int, set[int]] = {}
        for i in range(0, len(db.assign), ASSIGN_REC):
            _, pid, tid, _ = struct.unpack_from("<IIII", db.assign, i)
            self.teams_of.setdefault(pid, set()).add(tid)
        self.used: set[int] = set()                     # records given to an FM24 player of either side
        self.team_by_name: dict[str, int] = {}
        self.team_by_core: dict[str, list[tuple[int, frozenset]]] = {}
        for tid in db.team_index:
            self.team_by_name.setdefault(norm(db.team_name(tid)), tid)
            core, types = club_words(db.team_name(tid), drop_years=True)
            if core:
                self.team_by_core.setdefault(core, []).append((tid, types))
        self.next_pid = max(db.player_index) + 1
        self.next_row = max(struct.unpack_from("<I", db.assign, i)[0] for i in range(0, len(db.assign), ASSIGN_REC)) + 1
        self.log: list[str] = []
        self.assigned: list[tuple[int, dict, datetime.date]] = []     # (SPFL player id, FM player, match date)
        self.face_lends: dict[int, int] = {}       # borrowed record -> the FM24 player's own record (face + portrait)
        self.portrait_lends: dict[int, int] = {}   # borrowed record -> the FM24 player's own record (portrait only)
        self.hidden_faces: set[int] = set()        # borrowed records whose real face SPFL26 must not show
        self.blank_portraits: set[int] = set()     # borrowed records of FM24 players SPFL26 does not have

    def find_team(self, fm_team: dict) -> int | None:
        name, short = fm_team["name"], fm_team.get("short", "")
        for key in (name, short):
            tid = self.team_by_name.get(norm(key))
            if tid:
                return tid
        if "(" in name + short:                             # FM's "(Montevideo)", "(HON)": another club of that name
            return None
        tries = [club_words(name)]
        if short and not club_words(short)[1]:              # "Galatasaray", not "SV Uruguay" / "US Portsmouth"
            tries.append(club_words(short))
        for core, types in tries:
            hits = self.team_by_core.get(core, [])
            if len(hits) == 1 and (types <= hits[0][1] or hits[0][1] <= types):
                return hits[0][0]
        return None

    def template_for(self, team_id: int, want_gk: bool) -> bytes:
        rows = self.db.assignments(team_id)
        for r in rows:
            rec = self.db.player_rec(r["player"])
            is_gk = getbits(rec, *PES_PLAYER_FIELDS["Registered Position"][:2]) == 0
            if is_gk == want_gk:
                return bytes(rec)
        return bytes(self.db.player_rec(rows[0]["player"]))

    def new_player(self, template: bytes) -> tuple[int, bytearray]:
        if len(self.db.player) // PLAYER_REC >= PLAYER_CAP:
            raise RuntimeError("SPFL26 player table is full")
        pid = self.next_pid
        self.next_pid += 1
        rec = bytearray(template)
        struct.pack_into("<I", rec, PLAYER_ID_OFF, pid)
        self.db.player += rec
        self.db.player_index[pid] = len(self.db.player) - PLAYER_REC
        return pid, rec

    def put_squad(self, team_id: int, fm_team: dict, match_date: datetime.date, rename: bool,
                  match_teams: frozenset = frozenset()):
        """Write the FM24 match squad into this club's own SPFL26 player records. SPFL26 builds a club's squad from
        the players registered at it when the club is picked (records of other clubs are dropped; brand-new ids hang
        the pre-match screen), so every FM24 player uses one of these records: his own when SPFL26 has him at this
        club, else a stand-in. A stand-in keeps its id, and SPFL26 shows faces by id, so: an FM24 player SPFL26 has
        with a real face elsewhere gets that face and portrait (face_lends); otherwise the stand-in's own real face is
        hidden (hidden_faces: matchday.lua hides its files, SPFL26 builds a generic head) and the menu shows his own
        SPFL26 portrait (portrait_lends) or, for a player SPFL26 does not have at all, no portrait (blank_portraits).
        Stand-ins without a real face go to players without one first, so fewer faces need hiding."""
        db = self.db
        if rename:
            i = db.team_index[team_id]
            db.team[i + TEAM_NAME_OFF:i + TEAM_NAME_OFF + TEAM_NAME_LEN] = \
                fm_team["name"].encode("utf-8")[:TEAM_NAME_LEN - 1].ljust(TEAM_NAME_LEN, b"\0")
            abbr = re.sub(r"[^A-Z]", "", fm_team.get("short", fm_team["name"]).upper())[:3] or "FMC"
            db.team[i + TEAM_ABBR_OFF:i + TEAM_ABBR_OFF + TEAM_ABBR_LEN] = abbr.encode().ljust(3, b"\0")
        pool = [r["player"] for r in db.assignments(team_id)]
        starters = sorted([p for p in fm_team["players"] if p["slot"] < 11], key=self._line_order)
        subs = [p for p in fm_team["players"] if p["slot"] >= 11]
        squad = (starters + subs)[:len(pool)]
        if len(squad) < len(starters + subs):
            self.log.append(f"{fm_team['name']}: SPFL slot only has {len(pool)} players, dropped the last subs")
        chosen: dict[int, tuple[int, str]] = {}
        for k, pl in enumerate(squad):
            own = [] if rename else [p for p in self.by_name.get(norm(pl["name"]), []) if p in pool and p not in self.used]
            if own:
                chosen[k] = (own[0], "own SPFL record")
                self.used.add(own[0])
        faces = self.real_faces
        elsewhere = {k: self._record_elsewhere(pl, pool) for k, pl in enumerate(squad) if k not in chosen}
        # players SPFL26 has no face for take the faceless records first; the others get their own face lent
        order = sorted(elsewhere, key=lambda k: faces is not None and elsewhere[k] in faces)
        for k in order:
            pl, src = squad[k], elsewhere[k]
            pid = self._stand_in(pool, best_positions(pl)[0] == 0)
            self.used.add(pid)
            how = "took over SPFL record"
            if faces is not None and src in faces:
                self.face_lends[pid] = src
                how += f", shows his own SPFL face ({src})"
            elif faces is not None:
                if pid in faces:
                    self.hidden_faces.add(pid)
                    how += ", its real face hidden (generic head)"
                if src:
                    self.portrait_lends[pid] = src
                    how += f", his own SPFL portrait ({src})"
                else:
                    self.blank_portraits.add(pid)
                    how += ", not in SPFL26: no portrait"
            chosen[k] = (pid, how)
        squad_ids, shirts, info = [], [], []
        for k, pl in enumerate(squad):
            pid, how = chosen[k]
            rec = db.player_rec(pid)
            write_player(rec, pl, match_date)
            i = db.player_index[pid]
            db.player[i:i + PLAYER_REC] = rec
            self.assigned.append((pid, pl, match_date))
            squad_ids.append(pid)
            shirts.append(k + 1)
            info.append({"spfl_id": pid, "shirt": k + 1, "name": pl["name"], "fm_pid": pl.get("pid"),
                         "gk": best_positions(pl)[0] == 0, "starter": pl["slot"] < 11})
            self.log.append(f"{fm_team['name']}: #{k + 1} {pl['name']} -> {pid} ({how})")
        return squad_ids, shirts, info

    def _age_ok(self, pid: int, pl: dict) -> bool:
        if not pl.get("dob"):
            return True
        bit, width, add = PES_PLAYER_FIELDS["Age"]
        born = SPFL_AGE_YEAR - (getbits(self.db.player_rec(pid), bit, width) + add)
        return abs(int(pl["dob"][:4]) - born) <= 1

    def _record_elsewhere(self, pl: dict, pool: list[int]) -> int | None:
        """The FM24 player's SPFL26 record at another club (or none): the only record of that name with his birth
        year (+/- 1)."""
        cands = [p for p in self.by_name.get(norm(pl["name"]), []) if p not in pool and self._age_ok(p, pl)]
        return cands[0] if len(cands) == 1 else None

    def _is_gk(self, pid: int) -> bool:
        return getbits(self.db.player_rec(pid), *PES_PLAYER_FIELDS["Registered Position"][:2]) == 0

    def _stand_in(self, pool: list[int], want_gk: bool) -> int:
        """A free record of this club: without a real face first, a goalkeeper's for a goalkeeper when possible."""
        free = [p for p in pool if p not in self.used]
        if not free:
            raise RuntimeError("no SPFL26 player record left to lend")
        faces = self.real_faces or set()
        groups = ([p for p in free if p not in faces], [p for p in free if p in faces])
        for cands in groups:
            for gk_only in (True, False):
                for p in cands:
                    if not gk_only or self._is_gk(p) == want_gk:
                        return p
        return free[0]

    @staticmethod
    def _line_order(pl):
        reg = best_positions(pl)[0]
        line = {0: 0, 1: 1, 3: 2, 2: 3, 4: 4, 5: 5, 7: 6, 6: 7, 8: 8, 10: 9, 9: 10, 11: 11, 12: 12}
        return line.get(reg, 6)

    def build(self, md: dict, match_date: datetime.date) -> dict:
        plan = {}
        found = {side: self.find_team(md[side]) for side in ("home", "away")}
        if found["home"] is not None and found["home"] == found["away"]:
            found["away"] = None                       # two FM clubs with the same name: lend the away one a slot
        spares = [t for t in SPARE_SLOTS if t in self.db.team_index and t not in found.values()]
        # A spare slot's plain kits belong to the slot, so the human club takes the first spare every match day
        # (same kits each time) and the opponent the next one, whichever side either of them plays on.
        slot = {}
        for side in sorted((s for s in ("home", "away") if found[s] is None), key=lambda s: not md[s].get("human")):
            if not spares:
                raise RuntimeError("both clubs are missing from SPFL26 and no spare slot is left")
            slot[side] = spares.pop(0)
        teams = {side: slot[side] if side in slot else found[side] for side in ("home", "away")}
        for side in ("home", "away"):
            fm_team = md[side]
            rename = side in slot
            tid = teams[side]
            ids, shirts, info = self.put_squad(tid, fm_team, match_date, rename, frozenset(teams.values()))
            league = self.db.menu_league(tid)
            abbr = re.sub(r"[^A-Z]", "", fm_team.get("short", fm_team["name"]).upper())[:3] if rename else ""
            plan[side] = {"fm_name": fm_team["name"], "spfl_team": tid, "spfl_name": self.db.team_name(tid),
                          "spare_slot": rename, "ids": ids, "shirts": shirts, "abbr": abbr, "players": info,
                          "league": league, "human": bool(fm_team.get("human")),
                          "noface": [pid for pid in ids if pid in self.hidden_faces]}
        return plan

    def write_root(self, root: str):
        d = os.path.join(root, "common", "etc", "pesdb")
        os.makedirs(d, exist_ok=True)
        for name, data in (("Player", self.db.player), ("PlayerAssignment", self.db.assign), ("Team", self.db.team)):
            open(os.path.join(d, name + ".bin"), "wb").write(wesys_pack(bytes(data)))


def request_lines(md: dict, plan: dict, comp: str, date: str) -> str:
    """The text file the Sider module reads (key=value per line)."""
    req = {"home": md["home"]["name"], "away": md["away"]["name"], "comp": comp, "date": date, "fm_installed": "1"}
    for side in ("home", "away"):
        pl = plan[side]
        req[f"{side}_spfl"] = pl["spfl_name"]
        req[f"{side}_league"] = pl.get("league", "")
        req[f"{side}_tid"] = pl["spfl_team"]
        req[f"{side}_ids"] = ",".join(str(x) for x in pl["ids"])
        req[f"{side}_shirts"] = ",".join(str(x) for x in pl["shirts"])
        if pl.get("noface"):
            req[f"{side}_noface"] = ",".join(str(x) for x in pl["noface"])
        if pl["spare_slot"]:
            req[f"{side}_rename"] = pl["fm_name"]
            req[f"{side}_abbr"] = pl["abbr"]
    return "".join(f"{k}={v}\n" for k, v in req.items())
