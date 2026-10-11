# MODLOG — Matchday Bridge (FM24 × SPFL26)

Journal of the build. Anything not written here is lost at the next context compaction.

## Idea (agreed with the user, 2026-10-09)
You play Football Manager 2024 as normal. On match day for your club a prompt asks
"Play in SPFL26 or let FM sim?". Playing launches SP Football Life 2026 straight to kickoff with both
FM24 match squads, rated from their FM24 attributes. Clubs missing from SPFL26 (e.g. Oldham) get a spare
SPFL26 team slot with their real FM24 squad, names and ratings (generic faces/kits). Afterwards the score,
scorers, cards and injuries go back into the FM24 save. Solo: you control your FM club, CPU the opponent.
First playable = that round trip + one missing club via a spare slot.

## Installs (found automatically)
- FM24: Steam app 2252570, `C:\Program Files (x86)\Steam\steamapps\common\Football Manager 2024`, fm.exe
  24.4.0 (build 18129188). Saves: `%LOCALAPPDATA%\Sports Interactive\Football Manager 2024\cloud\games`.
  User career: a save managing Oldham Athletic.
- SPFL26: `C:\Program Files (x86)\SP Football Life 2026` (uninstall key "Football Life 2026"), FL_2026.exe
  26.2.0.3, data 2.2.0, Sider 7.4.1 in `SiderAddons`. Must be started elevated via `FL 2026 start.exe`
  (user note). sider.exe can linger after exit: kill by PID.

## Routes chosen
- FM24: Sports Interactive native C++ engine, Denuvo Anti-Tamper, no anti-cheat. No code loader exists.
  Route: external data-only memory access (ReadProcessMemory/WriteProcessMemory) like FMRTE/Genie Scout.
  We never patch FM code. MSVC RTTI is intact, so every object is found by vtable (COL→TypeDescriptor).
- SPFL26: PES 2021 (Fox Engine). Route: Sider 7 Lua module + LiveCPK root that serves rewritten
  `common/etc/pesdb` tables built from the player's own install at launch time (nothing shipped).

## Backups / lab
- `um backup`: `%USERPROFILE%\.universal-modder\backups\fm24-cloud-saves\20261009-115419.zip`,
  `...\spfl26-sideraddons\20261009-115832.zip`. Restore: `um backup restore <zip>`.
- FM tests run on a COPY: `Documents\Sports Interactive\Football Manager 2024\games\Matchday Lab.fm`.
  In the lab save, friendlies were switched from "delegated to Steve Collis" to the human manager.

## FM24 facts (verified live, lab save, 24.4.0)
- ACTUAL_PLAYER@db: stride 0x3E8 (34,993). Team ptr +0x130, weight +0x14c (kg), height +0x14e (cm),
  CA +0x200 u16, PA +0x202 u16, attributes u8[54] at +0x217 (1–100, UI = /5), DOB +0x2bc (u16 day-of-year
  low 9 bits, u16 year), names +0x2d0/+0x2d8/+0x2e0 (ptr→ptr→{u32 len, utf8}), nation +0x2e8.
  Attribute order and checks: `sheets/fm_attributes.json` (Marquinhos + Seimen profiles match 100%).
- TEAM@db +0x30 → CLUB@db; CLUB +0xc0 name, +0xc8 short name.
- FIXTURE@sicomps / FIXTURE_RESULT@sicomps: +0x08 home TEAM, +0x10 away TEAM, +0x4c date (doy|year).
- On match day FM creates GAME_MATCH objects (vtable .?AVGAME_MATCH@@) for the human club's match AND for
  other clubs' matches (Teplice v Porto was picked once). Pick the one whose teams include the human club:
  HUMAN_NON_PLAYER@db +0x518 → FULL_CONTRACT +0x10 → TEAM.
- GAME_MATCH +0xcea8: ONE list of up to 36 MATCH_PLAYER*: home squad first, then away, null-terminated.
  A 17-man squad shifts the away list, so never split by index. Group by MATCH_PLAYER +0x1d0 → MATCH_TEAM,
  MATCH_TEAM +0x48 → TEAM (works for clubs made of VIRTUAL_PLAYERs). First player's team = home.
  MATCH_PLAYER +0x1ec looked like a side flag but flipped after a reload — not used.
- MATCH_PLAYER@simatch: +0x28 → player sub-object (complete object via COL offset; ACTUAL_PLAYER,
  VIRTUAL_PLAYER or ACTUAL_PLAYER_AND_NON_PLAYER), +0x30 name, +0x397 attributes u8[54] (also for virtual
  players), +0x6bb team-sheet slot (0–10 starters) — matches FM's official roster for both clubs.
- No per-player goal/card counter found in MATCH_PLAYER (searched u8/u16/u32 against the known 0–4 events).

## FM24 write-back: SCORE SOLVED (scorers/cards/injuries not)
- FIXTURE_RESULT@sicomps has ~8–9 copies per fixture (same +0x08 home TEAM, +0x10 away TEAM, +0x4c date).
  +0x64 home goals u8, +0x68 away goals u8 (0xff = unplayed), +0x6c state (0 unplayed/in play, 0x010a done).
- During FM's match one copy counts live goals (found by single-value narrowing 4→5 away goals). At full time
  that copy turns finished. Writing the score there (or into every finished copy) before leaving the match
  makes FM commit it: all copies become finished with the written score; Oldham fixtures list shows "7-3";
  FM generated "Post-Match Analysis: (FR) Oldham 7-3 Atlanta United" from it next day.
- Earlier failure: (h,a) u32 pairs and the GAME_MATCH/MATCH constants tables are NOT the score.
- Bridge flow (`bridge/fm_writer.py`): at Play, lock today's fixture = earliest unplayed copy of home v away;
  after SPFL full time, poll every 2 s and write the SPFL score into finished copies of that fixture only
  (each copy re-validated: class, both teams, date, finished). Done when every copy is finished with it.
- FM's own match still has to be "played" (it can run at top speed); the scoreline is swapped at its end.
  Scorers, cards, injuries and player stats in FM stay FM's own — NOT carried over.

## FM24 match details (2026-10-10, lab save, verified live)
- Person id: ACTUAL_PLAYER +0x280 u32 (unique; used by the records below).
- Goal list of a result: FIXTURE_RESULT +0x70 -> {vector begin, end, cap} of 8-byte entries
  {u32 person id, u8 side (0 home, 1 away), u8 type (0 goal, 2 penalty), u16 minute}, chronological.
  Every copy of the fixture has its own vector with the same entries. FM's result lists and match panel
  ("Chukalov (11, 33)") are drawn from it.
- Per-player match stats: GAME_MATCH_PLAYER_STATS records (0x100 bytes, vtable .?AVGAME_MATCH_PLAYER_STATS@@),
  arrays per club in team-sheet order, several live copies during the match: +0x10 person id, +0x78 rating
  x100 u16, +0x7f goals u8, +0x89 assists u8 (probable), +0x9a yellow cards u8 (probable), +0x8c index.
  Editing goals in all live copies at full time is committed: the match panel shows the edited goal icons
  (Santos 2 after moving Ribeiro's goals) while the scorer text still came from the goal list above.
- Live match settings live in the match view (gear): highlights "Only Commentary", replays off, speeds max
  (the user keeps them like that).
- FM pauses a live match when a player is injured and will not resume until he is substituted.
- Write experiments at the FULL TIME screen (before leaving the match), all kept by FM:
  * goal list entries rewritten (same count): result lists/panel show the new scorers and minutes.
  * stats records +0x7f goals / +0x9a yellow / +0x7c injury type + 0xa4 minute: match panel shows the
    edited goal icons, yellow card and injury cross. BUT the injury edit creates no real injury (Medical
    Center unchanged): real injuries are separate objects.
- The goal list vector is exact-size at full time (cap == count): fewer goals = shrink `end` (safe);
  more goals than FM scored needs a bigger buffer allocated in FM's heap. FM uses the UCRT heap
  (api-ms-win-crt-heap malloc/free), so a remote call to ucrtbase!malloc would give FM-compatible memory —
  that would be code execution in FM (not done yet; user decision).
- FIXTURE_RESULT +0x70 points into a pool of 0x20-byte {vector, tail} goal-list entries (neighbours are other
  fixtures' lists). The list is the match EVENT list: type 0 goal, 2 penalty goal, 3 sent off (red card:
  "F. Lechner sent off (37)" = (95994, side 0, type 3, 37)); type 1 is probably an own goal (not seen yet).
- Real injuries: not linked from ACTUAL_PLAYER nor from the stats record. Injury history entries are 0x38-byte
  records {.., INJURY@db type +0x8, person-ish ptr +0x18, start date +0x20, days u16 +0x28/+0x2a, ..}; the
  current-injury link was not found. Writing stats +0x7c/+0xa4 or MATCH_PLAYER +0x2d5 does NOT create one.

## SPFL26 facts (verified)
- Effective pesdb: Player.bin + PlayerAssignment.bin from `download/data_extra.cpk`, Team.bin from
  `download/08_smkdb_ulk.cpk` (sizes match sider tracer log). Precedence from `download/spFileList.bin`.
- Live edit block: `[[0x143705e10]+0x48]`; teams at +0xadf4bc stride 0x690 (749 used), players at +0
  stride 0x17c (29,492). Team id = (encoded >> 14) & 0x1ffff. Liverpool 103, Atlanta United 5736.
- Player.bin record 312 B: id at +0x08, bit fields per Matozanato/FootballLife-new-leagues
  docs/player-record.md (MIT), names 4×0x3d at +0x44. PlayerAssignment 16 B: row, player, team,
  pack(shirt-1 | order<<10).
- Exhibition flow: title (Enter) → Local Match → side select → team select (league lists). SPFL remembers
  the last leagues/teams. Home: down×11 = MLS; Away: up×10 = Other European Leagues, down×40 = Oldham.
- Spare slots for clubs SPFL lacks (`sheets/spfl_slots.json`): 199 Zalgiris Vilnius, 200 Ceres Negros,
  899 Zamora FC (plain-kit clubs, see "Kits, crests" below). A club already found in SPFL26 never gets a spare;
  the human club takes the first free one (since 2026-10-11, see "Same kits" below).
- Squads must reuse the club's existing player records (new ids hang the pre-match screen / crash).
- Edit data keeps its own name/abbreviation: matchday.lua writes them (scoreboard showed ZLG before).
- Sider: `match-stats.enabled = 1` needed for match.stats(); live score → result.txt every frame change,
  final=1 on context_reset (leaving the match). `set_teams` cannot change teams (manual pick stays).
- Sider Lua sandbox: no pcall/dofile/require/os.rename; generated data is inlined in matchday.lua.
- SPFL per-player match stats: a stride-0x419 array holds shots per player (3 copies); goals/assists
  bitfields not found yet. Stamina arrays at stride 0x128/0x100 (100 at full time).

## SPFL26 test driving (testkit, 2026-10-10)
- Users: keyboard + XInput slot 0 = User 1; any other pad = User 2. Menus, title, START skips (intro
  cut-scenes, replays, highlights, replay viewer "End") accept User 1 only. Keyboard Start/Select are
  unassigned in settings.dat, so a ViGEm virtual pad (slot 1) or the keyboard cannot skip anything.
- The game reads XInput while unfocused (keyboard input needs focus). The proxy xinput1_3.dll (game
  folder; original kept as xinput1_3_orig.dll) ORs shared-memory buttons into slot 0 → User 1, no focus.
  Since 2026-10-10 it ships with the bridge (spfl/xinput, shared memory "Local\MatchdayBridgePad").
- Screens: Windows Graphics Capture works on the covered window; PrintWindow crashes sider.dll+0x2ff8.
- match.stats() is nil until the first kick-off (pre-match intro has ptr=0); it keeps the last match's
  pointer on the full-time/Rematch menus. Telemetry: SCOREBOARD_INFO +0x20 paused, +0x22 clock running.
- SPFL's matchset.lua answers set_match_settings first; modules loaded after it never see the event.
  matchday_test.lua loads before it and turns extra time/penalties off for tests.
- Buttons: A = confirm/kick-off/short pass, START = skip (a highlight reel only shows "Skip" after a
  press), B = leave pause menu / team sheet. A on the pre-match menu's Game Plan opens the team sheet.
- Timing with match_minutes=1: rematch → ball in play ~15 s, kick-off → full time 100-150 s. Remaining
  stalls are goal celebrations and set pieces (~1 game-s/s); the real match clock was not found
  (writing the scoreboard clock only changes the display).

## SPFL26 scorers / cards (2026-10-10, research)
- Side select: User 1 starts on Home; RIGHT = middle (CPU vs CPU: 2-min matches ended 0-0 three times),
  RIGHT*2 = Away (the idle user side concedes: 1-4 goals per 2-min match = test data).
- NOT found in memory (searched at full time with OCR ground truth for 8 goals):
  * no byte next to any occurrence of the squad's SPFL player ids equals per-player goals (sum = score);
  * no goal list {player id + minute} at any stride (u8/u16 minutes, u16/u32 seconds);
  * the old stride-0x419 per-player shots records hold no ids and no goals field.
  The in-match 22-player array (ids at stride 0xa0) exists; stats are probably indexed by roster slot.
- Scorer caption ("47 Ryan Harris / GOAL 1", bottom left of the 1280x720 frame, x 40-560, y 520-640) is
  readable by OCR in the background: 7 of 8 goals identified by prefix-matching the squad names
  (research/job_scorers.py); the miss was a pause menu over it. No card caption was seen in ~10 matches.

## Scorers shipped (2026-10-10, verified end to end)
- matchday.lua v0.3.0 logs each goal (side + clock minute) to result.txt `goals=`; the bridge reads the
  caption with bridge/spfl_scorers.py for 8 s after each mark (WGC native capture of the SPFL window, works
  covered but not minimized, from an unelevated or elevated process; PrintWindow is black and crashed Sider).
- FM write-back at FULL TIME: score bytes + FIXTURE_RESULT +0x70 event list (8-byte entries; longer list
  allocated with remote ucrtbase malloc in fm.exe) in every finished copy of the fixture, then the goal counts
  in today's GAME_MATCH_PLAYER_STATS run (identified by >=11 ratings and goals == FM's own events), repeated
  after the commit. Person id for every player kind = PLAYER sub-object +0x8.
- Sider's period value is unreliable (61' logged as period 1) -> only clock minute, clamped to 90 (120 in ET).
- research/test_bridge_scorers.py (FM lab save + elevated SPFL job): 4/4 scorers read, all 11 fixture copies
  carry the events, FM match report "William Wight (31, 90), Tim Penfold (50, 61)", 4-0.
- Frozen exe needs numpy (procmem) and the windows_capture .pyd loaded directly (its wrapper imports cv2);
  `MatchdayBridge.exe --selftest` logs frame size + OCR of the SPFL window.

## Automatic SPFL26 setup (2026-10-10, verified live 3×)
- bridge/spfl_drive.py: title (A) → main menu (A = Match) → Local Match (A) → side select → Select Team →
  pre-match screen (Kits / Stadium / Kick Off), ~35-40 s after the title screen (~85 s from launch).
- Side select: LEFT×2 puts User 1 on Home from any start; then RIGHT×2 = Away (CPU in the middle).
  Screenshots of each step: %LOCALAPPDATA%\MatchdayBridge\last_match\*.png.
- Select Team league list (non-wrapping; remembers the last league per column): league names =
  CompetitionRegulation.bin first row of the club's *_LEAGUE competition (region != 8), e.g. "Major League
  Soccer" (later rows are phases: "MLS First Round"), "Scottish Premiership"; clubs in no league are under
  the Team.bin +0x4f nibble group: 2 Other European Leagues, 3 Other Clubs (Asia), 6 Other Latin American
  Teams, 7 Other Clubs (Africa), 1 Classic Teams. Then national-team regions and "User Data".
- Club lists sort by the original name (the renamed Zalgiris slot is last in Other European Leagues).
- OCR misreads: "Wisła Kraków" → "Wista Krak6w", "J1" → "Jl", "Bodø/Glimt" → "G1imt": matching folds
  1/i/l and 0/6/o and accepts SequenceMatcher ≥ 0.82 (New York City vs New York RB = 0.70).
- After the away club is confirmed the game goes straight to the pre-match screen (no extra Confirm).

## Kits, crests, in-FM choice, FM auto-sim (2026-10-10, verified live)
- Kits: UniformParameter.bin (common/character0/model/character/uniform/team/, data_s25262b.cpk: u32 count,
  then {u32 off, u32 size, u32 name off} per entry) holds "<id>_DEF_<kind>.bin" kit definitions: 120-byte
  `_realUni` ones point at licensed textures (u<id>p1...), 96-byte plain ones are the game's editable generic
  kits. Clubs with only plain ones: 0, 199 Zalgiris, 200 Ceres Negros, 899 Zamora FC (1386 not in Team.bin).
  Spare slots are exactly those three: plain maroon / white kits, no sponsor, our crest on the chest (seen on
  the Kits screen). The sleeve patch is SPFL26's SleeveBadge module (competition), not the kit.
- Select Team groups: writing the Team.bin +0x4f nibble into the match Team.bin did not move Ceres Negros to
  Other European Leagues, and no byte of the live edit-block team records (0x690) maps to the group, so
  spare slots stay in their own groups (Other European / Other Clubs (Asia) / Other Latin American Teams);
  the bridge's menu driver picks them there.
- Crests: SPFL26 loads team crests as PNGs, common/render/symbol/flag/e_<id 6 digits>_<f|r>[_l|_ll].png at
  128/256/512 px (sider tracer). The bridge writes both _f and _r names into the LiveCPK root.
- FM24 logos: data/game/graphics.fmf (header 02 01 'fmf.' 08 00 00, u64 index offset; data as [u32 size][zstd]
  frames; an entry's bytes at offset + 25 = flag byte then data; index = tree of dirs/files, see
  bridge/fm_graphics.py). graphics/pictures/logos/normal/clubs/config.xml maps "eng/oldham" ->
  graphics/pictures/club/694/logo; CLUB +0xc = 694 (unique id). Birmingham Legion has none (drawn badge).
- FM match-day flow: BRIEFING (GO TO MATCH) -> TEAM NEWS (DRESSING ROOM; GAME_MATCH readable from here) -> PEP
  TALK (MATCH PREVIEW, Space needed ~3 presses) -> PRE-MATCH (KICK OFF) -> match. The bridge arms on the memory
  read and watches FM's top bar (OCR of a 940x58 crop, ~0.1 s) for PRE-MATCH / the KICK OFF button, then shows
  the choice over FM (translucent overlay + card, FM EnableWindow(FALSE) until answered).
- FM auto-sim (fm_drive): Kick Off, resume when the clock stalls, Space on half-time buttons, Yes/Ok on
  confirmations, injury pop-up: drag the first substitute who is neither injured nor already rated onto the
  injured player (a used sub in S1 made it loop). Lab save, commentary only, top speed: ~9 min to FULL TIME;
  leaving the match screen afterwards ~10 s.

## No restart per match; own goals (2026-10-10, verified live)
- SPFL26 reads Player/Team/PlayerAssignment.bin only at boot, so LiveCPK alone cannot change squads in a running
  game. Its edit block holds live player records: [[0x143705e10]+0x48] + i*0x17c, player id +0x30, the four
  Player.bin name slots at +0x38 byte for byte, and every Player.bin field at another bit position as its full
  value (abilities w7, height u8 at bit 0, weight w7 at bit 8, age w6 at bit 224, ...): each mapped field
  matches Player.bin for 6000/6000 players (research/job_livefields.py; sheets/pes_player_fields.json live_*).
- bridge/spfl_live.py writes the built players there (36 for a match day) and restores them before the next match
  (since 0.4.1; at full time before); matchday.lua 0.4.0 polls request.txt every second, restores the previous squads and applies the new team
  names/rosters. The bridge only takes this path when the game reads the controller proxy and sider.log shows
  matchday.lua >= 0.4.0 (else it restarts the game as before).
- Live run: Birmingham Legion v Oldham (cold, 107 s to pre-match), then Atlanta v Oldham into the same game:
  FM names on both sides, slot 199's crest changed to Oldham's FM24 logo (crest PNGs are read when shown),
  39 s from the write to the pre-match screen, a 2-minute match tracked to final=1 2-0.
- Backing out of the pre-match screen: B opens "If you return to the previous screen, your Game Plan and Kit
  settings will be lost. Proceed?" with No (left) selected: RIGHT, A. Then B steps back to the main menu.
- FM own goals: event type 1, person = the player who scored it, side = the team it counts for (447/448 of the
  own-goal fixtures in a 2032 save add up that way; research/og_census.py). SPFL26's caption says "OWN GOAL"; the
  bridge reads a name from the conceding squad, else credits a starting defender of that side.

## Write-back speed, second match day (2026-10-10, user report)
- User run: SPFL26 final -> "Saved in FM24" took ~90 s (31 s until FM's events were read: every 2-s check rescanned
  FM's memory for the fixture copies; 16 s stats/events; 28 s clicking out of FM's post-match screens with a
  full-screen OCR + fixed 2-s pause per button). Now: fixture copies cached (re-read, full rescan every 20 s or
  when one is gone); FM's own events and today's stat records read ahead while the player is still in SPFL26 (FM
  waits at full time); leaving the match reads only the top bar + main button and waits for the label to change.
- Second match day not prompted: the watcher armed and never saw the pre-match screen. Likely: a background
  capture that stopped delivering frames (client_image returns its last frame) and/or a window-width-based crop
  too small for a windowed FM. Now: screen grab while FM is the active window, capture restarted when its
  newest frame is >4 s old, top bar/button crops sized by FM's DPI too, a running FM match also counts as past
  Match Preview, and what the watcher reads is logged every 20 s. FmReader.matchday(skip=...) also skips the
  previous match's GAME_MATCH, which FM can keep next to the new one.
- Verified live (research/job_e2e_two.py, two match days in one bridge session, FM minimized while SPFL26 plays):
  both prompted over FM at Match Preview; match 2 loaded into the running SPFL26; SPFL26 final -> "Saved in FM24"
  in 24 s and 28 s (2 s to write, 8-15 s through FM's post-match screens, ~10 s FM processing).
- FM's post-match pep talk can ask "No pep talk has been given ... hand over the pep talk to <assistant>?"
  (Hand Over / Proceed / Cancel). Windows OCR does not read those outlined buttons at any scale, and the
  sentence contains "hand over", so a text click hit the sentence. Hand Over is the focused button: Enter.
  Main button labels outside match day also include SOCIAL FEED and MUST RESPOND (an inbox item to answer).
- A running SPFL26 left inside a match (testkit's old menu exit pressed A blindly and walked into a new match)
  can't be backed out with B: the bridge now restarts SPFL26 when its screen stays unrecognised for 20 s.

## Scoreboard abbreviation after a match (2026-10-11, user report)
- User saw a wrong scoreboard abbreviation for Oldham. Every match the bridge sets up shows OLD (hot, cold and
  restart paths, research/job_scoreboard.py), but a match started after it ended (SPFL26's Rematch, or the
  testkit's stray match: research/shots/spfl_now.png) showed ZLG: matchday.lua restored the borrowed slot's team
  record at context_reset, while its crest files and boot players stayed FM24's.
- The scoreboard reads the abbreviation from the edit block team record (+0x4a). A second copy of the team
  records on the heap keeps the boot name (from our Team.bin) with the edit data's abbreviation (ZLG / CER); the
  scoreboard does not use it. The dot next to the abbreviation is the kit's UniColor_Color1, i.e. the borrowed
  plain kit's colour, not the club's.
- Now (matchday.lua 0.4.1): the FM24 teams stay in SPFL26 until the next request, which restores first; the bridge
  restores the borrowed live players when it loads the next match into the running game or closes, not at full
  time. Verified (research/job_rematch.py): Rematch after a hot match shows ATL / OLD; the next hot match day
  restored 36 players (Atlanta's own SPFL26 names back) and the team records, then BIR / OLD.

## Select Team through a cursor hook (2026-10-11, from the user's forceselection.lua)
- forceselection.lua 2.0 (user's own module, not loaded) detours two sites: FL_2026.exe+C95D7B (store of a list
  cursor move, forced when the list has 0x25 entries) and +C953D4 (the shared "current item" lookup, forced every
  frame). Disassembly (research/forcesel_disasm.txt): both belong to the game's generic list widget.
  +C95CA0 move(list, down): list +0x100/+0x108 = vector of 0x70-byte groups, cursor +0x118 (+0x11c); when list
  +0x9b != 0 it moves the current group's inner cursor +0x64 (+0x68) over its vector +0x08/+0x10 of 0x50-byte
  items instead. +C95300 = get item (list, inner, group), -1 = current.
- Select Team: each column is one such widget (home and away differ). Groups = the 36 league lists, items = clubs,
  item +0x00 = encoded team id ((v >> 14) & 0x1ffff); every list is filled and each of the 728 clubs is in
  exactly one (research/job_selprobe.py). +0x9b becomes 1 when the league is confirmed. Offsets +0x11c / +0x68
  were 0.
- matchday.lua 0.5.0: one cave at +C95D7B records the list that moved, its cursor cell and a move counter, and when
  armed (flag + target list) stores the bridge's index instead of old +/- 1 (only on a real move: the bounds
  check is before the store, so DOWN on the last entry does not reach it; the bridge presses UP there). Address
  in SiderAddons\matchday\hooks.txt; bridge/spfl_select.py checks the detour still jumps to that cave.
- Driver.fast_pick per column: DOWN (or UP) to learn the widget, find (league, club) by team id, armed press,
  A, armed press, A. Falls back to the OCR scroll from wherever it stopped. Back-out now stops at side select
  and presses B every 0.5 s on Select Team (one list per B).
- research/job_fastpick.py: Select Team 0.8-1.2 s per column (was ~25 s for both); pre-match 15 s after the
  request from a running game's pre-match screen (was 33-39 s), 60 s cold from launch (was ~85-107 s); OCR
  fallback with the hook unavailable still picks both (34 s).

## Same kits for the human club every match day (2026-10-11, user report)
- Spare slots were handed out in side order (home first), so Oldham had 199 (maroon plain kit) away at Atlanta
  but 200 (Ceres Negros' kits) away at Birmingham, who got 199 and wore Oldham's previous kit (seen on the Kits
  screen). Kits belong to the slot (UniformParameter.bin), so MatchBuilder now gives the human club the first
  spare and the opponent the next, whichever side they play on: in an Oldham career Oldham is always 199 and
  missing opponents 200; when the human club is in SPFL26, missing opponents are always 199.
- tests/test_spfl_build.py test_human_club_keeps_its_slot (fails on the old order). Each check needs a fresh
  PesDb: a build renames the slot in the in-memory Team data, so a reused one "finds" Oldham in slot 199.

## Big match squads; club names (2026-10-11, user report: no prompt for Liverpool v Galatasaray)
- FM24 found the match (6 GAME_MATCH copies) but the reader stopped at 36 roster entries: Liverpool named 26 (11 +
  15 subs), Galatasaray 22 = 48, so Galatasaray had 10 players read and the match day was rejected (< 11) without a
  log line. The roster list is null-terminated ([48..51] null, other data from [52]); the reader now reads up to 64
  and stops at the first null. The watcher logs why there is no match day each time the reason changes.
- Club names: FM "Galatasaray A.Ş." / SPFL "Galatasaray SK" did not match, so Galatasaray would have borrowed a spare
  slot. MatchBuilder.find_team now has a second pass without legal forms (A.Ş., S.A., SAD), club-type words (SK, JK,
  CD, UD, US, Calcio, ...) and SPFL26's founding years, accepted only for a unique SPFL26 club whose type words do
  not conflict (FC = FK = CF); FM short names only when they carry no type word; FM names with "(...)" exact only.
  Over the save's 26,361 FM clubs: 394 -> 450 matched, every new one the same club (research/fm_club_names.json);
  rejected: VfL Freiburg / SC Freiburg, Malmö IK / Malmö FF, Porto 2005 / FC Porto, River Plate (Montevideo),
  CD Montenegro / SV Uruguay (national teams), US Portsmouth. Lost: 1922 Konyaspor (FM's own year stays).

## Faces; empty pre-match line-ups (2026-10-11, user report: Diogo Jota showed Virgil van Dijk's face)
- SPFL26 shows a player's real head and menu portrait by player id (Asset/model/character/face/real/<id>/,
  common/render/symbol/player/<id>.dds; 15,088 ids have a real face, from the .cpk tables of contents, ~2 s, cached:
  bridge/spfl_faces.py). FM24 players took over records of the club's other players (Jota -> 44840 = van Dijk).
- SPFL26 rebuilds a club's roster from the players registered at that club when the club is picked in Select Team
  (research/job_afterpick: after the pick the live roster is the PlayerAssignment order, 39 players; no live copy of
  the assignment table was found in memory). So records of other clubs cannot be used: a roster written after the
  pick that holds them empties the pre-match line-ups ("(GK)(C)" only, no crests/names); one written before the pick
  is simply replaced. Faces are therefore lent instead: the FM24 player keeps a record of this club and, when SPFL26
  has him at another club (one record of his name with his birth year +/- 1, SPFL ages = 2025 - birth year), his face
  folder and portrait are served for that record id from the LiveCPK match root (spfl_faces.lend_faces); players
  SPFL26 has no face for take the club's faceless records first, else a generic portrait.
- matchday.lua 0.5.3: the FM24 order is written when the request arrives and once more (up to 3 times) when the pick
  puts the club's original order back; any other order is the player's own team-sheet edit and stays; nothing during
  a match. Restores only the fields it changes (name/abbr, roster/captain/shirts), not whole 0x690 team records;
  roster entries keep the game's per-club tag ({id, 0, tag}, last {id, 0xffff, 0}, empty 0). 0.5.1 (rewrite every
  difference) and 0.5.2 (write once) both failed.
- The bridge only loads into a running game with matchday.lua >= 0.5.4 (else restarts it).
- Verified (research/job_faces3.py, Liverpool v Galatasaray 26 + 22 from the save's names/birth dates): fresh start
  and load into the running game both show the FM24 XIs on the pre-match screen; the team sheet shows Diogo Jota,
  Kelleher, Elliott (lent from Brentford/Aston Villa), Gomez, Gakpo, Icardi, Ziyech, Zaha... with their own faces.
- No wrong faces for players SPFL26 lacks (2026-10-11, user request; Joël Matip is in no SPFL26 record, retired):
  no Player.bin bit separates real-face players from the rest (best single bit 0.63 vs 0.34 over 29,492 players),
  so "real head" = the face files exist for the id. matchday.lua 0.5.4 registers livecpk_rewrite and renames
  face/real/<id>/ to face/real/matchday_noface/ for the ids in request.txt <side>_noface (borrowed real-face
  records given to FM24 players without an SPFL face; kept until the next request); SPFL26 then builds a generic
  head, as for a faceless player (no hang: Sider warns that missing model files can loop forever, but the game only
  asks for the face files and treats them as absent). Menu portrait: the player's own SPFL26 portrait when SPFL26
  has him without a real face, else a transparent 128x128 DXT5 (WESYS) portrait = no face icon
  (spfl_faces.blank_portrait). research/job_faces5.py (the Liverpool players SPFL26 lacks in the XI): six ids
  rewritten, zero real-face loads for them in the tracer over two matches (fresh start and running game), every
  other face loaded; the team sheet shows no icon for Adrián, Matip, Pinnington, Miles, Davidson, Doak, Tsimikas.

## Gotchas
1. um's chocolatey ffmpeg lacked gfxcapture; `um win setup --force` + `UM_FFMPEG_WIN`.
2. FM UI coordinates are logical (1706×960 client at 150% scaling); screenshots are physical pixels.
3. SPFL is elevated, so reading/driving it needs an elevated helper (`research/elevated_runner.py`).
4. FM friendly squads can be "ineligible" (tour squad); Quick Pick solves it.
5. SPFL is exclusive-fullscreen: it minimizes whenever another window takes focus (FM, installers).
   Restore with ShowWindow(SW_RESTORE)+SetForegroundWindow before sending keys or screenshots.
6. Killing fm.exe opens SI's crash_reporter, which blocks Steam relaunch until closed (never send).
7. The bridge exe is uac_admin: one UAC prompt, then SPFL can be restarted/launched without more prompts.
8. computer-use cannot click elevated windows (UIPI); drive them from the elevated runner.
