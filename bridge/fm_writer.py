"""Puts the SPFL26 result into the running FM24 match: score, scorers (event list) and per-player goals/cards.

FM keeps several FIXTURE_RESULT copies of a fixture (same home TEAM*, away TEAM*, date). The match
engine counts goals in one live copy; when its state turns "finished" at full time, writing the score
there makes FM commit it to every copy when you leave the match. Copies are re-checked (class, both
teams, date) immediately before every write, so nothing else is ever touched.

Each copy's +0x70 points to its event vector {begin, end, capacity} of 8-byte entries
{u32 person id, u8 side (0 home, 1 away), u8 type, u16 minute}; types: 0 goal, 1 own goal (person = the player
who scored it, side = the team it counts for: 447 of 448 own-goal fixtures in a 2032 save add up that way),
2 penalty goal, 3 sent off.
A longer list than FM's own needs a bigger buffer: it is taken from FM's own CRT heap (remote malloc), so FM
can free it later like its own. Per-player match stats (GAME_MATCH_PLAYER_STATS, 0x100-byte records, person id
+0x10, goals u8 +0x7f, yellow cards u8 +0x9a) are edited only in the live record runs of today's match.
"""
from __future__ import annotations

import struct
import time
from collections import Counter

from gen_structs import FIXTURE, FIXTURE_RESULT, GAME_MATCH_PLAYER_STATS as GS
from procmem import Proc

NOT_PLAYED = 0xFF
EVENTS_PTR = FIXTURE_RESULT.EVENTS
EV_GOAL, EV_OWN_GOAL, EV_PENALTY, EV_RED = 0, 1, 2, 3
GOAL_TYPES = (EV_GOAL, EV_OWN_GOAL, EV_PENALTY)
STATS_REC = 0x100
STATS_PID, STATS_RATING, STATS_GOALS, STATS_YELLOW = GS.PERSON_ID, GS.RATING_X100, GS.GOALS, GS.YELLOW_CARDS


class FmResultWriter:
    def __init__(self, home_team: int, away_team: int):
        self.p = Proc("fm.exe", write=True, call=True)
        self.vt = self.p.vtables(".?AVFIXTURE_RESULT@sicomps@@")[0]
        self.home, self.away = home_team, away_team
        self.date: int | None = None
        self._known: list[int] = []
        self._scan_t = 0.0

    def copies(self, rescan: bool = False) -> list[dict]:
        """Every FIXTURE_RESULT of home v away (in that order), any date. Finding them is a scan of FM's memory
        (seconds); in between, the copies found last time are re-read (instant), with a new scan every 5 minutes
        or as soon as one of them is gone."""
        if not rescan and self._known and time.time() - self._scan_t < 300:
            out = [r for r in map(self._read, self._known) if r]
            if len(out) == len(self._known):
                return out
        out = []
        for ref in self.p.find_qword(self.home):
            base = ref - FIXTURE.HOME_TEAM
            rec = self._read(base)
            if rec:
                out.append(rec)
        self._known, self._scan_t = [c["addr"] for c in out], time.time()
        return out

    def _read(self, base: int) -> dict | None:
        b = self.p.try_read(base, FIXTURE_RESULT.STATE + 4)
        if not b:
            return None
        vt, home, away = struct.unpack_from("<QQQ", b, 0)
        if vt != self.vt or home != self.home or away != self.away:
            return None
        return {"addr": base, "date": struct.unpack_from("<I", b, FIXTURE.DATE)[0],
                "home_goals": b[FIXTURE_RESULT.HOME_GOALS], "away_goals": b[FIXTURE_RESULT.AWAY_GOALS],
                "state": b[FIXTURE_RESULT.STATE]}

    def lock_fixture(self) -> int | None:
        """At team news: today's fixture is the earliest home-v-away fixture not played yet."""
        unplayed = [c["date"] for c in self.copies() if c["state"] == 0]
        if unplayed:
            self.date = min(unplayed, key=lambda d: ((d >> 16) & 0xFFFF, d & 0x1FF))
        return self.date

    def apply(self, home_goals: int, away_goals: int) -> dict:
        """Writes the score into every finished copy of today's fixture. Returns what it saw/did."""
        seen = finished = written = matching = 0
        for c in self.copies():
            if c["date"] != self.date:
                continue
            seen += 1
            if c["state"] == 0:
                continue
            finished += 1
            if (c["home_goals"], c["away_goals"]) == (home_goals, away_goals):
                matching += 1
                continue
            again = self._read(c["addr"])
            if not again or again["date"] != self.date or again["state"] == 0:
                continue
            self.p.write(c["addr"] + FIXTURE_RESULT.HOME_GOALS, bytes([home_goals]))
            self.p.write(c["addr"] + FIXTURE_RESULT.AWAY_GOALS, bytes([away_goals]))
            written += 1
            matching += 1
        # At full time only the live copy is finished; once you leave the match FM finishes every copy.
        committed = seen > 1 and finished == seen and matching == seen
        return {"copies": seen, "finished": finished, "written": written, "committed": committed}

    # ------------------------------------------------------------ events (scorers, red cards)
    def events_of(self, c: dict) -> tuple[int, list[tuple[int, int, int, int]]]:
        """(vector struct address, entries) of a fixture copy."""
        vec = self.p.u64(c["addr"] + EVENTS_PTR)
        if not vec:
            return 0, []
        beg, end, cap = struct.unpack_from("<QQQ", self.p.read(vec, 24))
        if not beg or not beg <= end <= cap or end - beg > 0x800:
            return vec, []
        d = self.p.read(beg, end - beg) if end > beg else b""
        return vec, [struct.unpack_from("<IBBH", d, i) for i in range(0, len(d) - 7, 8)]

    def fm_events(self) -> list[tuple[int, int, int, int]]:
        """FM's own event list of today's (finished) match, before it is replaced."""
        for c in self.copies():
            if c["date"] == self.date and c["state"]:
                return self.events_of(c)[1]
        return []

    def apply_events(self, events: list[tuple[int, int, int, int]]) -> dict:
        """Replace the event list of every finished copy of today's fixture with `events`
        [(person id, side, type, minute)] in match order. Returns counts."""
        data = b"".join(struct.pack("<IBBH", pid & 0xFFFFFFFF, side, typ, min(minute, 0xFFFF))
                        for pid, side, typ, minute in events)
        done = grown = 0
        for c in self.copies():
            if c["date"] != self.date or c["state"] == 0:
                continue
            vec, cur = self.events_of(c)
            if not vec or cur == list(events):
                done += bool(vec)
                continue
            again = self._read(c["addr"])
            if not again or again["date"] != self.date or again["state"] == 0:
                continue
            beg, end, cap = struct.unpack_from("<QQQ", self.p.read(vec, 24))
            if beg and len(data) <= cap - beg:
                if data:
                    self.p.write(beg, data)
                self.p.write(vec + 8, struct.pack("<Q", beg + len(data)))
            else:
                # FM's own heap; the old buffer is left alone (a few bytes) so nothing can read freed memory
                new = self.p.malloc(max(len(data), 8))
                if data:
                    self.p.write(new, data)
                self.p.write(vec, struct.pack("<QQQ", new, new + len(data), new + len(data)))
                grown += 1
            done += 1
        return {"copies": done, "grown": grown}

    # ------------------------------------------------------------ per-player match stats
    def live_stats(self, pids: set[int], fm_events: list[tuple[int, int, int, int]]) -> list[list[int]]:
        """Record runs of today's match: consecutive GAME_MATCH_PLAYER_STATS of today's players (one club's
        squad; some copies list the substitutes first) with at least 11 ratings, whose goal counts equal FM's own
        event list. Old matches' records do not match, nor do runs already rewritten. Empty if FM's match had
        no goals (today's records could not be told from old ones)."""
        want = Counter(e[0] for e in fm_events if e[2] in (EV_GOAL, EV_PENALTY))
        if not want:
            return []
        vt = self.p.vtables(".?AVGAME_MATCH_PLAYER_STATS@@")[0]
        recs = []
        for a in self.p.find_qword(vt):
            b = self.p.try_read(a + STATS_PID, 4)
            if b and struct.unpack("<I", b)[0] in pids:
                recs.append(a)
        recs.sort()
        runs, cur = [], []
        for a in recs:
            if cur and a != cur[-1] + STATS_REC:
                runs.append(cur)
                cur = []
            cur.append(a)
        if cur:
            runs.append(cur)
        live = []
        for run in runs:
            rows = [self.p.read(a, STATS_REC) for a in run]
            if sum(1 for b in rows if struct.unpack_from("<H", b, STATS_RATING)[0]) < 11:
                continue
            run_pids = {struct.unpack_from("<I", b, STATS_PID)[0] for b in rows}
            goals = Counter({struct.unpack_from("<I", b, STATS_PID)[0]: b[STATS_GOALS] for b in rows if b[STATS_GOALS]})
            if goals == Counter({k: v for k, v in want.items() if k in run_pids}):
                live.append(run)
        return live

    def apply_player_stats(self, runs: list[list[int]], goals: dict[int, int],
                           yellows: dict[int, int] | None = None) -> int:
        """Set the goals (and, if given, yellow cards) of every player record in `runs` (unlisted players: 0)."""
        n = 0
        for run in runs:
            for a in run:
                pid = self.p.u32(a + STATS_PID)
                self.p.write(a + STATS_GOALS, bytes([min(goals.get(pid, 0), 255)]))
                if yellows is not None:
                    self.p.write(a + STATS_YELLOW, bytes([min(yellows.get(pid, 0), 2)]))
                n += 1
        return n


def fm_minute(clock_minute: int, period: int = 0) -> int:
    """SPFL clock 27:44 is the 28th minute. SPFL26's period value is unreliable (a 61st-minute goal reported as
    period 1), so only the clock counts; the caller clamps to the match length."""
    return max(1, min(clock_minute + 1, 120))


def merge_events(spfl_goals: list[dict], fm_events: list[tuple[int, int, int, int]],
                 fallback: dict[int, list[int]], og_fallback: dict[int, list[int]] | None = None
                 ) -> list[tuple[int, int, int, int]]:
    """FM event list for the SPFL result.

    spfl_goals: [{"side": 0|1, "minute": int, "pid": FM person id or None, "own": bool}] in match order; side is
    the team the goal counts for. Goals whose scorer was not read get FM's own scorers of that side (in FM's
    order), then `fallback[side]` (forwards first). Own goals are FM type 1 events (person = the player who put
    it in his own net, side = the team it counts for, as in FM's own fixtures); one without a readable name goes
    to `og_fallback[conceding side]` (defenders first). FM's own red cards stay (cards are FM's own)."""
    own = {0: [e[0] for e in fm_events if e[2] in (EV_GOAL, EV_PENALTY) and e[1] == 0],
           1: [e[0] for e in fm_events if e[2] in (EV_GOAL, EV_PENALTY) and e[1] == 1]}
    out = []
    for g in spfl_goals:
        pid = g.get("pid")
        if g.get("own"):
            pid = pid or next(iter((og_fallback or {}).get(1 - g["side"], [])), 0)
            if pid:
                out.append((pid, g["side"], EV_OWN_GOAL, g["minute"]))
            continue
        if not pid:
            queue = own[g["side"]] or fallback.get(g["side"], [])
            pid = queue.pop(0) if own[g["side"]] else (queue[0] if queue else 0)
        if pid:
            out.append((pid, g["side"], EV_GOAL, g["minute"]))
    out += [e for e in fm_events if e[2] == EV_RED]
    out.sort(key=lambda e: (e[3], e[2] == EV_RED))
    return out
