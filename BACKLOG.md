# Titlebar skin: backlog

Last updated 2026-10-31. Status key:

- **DONE**: built and tested in real VLC 3.0.20 (Linux, skins2).
- **SKIN**: doable in the skin generator alone.
- **CONFIG**: doable with VLC settings / launcher arguments, no code.
- **HELPER**: needs the Windows dock helper (PowerShell/C#).
- **LUA**: needs a Lua interface script running next to the skin.
- **PATCH**: needs a patched `libskins2_plugin` (own build of VLC's skin engine).
- **BLOCKED**: not possible with any of the above without a trade-off (see notes).

"Verified" means checked in the VLC 3.0.x skins2 source or by running it. Anything marked *unverified* is from memory and must be tested before we rely on it.

---

## 1. Items

| # | Item | Status | Approach / workaround | Effort |
|---|------|--------|-----------------------|--------|
| 7 | PL / EQ attached to the bar, same width | **DONE** | Panels are now part of the main window's layouts (8 layouts: strip/full x EQ x PL). | done |
| 7a | Taskbar mode with panels open | **DONE (skin) / helper untested on Windows** | Panels open above or below the bar, chosen with the arrow on the panel header (one skin file, no separate taskbar build). The helper reads the window region (`GetWindowRgn`) to see whether the bar is at the top or bottom and whether the strip or full player is showing. Rule checked against real VLC window shapes at 100 % and 150 %; compiled with Mono (C# 5). Placement itself still needs a run on Windows. | done |
| 7b / 13 | Same width with playlist open / closed | **DONE** | All 4 layouts (strip / full x panels below / above) have the same size, so VLC carries the dragged width between them (verified in `setActiveLayout`). Unused space is transparent and click-through (window region). PL / EQ are shown / hidden inside the layout via invisible 1x1 "flag" windows whose visibility VLC saves. Tested in VLC: drag +120 px, open PL+EQ, expand, flip, collapse, quit, restart: width, panels, side and time mode all restored. Cost: playlist height is fixed. | done |
| 14 | Choose where PL / EQ open (above / below), bar must not move | **DONE** | Arrow on the PL / EQ header flips both panels to the other side; remembered across restarts. The bar no longer moves when panels open or close. Flipping itself moves the bar to the other end of the window (one-time re-drag). Both panels share the side; a per-panel side would need 4 more layouts. | done |
| 1 | Double-click on a file opens a second VLC with the default skin | **CONFIG + HELPER** | Cause: the launcher passes `--intf skins2` on the command line only, so a double-click starts plain `vlc.exe` (Qt). Fix: write `intf=skins2`, `skins2-last=<vlt>`, `one-instance=1`, `playlist-enqueue=1` into `vlcrc` (the launcher can do it, or VLC > Preferences > Show all). Then Explorer double-click goes to the running instance with the skin. Needs your answer: do you start VLC through the launcher or normally? | S |
| 3 | Show elapsed time, countdown on click | **DONE** | Elapsed by default; click the time (strip or full player) for time left. The time background is a checkbox bound to a flag window, the texts use `focus="false"` so the click reaches it (an Image only reacts to double-click, a Text takes the whole rectangle: both verified in source). Remembered across restarts. Tested in VLC. | done |
| 4 | A-B loop in the full player | **LUA** or **PATCH** | skins2 has no A-B action (verified: no such action in the interpreter). Qt's A-B is implemented in the Qt GUI, not in the core. A Lua interface can implement it by watching the input time and seeking back (*unverified*, expect ~100 ms jitter). The skin button still needs a way to talk to it, see section 2. | L |
| 5 | Replace the strip's slower/faster buttons with next/prev *folder* (speed buttons move to the full player, a layout-only change) | **LUA** or **PATCH** | No folder concept in skins2 actions (verified). A Lua interface can walk the playlist, compare the directory of each item URI, and jump (`vlc.playlist.goto`). Works for local files only. Button problem as in 4. | M-L |
| 6 | Odd button resize on mouse-over (screenshot) | **DONE (needs a check on Windows)** | Cause: strip and full player bitmaps had ids differing only by case (`b_slower` / `B_slower`, `t_play` / `T_play` ...). VLC unpacks the .vlt to disk, and on Windows (case-insensitive) one PNG overwrote the other, so strip buttons showed the full player's larger images. Renamed to `fb_*` / `ft_*`; the build now fails on any case-only collision. Linux never showed it. | done |
| 8 | Playlist: show duration, optional columns | **BLOCKED** | The skins2 Playtree control draws one text column (verified: no column support in `ctrl_tree`). Workarounds: (a) accept; (b) a Lua *playlist rename* that appends the duration to item titles (changes titles, clunky); (c) PATCH: add a column renderer to the Playtree control (large). | L / XL |
| 9 | Empty space in the full player LCD, meaning of the numbers | **DONE** | Big number = time left, `12:22 / 18:34` = elapsed / total, `SPEED 1x` = playback speed. Full player is now 122 px (was 146): toggles and speed share one row under the bitrate line, empty boxes gone. Tested in VLC. | done |
| 10 | Timer wider than 59:59 (hours) | **DONE** | Strip time box 50 -> 64 px (title field 14 px shorter, min strip width 428 -> 442); full player time column widened to 126 px. Tested with a 63-minute track in VLC: `-1:03:16` fits both. Tracks of 10 h+ would still overflow. | done |
| N2 | Playlist stretch only from the bottom-left corner | **Superseded by 13** (playlist height is now fixed; width follows the bar) | skins2 only has `resizeS`, `resizeE`, `resizeSE` (verified in the builder): **no west or south-west resize**, so a bottom-left handle cannot resize leftwards. Options: (a) one grip in the bottom-*right* corner, height only; (b) bottom-left grip that uses `resizeSE` (drag right/down, feels wrong); (c) PATCH: add `resizeSW`. Also decide: should the playlist ever change width on its own, or only follow the bar? Proposed default: remove the right and bottom edge handles, keep a single bottom-corner grip that changes the height only. | S |
| N3 | "Knihovna medii" (Media Library) node does nothing | **CONFIG** | **Verified:** launching with `--no-media-library` removes the node from the skin's playlist. The media library UI only exists in the Qt interface, so the node can never open anything in skins2. Set `media-library=0` in `vlcrc` (the launcher writes it, same as item 1). | S |
| N1 | Start pinned to top (always on top) | **HELPER** (or **PATCH**) | skins2 cannot do it: `vlc.onTop` is only a toggle action, the state is not saved in `skins2-config`, and the theme DTD has no on-top attribute (verified). Options: (a) helper sets `HWND_TOPMOST` at start (the pin button then does not light up, because VLC does not know); (b) helper posts a click to the pin button right after start (the button geometry is known from the skin), which keeps VLC's own state in sync, hacky but works; (c) PATCH: a `<Theme ontop="true">` attribute. Taskbar mode already forces topmost. | S-M |
| 2 | EQ presets | **LUA** / **PATCH** | skins2 has no preset action and sliders cannot be driven by actions (verified). Lua has an equalizer library in 3.0.x (`modules/lua/libs/equalizer.c` exists; API details *unverified*). Needs a button bridge like 4 and 5. Cheapest partial: ship a few presets as extra buttons that need a patched action, or as hotkeys handled by the Lua interface. | M-L |
| 15 | Clicking the taskbar hides the player even when pinned | **HELPER, needs info** | Windows behaviour: when the taskbar is clicked it moves itself to the top of the "always on top" group, so any pinned window lying over it is covered. VLC's pin (`vlc.onTop`) sets topmost once and never re-asserts it, so without the helper this is expected. The helper re-asserts topmost when the taskbar is above VLC (on every foreground change and every 250 ms), so with the helper the player should come back within a fraction of a second. If it does not: (a) check the helper is running (started via `VLC in taskbar.cmd`); (b) debug the z-order check on Windows. Stronger fix: (c) re-parent the strip into the taskbar window (`SetParent` onto `Shell_TrayWnd`, the technique TrafficMonitor uses on Windows 11), so the taskbar can never cover it. Cost: only while the bare strip shows (a child window is clipped to the taskbar, so panels / full player need it un-parented again), plus the cross-process input coupling risks of SetParent. Questions: helper running? Gone for good or back after a moment? Clicked an empty taskbar spot, an app icon, or VLC's own taskbar button (that one minimizes)? | S-M |
| 16 | Project under version control | **SETUP** | The folder is not a git repository. Every change so far overwrote files in place (the taskbar builds were deleted). `git init` + a first commit would make each step reviewable and reversible. | XS |
| 11 | Tray icon for the helper (replace the Ctrl+Alt+Shift+V hotkey) | **HELPER** | Listed in the original open items. | S |
| 12 | Taller strip for the taskbar (e.g. 36 px), hide the pin in taskbar mode | **SKIN + HELPER** | Listed in the original open items. | S |

Numbers 1-10 follow your first list; N1-N3 your second list; 13-14 your third list (13 = width, 14 = panel side); 15 your fourth; 7a, 7b, 11, 12, 16 were added during analysis.

---

## 2. Plugin and extension options

Common problem: **a skin button can only run actions that skins2 knows** (verified list: `dialogs.*`, `dvd.*`, `playlist.*`, `vlc.play/pause/stop/faster/slower/mute/volume/minimize/onTop/snapshot/toggleRecord/nextFrame/quit/fullscreen`, `equalizer.enable/disable`, `*.setLayout/show/hide/maximize`). There is no "run script", no custom action, and no way to send a key. So any feature built outside the skin needs a bridge from the button to that feature. The options:

### A. Lua interface script (`lua/intf/titlebar.lua`, started with `--extraintf luaintf --lua-intf titlebar`)

- Runs inside VLC beside skins2, on Windows and Linux. Can read and control playback, the playlist, and the input (time, seek).
- Good for: A-B loop, next/prev folder, EQ presets (via the Lua equalizer library), sleep timer, "remember position", extra hotkeys.
- Hotkeys: libvlc exposes the integer variables `key-pressed` and `key-action` (verified in `src/misc/actions.c`). A Lua interface that adds a callback to `key-pressed` could implement custom hotkeys (*unverified in Lua: `vlc.var.add_callback` availability in 3.0.x*). This is the **only bridge that works without code outside VLC**, but it is keyboard-only.
- Does not give the skin new buttons.

### B. Lua extension (`lua/extensions/*.lua`, shown in the View menu)

- Their dialogs are drawn by the Qt interface (`vlc_dialog`/extension dialog provider). The skins2 module has no extension dialog support (verified: `dialogs.cpp` has none). In skins2 they would not show a window. **Not useful.**

### C. Patched skins2 module (own build of `libskins2_plugin`)

- Adds real skin actions and attributes: `vlc.abLoop()`, `playlist.nextFolder()`, `equalizer.preset(name)`, `resizeSW`, `<Theme ontop="true">`, Playtree columns. The skin buttons then work like any other.
- Cost: it must match the exact installed VLC 3.0.x build (a plugin from another version is rejected), needs a Windows build setup (mingw cross-compile of VLC 3.0.x, several GB), and must be rebuilt on each VLC update. The patch itself could be small (an action is ~30 lines). Could be proposed upstream, but 3.0.x is in maintenance mode.
- This is the only route to a *clean* solution for 4, 5, 2, N2 (west resize) and N1.

### D. Dock helper as the control surface (C#/PowerShell, already exists)

- Windows-only, runs as its own process. It can: set on-top at start, handle file association and launching, show a tray icon with a menu (presets, A-B, folder jump), register global hotkeys, and talk to VLC through the Lua/RC/HTTP interface.
- Gives menu-style controls, not buttons inside the skin. A second UI toolkit next to the skin is a design compromise, but it is the cheapest way to get the missing features on Windows.
- Needs Lua interface A (or VLC's built-in `--extraintf http` / `rc` interface) as the receiving end.

### E. Own player on libvlc (outside the current scope)

- A new app (C#/WPF or Qt) using libvlc, with its own title-bar strip, playlist with columns, A-B loop, presets, folder navigation, media keys. Removes every skins2 limit. It is a different project, not an upgrade of this skin. Mentioned only as the long-term clean option.

### Evaluation summary

| Feature | A Lua | B Ext | C Patch | D Helper | Best fit |
|---------|:-----:|:-----:|:-------:|:--------:|----------|
| A-B loop | yes (logic) | no | yes | yes (via A) | C for a button, A + hotkey for a quick version |
| Next/prev folder | yes (logic) | no | yes | yes (via A) | same |
| EQ presets | yes (*unverified API*) | no | yes | yes (via A) | same |
| Start on top | no | no | yes | yes | D |
| Playlist columns | no | no | yes (large) | no | accept or C |
| West / SW resize | no | no | yes | no | C or accept |
| Media Library node | n/a | n/a | n/a | n/a | CONFIG |

---

## 3. Suggested order

1. **Windows test round (blocking).** Since the last Windows run: case-collision fix (6), one-size layouts and click-through (13), panel side (14), flag windows, time toggle (3), and the helper's region-based placement (7a). All were tested only on Linux. Windows-only risks: the 1x1 flag windows briefly taking focus when PL / EQ toggle, region shaping, and helper placement. Report back with 15's questions.
2. **Version control (16):** before the next round of changes.
3. **Launcher setup, one step:** 1 (skins2 as default interface, single instance, files go to the running player), N3 (`media-library=0`), N1 (start pinned; option b, the helper clicks the pin). All are settings the launcher can write to `vlcrc`, plus a few helper lines.
4. **Fix 15** based on the test results: first make sure re-asserting topmost works; SetParent only if that is not enough.
5. **Strip layout:** move slower / faster to the full player (part of 5). That frees 48 px in the strip for the title or for the folder buttons later.
6. **Decision point:** features 4, 5, 2 (A-B loop, folder jump, EQ presets). Choose between A + D (Lua script + hotkeys / tray menu, no skin buttons) and C (patched skins2 plugin with real buttons).
7. **Playlist columns (8):** only if C is chosen.

## 4. Open questions

1. Item 1: do you start VLC through `VLC in taskbar.cmd`, or normally (Start menu / double-click)?
2. Playlist height: is the fixed height (about 10 rows) OK, or should it be taller / shorter?
3. Items 4, 5, 2: is a hotkey / tray-menu solution acceptable, or do you want real buttons in the skin (patched plugin)?
4. Do you have a way to test on Windows, so helper changes (7a, N1, 15) can be verified?
5. Item 15: is the helper running, does the player come back after a moment, and what exactly was clicked?
