--[[
matchday_test.lua - DEV/TEST ONLY companion for Matchday Bridge (installed by testkit, never shipped).

* Writes SPFL26 state to SiderAddons\matchday\test_state.txt about 10x per second (match pointer, period,
  clock, score, pause/clock-running flags, match stage, counters of Sider events) so test scripts wait on
  real game events, not fixed delays.
* Reads SiderAddons\matchday\test.txt (key=value):
    match_minutes=N   -> match length in real minutes (Sider allows less than the menu's 5-minute minimum)
    extra_time=0|1, penalties=0|1 -> override the match settings (tests use 0/0: draws end at 90 minutes)

Team forcing (patching the final team ids, as SiderAddons\modules\forceteamid.lua does) was tried and
removed: kits/squads are prepared for the selected teams, so swapping ids afterwards crashed sider.dll.
--]]

local m = { version = "0.5.0" }
local dir
local counts = {}
local frame = 0
local goals = {}              -- "h45" / "a12": side + clock minute of each goal, in order
local last_score = nil

local function bump(ev) counts[ev] = (counts[ev] or 0) + 1 end

local function read_cfg()
    local cfg = {}
    local f = io.open(dir .. "test.txt", "rb")
    if not f then return cfg end
    for k, v in string.gmatch(f:read("*a") or "", "([%w_]+)=([^\r\n]*)") do cfg[k] = v end
    f:close()
    return cfg
end

local function u8(a) return memory.unpack("u8", memory.read(a, 1)) end
local function u64(a) return memory.unpack("u64", memory.read(a, 8)) end

local function write_state(st)
    local parts = { string.format("t=%.3f", os.clock()) }
    for ev, n in pairs(counts) do parts[#parts + 1] = "ev_" .. ev .. "=" .. n end
    parts[#parts + 1] = "goals=" .. table.concat(goals, ",")
    if st then
        parts[#parts + 1] = "ptr=" .. memory.hex(st.ptr)
        parts[#parts + 1] = "period=" .. tostring(st.period)
        parts[#parts + 1] = "minute=" .. tostring(st.clock_minutes)
        parts[#parts + 1] = "second=" .. tostring(st.clock_seconds)
        parts[#parts + 1] = "home=" .. tostring(st.home_score)
        parts[#parts + 1] = "away=" .. tostring(st.away_score)
        -- SCOREBOARD_INFO: +0x20 is_paused, +0x22 is_clock_running, +0x38 -> info2 (+0x88 match stage)
        local p = tonumber(memory.hex(st.ptr))   -- st.ptr is userdata; addresses < 2^47 fit a double
        if p and p > 0x10000 then
            parts[#parts + 1] = "paused=" .. u8(p + 0x20)
            parts[#parts + 1] = "running=" .. u8(p + 0x22)
            local p2 = u64(p + 0x38)
            if p2 > 0x10000 and p2 < 0x7fffffffffff then
                parts[#parts + 1] = "stage=" .. u8(p2 + 0x88)
            end
        end
    else
        parts[#parts + 1] = "ptr=0"
    end
    local f = io.open(dir .. "test_state.txt", "wb")
    if f then f:write(table.concat(parts, "\n") .. "\n"); f:close() end
end

function m.display_frame(ctx)
    frame = frame + 1
    local st = match.stats()
    if st and st.home_score then
        local h, a = st.home_score, st.away_score or 0
        if not last_score and h == 0 and a == 0 then
            goals = {}                         -- a new match starts at 0-0 (stats are nil between matches)
        end
        if last_score and (h < last_score[1] or a < last_score[2]) then
            goals = {}                         -- a new match (rematch keeps the old match pointer)
        elseif last_score and (h ~= last_score[1] or a ~= last_score[2]) then
            local side = (h ~= last_score[1]) and "h" or "a"
            goals[#goals + 1] = string.format("%s%d:%02d", side, st.clock_minutes or 0, st.clock_seconds or 0)
        end
        last_score = { h, a }
    elseif not st then
        last_score = nil
    end
    if frame % 6 == 0 then
        write_state(st)
    end
end

function m.set_match_time(ctx, minutes)
    bump("set_match_time")
    local n = tonumber(read_cfg().match_minutes or "")
    if n and n > 0 then
        log(string.format("matchday_test: match time %d -> %d minutes", minutes, n))
        return n
    end
end

-- extra_time=0 / penalties=0 in test.txt: a drawn test match ends at 90 minutes (Local Match has both on).
-- Must load before SPFL's matchset.lua (testkit inserts it there): the first module returning a table wins.
function m.set_match_settings(ctx, options)
    bump("set_match_settings")
    local cfg = read_cfg()
    local out
    for _, k in ipairs({ "extra_time", "penalties" }) do
        local v = tonumber(cfg[k] or "")
        if v then
            if not out then
                out = {}
                for ok, ov in pairs(options) do out[ok] = ov end
            end
            out[k] = v
        end
    end
    if out then
        log(string.format("matchday_test: extra_time %s -> %s, penalties %s -> %s", tostring(options.extra_time),
            tostring(out.extra_time), tostring(options.penalties), tostring(out.penalties)))
    end
    return out
end

-- Handlers must stay referenced from the module table: Sider keeps them only on its Lua stack, and a
-- collected anonymous closure crashed the game in the LuaJIT VM (sider.dll+0x2ff8) on set_teams/context_reset.
function m.on_set_teams() bump("set_teams"); goals = {}; last_score = nil end
function m.on_after_set_conditions() bump("after_set_conditions") end
function m.on_context_reset() bump("context_reset") end

function m.init(ctx)
    dir = ctx.sider_dir .. "matchday\\"
    fs.make_dirs(dir)
    ctx.register("display_frame", m.display_frame)
    ctx.register("set_match_time", m.set_match_time)
    ctx.register("set_match_settings", m.set_match_settings)
    ctx.register("set_teams", m.on_set_teams)
    ctx.register("after_set_conditions", m.on_after_set_conditions)
    ctx.register("context_reset", m.on_context_reset)
    log("matchday_test: loaded")
end

return m
