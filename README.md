# Matchday Bridge — Football Manager 2024 × SP Football Life 2026

[Watch the video](https://www.youtube.com/watch?v=dPkCeqTkNk8)

Manage your club in Football Manager 2024 as normal. On match day, play the match yourself in
SP Football Life 2026 with both clubs' real FM24 match squads, and the score goes back into your FM24 save.

## Feature status

| Feature | Status | Notes |
|---|---|---|
| Choice inside FM24 at Match Preview (play in SPFL26 or simulate in FM24) | ✅ Done | FM24 takes no input until you answer |
| Both FM24 match squads in SPFL26 (starters, subs, team-sheet order) | ✅ Done | Names, age, height, weight, positions, foot, 25 abilities from FM24 attributes |
| Clubs SPFL26 lacks: FM24 name, 3-letter abbreviation and FM24 logo as crest | ✅ Done | Uses spare SPFL26 slots |
| Generic kits without logo or sponsor for those clubs | ✅ Done | Your club wears the same kits every match day |
| Automatic SPFL26 setup to the pre-match screen | ✅ Done | Local Match, both clubs, controller 1 on your club; runs in the background |
| No SPFL26 restart between matches | ✅ Done | Restarts by itself only when the game is stuck (e.g. inside a match) |
| FM24 simulates its own match in the background meanwhile | ✅ Done | Half time, confirmations and injury substitutions included |
| Live score in the Matchday Bridge window | ✅ Done | |
| SPFL26 score written into FM24 | ✅ Done | Fixtures, league table, match report and news use it |
| Goal scorers and goal minutes written into FM24 | ✅ Done | Read from SPFL26's goal caption; unreadable ones fall back to an FM24 scorer |
| Own goals | ✅ Done | Checked with offline tests; not yet seen in a live SPFL26 match |
| Leaving FM24's post-match screens automatically | ✅ Done | Post-match team talk is handed to your assistant |
| Several match days in one session | ✅ Done | |
| Real player faces | ✅ Done | Every player SPFL26 has (at any club) shows his own face; players it lacks get a generic head and no face icon |
| SPFL26 match left before full time | ✅ Done | Nothing is written; FM24's own result stands |
| Uninstall | ✅ Done | `MatchdayBridge.exe --uninstall` |
| Assists | ⏳ Not yet | FM24 keeps its own |
| Yellow and red cards | ⏳ Not yet | FM24 keeps its own; SPFL26 shows no card caption to read |
| Injuries | ⏳ Not yet | FM24 keeps its own |
| Substitutions, minutes played and player ratings | ⏳ Not yet | FM24 keeps its own |
| Club colours on the generic kits | ⏳ Not yet | Kits come from the borrowed SPFL26 slot |
| Extra time and penalty shootouts (cup ties) | ⏳ Untested | |
| FM24 in languages other than English | ⏳ Not yet | FM24's screen text is read in English |
| Other FM24 / SPFL26 versions | ⏳ Not yet | Verified on FM24 24.4 and SPFL26 2.2 |
| Two human players | ⏳ Not yet | You play against the CPU |

## What it does

1. **The choice pops up in FM24.** On match day, when you press **Match Preview** in FM24 (Pep Talk → the
   pre-match screen), FM24 dims and asks: *Play in SP Football Life 2026, or simulate in FM24?* FM takes no
   input until you answer. (Matchday Bridge's own window only shows progress.)
2. **Play in SPFL26.** Both FM24 match squads (starters, subs, team-sheet order) are rebuilt into SPFL26:
   names, ages, height, weight, positions, preferred foot, and 25 PES abilities computed from each player's
   FM24 attributes (`sheets/ratings_map.json`). Clubs SPFL26 doesn't have (e.g. Oldham Athletic) borrow a
   spare SPFL26 slot (Zalgiris Vilnius, then Ceres Negros, then Zamora FC) with the FM24 club name and
   3-letter abbreviation, **FM24's club logo as the crest** (a plain badge with the initials when FM24 has no
   logo for the club) and the game's **generic kits without logo or sponsor** (the spare slots only have
   SPFL26's plain editable kits). Your own club always gets the first of these slots, so it wears the same kits
   every match day. Every FM24 player SPFL26 has, at any club, shows his own face and portrait. Players it
   doesn't have (e.g. retired since FM24's database) get a generic head and no face icon, never another
   player's face. If SPFL26 is already running (from your last match), the
   squads are written straight into the running game: no restart. Otherwise SPFL26 is started so it loads
   them (also when the running game is stuck somewhere it can't be walked back from, e.g. inside a match).
   **Leave SPFL26 open between matches**: setting up then takes about 20 seconds instead of about a minute.
3. **SPFL26 sets itself up.** Matchday Bridge walks SPFL26's menus for you (Match → Local Match, both
   clubs, controller 1 on the club you manage in FM24) and stops on the pre-match screen. Choose kits and
   stadium, then Kick Off and play against the CPU. This takes about 20 seconds after the title screen, in the
   background: `matchday.lua` hooks the game's list cursor so each Select Team list jumps straight to the club
   (one button press per list; idea and hook site from forceselection.lua). If anything unexpected shows up, it
   stops and tells you which teams to pick yourself. The live score is tracked while you play.
4. **FM24 plays its own match meanwhile.** Right after you choose SPFL26, Matchday Bridge kicks off FM's
   match and runs it to full time in the background (half time, confirmations and injury substitutions
   included), then waits there. When your SPFL26 match ends, your score and goal scorers go in and Matchday
   Bridge leaves FM's match screen (about half a minute; FM's post-match team talk is handed to your assistant,
   as when you delegate it), which is when FM saves the result: fixtures, league table, match report,
   player goal tallies, news and post-match analysis all use your match. FM's own match takes a few minutes
   (about 9 with commentary only at top speed), so it is normally done before yours.
5. **Simulate in FM24** does nothing to either game.

### Goal scorers

Scorers are read from SPFL26's on-screen goal caption ("47 Ryan Harris / GOAL 1") with Windows OCR and
matched to the FM24 squad. Keep the SPFL26 window open (it may be covered, but not minimized) while you
play. A scorer that can't be read is credited to a player FM had scoring for that side (else a starter).
An "OWN GOAL" caption becomes an own goal in FM24, by the player named in it (one of the conceding side's
starting defenders when no name can be read). Goal minutes are SPFL26's match clock.

### Not carried over

Assists, cards, injuries and player ratings in FM24 are still FM's own simulation of the match.
If you leave the SPFL26 match before full time, nothing is written and FM's own result stands.

### FM24 needs

FM24 in English (the pre-match screen and buttons are read from the screen), its window open while you play
SPFL26 (it may be covered, not minimized), and no clicking in FM24 while its match runs in the background.

## Requirements

- Windows 10/11, Football Manager 2024 (Steam, version 24.4) and SP Football Life 2026 (2.2 data, Sider 7).
- Matchday Bridge asks for administrator rights once at start (SP Football Life 2026 runs as admin).

## Install

1. Download the latest `MatchdayBridge-v1.0.<n>.zip` from this repository's
   [Releases](https://github.com/terry-haire/matchday-bridge/releases) page, unzip it anywhere, and close
   SP Football Life 2026.
2. Run `MatchdayBridge.exe` and accept the Windows prompt. On first run it:
   - copies `matchday.lua` into `SiderAddons\modules`,
   - backs up `SiderAddons\sider.ini` to `sider.ini.matchday-backup` and adds
     `cpk.root = ".\livecpk\matchday"`, `lua.module = "matchday.lua"` and (if missing) `match-stats.enabled = 1`.
   On the first match it also renames the game's `xinput1_3.dll` to `xinput1_3_orig.dll` and puts a small
   proxy `xinput1_3.dll` in its place (source: `spfl/xinput/xinput_proxy.c`). The proxy passes your
   controller through unchanged and adds the bridge's button presses as controller 1, so the menus can be
   set up while the game window is in the background.
3. Leave it running and play FM24. Keep it running until the score has been saved in FM24.

Both games are found automatically (Steam libraries; the SPFL26 default folder or its uninstall entry).

## Uninstall

Run `MatchdayBridge.exe --uninstall` with SP Football Life 2026 closed. It removes the module, the
`livecpk\matchday` folder and the two sider.ini lines it added, and puts the game's own `xinput1_3.dll` back.
Your original sider.ini is also kept as `sider.ini.matchday-backup`.

## Notes and safety

- FM24 is only read while you play. Writes happen only after FM's match has ended, and only into records
  re-checked to be today's fixture (both clubs and the date): the two goal bytes, the fixture's goal list
  (a longer list is allocated inside FM24 with its own `malloc`), and the goal counts in today's player
  match stats.
- No FM24 or SPFL26 data files are modified or shipped (the only file swapped in the game folder is the
  `xinput1_3.dll` proxy above). The SPFL26 squads are rebuilt from your own install into
  `SiderAddons\livecpk\matchday` each match (read when SPFL26 starts) and, when SPFL26 is already running,
  written into its memory: the borrowed players and your SPFL26 edit data are put back when the next match is
  loaded or Matchday Bridge closes (so a Rematch still shows the FM24 teams).
- Log: `%LOCALAPPDATA%\MatchdayBridge\bridge.log`, with screenshots of the last automatic SPFL26 setup in
  `last_match\`. SPFL26 side: `SiderAddons\matchday\` (request, result, build log) and
  `SiderAddons\sider.log` (lines starting with `matchday:`).
- Tested with FM24 24.4.0 (build 18129188) and SPFL26 exe 26.2.03 / Game Version 2.2. Other versions may
  need the offsets in `sheets/` re-verified.

## For developers

- `sheets/*.json` are the source of truth (every offset with how it was verified).
  `python tools/gen.py` regenerates `bridge/gen_structs.py` and the table inside `spfl/modules/matchday.lua`;
  `python tools/preflight.py` lists unverified cells.
- `python tests/test_spfl_build.py` checks the squad builder against your SPFL26 install (with the made-up
  squads in `tests/sample_matchday.json`); `python tests/test_own_goals.py` checks own-goal handling offline.
- Build the exe: `pip install -r requirements.txt` (Python 3.11), then `pyinstaller MatchdayBridge.spec`.
  `MatchdayBridge.exe --selftest` checks the bundled modules, the
  controller proxy and SPFL26 capture + OCR. Rebuild the proxy with `python testkit/pad.py build` (clang).
- GitHub Actions (`.github/workflows/build.yml`) builds, tests and self-tests the exe on every push and pull
  request (download it from the run's artifacts). Every push to `main` also publishes a release numbered
  `v1.0.1`, `v1.0.2`, ... with the zip and the commit subjects since the previous release; change
  `VERSION_BASE` in the workflow to start a new series (e.g. `1.1` → `v1.1.1`).
- `testkit/` (dev only, never shipped) drives SPFL26 in the background for fast tests:
  `python testkit/spfl.py roundtrip --home "Atlanta United FC" --away "Oldham Athletic"` starts the game,
  picks the teams and plays a 1-minute match out (~3 min cold, ~2 min per rematch). Run it elevated.
  It uses the bridge's proxy `xinput1_3.dll` and installs `matchday_test.lua` into Sider. Remove both with
  `python testkit/pad.py uninstall` and by deleting the `matchday_test.lua` line from `sider.ini`.
- `MODLOG.md` is the research journal. Credits: see `THIRD_PARTY_NOTICES.md`.
