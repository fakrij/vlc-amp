# Lua API notes (T5)

Source: VLC 3.0.x only (branch `3.0.x`, HEAD `b9322dfc` when fetched on 2026-10-31). Files were read from `raw.githubusercontent.com`; repo-wide greps used the branch tarball from `codeload.github.com`. Nothing was run and nothing is from memory.

File references are relative to the root of the VLC repository (`modules/...`, `src/...`), not to this repo. Line numbers are from the 3.0.x files.

Lua version: `share/lua/README.txt:8` says "VLC uses Lua 5.1". Which Lua the Debian or Windows builds link against was not checked. The notes below work either way.

## Summary

1. **No callback API.** `vlc.var` has no `add_callback` or `del_callback` in 3.0.x. `key-pressed` can only be polled. `key-action` is the usable signal: poll it and reset it to 0.
2. **`vlc.equalizer` exists** and can set 18 presets (`setpreset(0..17)`) and single bands (`equalizerset(band, dB)`) live. It works only while the equalizer audio filter is loaded and something is playing.
3. **Time** is read and written as `vlc.var.get/set(vlc.object.input(), "time")`, in microseconds. There is no time function in `vlc.input`. `vlc.object.input()` returns nil when nothing plays.
4. **Playlist:** `vlc.playlist.get()` returns a tree. Each leaf has `id` and `path` (raw URI). Jump with `vlc.playlist.gotoitem(id)`. The name `goto` is only a Lua 5.1 alias.
5. **Start:** `extraintf=luaintf` and `lua-intf=titlebar`. On Windows the script goes in `%APPDATA%\vlc\lua\intf\titlebar.lua`. The script must run its own loop, because the interface ends when the script returns.

---

## Q1. `vlc.var.add_callback` / `del_callback`, and watching `key-pressed`

**Short answer:** Neither function exists in 3.0.x. The `vlc.var` table has 11 functions and none of them adds or removes a callback. `key-pressed` can only be read with `vlc.var.get`. It holds one integer, so a poll can miss a key that is followed by another key before the next poll. Repeated presses of the same key also look identical to a poll unless the value is reset after reading. The workable pattern is to poll `key-action` (the ID of the mapped VLC action), act on it, then set it back to 0.

**Evidence:**

- `modules/lua/libs/variables.c:362-375`, the full `vlc.var` registration list: `inherit`, `get`, `get_list`, `set`, `create`, `trigger_callback`, `libvlc_command`, `inc_integer`, `dec_integer`, `count_choices`, `toggle_bool`. The only callback-related entry is `trigger_callback` (`variables.c:310-317`), which fires existing callbacks and adds none.
- `share/lua/README.txt:415-436` documents the same list. The only callback entry is `var.trigger_callback( object, name )`.
- A grep for `AddCallback` in `modules/lua/` finds one hit, `modules/lua/extension.c:120` (C code, not exposed to Lua).
- `key-pressed` is created on the libvlc object and wired to the action map: `src/misc/actions.c:513-515` (`var_Create (obj, "key-pressed", VLC_VAR_INTEGER);`, plus `global-key-pressed` and `key-action`), and the callbacks at `actions.c:548-549` (`var_AddCallback (obj, "key-pressed", vlc_key_to_action, &as->map);`).
- `vlc_key_to_action` (`actions.c:401-415`) looks up the key code and then does `return var_SetInteger (obj, "key-action", (*pent)->action);` (`actions.c:414`). Keys with no mapping leave `key-action` unchanged.
- Every `var_Set` fires callbacks, with no equality check. `src/misc/variables.c:742-758` stores the new value and calls `TriggerCallback` unconditionally (`variables.c:757-758`). So setting the same value twice fires twice, and a poll only sees a new event if the value changed.
- Who writes `key-pressed` (grep over the whole 3.0.x tree):
  - `src/video_output/event.h:47-49` `vout_SendEventKey()`, called from `src/video_output/display.c:587` for `VOUT_DISPLAY_EVENT_KEY`.
  - `modules/video_output/xcb/keys.c:170`.
  - `modules/gui/qt/main_interface.cpp:1683` and `:1693`, and `modules/gui/qt/dialogs_provider.cpp:880` (only when no Qt accelerator matched).
  - macOS: `modules/gui/macosx/VLCVoutView.m` and `VLCCoreInteraction.m`.
- How skins2 keys get there: `modules/gui/skins2/src/top_window.cpp:210`, `vout_window.cpp:117` and `ctrl_tree.cpp:386` call `Dialogs::sendKey()` (`modules/gui/skins2/src/dialogs.cpp:355-362`). That sends `INTF_DIALOG_SENDKEY` to the "dialogs provider" module. The only module with that capability is Qt (`modules/gui/qt/qt.cpp:330`, `set_capability( "dialogs provider", 51 )`). Qt then writes `key-pressed` (`dialogs_provider.cpp:880`). **Inference from the code, not tested:** without the Qt plugin, keys pressed in the skin never reach `key-pressed` or `key-action`.
- Who writes `key-action`:
  - `modules/control/hotkeys.c:318` registers `ActionEvent` on `key-action`. That is the core hotkey executor (`hotkeys.c:1386`, which dispatches to `PutAction`, defined at `hotkeys.c:345`).
  - `modules/control/globalhotkeys/win32.c:306-309` sets `key-action` directly for global hotkeys (`if( action != ACTIONID_NONE ) var_SetInteger( ..., "key-action", action )`).
  - `modules/control/globalhotkeys/xcb.c:406` writes `global-key-pressed` instead, which goes through the same map and also sets `key-action`.
- The hotkey executor is loaded by the VLC binary: `bin/vlc.c:240-242` (`libvlc_add_intf (vlc, "hotkeys,none");` and `"globalhotkeys,none"`). `bin/winvlc.c:267-268` does the same on Windows.
- `ACTIONID_NONE` is 0 (`include/vlc_actions.h:121`). `PutAction` has no case for 0, so writing 0 to `key-action` does nothing (checked: no `ACTIONID_NONE` case in `hotkeys.c`).

**Implications for T6:**

- Do not plan around a callback. Use a timer loop (see Q5 for the wait call). Each tick:
  ```lua
  local lib = vlc.object.libvlc()
  local id = vlc.var.get(lib, "key-action")
  if id and id ~= 0 then
    vlc.var.set(lib, "key-action", 0)   -- consume it
    -- act on id
  end
  ```
  Setting it back to 0 is what makes a repeated press visible. The reset does not fire anything, because `hotkeys.c` ignores 0.
- `key-action` is one slot. Two different keys within one poll period overwrite each other. Keep the poll short (50-100 ms) and say so in the docs. The poll interval was not measured.
- Only keys that VLC maps to an action reach the script. Those are the ones in Preferences > Hotkeys, plus global hotkeys if they are bound. There is no way for Lua to define a new key.
- The script cannot add an action. It can only reuse an existing ID from the table in `src/misc/actions.c:264-378`. Each reused ID still runs its normal core handler in `hotkeys.c` (for example `set-bookmark1` stores a bookmark). A reused ID must be checked case by case in `PutAction`. That check was not done here.
- Keyboard tests in the skin depend on Qt (see the inference above). The T1 package list has no Qt, so T6 keyboard tests may not reach `key-action` at all. Test first with `xdotool` on a Qt-enabled VLC, or drive `key-action` directly for a test.
- Reverse direction (not tested): `vlc.var.set(libvlc, "key-action", id)` makes the hotkey executor run that core action, because `hotkeys.c:318` listens on that variable. IDs come from `vlc.misc.action_id("key-...")` (see Q5). This could drive core actions such as play/pause from Lua. It does not give any A-B, folder or EQ action, because none exist in the core (`actions.c:264-378`).

---

## Q2. `vlc.equalizer` (`modules/lua/libs/equalizer.c`)

**Short answer:** `vlc.equalizer` exists in every interface Lua state (`modules/lua/intf.c:279`). It has seven functions. Presets (18 fixed names, index 0-17) and single band levels (10 bands, in dB) change the running filter live. Every call except `enable` does nothing unless the equalizer audio filter is loaded on the current audio output, and that requires something to be playing.

**Functions** (`modules/lua/libs/equalizer.c`, registration at `:294-303`, `luaopen_equalizer` at `:306-311`):

| Lua call | C function, lines | Notes |
|---|---|---|
| `vlc.equalizer.enable(bool)` | `vlclua_equalizer_enable`, `:270-276` | `luaL_checkboolean`, so pass `true`/`false`, not `"on"`. Calls `playlist_EnableAudioFilter(pl, "equalizer", state)`. |
| `vlc.equalizer.setpreset(id)` | `vlclua_equalizer_setpreset`, `:244-265` | `id` is 0-based, `0 <= id < NB_PRESETS` (18). Sets `equalizer-preset` on the aout. |
| `vlc.equalizer.presets()` | `vlclua_equalizer_get_presets`, `:280-293` | Returns a table keyed `preset id="N"` with the display names. Iterate with `pairs`, not `ipairs`. |
| `vlc.equalizer.equalizerget()` | `vlclua_equalizer_get`, `:123-181` | Returns a table keyed `band id="N"` with string values in dB. |
| `vlc.equalizer.equalizerset(band, dB)` | `vlclua_equalizer_set`, `:187-239` | `band` 0-9. Rewrites the `equalizer-bands` string. |
| `vlc.equalizer.preampget()` / `preampset(dB)` | `:60-79` / `:85-104` | Preamp in dB, through `equalizer-preamp`. |

**Evidence:**

- `equalizer.c:67-73` (the same pattern is in every function): the aout's `audio-filter` must contain `"equalizer"`, otherwise the function returns 0. `playlist_GetAout` returns NULL when nothing is playing, so the early `return 0` covers that case too (`equalizer.c:128-130`).
- `src/playlist/aout.c:116-124`: `playlist_EnableAudioFilter()` changes the `audio-filter` string on the playlist and on the running aout, if there is one.
- `equalizer.c:256-261`: `setpreset` writes `preset_list[presetid]` to `equalizer-preset` on the aout. This only works when the filter is already in `audio-filter`.
- Preset names, `modules/audio_filter/equalizer_presets.h:47-52`, `NB_PRESETS` 18: `flat, classical, club, dance, fullbass, fullbasstreble, fulltreble, headphones, largehall, live, party, pop, reggae, rock, ska, soft, softrock, techno`.
- Band count: `equalizer_presets.h:34` `#define EQZ_BANDS_MAX 10`. Band frequencies are listed in a comment at `equalizer.c:109-118`: 60 Hz, 170, 310, 600, 1k, 3k, 6k, 12k, 14k, 16k (band 0 to 9).
- Live update, `modules/audio_filter/equalizer.c`: the filter registers callbacks on `equalizer-preset`, `equalizer-bands`, `equalizer-preamp` (`:367-370`). `PresetCallback` (`:470`) expands a preset into bands and sets the preamp. `BandsCallback` (`:537`) reads the dB values, "Read dB -20/20" (`:545`). `PreampCallback` (`:517`) converts the preamp. So a change applies to the running filter with no restart.
- On open, the filter loads the preset only when `equalizer-bands` is not set (`audio_filter/equalizer.c:344-353`).

**Implications for T6:**

- EQ presets via hotkeys: call `vlc.equalizer.enable(true)` once, then `vlc.equalizer.setpreset(i)` with `i` from the cycle (0-17). Keep the index in the script. The script must re-apply the preset when a new track starts, because nothing persists it in the script's own state. Not tested: whether `audio-filter` survives a stop/start.
- While stopped, `setpreset` and `equalizerset` do nothing and return 0. The script should either refuse the key press while stopped or store the choice and apply it on the next start.
- Single bands or preamp can also be set. `equalizerset` changes one band without a full preset.
- Verify a change with `vlc.equalizer.equalizerget()` after each call.
- The core has no EQ action, so the key itself still needs one of the reused-ID approaches described in Q1.

---

## Q3. Reading and seeking the input time

**Short answer:** `vlc.input` has no time function (`is_playing`, `item`, `add_subtitle`, `add_subtitle_mrl` only). Get the input with `vlc.object.input()`, then read or write the input's `time` variable with `vlc.var.get` / `vlc.var.set`. Units are **microseconds** (integer). `length` is also in microseconds. `position` is a float from 0 to 1. Seeking is a `set` of `time`, and the seek is queued, so a read right after a write may still show the old value. `vlc.object.input()` returns nil when nothing is playing, and `vlc.var.get(nil, ...)` raises a Lua error, so check for nil first.

**Evidence:**

- `modules/lua/libs/input.c:419-424`: the `vlc.input` table is `is_playing`, `item`, `add_subtitle`, `add_subtitle_mrl`. No time.
- `modules/lua/libs/objects.c:145-153`: `vlc.object` has `input`, `playlist`, `libvlc`, `find`, `vout`, `aout`. `vlclua_get_input` (`objects.c:80-90`) pushes the input object, or nil.
- `modules/lua/intf.c:267` registers `vlc.object`; `intf.c:273` registers `vlc.var`.
- Input variables, created in `src/input/var.c`: `position` as float (`:144`), `time` as integer (`:147`), `length` as integer (`:209`).
- Units: `include/vlc_config.h:46`, `#define CLOCK_FREQ INT64_C(1000000)`. `src/input/input.c:1867` divides `time` by `CLOCK_FREQ` to get seconds.
- Seek: `src/input/var.c:606-630` (`TimeCallback`) ends with `input_ControlPush( p_input, INPUT_CONTROL_SET_TIME, &newval );` (`:627`). The seek is queued to the input thread. `PositionCallback` (`:584-604`) does the same for `position`.
- Lua side: `modules/lua/libs/variables.c:168-183` (`vlclua_var_get`) and `:185-198` (`vlclua_var_set`). `vlclua_var_get` uses `luaL_checkudata( L, 1, "vlc_object" )` (`:171`), which raises on nil.

Example:
```lua
local input = vlc.object.input()          -- nil when nothing plays
if input then
  local t   = vlc.var.get(input, "time")     -- microseconds
  local len = vlc.var.get(input, "length")   -- microseconds
  vlc.var.set(input, "time", t + 5000000)    -- seek +5 s
end
```

**Implications for T6:**

- A-B loop: each tick, read `time`. When it reaches B, `set` `time` to A. The error is at least one poll period plus the seek latency. Use 50-100 ms for the poll. The BACKLOG "~100 ms jitter" is consistent with this, but was not measured.
- Set `A` and `B` in microseconds: `seconds * 1000000`.
- Get the input fresh on every tick and check for nil. Do not keep the input object across ticks, because the input can be replaced between tracks.

---

## Q4. Playlist items with URIs, and jumping to one

**Short answer:** `vlc.playlist.get(...)` returns a Lua table tree. Leaves are items with `id`, `name`, `path` (the raw URI, percent-encoded), `duration` (seconds, -1 if unknown), `nb_played` and `flags`. Nodes have a `children` table, which is recursive. `vlc.playlist.get("playlist")` returns the main playlist node. Jump with `vlc.playlist.gotoitem(id)`. The name `goto` exists only as a Lua 5.1 alias (`playlist.c:426-428`), so use `gotoitem`. `gotoitem` returns `0, "success"` even for an unknown ID, so check the ID first.

**Evidence:**

- `modules/lua/libs/playlist.c:272-318` (`vlclua_playlist_get`): no argument gives the root (`:313`). A number gives the item with that ID (`:278-287`). `"normal"` or `"playlist"` gives `p_playlist->p_playing`, which is the main playlist node (`:291-293`). `"ml"` / `"media library"` and `"root"` are also accepted, and any other string is looked up as an SD module name (`:294-309`).
- `playlist.c:221-270` (`push_playlist_item`): `id` (`:227-228`), `flags` (`:229-239`), `name` from `input_item_GetTitleFbName` (`:244-247`), `path` from `p_input->psz_uri` (`:248-249`), `duration` in seconds (`:250-254`), `nb_played` (`:255-256`), an `item` userdata with `uri()`, `name()`, `metas()` (`:257`), and `children` (`:259-269`) when `i_children >= 0`, recursively.
- `playlist.c:128-137` (`vlclua_playlist_gotoitem`): `playlist_ViewPlay( p_playlist, NULL, playlist_ItemGetById( p_playlist, i_id ) );` then `return vlclua_push_ret( L, VLC_SUCCESS );`. For an unknown ID the item is NULL, and `src/playlist/control.c:70-86` accepts that without failing: it only clears `request.p_item`, so the engine picks the next item by its normal rules.
- `playlist.c:426-429`: `#if LUA_VERSION_NUM < 502` adds the `goto` alias. `gotoitem` is always registered (`:429`).
- `playlist.c:331-344`: `vlc.playlist.current()` returns the current item ID, or -1.
- `playlist.c:56-68`: `vlc.playlist.next()` and `prev()` call `playlist_Next` and `playlist_Prev`, so they follow the playlist's own order, including repeat and random.
- Decoding helpers: `vlc.strings.decode_uri(uri)` (`modules/lua/libs/strings.c:47-62`, registered at `:182`). `vlc.strings.make_path(uri)` (`strings.c:94-101`, registered at `:185`) is in the code but not in `share/lua/README.txt`.
- The current item's URI: `vlc.input.item():uri()` (`modules/lua/libs/input.c:302-317` and `:331-337`).

**Implications for T6:**

- Listing: call `vlc.playlist.get("playlist")`. Walk `children` recursively, and treat each entry with a `path` as an item. The `path` is the raw URI. The directory is everything before the last `/`. Comparing raw strings is consistent as long as both sides come from `path`. Use `vlc.strings.decode_uri` only if a readable name is needed.
- Folder jump: take the current ID from `vlc.playlist.current()`. Walk the flattened list, find the first entry whose directory differs from the current one, then `vlc.playlist.gotoitem(id)`. The `goto` alias is not needed.
- No playlist-change event is exposed to Lua in `playlist.c`. Rebuild the flattened list on demand, or poll it.
- Only local files give a meaningful directory. This matches the BACKLOG note for item 5.

---

## Q5. Starting the Lua interface next to skins2, and the Windows script path

**Short answer:** Use `--extraintf luaintf --lua-intf titlebar`, or put `extraintf=luaintf` and `lua-intf=titlebar` in `vlcrc`. The script is looked up as `intf/titlebar.lua` in the VLC lua directories, user directory first. On Windows that is `%APPDATA%\vlc\lua\intf\titlebar.lua`. The script runs in its own thread, and the interface ends when the file returns, so the script needs its own loop.

**Evidence:**

- `modules/lua/vlc.c:84-94`: the "Lua interpreter" module, with `add_string( "lua-intf", "dummy", ...)` (`:90`) and `add_shortcut( "luaintf" )` (`:94`). The default `dummy` gives "Couldn't find lua interface script" (`intf.c:232-236`), so `lua-intf` must be set.
- `src/libvlc-module.c:2166-2169`: `intf` and `extraintf` options. `src/libvlc.c:302-303` loads `extraintf` and `control` modules at startup, next to the main interface.
- `src/libvlc-module.c:1933`: `add_bool( "lua", true, ...)`. The check `lua_Disabled()` is `modules/lua/vlc.h:109-112`.
- `modules/lua/intf.c:202-232` (`Start_LuaIntf`): the name comes from `lua-intf` when none is passed (`:212-217`). The file is found with `vlclua_find_file( "intf", name )` (`:232`).
- Search order, `modules/lua/vlc.c:214-241` (`vlclua_dir_list`): user data dir (`config_GetUserDir(VLC_DATA_DIR)` + `/lua/intf`), then the lib dir, then the data dir. Extensions tried: `.luac`, `.lua`, `.vle` (`vlc.c:181`, `vlclua_find_file` at `:309-330`).
- Windows paths: `src/win32/dirs.c:282-290` builds `"%s\\vlc"` from `CSIDL_APPDATA`. `dirs.c:292-300`: `VLC_DATA_DIR` and `VLC_CONFIG_DIR` both return that path. So the user location is `%APPDATA%\vlc\lua\intf\`.
- Linux equivalent: `src/posix/dirs.c:218-221`, `VLC_DATA_DIR` is `$XDG_DATA_HOME/vlc`, default `~/.local/share/vlc`.
- `share/lua/README.txt:18-25` gives the same locations.
- Thread: `intf.c:377` starts `Run` in a thread. `Run` (`intf.c:407-420`) calls `vlclua_dofile` once. When the script returns, the thread ends.
- Waiting: `vlc.misc.mwait(deadline)` takes an **absolute** deadline in microseconds (`modules/lua/libs/misc.c:136-147`; `include/vlc_interrupt.h:74` `vlc_mwait_i11e(vlc_tick_t)` and `:89` `vlc_mwait_i11e(mdate() + delay)`). `vlc.misc.mdate()` gives the current time (`misc.c:130-133`). Shutdown interrupts the wait and raises "Interrupted." (`misc.c:136-147`), which ends the script.
- Example loop: `share/lua/intf/cli.lua:808` uses `while running do`, but its wait is blocking I/O, not a timer.
- `vlc.misc.*` is interface-only (`share/lua/README.txt:171`). `vlc.misc.action_id(name)` (`misc.c:149-158`) returns the numeric ID. `vlc_actions_get_id` (`src/misc/actions.c:587-597`) returns `ACTIONID_NONE` unless the name starts with `key-`. So `vlc.misc.action_id("key-play-pause")` works and `"play-pause"` returns nil.

**Implications for T6:**

- Setup writes `extraintf=luaintf` and `lua-intf=titlebar` to `vlcrc`, and copies the script to `%APPDATA%\vlc\lua\intf\titlebar.lua`. The directory has to be created first.
- Loop template: `while true do ... vlc.misc.mwait(vlc.misc.mdate() + 100000) end`.
- Look up action IDs with `vlc.misc.action_id("key-...")`, using the `key-` prefix.
- A Lua error ends the script. The error is logged by `Run` (`intf.c:413-416`) and there is no restart. Check the VLC log when testing.

---

## Where BACKLOG.md disagrees with the source

Not edited, as instructed. Corrections for whoever updates the backlog:

1. **Section 2 A, "Hotkeys":** `vlc.var.add_callback` is listed as *unverified*. It does not exist in 3.0.x. A Lua script can only poll `key-pressed` or `key-action`. The sentence "A Lua interface that adds a callback to `key-pressed` could implement custom hotkeys" is not possible in 3.0.x.
2. **Section 2 A, "Hotkeys":** "libvlc exposes ... `key-pressed` and `key-action` (verified in `src/misc/actions.c`)" is correct but incomplete. `key-action` is the bus that the core hotkey executor reads (`modules/control/hotkeys.c:318`). `key-pressed` is written by the video output, Qt, xcb and macOS, not by skins2 directly. Skin keys reach it only through the Qt dialogs provider (`dialogs.cpp:355`, `qt/dialogs_provider.cpp:880`).
3. **Section 2 A, "Good for":** "the input (time, seek)" is correct, but there is no input time API. Time is the `time` variable (Q3).
4. **Section 2 A and the evaluation table:** "EQ presets: yes (*unverified API*)" can now be marked verified (Q2). The `vlc.equalizer` functions are listed in Q2 with their arguments.
5. **Section 2 and item 2:** "Lua has an equalizer library in 3.0.x (API details *unverified*)". Now verified. The library exists, and it can set presets and bands live.
6. **Item 4, "Qt's A-B is implemented in the Qt GUI, not in the core":** not supported by the 3.0.x source. A grep of the whole tree (`modules/`, `src/`, `include/`) for A-B loop code found nothing. `modules/gui/qt` has only `LOOP_BUTTON` (`controller.cpp:448`), which is the playlist repeat. Either the claim comes from a later VLC or it is wrong; in either case it does not help the 3.0.20 target.
7. **Item 5, "(`vlc.playlist.goto`)":** the name is `gotoitem` in 3.0.x. `goto` exists only as a Lua 5.1 alias (`playlist.c:426-428`).
8. **T1 package list (BACKLOG section 5, T1):** it installs no Qt plugin. By the Q1 inference, skin key presses then never reach `key-pressed` or `key-action`. Keyboard tests of T6 would fail for that reason, not because of the script. Install Qt for the test, or test with `key-action` set directly. This needs a run to confirm.
9. **Section 2 B (extensions):** consistent with the source. `modules/lua/extension.c:120` listens on `dialog-event`, and the only "dialogs provider" in the tree is Qt (`modules/gui/qt/qt.cpp:330`). Not a T5 question, so not checked further.

## Not determined from source, or to test

- Poll period and whether two keys in one period are lost: not measured.
- Whether skin key presses reach `key-action` without the Qt plugin: inferred from the code only.
- Whether a Lua write to `key-action` runs the core action in practice: inferred from `hotkeys.c:318`, not tested.
- Whether `audio-filter` (and so the EQ state) survives stop and start: not checked.
- Which reused action IDs are free of side effects in `hotkeys.c` `PutAction`: not checked per ID.
- Which Lua version the Debian and Windows builds link against: not checked.
