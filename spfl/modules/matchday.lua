--[[
matchday.lua - Matchday Bridge (FM24 x SPFL26) for Sider 7

Shows which Football Manager 2024 fixture is loaded, and writes the live and final score to
SiderAddons\matchday\result.txt so the Matchday Bridge app can hand it back to FM24.

The squads themselves are not in this file: the bridge builds them from your FM24 match day and
serves them through the LiveCPK root SiderAddons\livecpk\matchday (common\etc\pesdb\*.bin),
generated from your own SPFL26 install.

Overlay: Spacebar toggles the Sider overlay; press 1 until "matchday" is shown.
--]]

-- BEGIN GENERATED (tools/gen.py from sheets/ui_text.json + hooks.json)
local G = {}
G.text = {
    banner = "FM24 MATCHDAY  {home} v {away}  ({comp}, {date})",
    pick_teams = "Pick {home_spfl} ({home_league}) as home and {away_spfl} ({away_league}) as away in Match > Local Match. FM24 squads and ratings are loaded.",
    no_request = "Matchday Bridge: no FM24 match waiting. Start it from FM24's team news screen.",
    fm_missing = "Football Manager 2024 is not installed (looked in every Steam library). Matchday Bridge needs it.",
    spfl_missing = "SP Football Life 2026 is not installed. Matchday Bridge needs it.",
    result_saved = "Final score saved for FM24: {home} {hg}-{ag} {away}",
    prompt = "Match day: {home} v {away}\nPlay this match in SP Football Life 2026, or let FM24 simulate it?",
    writeback_wait = "Full time in SPFL26: {home} {hg}-{ag} {away}.\nFM24 plays its own match out in the background; at FM's full time this score and its scorers go in and FM24 moves on to save them. Leave FM24's window open (not minimized).",
    writeback_done = "Saved in FM24: {home} {hg}-{ag} {away}.",
    spfl_restart = "Restarting SP Football Life 2026 so it loads this match's squads...",
    drive_busy = "SPFL26 is starting. Matchday Bridge walks its menus for you: Local Match, {home} v {away}, controller 1 on {you}. It works in the background; you don't need to touch the game yet.",
    drive_ready = "SPFL26 is on the pre-match screen. Choose kits and stadium, then Kick Off. You play {you} ({side}) with controller 1. FM24 is simulating its own match in the background meanwhile.",
}
G.off = {
    owner_global = 0x143705e10,  -- EDIT_BLOCK: [global]+0x48 = edit block (no ASLR)
    team_count = 0xd0bcec,  -- EDIT_BLOCK: teams in use (749)
    player_count = 0xd0bce8,  -- EDIT_BLOCK: players in use; grew 29492->29524 with our 32 new players
    teams = 0xadf4bc,  -- EDIT_BLOCK: team records
    id_encoded = 0x0,  -- TEAM_REC: team id = (v>>14)&0x1ffff
    name = 0x4,  -- TEAM_REC: team name
    abbr = 0x4a,  -- TEAM_REC: 3-letter scoreboard name
    roster = 0x150,  -- TEAM_REC: squad in order; first 11 start; marker 0xffff on the last player and every empty slot
    captain_index = 0x294,  -- TEAM_REC: roster index (assumed captain); must be < squad size
    shirts = 0x29a,  -- TEAM_REC: shirt numbers in roster order
    stride = 0x17c,  -- LIVE_PLAYER: live player records from the edit block start (+0x0), player_count of them
    player_id = 0x30,  -- LIVE_PLAYER: player id (Player.bin +0x08)
    names = 0x38,  -- LIVE_PLAYER: the four Player.bin name slots (+0x44 there)
}
G.hooks = {
    spfl_db_override = { event = "livecpk_get_filepath", enabled = true },
    spfl_banner = { event = "overlay_on", enabled = true },
    spfl_result_capture = { event = "display_frame", enabled = true },
    spfl_scorers_capture = { event = "display_frame", enabled = false },
    spfl_autokickoff = { event = "menu automation to kickoff", enabled = false },
}
-- END GENERATED
local m = { version = "0.5.4" }

local dir, request, status_line = nil, nil, ""
local last_written = ""
local applied, saved, frame = false, {}, 0
local TEAM_REC = 0x690
local goals = {}          -- one entry per goal in match order: side ("h"/"a") .. clock minute .. "p" .. period
local last_score = nil    -- {home, away} of the previous frame; nil between matches

-- Score went up: remember who scored (side) and when; the Matchday Bridge app reads the scorer's name from
-- SPFL's on-screen caption. A new match always starts at 0-0 after a frame without match stats.
local function track_goals(st)
    local h, a = st.home_score or 0, st.away_score or 0
    if not last_score then
        if h == 0 and a == 0 then goals = {} end
    elseif h < last_score[1] or a < last_score[2] then
        goals = {}
    else
        for _ = 1, h - last_score[1] do
            goals[#goals + 1] = string.format("h%dp%d", st.clock_minutes or 0, st.period or 0)
        end
        for _ = 1, a - last_score[2] do
            goals[#goals + 1] = string.format("a%dp%d", st.clock_minutes or 0, st.period or 0)
        end
    end
    last_score = { h, a }
end

local function u32(a) return memory.unpack("u32", memory.read(a, 4)) end
local function u64(a) return memory.unpack("u64", memory.read(a, 8)) end

local function edit_block()
    local owner = u64(G.off.owner_global)
    if owner == 0 then return nil end
    local blk = u64(owner + 0x48)
    if blk == 0 then return nil end
    local n = u32(blk + G.off.team_count)
    if n < 100 or n > 4000 then return nil end
    return blk, n
end

local function find_team(blk, n, tid)
    local base = blk + G.off.teams
    for i = 0, n - 1 do
        local enc = u32(base + i * TEAM_REC)
        if bit.band(bit.rshift(enc, 14), 0x1ffff) == tid then
            return base + i * TEAM_REC
        end
    end
    return nil
end

local function split_nums(s)
    local t = {}
    for v in string.gmatch(s or "", "%d+") do t[#t + 1] = tonumber(v) end
    return t
end

-- Only what the bridge changes is saved and put back (name + abbreviation; roster, captain and shirt numbers), so
-- the game's own state elsewhere in the team record is never overwritten with an old copy.
local SAVE_RANGES = { { 0x4, 0x4a }, { 0x150, 0x19a } }
local match_live = false    -- a match has kicked off (rosters are left alone until the next request)

local function remember(rec)
    for _, s in ipairs(saved) do if s[1] == rec then return end end
    local parts = {}
    for _, r in ipairs(SAVE_RANGES) do parts[#parts + 1] = { rec + r[1], memory.read(rec + r[1], r[2]) } end
    saved[#saved + 1] = { rec, parts }
end

local function roster_ids(rec)
    local t = {}
    for k = 0, 39 do
        local id = u32(rec + G.off.roster + k * 8)
        if id == 0 then break end
        t[#t + 1] = id
    end
    return t
end

local function same_list(a, b)
    if #a ~= #b then return false end
    for i = 1, #a do if a[i] ~= b[i] then return false end end
    return true
end

-- Entries as the game writes them: {u32 player, u16 0, u16 tag} with the club's tag, the last {player, 0xffff, 0},
-- empty slots zero.
local function write_roster(rec, ids, shirts)
    local n = #ids
    local tag = memory.unpack("u16", memory.read(rec + G.off.roster + 6, 2))
    for k = 0, 39 do
        local e = rec + G.off.roster + k * 8
        local id = ids[k + 1] or 0
        memory.write(e, memory.pack("u32", id))
        memory.write(e + 4, memory.pack("u16", (k == n - 1) and 0xffff or 0))
        memory.write(e + 6, memory.pack("u16", (id ~= 0 and k < n - 1) and tag or 0))
        memory.write(rec + G.off.shirts + k * 2, memory.pack("u16", shirts[k + 1] or 0))
    end
    if u32(rec + G.off.captain_index) % 0x10000 >= n then
        memory.write(rec + G.off.captain_index, memory.pack("u16", 0))
    end
end

local function padded(s, len)
    s = string.sub(s, 1, len - 1)
    return s .. string.rep("\0", len - #s)
end

-- SPFL26's edit data keeps its own scoreboard abbreviation, so the spare slot's name and
-- abbreviation are written here even when the LiveCPK database already supplies the squad.
local function names_need_write(rec, name, abbr)
    if name and name ~= "" and memory.read(rec + G.off.name, 0x46) ~= padded(name, 0x46) then return true end
    if abbr and abbr ~= "" and memory.read(rec + G.off.abbr, 4) ~= padded(abbr, 4) then return true end
    return false
end

local function write_names(rec, name, abbr)
    if name and name ~= "" then memory.write(rec + G.off.name, padded(name, 0x46)) end
    if abbr and abbr ~= "" then memory.write(rec + G.off.abbr, padded(abbr, 4)) end
end

-- SPFL26 rebuilds a club's roster in its own order (the players registered at the club) when the club is picked in
-- Select Team. The FM24 order is written when the request arrives and, if the pick then puts the club's original
-- order back, once more; any other order is the player's own team-sheet change and stays. Rosters are not touched
-- while a match is on. (0.5.1 rewrote every difference, also over records the pick had dropped: empty line-ups.)
local function roster_matches(rec, ids)
    return #ids > 0 and same_list(roster_ids(rec), ids)
end

local rosters_written = {}    -- side -> {orig = the club's own order, rewrites = n} once this request's roster went in

local function apply_squads()
    if not request or not request.home_tid then return end
    local blk, n = edit_block()
    if not blk then return end
    local done = 0
    for _, side in ipairs({ "home", "away" }) do
        local ids = split_nums(request[side .. "_ids"])
        local rec = find_team(blk, n, tonumber(request[side .. "_tid"]))
        if rec then
            local name, abbr = request[side .. "_rename"], request[side .. "_abbr"]
            local rw = rosters_written[side]
            if not match_live and #ids > 0 and not roster_matches(rec, ids) then
                local now = roster_ids(rec)
                if not rw or (rw.rewrites < 3 and same_list(now, rw.orig)) then
                    remember(rec)
                    rosters_written[side] = { orig = rw and rw.orig or now, rewrites = rw and rw.rewrites + 1 or 0 }
                    write_roster(rec, ids, split_nums(request[side .. "_shirts"]))
                    done = done + 1
                end
            elseif not rw then
                rosters_written[side] = { orig = roster_ids(rec), rewrites = 0 }
            end
            if names_need_write(rec, name, abbr) then
                remember(rec)
                write_names(rec, name, abbr)
                done = done + 1
            end
        end
    end
    if done > 0 then
        applied = true
        log(string.format("matchday: wrote %d FM24 team changes into SPFL26 edit data", done))
    end
end

function m.set_teams(ctx, home, away)
    if not request then return end
    apply_squads()
    for i, side in ipairs({ "home", "away" }) do
        local tid = (i == 1) and home or away
        if tid == tonumber(request[side .. "_tid"]) then
            log("matchday: " .. side .. " is the FM24 squad (" .. tostring(tid) .. ")")
        end
    end
end

local function restore_squads()
    for i = #saved, 1, -1 do
        for _, part in ipairs(saved[i][2]) do memory.write(part[1], part[2]) end
    end
    if #saved > 0 then log("matchday: restored original SPFL26 squads") end
    saved = {}
end

local function read_file(path)
    local f = io.open(path, "rb")
    if not f then return nil end
    local s = f:read("*a")
    f:close()
    return s
end

local function parse_request(s)
    local r = {}
    for k, v in string.gmatch(s or "", "([%w_]+)=([^\r\n]*)") do
        r[k] = v
    end
    if not r.home then return nil end
    return r
end

local function fmt(template, t)
    return (string.gsub(template, "{([%w_]+)}", function(k) return t[k] or ("{" .. k .. "}") end))
end

local function write_result(stats, final)
    local line = string.format("home=%d\naway=%d\nperiod=%d\nminute=%d\nfinal=%s\ngoals=%s\n",
        stats.home_score or 0, stats.away_score or 0, stats.period or 0, stats.clock_minutes or 0,
        final and "1" or "0", table.concat(goals, ","))
    if line == last_written then return end
    local f = io.open(dir .. "result.txt", "wb")
    if f then
        f:write(line)
        f:close()
        last_written = line
    end
end

function m.overlay_on(ctx)
    request = parse_request(read_file(dir .. "request.txt")) or request
    if not request then
        return G.text.no_request
    end
    if request.fm_installed == "0" then
        return G.text.fm_missing
    end
    local s = fmt(G.text.banner, request) .. "\n" .. fmt(G.text.pick_teams, request)
    if status_line ~= "" then s = s .. "\n" .. status_line end
    return s
end

local was_live = false
local last_request_text = nil

-- Borrowed records whose real face must not show (the bridge lends them to FM24 players SPFL26 has no face for).
-- SPFL26 decides "real head or generic head" only by whether the face files for the id exist (no Player.bin flag
-- separates the 15,088 real-face players from the rest), so their face files are renamed to a folder that does not
-- exist and SPFL26 builds a generic head, as for any player without a real face. Kept until the next request, like
-- the FM24 squads (a Rematch still has them).
local noface, noface_logged = {}, {}

local function load_noface(r)
    noface, noface_logged = {}, {}
    for _, side in ipairs({ "home", "away" }) do
        for _, id in ipairs(split_nums(r and r[side .. "_noface"])) do noface[id] = true end
    end
end

function m.rewrite(ctx, filename)
    local id, after = string.match(filename, "[Ff]ace[\\/]real[\\/](%d+)()[\\/]")
    if not id or not noface[tonumber(id)] then return nil end
    if not noface_logged[id] then
        noface_logged[id] = true
        log("matchday: real face of " .. id .. " hidden (" .. filename .. ")")
    end
    return string.sub(filename, 1, after - #id - 1) .. "matchday_noface" .. string.sub(filename, after)
end

-- A running SPFL26 gets each new FM24 match through request.txt (the bridge no longer restarts the game per
-- match): picked up within a second or two, after the previous match's squads are put back.
local function poll_request()
    local text = read_file(dir .. "request.txt")
    if text == last_request_text then return end
    last_request_text = text
    local r = parse_request(text)
    if not r then return end
    restore_squads()
    request, applied, saved, rosters_written, match_live = r, false, {}, {}, false
    load_noface(r)
    goals, last_score, last_written, status_line, was_live = {}, nil, "", "", false
    log(string.format("matchday: new FM24 fixture %s v %s", request.home or "?", request.away or "?"))
    apply_squads()
end

function m.display_frame(ctx)
    frame = frame + 1
    if frame % 60 == 0 then
        poll_request()
    end
    if not request then return end
    if frame % 120 == 1 then
        apply_squads()
    end
    local st = match.stats()
    if st and st.period and st.period > 0 then
        was_live, match_live = true, true
        track_goals(st)
        write_result(st, false)
        status_line = string.format("Live: %s %d-%d %s (%d')", request.home_spfl or "home", st.home_score or 0,
            st.away_score or 0, request.away_spfl or "away", st.clock_minutes or 0)
    elseif was_live and not st then
        was_live = false
        last_score = nil
    end
end

function m.context_reset(ctx)
    match_live = false
    -- leaving a match: the last live score is the final one. The FM24 teams stay in the edit data until the
    -- next request (poll_request restores first), so a Rematch still shows their names and abbreviations.
    if request and last_written ~= "" then
        local s = string.gsub(last_written, "final=0", "final=1")
        local f = io.open(dir .. "result.txt", "wb")
        if f then f:write(s); f:close() end
        last_written = s
        status_line = fmt(G.text.result_saved, {home = request.home_spfl, away = request.away_spfl,
            hg = string.match(s, "home=(%d+)"), ag = string.match(s, "away=(%d+)")})
        local rf = io.open(dir .. "request.txt", "wb")
        if rf then rf:write("done=1\n"); rf:close() end
        last_request_text = "done=1\n"
        request = nil
    end
end

-- Select Team in one press per list (after forceselection.lua 2.0, the project author's Sider module: its league
-- write-force site).
-- FL_2026.exe+C95D7B is the cursor store of the game's list widget (every menu list): [r8] = old index +/- 1, rbx =
-- the list. The cave records the list that moved last and a move counter; armed for one list (flag, target list), it
-- stores the bridge's index instead. The bridge reads the cave (address in matchday\hooks.txt), finds the club in
-- that list's own league/team vectors and sets each cursor with a single DOWN or UP.
-- Cave: code 0-71, then rec_list u64 @72, rec_cell u64 @80, target_list u64 @88, value u32 @96, moves u32 @100,
-- flag u8 @104.
local SELECT_SIG = "\x42\x8d\x04\x11\x41\x89\x00\x80\xbb\x9b\x00\x00\x00\x00"

local function select_cave_code(ret)
    local function d(n) return memory.pack("i32", n) end
    return table.concat({
        "\x48\x89\x1D", d(65),          -- 00 mov [rec_list],rbx
        "\x4C\x89\x05", d(66),          -- 07 mov [rec_cell],r8
        "\xFF\x05", d(80),              -- 14 inc dword [moves]
        "\x42\x8D\x04\x11",             -- 20 lea eax,[rcx+r10]        (original)
        "\x80\x3D", d(73), "\x00",      -- 24 cmp byte [flag],0
        "\x74\x0F",                     -- 31 je store
        "\x48\x3B\x1D", d(48),          -- 33 cmp rbx,[target_list]
        "\x75\x06",                     -- 40 jne store
        "\x8B\x05", d(48),              -- 42 mov eax,[value]
        "\x41\x89\x00",                 -- 48 store: mov [r8],eax      (original)
        "\x80\xBB\x9B\x00\x00\x00\x00", -- 51 cmp byte [rbx+9B],0      (original)
        "\xFF\x25\x00\x00\x00\x00",     -- 58 jmp [rip]
        memory.pack("u64", ret),        -- 64
        string.rep("\0", 40),           -- 72 data
    })
end

local function install_select_hook()
    local at = memory.search_process(SELECT_SIG)
    if not at then
        log("matchday: Select Team hook not installed (cursor store not found; another module may hook it)")
        return nil
    end
    local cave = memory.allocate_codecave(128)
    memory.write(cave, select_cave_code(at + #SELECT_SIG))
    memory.write(at, "\xFF\x25\x00\x00\x00\x00" .. memory.pack("u64", cave))
    log("matchday: Select Team hook at " .. memory.hex(at) .. ", cave " .. memory.hex(cave))
    return cave, at
end

function m.init(ctx)
    dir = ctx.sider_dir .. "matchday\\"
    fs.make_dirs(dir)
    last_request_text = read_file(dir .. "request.txt")
    request = parse_request(last_request_text)
    load_noface(request)
    log("matchday: matchday.lua " .. m.version)
    if request then
        log(string.format("matchday: FM24 fixture %s v %s loaded", request.home or "?", request.away or "?"))
    else
        log("matchday: no FM24 request waiting")
    end
    local cave, at = install_select_hook()
    local hf = io.open(dir .. "hooks.txt", "wb")
    if hf then
        hf:write(string.format("version=%s\n", m.version))
        if cave then
            hf:write(string.format("select_cave=%s\nselect_at=%s\n", memory.hex(cave), memory.hex(at)))
        end
        hf:close()
    end
    ctx.register("overlay_on", m.overlay_on)
    ctx.register("display_frame", m.display_frame)
    ctx.register("context_reset", m.context_reset)
    ctx.register("set_teams", m.set_teams)
    ctx.register("livecpk_rewrite", m.rewrite)
end

return m
