"""Offline checks of the squad builder against the local SPFL26 and PES 2021 installs (no game running needed)."""
import copy
import datetime
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bridge"))

import install  # noqa: E402
from fl26db import cstr  # noqa: E402
from gen_structs import SPARE_SLOTS as SLOTS  # noqa: E402
from spfl_build import MatchBuilder, request_lines  # noqa: E402
from spfl_db import PesDb  # noqa: E402

SPARE_SLOTS, PES_HOSTS = SLOTS["spfl26"], SLOTS["pes2021"]
SAMPLE = json.load(open(os.path.join(ROOT, "tests", "sample_matchday.json"), encoding="utf-8"))
DATE = datetime.date(2032, 7, 15)


def load_db():
    g = install.find_spfl26()
    assert g, "SP Football Life 2026 not found"
    return PesDb.load(g, [os.path.join(g, "SiderAddons", "livecpk", "root")])


def check_plan(db, b, plan, md):
    used = []
    for side in ("home", "away"):
        pl = plan[side]
        assert len(pl["ids"]) == len(md[side]["players"]), side
        used += pl["ids"]
        team_ids = {r["player"] for r in db.assignments(pl["spfl_team"])}
        assert set(pl["ids"]) <= team_ids, f"{side}: player not on the SPFL club (SPFL26 would drop him)"
        names = [cstr(db.player_rec(pid)[0x44:0x44 + 0x3d]) for pid in pl["ids"]]
        want = [p["name"] for p in md[side]["players"]]
        assert sorted(names) == sorted(want), (side, names, want)
        if pl["spare_slot"]:
            assert db.team_name(pl["spfl_team"]).lower() == md[side]["name"].lower(), side
    assert len(used) == len(set(used)), "an SPFL record is used twice"


def test_faces():
    """Players SPFL26 has at another club keep the club's records but show their own face; players it has no face
    for get the club's faceless records first (2026-10-11: Diogo Jota showed Virgil van Dijk's face)."""
    db = load_db()
    real = {pid for pid in db.player_index if pid % 3}          # a made-up face list: every id not divisible by 3
    gomez = next(pid for pid in db.player_index if db.player_name(pid) == "Joe Gomez")
    kelleher = next(pid for pid in db.player_index if db.player_name(pid) == "Caoimhin Kelleher")
    real.add(kelleher)
    md = copy.deepcopy(SAMPLE)
    md["home"]["players"][1] = {**md["home"]["players"][1], "name": "Joe Gomez", "dob": "1997-05-23"}
    md["home"]["players"][2] = {**md["home"]["players"][2], "name": "Caoimhin Kelleher", "dob": "1998-11-23"}
    b = MatchBuilder(db, real)
    plan = b.build(md, DATE)
    check_plan(db, b, plan, md)
    ids = dict(zip((p["name"] for p in plan["home"]["players"]), plan["home"]["ids"]))
    assert gomez not in plan["home"]["ids"] and ids["Caoimhin Kelleher"] != kelleher   # not Atlanta's records
    assert b.face_lends.get(ids["Caoimhin Kelleher"]) == kelleher, b.face_lends
    for side in ("home", "away"):
        pool = [r["player"] for r in db.assignments(plan[side]["spfl_team"])]
        faceless = [p for p in pool if p not in real]
        lent = [pid for pid in plan[side]["ids"] if pid not in b.face_lends]
        # players with no SPFL face take the club's faceless records before any record with a real face
        assert all(p in lent for p in faceless[:len(lent)]) or all(p not in real for p in lent), side
        for p, pid in zip(plan[side]["players"], plan[side]["ids"]):
            if pid in b.face_lends:
                continue
            if pid in real and p["name"] not in ("Joe Gomez",):       # never another player's real face
                assert pid in b.hidden_faces and pid in plan[side]["noface"], (side, p["name"], pid)
            own = [x for x in db.player_index if db.player_name(x) == p["name"]]
            if not own:                                                # not in SPFL26 at all: no portrait
                assert pid in b.blank_portraits, (side, p["name"], pid)
    req = request_lines(md, plan, "FM24", "15 Jul 2032")
    assert ("home_noface=" in req) == bool(plan["home"]["noface"])


def test_one_missing_club():
    db = load_db()
    b = MatchBuilder(db)
    plan = b.build(SAMPLE, DATE)
    assert not plan["home"]["spare_slot"] and plan["away"]["spare_slot"]
    assert plan["away"]["spfl_team"] == SPARE_SLOTS[0]
    check_plan(db, b, plan, SAMPLE)
    req = request_lines(SAMPLE, plan, "FM24", "15 Jul 2032")
    assert "away_rename=Oldham Athletic" in req and "home_rename" not in req


def test_both_clubs_missing():
    md = copy.deepcopy(SAMPLE)
    md["home"]["name"], md["home"]["short"] = "Birmingham Legion", "Birmingham Legion"
    md["home"]["players"] = md["home"]["players"][:17]
    db = load_db()
    b = MatchBuilder(db)
    plan = b.build(md, DATE)
    assert [plan[s]["spfl_team"] for s in ("home", "away")] == SPARE_SLOTS[:2]
    check_plan(db, b, plan, md)
    req = request_lines(md, plan, "FM24", "15 Jul 2032")
    assert "home_rename=Birmingham Legion" in req and "home_abbr=BIR" in req
    assert "away_rename=Oldham Athletic" in req


def test_club_name_matching():
    """FM24 names that differ from SPFL26's only by legal form or club-type words find the club; different clubs with
    a similar name do not (names from a 2024 FM24 database, 2026-10-11)."""
    b = MatchBuilder(load_db())
    find = lambda name, short="": b.db.team_name(t) if (t := b.find_team({"name": name, "short": short})) else None
    assert find("Galatasaray A.Ş.", "Galatasaray") == "Galatasaray SK"
    assert find("Fenerbahçe A.Ş.", "Fenerbahçe") == "Fenerbahçe SK"
    assert find("Almería", "Almería") == "UD Almería"
    assert find("Reggiana", "Reggiana") == "AC Reggiana 1919"
    assert find("FC Krasnodar", "Krasnodar") == "FK Krasnodar"
    assert find("Club Atlético Banfield", "Banfield") == "CA Banfield"
    for name, short in (("VfL Freiburg", "VfL Freiburg"), ("Malmö IK", "MIK"), ("Porto 2005", "Porto 2005"),
                        ("Club Atlético River Plate (Montevideo)", "River Plate"), ("CD Platense", "Platense (HON)"),
                        ("Sport Vereniging Uruguay", "SV Uruguay"), ("Clube Desportivo Montenegro", "CD Montenegro"),
                        ("United Services Portsmouth", "US Portsmouth"), ("FC Lazio", "FC Lazio"),
                        ("Oldham Athletic", "Oldham")):
        assert find(name, short) is None, (name, find(name, short))


def test_human_club_keeps_its_slot():
    """The spare slot's kits go with the slot: the human club must get the same one every match day, home or
    away, alone or with a missing opponent (user report 2026-10-11: Birmingham wore Oldham's kits)."""
    seen = []
    for home, away in (("Atlanta United FC", "Oldham Athletic"), ("Birmingham Legion", "Oldham Athletic"),
                       ("Oldham Athletic", "Birmingham Legion")):
        db = load_db()                                   # fresh per match day, like the bridge (builds rename slots)
        md = copy.deepcopy(SAMPLE)
        squads = {SAMPLE["home"]["name"]: SAMPLE["home"], SAMPLE["away"]["name"]: SAMPLE["away"]}
        for side, name in (("home", home), ("away", away)):
            src = squads.get(name) or SAMPLE["home"]
            md[side] = {**copy.deepcopy(src), "name": name, "short": name.split()[0], "human": name == "Oldham Athletic"}
            md[side]["players"] = md[side]["players"][:17]
        plan = MatchBuilder(db).build(md, DATE)
        mine = "home" if home == "Oldham Athletic" else "away"
        other = "away" if mine == "home" else "home"
        seen.append(plan[mine]["spfl_team"])
        if plan[other]["spare_slot"]:
            assert plan[other]["spfl_team"] == SPARE_SLOTS[1], (home, away, plan[other]["spfl_team"])
        check_plan(db, None, plan, md)
    assert seen == [SPARE_SLOTS[0]] * 3, seen


def load_pes_db():
    g = install.find_pes2021()
    assert g, "eFootball PES 2021 not found"
    return PesDb.load(g)


def test_pes_hosts():
    """PES 2021 LITE's Local Match only has five clubs: both FM24 clubs play in them, the human club in the first
    (Manchester United's slot) every time, under their FM24 names in PES capitals and without a league to pick."""
    md = copy.deepcopy(SAMPLE)
    md["away"]["human"] = True
    db = load_pes_db()
    b = MatchBuilder(db, None, "pes2021")
    plan = b.build(md, DATE)
    assert plan["away"]["spfl_team"] == PES_HOSTS[0] and plan["home"]["spfl_team"] == PES_HOSTS[1], plan
    assert plan["home"]["slot_name"] == "ARSENAL" and plan["away"]["spfl_name"] == "OLDHAM ATHLETIC"
    assert all(plan[s]["spare_slot"] and plan[s]["league"] == "" for s in ("home", "away"))
    check_plan(db, b, plan, md)
    req = request_lines(md, plan, "FM24", "15 Jul 2032")
    assert "away_rename=OLDHAM ATHLETIC" in req and "home_rename=ATLANTA UNITED FC" in req
    assert "home_where=\n" in req and "away_abbr=OLD" in req


def test_pes_own_club():
    """An FM24 club that is one of the five keeps its own slot (and its own players' records); "ARSENAL" is in PES
    2021 twice, the Local Match one (101) counts. Clubs the game has but Local Match can't pick get a host."""
    md = copy.deepcopy(SAMPLE)
    md["home"]["name"], md["home"]["short"] = "Manchester United", "Man Utd"
    md["away"]["name"], md["away"]["short"] = "Liverpool", "Liverpool"
    db = load_pes_db()
    b = MatchBuilder(db, None, "pes2021")
    assert b.find_team({"name": "Arsenal", "short": "Arsenal"}) == 101
    assert b.find_team({"name": "Liverpool", "short": "Liverpool"}) is None
    plan = b.build(md, DATE)
    assert plan["home"]["spfl_team"] == 100 and not plan["home"]["spare_slot"]
    assert plan["away"]["spfl_team"] == PES_HOSTS[1] and plan["away"]["spare_slot"]
    check_plan(db, b, plan, md)


def test_pes_player_names():
    """PES 2021 files players as "M. SALAH" (its Japanese name comes first): FM24's Mohamed Salah is still found, so
    his own face is lent to the record he plays in; his PES 2021 age (2020 database) matches his birth year."""
    db = load_pes_db()
    salah = 57123
    md = copy.deepcopy(SAMPLE)
    md["home"]["players"][9] = {**md["home"]["players"][9], "name": "Mohamed Salah", "first": "Mohamed",
                                "last": "Salah", "common": "", "dob": "1992-06-15"}
    b = MatchBuilder(db, {salah}, "pes2021")
    assert b._named(md["home"]["players"][9]) == [salah]
    plan = b.build(md, DATE)
    ids = dict(zip((p["name"] for p in plan["home"]["players"]), plan["home"]["ids"]))
    assert b.face_lends.get(ids["Mohamed Salah"]) == salah, b.face_lends
    check_plan(db, b, plan, md)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
