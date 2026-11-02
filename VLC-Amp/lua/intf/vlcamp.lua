--[[
vlcamp.lua - Lua interface for the VLC Amp skin (VLC 3.0.x, Lua 5.1).

Adds what the skins2 engine cannot do with buttons:
  * A-B loop           (1st trigger sets A, 2nd sets B and loops, 3rd clears)
  * Next / previous folder (local files, from the playlist order)
  * Next / previous equalizer preset
  * A bitrate for lossless files (FLAC, WAV, ...), so the skin's "kbps" is not 0
  * Durations in the playlist, at the right edge (not on the playing item;
    --lua-config "vlcamp={durations='suffix'}" for "Title (3:42)", 'off' for none)

Start it next to the skin:
    vlc --intf skins2 --extraintf luaintf --lua-intf vlcamp
or put   extraintf=luaintf   and   lua-intf=vlcamp   into vlcrc (Setup does).
It goes into VLC's user Lua folder:
    Windows  %APPDATA%\vlc\lua\intf\vlcamp.lua
    Linux    ~/.local/share/vlc/lua/intf/vlcamp.lua

How it is triggered
-------------------
Lua in VLC 3.0 has no callbacks, so the script polls the libvlc variable
"key-action" (the id of the hotkey action VLC just ran) every 50-100 ms and
sets it back to 0. It reacts to five hotkey actions that VLC has but that are
useless for music; VLC still runs its own handler for them, which does nothing
unless a 360 degree video is playing (subsync-markaudio only stores a time stamp):

    action name                      does here                  default key
    key-subsync-markaudio            A-B loop                   Ctrl+Shift+A
    key-viewpoint-roll-clock         next folder                Ctrl+Shift+Right
    key-viewpoint-roll-anticlock     previous folder            Ctrl+Shift+Left
    key-viewpoint-fov-in             next equalizer preset      Ctrl+Shift+Up
    key-viewpoint-fov-out            previous equalizer preset  Ctrl+Shift+Down

Bind any key (or a global key, "global-key-<name>") to them in VLC's
preferences, or let a program send them through the web interface:
    requests/status.json?command=key&val=subsync-markaudio
The skin itself shows no A-B state (skins2 reads the title once per track);
state and results go to VLC's log (vlc -v, or Tools > Messages).

Everything runs inside pcall: an error is logged and the loop goes on.
--]]

local TAG = "[vlcamp] "
local POLL_IDLE_US = 100000      -- poll period normally
local POLL_FAST_US = 50000       -- while an A-B loop is running
local AB_MIN_SPAN_US = 500000    -- B must be at least this much after A
local AB_HOLD_US = 400000        -- after looping back, ignore time for a moment (seeks are queued)
local EQ_RETRY_US = 6000000      -- how long a chosen preset waits for the equalizer filter

local ACTIONS = {                -- what each trigger is, by VLC action name
    ab          = "key-subsync-markaudio",
    folder_next = "key-viewpoint-roll-clock",
    folder_prev = "key-viewpoint-roll-anticlock",
    eq_next     = "key-viewpoint-fov-in",
    eq_prev     = "key-viewpoint-fov-out",
}

local function log(msg)  vlc.msg.info(TAG .. msg) end
local function warn(msg) vlc.msg.warn(TAG .. msg) end
local function now()     return vlc.misc.mdate() end

-- vlc.var.get that never raises (nil object, unknown variable)
local function varget(obj, name)
    if obj == nil then return nil end
    local ok, v = pcall(vlc.var.get, obj, name)
    if ok then return v end
    return nil
end

local function fmt_time(us)
    local s = math.floor((us or 0) / 1000)       -- ms
    local m = math.floor(s / 60000); s = s - m * 60000
    return string.format("%d:%04.1f", m, s / 1000)
end

-- an identity for the playing track: playlist id + URI ("" when nothing plays)
local function track_key()
    local ok, k = pcall(function()
        local item = vlc.input.item()
        if not item then return "" end
        return tostring(vlc.playlist.current()) .. "|" .. tostring(item:uri())
    end)
    if ok then return k end
    return ""
end

----------------------------------------------------------------------
-- A-B loop
----------------------------------------------------------------------
local ab = { state = "off", a = 0, b = 0, key = "", hold = 0 }

local function ab_clear(why)
    if ab.state ~= "off" then log("A-B loop cleared" .. (why and (" (" .. why .. ")") or "")) end
    ab.state = "off"
end

local function ab_trigger()
    local input = vlc.object.input()
    if ab.state == "off" then
        if not input then log("A-B loop: nothing is playing"); return end
        if varget(input, "can-seek") == false then log("A-B loop: this stream cannot seek"); return end
        local t = varget(input, "time")
        if not t then return end
        ab.a, ab.key, ab.state = t, track_key(), "a"
        log("A-B loop: A set at " .. fmt_time(t) .. " (trigger again for B)")
    elseif ab.state == "a" then
        if not input or track_key() ~= ab.key then ab_clear("track changed"); return end
        local t = varget(input, "time")
        if not t then return end
        if t < ab.a + AB_MIN_SPAN_US then
            log("A-B loop: B must be at least 0.5 s after A (" .. fmt_time(ab.a) .. ")")
            return
        end
        ab.b, ab.state, ab.hold = t, "ab", now() + AB_HOLD_US
        vlc.var.set(input, "time", ab.a)
        log("A-B loop: looping " .. fmt_time(ab.a) .. " - " .. fmt_time(ab.b) .. " (trigger again to clear)")
    else
        ab_clear("by user")
    end
end

local function ab_tick()
    if ab.state == "off" then return end
    local input = vlc.object.input()
    if not input or track_key() ~= ab.key then ab_clear("track changed or playback stopped"); return end
    if ab.state ~= "ab" or now() < ab.hold then return end
    local t = varget(input, "time")
    if t and t >= ab.b then
        vlc.msg.dbg(TAG .. "A-B loop back at " .. fmt_time(t) .. " (B " .. fmt_time(ab.b) .. ")")
        vlc.var.set(input, "time", ab.a)
        ab.hold = now() + AB_HOLD_US
    end
end

----------------------------------------------------------------------
-- Next / previous folder
----------------------------------------------------------------------
local is_windows = package.config:sub(1, 1) == "\\"

-- Directory part of a local file URI (normalised for comparing), nil for anything else
local function dir_of(uri)
    if type(uri) ~= "string" or uri:sub(1, 7):lower() ~= "file://" then return nil end
    local d = uri:match("^(.*)/[^/]*$")
    if not d then return nil end
    d = d:gsub("%%(%x%x)", function(h) return "%" .. h:upper() end)
    if is_windows then d = d:lower() end
    return d
end

-- All playlist items in play order: { {id=, dir=}, ... }
local function flat_playlist()
    local list = {}
    local function walk(node, depth)
        if depth > 32 then return end
        if node.path ~= nil and node.id ~= nil then
            list[#list + 1] = { id = node.id, dir = dir_of(node.path), path = node.path }
        end
        if node.children then
            for _, c in ipairs(node.children) do walk(c, depth + 1) end
        end
    end
    local root = vlc.playlist.get("playlist")
    if root then walk(root, 0) end
    return list
end

local function folder_jump(dir)       -- dir = +1 next folder, -1 previous folder
    local list = flat_playlist()
    local cur = vlc.playlist.current()
    local idx
    for i, e in ipairs(list) do if e.id == cur then idx = i; break end end
    if not idx then
        local item = vlc.input.item()
        local uri = item and item:uri()
        if uri then for i, e in ipairs(list) do if e.path == uri then idx = i; break end end end
    end
    if not idx then log("folder jump: nothing is playing"); return end
    local here = list[idx].dir
    if not here then log("folder jump: the current item is not a local file"); return end

    local target
    if dir > 0 then
        for i = idx + 1, #list do
            local d = list[i].dir
            if d and d ~= here then target = i; break end
        end
    else
        local j
        for i = idx - 1, 1, -1 do
            local d = list[i].dir
            if d and d ~= here then j = i; break end
        end
        if j then                       -- walk back to the first item of that folder
            local want = list[j].dir
            target = j
            for i = j - 1, 1, -1 do
                local d = list[i].dir
                if d == nil then            -- streams in between do not break a folder
                elseif d == want then target = i
                else break end
            end
        end
    end
    if not target then
        log("folder jump: no " .. (dir > 0 and "next" or "previous") .. " folder in the playlist")
        return
    end
    log("folder jump: " .. (dir > 0 and "next" or "previous") .. " folder, item " .. tostring(list[target].id)
        .. " (" .. tostring(list[target].dir) .. ")")
    vlc.playlist.gotoitem(list[target].id)
end

----------------------------------------------------------------------
-- Equalizer presets
----------------------------------------------------------------------
local PRESET_FALLBACK = { "Flat", "Classical", "Club", "Dance", "Full bass", "Full bass and treble",
    "Full treble", "Headphones", "Large Hall", "Live", "Party", "Pop", "Reggae", "Rock", "Ska",
    "Soft", "Soft rock", "Techno" }
local eq = { index = nil, names = nil, pending = false, deadline = 0, key = "" }

local function eq_names()
    if eq.names then return eq.names end
    local names = {}
    local ok, t = pcall(vlc.equalizer.presets)
    if ok and type(t) == "table" then
        for k, v in pairs(t) do
            local n = tostring(k):match("(%d+)")
            if n then names[tonumber(n) + 1] = tostring(v) end
        end
    end
    for i = 1, #PRESET_FALLBACK do names[i] = names[i] or PRESET_FALLBACK[i] end
    eq.names = names
    return names
end

-- Try to apply the chosen preset; true when VLC accepted it (the filter is loaded and playing)
local function eq_apply()
    if not eq.index then return true end
    local ok, r = pcall(vlc.equalizer.setpreset, eq.index)
    return ok and r ~= nil
end

local function eq_step(step)
    local names = eq_names()
    local n = #names
    if eq.index == nil then
        eq.index = (step > 0) and 0 or (n - 1)
    else
        eq.index = (eq.index + step) % n
    end
    pcall(vlc.equalizer.enable, true)          -- load the equalizer filter if it is not
    eq.key = track_key()
    if eq_apply() then
        eq.pending = false
        log("equalizer preset: " .. names[eq.index + 1])
    else                                       -- filter not running yet: retry for a few seconds
        eq.pending, eq.deadline = true, now() + EQ_RETRY_US
        log("equalizer preset: " .. names[eq.index + 1] .. " (applied when audio plays)")
    end
end

local function eq_tick()
    if not eq.index then return end
    local k = track_key()
    if k ~= eq.key then                        -- new track: a new audio output may have reset it
        eq.key = k
        if k ~= "" then eq.pending, eq.deadline = true, now() + EQ_RETRY_US end
    end
    if not eq.pending then return end
    if eq_apply() then
        eq.pending = false
        log("equalizer preset applied: " .. eq_names()[eq.index + 1])
    elseif now() > eq.deadline then
        eq.pending = false                     -- equalizer switched off by the user: leave it
    end
end

----------------------------------------------------------------------
-- Bitrate for lossless files: skins2's "$B kbps" shows the input's "bit-rate"
-- variable, which VLC only sets from a bitrate the codec declares (MP3, AAC ...),
-- so FLAC / WAV show 0. When it is 0, set it once per track to size / duration
-- (local files) or to the bytes read per second played (everything else).
----------------------------------------------------------------------
local br = { cache = {}, count = 0, next_try = 0 }

local function local_file_size(uri)
    local ok, path = pcall(vlc.strings.make_path, uri)
    if not ok or type(path) ~= "string" or path == "" then return nil end
    local f = io.open(path, "rb")             -- fails for non-ASCII paths on Windows: then the stats are used
    if not f then return nil end
    local size = f:seek("end")
    f:close()
    return size
end

local function bitrate_kbps(input, item, uri)
    if br.cache[uri] then return br.cache[uri] end
    local len = varget(input, "length")       -- microseconds
    if len and len > 0 then
        local size = local_file_size(uri)
        if size and size > 0 then
            local kbps = math.floor(size * 8 / (len / 1000000) / 1000 + 0.5)
            if kbps > 0 then
                if br.count >= 64 then br.cache, br.count = {}, 0 end
                br.cache[uri], br.count = kbps, br.count + 1
                return kbps
            end
        end
    end
    local t = varget(input, "time")           -- no file: bytes read so far / seconds played
    if t and t >= 5000000 then
        local ok, st = pcall(item.stats, item)
        if ok and type(st) == "table" and (st.demux_read_bytes or 0) > 0 then
            local kbps = math.floor(st.demux_read_bytes * 8 / (t / 1000000) / 1000 + 0.5)
            if kbps > 0 then return kbps end
        end
    end
    return nil
end

local function bitrate_tick(input)
    local cur = varget(input, "bit-rate")
    if cur == nil or cur > 0 then return end   -- codec knows it (or no variable): leave it
    if now() < br.next_try then return end
    local item = vlc.input.item()
    local uri = item and item:uri()
    if not uri then return end
    local kbps = bitrate_kbps(input, item, uri)
    if kbps then
        vlc.var.set(input, "bit-rate", kbps * 1000)   -- skins2 divides by 1000
        vlc.msg.dbg(TAG .. "bitrate for " .. tostring(uri) .. ": " .. kbps .. " kbps")
    else
        br.next_try = now() + 1000000
    end
end

----------------------------------------------------------------------
-- Durations in the playlist: skins2's Playtree draws one text column, the
-- item's title (input_item_GetTitleFbName), and redraws an item on the
-- playlist's "item-change" event, which a meta change raises. So the title of
-- every item with a known length gets it at the right edge: the playlist font
-- is monospaced, so the title is padded with spaces (or cut with "...") to the
-- number of characters that fit (pl_columns). The playing item keeps its real
-- title: the strip, the web interface (taskbar card), MPRIS and SMTC all show
-- the current title. The length goes after the title (not before it), so the
-- playlist's SORT button, which sorts by title, still sorts by name.
-- --lua-config "vlcamp={durations='suffix'}" gives "Title (3:42)" instead,
-- 'off' none; columns=N overrides the computed width.
----------------------------------------------------------------------
local PL_EVERY_US = 2000000                    -- full playlist pass
local PL_SKIN_W, PL_MARGIN, PL_FONT = 620, 50, 12   -- the skin's default width, playtree = width - P(margin), font px (build_skin.py add_pl)
local PL_DECORATED = {                         -- a title we (or a saved playlist) decorated
    "^(.-) %(%d+:%d%d%)$", "^(.-) %(%d+:%d%d:%d%d%)$", "^(.-)  +%d+:%d%d$", "^(.-)  +%d+:%d%d:%d%d$" }
local pl = { mode = "right", cols = 72, next_pass = 0, cur = nil, items = {} }   -- items[id] = { orig = title meta or "", shown = decorated title }

-- Python's round() (half to even), as the skin generator sizes its fonts with it
local function py_round(x)
    local f = math.floor(x)
    local d = x - f
    if d > 0.5 or (d == 0.5 and f % 2 == 1) then return f + 1 end
    return f
end

-- Characters that fit in a playlist line. skins2 (ctrl_tree.cpp makeImage) draws a flat playtree's
-- text 7 px in (itemImageWidth: 5 + 2) and cuts what does not fit with "..."; each glyph is
-- FreeType's hinted advance (ft2_font.cpp). The skin (build_skin.py) uses VLC Amp Mono (DejaVu Sans Mono) at
-- P(12) = round(12 x scale) px, whose advance is round(px x 0.6021) for every character, and makes
-- the playtree PW - P(50) wide (rows end 6 px before the scroll track, PP8). Scale from the skin's file name
-- (VLC-Amp-150.vlt), window width from skins2-config (the width VLC saved at its last exit).
-- w = the main window's width in px (nil: the one VLC saved at its last exit, else the default)
local function pl_columns(w)
    local s = 1
    local last = vlc.config.get("skins2-last") or ""
    local pct = last:match("%-(%d+)%.vlt$")
    if pct then s = tonumber(pct) / 100 end
    if not w then
        w = py_round(PL_SKIN_W * s)
        local cfg = vlc.config.get("skins2-config") or ""
        local mw = cfg:match('%["main" "[^"]*" %-?%d+ %-?%d+ (%d+) %d+')
        if mw then w = tonumber(mw) end
    end
    local px = py_round(PL_FONT * s)
    local adv = py_round(px * 0.6021)
    -- box width of "." in skins2: the skin's font (VLCAmpMono.ttf, tools/make-cell-font.py) makes every
    -- glyph's box span its whole cell, 0 .. ceil(1233 units x px / 2048) (DejaVu: just the dot's ink)
    local dot = math.ceil(px * 1233 / 2048)
    local tree = w - py_round(PL_MARGIN * s)   -- the playtree is PW - P(50) wide
    -- skins2 (ft2_font.cpp drawString) shows the whole line only if after every character the pen
    -- plus "..." (2 advances + the dot's box) stays left of the limit (tree - 7); otherwise it ends
    -- the line with "...". So the most characters n with n*adv + 2*adv + dot < tree - 7. Checked
    -- in VLC 3.0.20 (hi-fi skin, 620 px): see docs/architecture.md "Playlist durations".
    local limit = tree - 7 - 2 * adv - dot
    return math.max(20, math.floor((limit - 1) / adv))
end

-- UTF-8 aware length and cut (a character is one cell in a monospaced font)
local function u_len(str)
    local _, n = str:gsub("[^\128-\191]", "")
    return n
end

local function u_sub(str, n)
    local out, count = {}, 0
    for ch in str:gmatch("[%z\1-\127\194-\244][\128-\191]*") do
        if count >= n then break end
        count = count + 1
        out[count] = ch
    end
    return table.concat(out)
end

local function fmt_len(sec)
    sec = math.floor(sec + 0.5)
    local h, m, s = math.floor(sec / 3600), math.floor(sec / 60) % 60, sec % 60
    if h > 0 then return string.format("%d:%02d:%02d", h, m, s) end
    return string.format("%d:%02d", m, s)
end

local function strip_len(title)
    for _, pat in ipairs(PL_DECORATED) do
        local t = title:match(pat)
        if t then return t end
    end
    return title
end

-- "Title          3:42" filling pl.cols characters (a title that is too long is cut with an
-- ellipsis, so the length stays visible); in "suffix" mode "Title (3:42)"
local function decorate(title, sec)
    local len = fmt_len(sec)
    if pl.mode == "suffix" then return title .. " (" .. len .. ")" end
    local room = pl.cols - u_len(len) - 2             -- at least two spaces before the length
    if u_len(title) > room then title = u_sub(title, room - 1) .. "\226\128\166" end   -- U+2026
    return title .. string.rep(" ", pl.cols - u_len(title) - u_len(len)) .. len
end

-- Put the real title back on the playing item (cheap: done on every tick when the track changes)
local function pl_restore(id, item)
    local e = pl.items[id]
    if not e or not item then return end
    item:set_meta("title", e.orig)             -- "" = no title tag: the file name shows again
    pl.items[id] = nil
end

local function pl_pass(cur)
    local seen = {}
    local function walk(node, depth)
        if depth > 32 then return end
        if node.children then
            for _, c in ipairs(node.children) do walk(c, depth + 1) end
        elseif node.id and node.item and node.duration and node.duration > 0 then
            seen[node.id] = true
            local e = pl.items[node.id]
            if node.id == cur then
                if e then pl_restore(node.id, node.item) end
            elseif not e or node.name ~= e.shown or e.cols ~= pl.cols then
                local orig, base
                if e and node.name == e.shown then        -- only the width changed: from the remembered title
                    orig, base = e.orig, e.base
                else                                      -- new item, or its title changed since
                    local metas = node.item:metas() or {}
                    orig, base = strip_len(metas.title or ""), strip_len(node.name or "")
                end
                local shown = decorate(base, node.duration)
                if node.name ~= shown then node.item:set_meta("title", shown) end
                pl.items[node.id] = { orig = orig, base = base, shown = shown, cols = pl.cols }
            end
        end
    end
    local root = vlc.playlist.get("playlist")
    if root then walk(root, 0) end
    for id in pairs(pl.items) do if not seen[id] then pl.items[id] = nil end end   -- removed items
end

-- The live window width: the Windows helper writes it to %TEMP%\vlc-amp-width.txt while VLC runs
-- (VlcDock.ShareWidth); without it the width stays the one read at start.
local PL_WIDTH_EVERY_US = 500000
local function pl_width_file()
    local tmp = os.getenv("TMP") or os.getenv("TEMP") or os.getenv("TMPDIR") or "/tmp"   -- as .NET GetTempPath
    return tmp .. (is_windows and "\\" or "/") .. "vlc-amp-width.txt"
end

local function pl_follow_width()
    if pl.mode ~= "right" or pl.fixed or now() < (pl.next_width or 0) then return end
    pl.next_width = now() + PL_WIDTH_EVERY_US
    local w
    local f = is_windows and io.open(pl_width_file(), "r")   -- only the Windows helper writes it
    if f then
        w = tonumber(f:read("*l") or "")
        f:close()
    end
    local skin = vlc.config.get("skins2-last") or ""   -- skins2 stores it once the skin is loaded
    if w == pl.width and skin == pl.skin then return end
    pl.width, pl.skin = w, skin
    local cols = pl_columns(w)
    if cols ~= pl.cols then
        pl.cols = cols
        pl.next_pass = 0                       -- re-pad every title now
        vlc.msg.dbg(TAG .. "playlist width " .. tostring(w or "saved") .. " px, " .. skin .. ": " .. cols .. " columns")
    end
end

local function pl_tick()
    if not pl.on then return end
    pl_follow_width()
    local cur = vlc.playlist.current()
    if cur ~= pl.cur then                      -- track changed: real title back at once
        pl.cur = cur
        if cur and pl.items[cur] then pl_restore(cur, vlc.input.item()) end
        pl.next_pass = 0                       -- and decorate the previous one now
    end
    if now() < pl.next_pass then return end
    pl.next_pass = now() + PL_EVERY_US
    pl_pass(cur)
end

----------------------------------------------------------------------
-- Dispatch and main loop
----------------------------------------------------------------------
local handlers = {}
local function register(name, fn)
    local id = vlc.misc.action_id(ACTIONS[name])
    if id then handlers[id] = fn else warn("unknown action " .. ACTIONS[name]) end
end

local last_err, last_err_at = nil, 0
local function guarded(what, fn, ...)
    local ok, err = pcall(fn, ...)
    if not ok then
        err = tostring(err)
        if err ~= last_err or now() - last_err_at > 5000000 then
            warn(what .. " failed: " .. err)
            last_err, last_err_at = err, now()
        end
    end
end

local function tick(lib)
    local id = varget(lib, "key-action")
    if id and id ~= 0 then
        vlc.var.set(lib, "key-action", 0)      -- consume it (VLC ignores 0)
        local fn = handlers[id]
        if fn then guarded("action", fn) end
    end
    guarded("A-B loop", ab_tick)
    guarded("equalizer", eq_tick)
    guarded("playlist durations", pl_tick)
    local input = vlc.object.input()
    if input then guarded("bitrate", bitrate_tick, input) end
end

local function main()
    register("ab",          ab_trigger)
    register("folder_next", function() folder_jump(1) end)
    register("folder_prev", function() folder_jump(-1) end)
    register("eq_next",     function() eq_step(1) end)
    register("eq_prev",     function() eq_step(-1) end)

    local cfg = (type(config) == "table") and config or {}
    pl.mode = (cfg.durations == "off" or cfg.durations == "suffix") and cfg.durations or "right"
    pl.on = pl.mode ~= "off"
    local ok, cols = pcall(pl_columns)
    if ok and cols then pl.cols = cols end
    if tonumber(cfg.columns) then pl.cols, pl.fixed = math.floor(tonumber(cfg.columns)), true end
    local lib = vlc.object.libvlc()
    log("interface started (A-B loop, folder jump, equalizer presets, bitrate"
        .. (pl.on and (", playlist durations " .. (pl.mode == "right" and pl.cols .. " columns" or pl.mode)) or "") .. ")")
    while true do
        guarded("tick", tick, lib)
        local period = (ab.state == "ab") and POLL_FAST_US or POLL_IDLE_US
        if not pcall(vlc.misc.mwait, now() + period) then break end   -- VLC is quitting
    end
end

main()
