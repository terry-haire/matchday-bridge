# Matchday Bridge — Football Manager 2024 × eFootball PES 2021


<img width="505" height="476" alt="image" src="https://github.com/user-attachments/assets/64945082-1600-4977-b713-8ff293f28781" />

[Watch the video](https://www.youtube.com/watch?v=dPkCeqTkNk8)

Manage your club in Football Manager 2024 as normal. On match day, play the match yourself in
**eFootball PES 2021** (the free PES 2021 LITE edition on Steam is enough) with both clubs' real FM24 match
squads, and the score and scorers go back into your FM24 save.
**SP Football Life 2026** is supported too: with both games installed, the match-day question offers both.

## Feature status

| Feature | Status | Notes |
|---|---|---|
| Choice inside FM24 at Match Preview (PES 2021, Football Life 2026 or simulate in FM24) | ✅ Done | One button per installed game; FM24 takes no input until you answer |
| Both FM24 match squads in the game (starters, subs, team-sheet order) | ✅ Done | Names, age, height, weight, positions, foot, 25 abilities from FM24 attributes |
| FM24 club name, 3-letter abbreviation and FM24 logo as crest | ✅ Done | PES 2021: for every club outside its five Local Match clubs; SPFL26: clubs it lacks |
| Kits | ✅ Done | PES 2021: the kits of the Local Match club whose slot it plays in; SPFL26: generic kits for clubs it lacks. Your club wears the same kits every match day |
| Automatic setup to the pre-match screen | ✅ Done | Local Match, both clubs, controller 1 on your club; runs in the background |
| No game restart between matches | ✅ Done | Restarts by itself only when the game was started without Sider or is stuck |
| FM24 simulates its own match in the background meanwhile | ✅ Done | Half time, confirmations and injury substitutions included |
| Live score in the Matchday Bridge window | ✅ Done | |
| Score written into FM24 | ✅ Done | Fixtures, league table, match report and news use it |
| Goal scorers and goal minutes written into FM24 | ✅ Done | Read from the game's goal caption; unreadable ones fall back to an FM24 scorer |
| Own goals | ✅ Done | Checked with offline tests; not yet seen in a live match |
| Leaving FM24's post-match screens automatically | ✅ Done | Post-match team talk is handed to your assistant |
| Several match days in one session | ✅ Done | |
| Real player faces | ✅ Done | Every player the game has (at any club) shows his own face; players it lacks get a generic head and no face icon |
| Match left before full time | ✅ Done | Nothing is written; FM24's own result stands |
| Uninstall | ✅ Done | `MatchdayBridge.exe --uninstall` |
| Assists | ⏳ Not yet | FM24 keeps its own |
| Yellow and red cards | ⏳ Not yet | FM24 keeps its own |
| Injuries | ⏳ Not yet | FM24 keeps its own |
| Substitutions, minutes played and player ratings | ⏳ Not yet | FM24 keeps its own |
| Club colours on the kits | ⏳ Not yet | Kits come from the borrowed slot |
| Stadiums in PES 2021 LITE | ⏳ Not possible | LITE's Local Match has one stadium |
| Extra time and penalty shootouts (cup ties) | ⏳ Untested | |
| FM24 in languages other than English | ⏳ Not yet | FM24's screen text is read in English |
| Other FM24 / game versions | ⏳ Not yet | Verified on FM24 24.4, PES 2021 1.07.02 (LITE) and SPFL26 2.2 |
| Two human players | ⏳ Not yet | You play against the CPU |

## PES 2021 or Football Life 2026?

- **eFootball PES 2021** (Steam app 1259970). The free **LITE** edition works: its offline Local Match only
  offers five clubs (Manchester United, Arsenal, Bayern, Barcelona, Juventus) and one stadium, so every FM24
  club plays *in one of those five slots*, under its FM24 name (in capitals, like PES's own), abbreviation and
  crest, with its FM24 squad, ratings and faces, but in that club's kits. Your club always gets Manchester
  United's slot (so the same kits every match day; choose Away or Third kits on the pre-match screen if you
  prefer), the opponent the next free one. An FM24 club that *is* one of the five keeps its own slot.
  Player data comes from PES 2021's own last update (Data Pack 7.0, 2021): FM24 players PES 2021 doesn't have
  get a generic head.
- **SP Football Life 2026** (a standalone PES 2021-engine game with current squads, most clubs, kits and
  stadiums). Clubs it has play as themselves; clubs it lacks borrow one of three plain-kit slots.

Both keep their own saves (PES 2021: `Documents\KONAMI\eFootball PES 2021 LITE` or `... SEASON UPDATE\<Steam
id>`; Football Life: `Documents\KONAMI\eFootball PES 2021 SEASON UPDATE\2026`). Matchday Bridge doesn't touch
either save.

## What it does

1. **The choice pops up in FM24.** On match day, when you press **Match Preview** in FM24 (Pep Talk → the
   pre-match screen), FM24 dims and asks where to play: **PES 2021**, **Football Life 2026** (a button for each
   installed game) or **Simulate in FM24**. FM takes no input until you answer. (Matchday Bridge's own window
   only shows progress.)
2. **Play.** Both FM24 match squads (starters, subs, team-sheet order) are rebuilt into the game: names, ages,
   height, weight, positions, preferred foot, and 25 PES abilities computed from each player's FM24 attributes
   (`sheets/ratings_map.json`). Clubs the game can't pick borrow a slot (see above) with the FM24 club name,
   3-letter abbreviation and **FM24's club logo as the crest** (a plain badge with the initials when FM24 has no
   logo for the club). Every FM24 player the game has, at any club, shows his own face and portrait; players
   it doesn't have (e.g. retired since FM24's database) get a generic head and no face icon, never another
   player's face. If the game is already running with Matchday Bridge's Sider module (from your last match),
   the squads are written straight into it: no restart. Otherwise it is (re)started so it loads them: PES 2021
   through Sider, which starts it via Steam. **Leave the game open between matches**: setting up then takes
   about 20 seconds instead of about a minute.
3. **The game sets itself up.** Matchday Bridge walks the menus for you (Match → Local Match, both clubs,
   controller 1 on the club you manage in FM24) and stops on the pre-match screen. Choose kits (and stadium in
   Football Life), then Kick Off and play against the CPU. This runs in the background: `matchday.lua` hooks
   the game's list cursor so each Select Team list jumps straight to the club (one button press per list; idea
   and hook site from forceselection.lua). If anything unexpected shows up, it stops and tells you which teams
   to pick yourself. The live score is tracked while you play.
4. **FM24 plays its own match meanwhile.** Right after you choose a game, Matchday Bridge kicks off FM's
   match and runs it to full time in the background (half time, confirmations and injury substitutions
   included), then waits there. When your match ends, your score and goal scorers go in and Matchday Bridge
   leaves FM's match screen (about half a minute; FM's post-match team talk is handed to your assistant, as
   when you delegate it), which is when FM saves the result: fixtures, league table, match report, player goal
   tallies, news and post-match analysis all use your match. FM's own match takes a few minutes (about 9 with
   commentary only at top speed), so it is normally done before yours.
5. **Simulate in FM24** does nothing to either game.

### Goal scorers

Scorers are read from the game's on-screen goal caption with Windows OCR and matched to the FM24 squad:
under the scoreboard in PES 2021 ("7 Arlo Brightwater / Today's Goals 1"), bottom left in Football Life
("47 Ryan Harris / GOAL 1"). Keep the game window open (it may be covered, but not minimized) while you play.
A scorer that can't be read is credited to a player FM had scoring for that side (else a starter). An
"OWN GOAL" caption becomes an own goal in FM24, by the player named in it (one of the conceding side's
starting defenders when no name can be read). Goal minutes are the game's match clock.

### When the match ends

Leave the match through **Top Menu** after full time: that is when the score counts as final. A Rematch
replays the fixture (the FM24 teams stay) and the score of the new match is the one that goes in.
Assists, cards, injuries and player ratings in FM24 are still FM's own simulation of the match. If you leave
the match before full time, nothing is written and FM's own result stands.

### FM24 needs

FM24 in English (the pre-match screen and buttons are read from the screen), its window open while you play
(it may be covered, not minimized), and no clicking in FM24 while its match runs in the background.

## Requirements

- Windows 10/11 and Football Manager 2024 (Steam, version 24.4).
- eFootball PES 2021 on Steam (the free LITE edition is enough; version 1.07.02, Data Pack 7.00), started
  once by yourself to accept its terms, and/or SP Football Life 2026 (2.2 data, Sider 7).
- Matchday Bridge asks for administrator rights once at start (SP Football Life 2026 runs as admin; PES 2021
  itself is started without them, through Steam).

## Install

1. Download the latest `MatchdayBridge-v1.0.<n>.zip` from this repository's
   [Releases](https://github.com/terry-haire/matchday-bridge/releases) page, unzip it anywhere, and close the
   game(s).
2. Run `MatchdayBridge.exe` and accept the Windows prompt. On first run it sets up each game it finds:
   - **PES 2021**: downloads the official [Sider 7.4.1](https://github.com/pes-modding/sider7/releases/tag/v7.4.1)
     (checksum-checked; Sider is not bundled) into `<PES 2021 folder>\sider`, with a `sider.ini` that starts
     PES 2021 through Steam, closes Sider with the game and loads only `netblock.lua` (Sider's module that keeps
     PES 2021 off Konami's servers and live updates while Sider runs) and `matchday.lua`. `PES2021.exe` is
     not patched: starting PES 2021 from Steam yourself runs it without Sider, as before.
   - **Football Life 2026**: copies `matchday.lua` into `SiderAddons\modules`, backs up
     `SiderAddons\sider.ini` to `sider.ini.matchday-backup` and adds `cpk.root = ".\livecpk\matchday"`,
     `lua.module = "matchday.lua"` and (if missing) `match-stats.enabled = 1`.
   On the first match in a game it also puts a small proxy `xinput1_3.dll` in the game folder (Football Life's
   own copy is kept as `xinput1_3_orig.dll`; source: `spfl/xinput/xinput_proxy.c`). The proxy passes your
   controller through unchanged (Steam Input included) and adds the bridge's button presses as controller 1, so
   the menus can be set up while the game window is in the background.
3. Leave it running and play FM24. Keep it running until the score has been saved in FM24.

The games are found automatically (Steam libraries; the Football Life default folder or its uninstall entry).

## Uninstall

Run `MatchdayBridge.exe --uninstall` with the games closed. For PES 2021 it deletes the `sider` folder it
downloaded; for Football Life it removes the module, the `livecpk\matchday` folder and the two sider.ini lines
it added (your original sider.ini is also kept as `sider.ini.matchday-backup`) and puts the game's own
`xinput1_3.dll` back. The proxy `xinput1_3.dll` is removed from PES 2021's folder.

## Notes and safety

- FM24 is only read while you play. Writes happen only after FM's match has ended, and only into records
  re-checked to be today's fixture (both clubs and the date): the two goal bytes, the fixture's goal list
  (a longer list is allocated inside FM24 with its own `malloc`), and the goal counts in today's player
  match stats.
- No FM24, PES 2021 or Football Life data files are modified or shipped (the only file added to a game folder,
  besides Sider for PES 2021, is the `xinput1_3.dll` proxy above). The squads are rebuilt from your own game
  install into `<sider folder>\livecpk\matchday` each match (read when the game starts) and, when the game is
  already running, written into its memory: the borrowed players and the game's edit data are put back when the
  next match is loaded or Matchday Bridge closes (so a Rematch still shows the FM24 teams).
- Log: `%LOCALAPPDATA%\MatchdayBridge\bridge.log`, with screenshots of the last automatic setup in
  `last_match\`. Game side: `<sider folder>\matchday\` (request, result, build log) and `<sider folder>\sider.log`
  (lines starting with `matchday:`). The Sider folder is `sider` in PES 2021, `SiderAddons` in Football Life.
- Tested with FM24 24.4.0 (build 18129188), PES 2021 1.07.02 LITE (Steam) and SPFL26 exe 26.2.03 / Game
  Version 2.2. Other versions need their edit-data address in `sheets/game_exes.json`.
- Sider's `match.minutes` option doesn't work with PES 2021 1.07.02 (Sider then loads no hooks at all); leave it 0.

## For developers

- `sheets/*.json` are the source of truth (every offset with how it was verified).
  `python tools/gen.py` regenerates `bridge/gen_structs.py` and the table inside `spfl/modules/matchday.lua`;
  `python tools/preflight.py` lists unverified cells. `bridge/games.py` holds what differs per game.
- `python tests/test_spfl_build.py` checks the squad builder against your Football Life and PES 2021 installs
  (with the made-up squads in `tests/sample_matchday.json`); `python tests/test_own_goals.py` checks caption
  reading and own-goal handling offline.
- Build the exe: `pip install -r requirements.txt` (Python 3.11), then `pyinstaller MatchdayBridge.spec`.
  `MatchdayBridge.exe --selftest` checks the bundled modules, the controller proxy and game window capture +
  OCR. Rebuild the proxy with `python testkit/pad.py build` (clang).
- GitHub Actions (`.github/workflows/build.yml`) builds, tests and self-tests the exe on every push and pull
  request (download it from the run's artifacts). Every push to `main` also publishes a release numbered
  `v1.0.1`, `v1.0.2`, ... with the zip and the commit subjects since the previous release; change
  `VERSION_BASE` in the workflow to start a new series (e.g. `1.1` → `v1.1.1`).
- PES 2021 test jobs (dev only, no FM24 needed): `python research/job_pes.py "Atlanta United FC" "Oldham
  Athletic"` runs the bridge's real setup to the pre-match screen; `research/job_pes_e2e.py` also plays the
  match out as an idle user and reports the live score and scorers the bridge read.
- `testkit/` (dev only, never shipped) drives Football Life in the background for fast tests:
  `python testkit/spfl.py roundtrip --home "Atlanta United FC" --away "Oldham Athletic"` starts the game,
  picks the teams and plays a 1-minute match out (~3 min cold, ~2 min per rematch). Run it elevated.
  It uses the bridge's proxy `xinput1_3.dll` and installs `matchday_test.lua` into Sider. Remove both with
  `python testkit/pad.py uninstall` and by deleting the `matchday_test.lua` line from `sider.ini`.
- `MODLOG.md` is the research journal. Credits: see `THIRD_PARTY_NOTICES.md`.
