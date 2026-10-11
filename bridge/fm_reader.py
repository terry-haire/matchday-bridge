"""Reads the human club's match-day squads from a running FM24 (data only, never writes)."""
from __future__ import annotations

import datetime
import struct
import time

from gen_structs import (ACTUAL_PLAYER, CLUB, FM_ATTRIBUTES, FM_POSITION_SLOTS, FULL_CONTRACT, GAME_MATCH,
                         HUMAN_NON_PLAYER, MATCH_PLAYER, MATCH_TEAM, PLAYER, TEAM)
from procmem import Proc

ROSTER_SLOTS = 64       # both match squads in one null-terminated list: up to 26 per side seen (11 + 15 subs)


class FmReader:
    def __init__(self):
        self.p = Proc("fm.exe")
        self.vt_game_match = self.p.vtables(".?AVGAME_MATCH@@")[0]
        self.vt_match_player = self.p.vtables(".?AVMATCH_PLAYER@simatch@@")[0]
        self.vt_actual_player = self.p.vtables(".?AVACTUAL_PLAYER@db@@")[0]

    # ------------------------------------------------------------ strings
    def fm_string(self, ptr: int) -> str:
        if not ptr:
            return ""
        n = self.p.u32(ptr)
        if n > 400:
            return ""
        return self.p.read(ptr + 4, n).decode("utf-8", "replace")

    def name_ref(self, field_ptr: int) -> str:
        if not field_ptr:
            return ""
        return self.fm_string(self.p.u64(field_ptr))

    # ------------------------------------------------------------ objects
    def complete_object(self, sub: int) -> int | None:
        """MSVC: the vtable's CompleteObjectLocator stores this sub-object's offset in the full object."""
        try:
            col = self.p.u64(self.p.u64(sub) - 8)
            if not (self.p.base <= col < self.p.base + self.p.size):
                return None
            return sub - self.p.u32(col + 4)
        except OSError:
            return None

    def find_game_matches(self) -> list[int]:
        return self.p.find_qword(self.vt_game_match, limit=32)

    def find_game_match(self) -> int | None:
        """The GAME_MATCH of a match your club plays (FM also builds them for other clubs' matches)."""
        found = self.find_human_game_matches()
        return found[0] if found else None

    def find_human_game_matches(self) -> list[int]:
        """Every GAME_MATCH your club plays in: after a match day FM can keep the last one next to the new one."""
        mine = self.human_teams()
        out = []
        for gm in self.find_game_matches():
            try:
                if mine & set(self.side_teams(gm).values()):
                    out.append(gm)
            except OSError:
                continue
        return out

    def human_teams(self) -> set[int]:
        """TEAM* of every club a human manager is employed by (cached for a minute)."""
        if getattr(self, "_human", None) and time.time() - self._human[0] < 60:
            return self._human[1]
        teams = set()
        vt = self.p.vtables(".?AVHUMAN_NON_PLAYER@db@@")
        for h in self.p.find_qword(vt[0], limit=16) if vt else []:
            try:
                contract = self.p.u64(h + HUMAN_NON_PLAYER.CONTRACT)
                if contract:
                    t = self.p.u64(contract + FULL_CONTRACT.TEAM)
                    if t:
                        teams.add(t)
            except OSError:
                continue
        self._human = (time.time(), teams)
        return teams

    def match_players(self, gm: int) -> list[int]:
        out = []
        vt = struct.pack("<Q", self.vt_match_player)
        for (mp,) in struct.iter_unpack("<Q", self.p.read(gm + GAME_MATCH.ROSTER, 8 * ROSTER_SLOTS)):
            if not mp:
                break
            if self.p.try_read(mp, 8) == vt:
                out.append(mp)
        return out

    def player_team(self, mp: int) -> int:
        mt = self.p.u64(mp + MATCH_PLAYER.MATCH_TEAM)
        return self.p.u64(mt + MATCH_TEAM.TEAM) if mt else 0

    def side_teams(self, gm: int) -> dict[int, int]:
        """{0: home TEAM*, 1: away TEAM*}. FM lists the home squad first."""
        teams: list[int] = []
        for mp in self.match_players(gm):
            t = self.player_team(mp)
            if t and t not in teams:
                teams.append(t)
            if len(teams) == 2:
                break
        return dict(enumerate(teams))

    def player(self, base: int) -> dict:
        p = self.p
        b = p.read(base, 0x3E8)
        first = self.name_ref(struct.unpack_from("<Q", b, ACTUAL_PLAYER.FIRST_NAME)[0])
        last = self.name_ref(struct.unpack_from("<Q", b, ACTUAL_PLAYER.SECOND_NAME)[0])
        common = self.name_ref(struct.unpack_from("<Q", b, ACTUAL_PLAYER.COMMON_NAME)[0])
        doy, year = struct.unpack_from("<HH", b, ACTUAL_PLAYER.DATE_OF_BIRTH)
        try:
            dob = datetime.date(year, 1, 1) + datetime.timedelta(days=(doy & 0x1FF) - 1)
        except ValueError:
            dob = None
        return {
            "first": first, "last": last, "common": common,
            "name": common or f"{first} {last}".strip(),
            "dob": dob.isoformat() if dob else None,
            "height": struct.unpack_from("<H", b, ACTUAL_PLAYER.HEIGHT_CM)[0],
            "weight": b[ACTUAL_PLAYER.WEIGHT_KG],
            "ca": struct.unpack_from("<H", b, ACTUAL_PLAYER.CURRENT_ABILITY)[0],
            "pa": struct.unpack_from("<H", b, ACTUAL_PLAYER.POTENTIAL_ABILITY)[0],
            "attrs": {k: b[off] for k, off in FM_ATTRIBUTES.items()},
            "positions": {code: b[ACTUAL_PLAYER.POSITION_RATINGS + i] for i, (code, _) in enumerate(FM_POSITION_SLOTS)},
        }

    def team(self, team_ptr: int) -> dict:
        club = self.p.u64(team_ptr + TEAM.CLUB)
        return {"name": self.fm_string(self.p.u64(club + CLUB.NAME)),
                "short": self.fm_string(self.p.u64(club + CLUB.SHORT_NAME)),
                "club_id": self.p.u32(club + CLUB.UNIQUE_ID)}

    def roster(self, gm: int, team_ptr: int) -> tuple[dict, list[dict]]:
        out = []
        for mp in self.match_players(gm):
            if self.player_team(mp) != team_ptr:
                continue
            attrs = self.p.read(mp + MATCH_PLAYER.ATTRIBUTES, 54)
            sub = self.p.u64(mp + MATCH_PLAYER.ACTUAL_PLAYER_SUB)
            base = self.complete_object(sub)
            if base and self.p.u64(base) == self.vt_actual_player:
                pl = self.player(base)
                pl["kind"] = "actual"
            else:
                pl = {"first": "", "last": "", "common": "", "dob": None, "height": None, "weight": None,
                      "ca": None, "pa": None, "positions": None, "kind": "virtual"}
            pl["pid"] = (self.p.u32(sub + PLAYER.PERSON_ID) or None) if sub else None
            pl["attrs"] = {k: attrs[off_ - ACTUAL_PLAYER.ATTRIBUTES] for k, off_ in FM_ATTRIBUTES.items()}
            pl["slot"] = self.p.u8(mp + MATCH_PLAYER.SHEET_SLOT)
            pl["match_name"] = self.fm_string(self.p.u64(mp + MATCH_PLAYER.FULL_NAME))
            if not pl.get("name"):
                pl["name"] = pl["match_name"]
            out.append(pl)
        out.sort(key=lambda r: r["slot"])
        team = self.team(team_ptr) if team_ptr else {"name": "?", "short": "?"}
        team["team_ptr"] = team_ptr
        return team, out

    def matchday(self, skip=None) -> dict | None:
        """Today's match day; `skip`: a match_key already handled (FM may still hold that match's GAME_MATCH
        next to the new one), so the other one is returned. When there is none, `self.why` says why."""
        found = self.find_human_game_matches()
        self.why = "no match of your club in FM24's memory yet (it appears from Team News on)"
        for gm in found:
            try:
                md = self._matchday(gm)
            except OSError as e:
                self.why = f"your club's match could not be read ({e})"
                continue
            if md and (skip is None or match_key(md) != skip):
                return md
            if md:
                self.why = f"{md['home']['name']} v {md['away']['name']} was already handled"
        return None

    def _matchday(self, gm: int) -> dict | None:
        teams = self.side_teams(gm)
        if len(teams) < 2:
            self.why = "your club's match has only one squad in FM24's memory"
            return None
        home_team, home = self.roster(gm, teams[0])
        away_team, away = self.roster(gm, teams[1])
        if len(home) < 11 or len(away) < 11:
            self.why = (f"{home_team['name']} v {away_team['name']}: {len(home)} and {len(away)} players read, "
                        "11 needed on each side")
            return None
        mine = self.human_teams()
        return {"source": "fm24", "home": {**home_team, "players": home, "human": teams[0] in mine},
                "away": {**away_team, "players": away, "human": teams[1] in mine}}


def match_key(md: dict) -> tuple:
    """Identifies one match day: both clubs and the home team sheet."""
    return md["home"]["name"], md["away"]["name"], tuple(p["name"] for p in md["home"]["players"])


if __name__ == "__main__":
    import json
    import sys
    md = FmReader().matchday()
    json.dump(md, sys.stdout, indent=1, ensure_ascii=False)

