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
| 1 | Double-click on a file opens a second VLC with the default skin | **DONE (untested on Windows)** | You start VLC from files / folders. `taskbar\Setup.cmd` writes `vlcrc`: `intf=skins2`, `skins2-last=<skin for the display scale>`, `one-instance=1`, `one-instance-when-started-from-file=1`, `playlist-enqueue=0`. Backs up the old file as `vlcrc.before-titlebar`. Cause of the bug: the instance started by the launcher was not started from a file and had `one-instance=0`, so it never listened for files and Explorer started a second, normal VLC. | done |
| 3 | Show elapsed time, countdown on click | **DONE** | Elapsed by default; click the time (strip or full player) for time left. The time background is a checkbox bound to a flag window, the texts use `focus="false"` so the click reaches it (an Image only reacts to double-click, a Text takes the whole rectangle: both verified in source). Remembered across restarts. Tested in VLC. | done |
| 4 | A-B loop in the full player | **LUA** or **PATCH** | skins2 has no A-B action (verified: no such action in the interpreter). Qt's A-B is implemented in the Qt GUI, not in the core. A Lua interface can implement it by watching the input time and seeking back (*unverified*, expect ~100 ms jitter). The skin button still needs a way to talk to it, see section 2. | L |
| 5 | Replace the strip's slower/faster buttons with next/prev *folder* (speed buttons move to the full player, a layout-only change) | **LUA** or **PATCH** | No folder concept in skins2 actions (verified). A Lua interface can walk the playlist, compare the directory of each item URI, and jump (`vlc.playlist.goto`). Works for local files only. Button problem as in 4. | M-L |
| 6 | Odd button resize on mouse-over (screenshot) | **DONE (needs a check on Windows)** | Cause: strip and full player bitmaps had ids differing only by case (`b_slower` / `B_slower`, `t_play` / `T_play` ...). VLC unpacks the .vlt to disk, and on Windows (case-insensitive) one PNG overwrote the other, so strip buttons showed the full player's larger images. Renamed to `fb_*` / `ft_*`; the build now fails on any case-only collision. Linux never showed it. | done |
| 8 | Playlist: show duration, optional columns | **BLOCKED** | The skins2 Playtree control draws one text column (verified: no column support in `ctrl_tree`). Workarounds: (a) accept; (b) a Lua *playlist rename* that appends the duration to item titles (changes titles, clunky); (c) PATCH: add a column renderer to the Playtree control (large). | L / XL |
| 9 | Empty space in the full player LCD, meaning of the numbers | **DONE** | Big number = time left, `12:22 / 18:34` = elapsed / total, `SPEED 1x` = playback speed. Full player is now 122 px (was 146): toggles and speed share one row under the bitrate line, empty boxes gone. Tested in VLC. | done |
| 10 | Timer wider than 59:59 (hours) | **DONE** | Strip time box 50 -> 64 px (title field 14 px shorter, min strip width 428 -> 442); full player time column widened to 126 px. Tested with a 63-minute track in VLC: `-1:03:16` fits both. Tracks of 10 h+ would still overflow. | done |
| N2 | Playlist stretch only from the bottom-left corner | **Superseded by 13** (playlist height is now fixed; width follows the bar) | skins2 only has `resizeS`, `resizeE`, `resizeSE` (verified in the builder): **no west or south-west resize**, so a bottom-left handle cannot resize leftwards. Options: (a) one grip in the bottom-*right* corner, height only; (b) bottom-left grip that uses `resizeSE` (drag right/down, feels wrong); (c) PATCH: add `resizeSW`. Also decide: should the playlist ever change width on its own, or only follow the bar? Proposed default: remove the right and bottom edge handles, keep a single bottom-corner grip that changes the height only. | S |
| N3 | "Knihovna medii" (Media Library) node does nothing | **DONE (untested on Windows)** | Setup writes `media-library=0` (verified in VLC: the node disappears). | done |
| N1 | Start pinned to top (always on top) | **DONE (untested on Windows)** | Option (b): the helper posts a mouse click to the skin's own pin button 1.5 s after VLC's window appears, once per VLC start, so VLC's state and the lit pin agree. Pin positions checked by clicking in VLC at 150 %. Setup can start the helper with Windows in watch mode (`-Watch`, waits for VLC, also when VLC is started from a file), with or without docking (`-NoDock`). Untested: that skins2 on Windows accepts the posted messages (the source handles WM_MOUSEMOVE / WM_LBUTTONDOWN / UP from the message queue, so it should). | done |
| 2 | EQ presets | **LUA** / **PATCH** | skins2 has no preset action and sliders cannot be driven by actions (verified). Lua has an equalizer library in 3.0.x (`modules/lua/libs/equalizer.c` exists; API details *unverified*). Needs a button bridge like 4 and 5. Cheapest partial: ship a few presets as extra buttons that need a patched action, or as hotkeys handled by the Lua interface. | M-L |
| 15 | Clicking the taskbar hides the player even when pinned | **HELPER, needs info** | Windows behaviour: when the taskbar is clicked it moves itself to the top of the "always on top" group, so any pinned window lying over it is covered. VLC's pin (`vlc.onTop`) sets topmost once and never re-asserts it, so without the helper this is expected. The helper re-asserts topmost when the taskbar is above VLC (on every foreground change and every 250 ms), so with the helper the player should come back within a fraction of a second. If it does not: (a) check the helper is running (started via `VLC in taskbar.cmd`); (b) debug the z-order check on Windows. Stronger fix: (c) re-parent the strip into the taskbar window (`SetParent` onto `Shell_TrayWnd`, the technique TrafficMonitor uses on Windows 11), so the taskbar can never cover it. Cost: only while the bare strip shows (a child window is clipped to the taskbar, so panels / full player need it un-parented again), plus the cross-process input coupling risks of SetParent. Questions: helper running? Gone for good or back after a moment? Clicked an empty taskbar spot, an app icon, or VLC's own taskbar button (that one minimizes)? | S-M |
| 16 | Project under version control | **DONE** | Git repository in `Titlebar-VLC-skin/`, first commit = state before the launcher setup. | done |
| 17 | Seek from the strip (no rewind / fast-forward before) | **DONE** | The strip's title window is a seek slider over the song name: the played part fills it (201 frames plus a play-head line), a click jumps to that point and can drag, the mouse wheel steps 5 %. The title text uses `focus="false"` so the click reaches the slider. Verified in source (`CtrlSliderBg`: click = jump, wheel = variable step 0.05) and in VLC: a click at 50 % went to 1:41 of 3:20, at 25 % on a wider strip to 0:51. Keyboard also works: VLC's hotkeys (Shift / Alt / Ctrl + arrow keys) jump 3 s / 10 s / 1 min while the player has focus. | done |
| 11 | Tray icon for the helper (replace the Ctrl+Alt+Shift+V hotkey) | **HELPER** | Listed in the original open items. | S |
| 12 | Taller strip for the taskbar (e.g. 36 px), hide the pin in taskbar mode | **SKIN + HELPER** | Listed in the original open items. | S |

Numbers 1-10 follow your first list; N1-N3 your second list; 13-14 your third list (13 = width, 14 = panel side); 15 and 17 your fourth and fifth; 7a, 7b, 11, 12, 16 were added during analysis.

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

1. **Windows test of the setup:** run `Setup.cmd`, then open a file from Explorer: skin, single window, Media Library gone, player pinned (pin lit).
2. **Fix 15** (taskbar click hides the player): needs the answers to its questions.
3. **Strip layout:** move slower / faster to the full player (part of 5). That frees 48 px in the strip for the title or for the folder buttons later.
4. **Decision point:** features 4, 5, 2 (A-B loop, folder jump, EQ presets). Choose between A + D (Lua script + hotkeys / tray menu, no skin buttons) and C (patched skins2 plugin with real buttons).
5. **Playlist columns (8):** only if C is chosen.

Agent-sized work packages for these steps are in section 5.

## 4. Open questions

1. Items 4, 5, 2: is a hotkey / tray-menu solution acceptable, or do you want real buttons in the skin (patched plugin)?
2. Item 15: is the helper running, does the player come back after a moment, and what exactly was clicked?

---

## 5. Subtasks for agents

Self-contained work packages, sized for one agent each. Each brief says what to read, what to change, how to verify, and what not to do.

**Model guide**
- **Haiku**: mechanical, fully specified, easy to check (docs, lookups with a known answer shape).
- **Sonnet**: normal implementation with a clear spec and a test path (generator, helper, scripts).
- **Opus**: open-ended design, root-cause work on unclear bugs, or large, risky spikes.

**Rules for every agent**
- Read `README.md` and this file first. The generator is `source/build_skin.py`; built skins are `Titlebar-{100,125,150,200}.vlt` in the repo root (rebuild all four with `--scale 1 / 1.25 / 1.5 / 2`, `--out` to a temp folder, then copy the `.vlt` files and `preview-100.png` -> `preview.png`).
- skins2 limits are listed in items 7b/13, 3, and section 2. Check the VLC 3.0.x source (github.com/videolan/vlc, branch `3.0.x`, `modules/gui/skins2`) before relying on any skins2 behaviour; do not guess.
- Windows scripts keep CRLF line endings and plain ASCII. `VlcDock.cs` must stay C# 5 (Windows PowerShell 5.1 `Add-Type`).
- Never `pkill vlc` / `killall`: kill only PIDs you started. No `sudo`.
- Do not commit; leave changes in the working tree for review. Update this backlog's item row when done.

| ID | Task | Model | Depends on | Size |
|----|------|-------|------------|------|
| T1 | Test harness in the repo | Sonnet | - | M |
| T2 | Move slower / faster to the full player | Sonnet | T1 | S |
| T3 | Helper debug log (for 15) | Sonnet | - | S |
| T4 | Docs consistency pass | Haiku | after others | XS |
| T5 | Lua API fact check (for 4, 5, 2) | Haiku | - | S |
| T6 | Lua interface prototype: A-B loop, folder jump, EQ presets via hotkeys | Sonnet | T1, T5, decision on 4/5/2 | L |
| T7 | Tray icon for the helper (11) | Sonnet | - | M |
| T8 | Taller taskbar strip option (12) | Sonnet | T1 | M |
| T9 | Fix 15 (taskbar click hides the player) | Opus | Windows answers + T3 log | M |
| T10 | Patched skins2 feasibility spike (option C) | Opus | decision on 4/5/2 | XL |

### T1 - Test harness in the repo (Sonnet)
Goal: any agent can run real VLC 3.0.20 with the skin, click it and take screenshots, without sudo.
- Add `tools/setup-test-env.sh`: download (not install) the packages with `apt-get download` into `~/.cache/titlebar-test/debs`. The packages are vlc-bin, vlc-plugin-base, vlc-plugin-skins2, xvfb, xdotool and imagemagick, plus their recursive dependencies that `dpkg -s` reports as not installed. Extract them with `dpkg-deb -x` into `~/.cache/titlebar-test/root`. Then create a Python venv with Pillow and python-xlib.
- Add `tools/vlc-test.sh` with subcommands `start <vlt> [files]`, `shot <name> [crop]`, `click <x> <y>`, `drag <x> <y> <dx> <dy>`, `geometry`, `shape` (X11 shape box of the main window), `quit` (clicks the skin's quit button, so VLC saves `skins2-config`), `stop` (kills only the VLC PID it saved) and `xvfb-stop`.
- Gotchas (all hit before): Xvfb needs `xkbcomp` at `/usr/bin`, so mount an overlay in a user namespace: `unshare -Urm sh -c "mount -t overlay overlay -o lowerdir=/usr/bin,upperdir=<dir with xkbcomp>,workdir=<w> /usr/bin && exec Xvfb :99 ..."`. Set QT_PLUGIN_PATH, VLC_PLUGIN_PATH, VLC_DATA_PATH and LD_LIBRARY_PATH to the extracted root. ImageMagick needs MAGICK_CONFIGURE_PATH and MAGICK_CODER_MODULE_PATH. Use a private HOME so VLC's config starts clean. Generate test audio with Python's `wave` module, including a 63-minute file for hour formats.
- Done when: a fresh shell can run setup, start the 100 % skin, click PL, screenshot, and quit, and `tools/README.md` documents it.

### T2 - Move slower / faster to the full player (Sonnet)
Part of item 5. The strip loses its slower and faster buttons; the full player already has them.
- In `add_strip` (build_skin.py), remove `b_slower` and `b_faster`, shift play, next and the title LCD left so the gaps close, and give the freed 48 px to the title. Lower `MIN_W` by the same amount if the title keeps its minimum width.
- Keep the right group anchored to the right edge. Keep the dock helper's pin offsets valid: the strip pin is at `W - 34 + 11`. If any right-group offset changes, update `PinOnce` in `VlcDock.cs` too.
- Verify with T1: rebuild, screenshot the strip at 100 % and 150 %, confirm prev / play / next / expand work by clicking, and confirm no warnings in VLC's log. Update the README controls list.

### T3 - Helper debug log (Sonnet)
For item 15. Nobody can watch the helper on Windows, so give it an opt-in log.
- `vlc-taskbar.ps1`: add `$DebugLog = $false` and pass it to `[VlcDock]::LogPath` (`$env:TEMP\titlebar-helper.log` when on).
- `VlcDock.cs`: when `LogPath` is set, append timestamped lines for these events:
  - VLC PID found / lost
  - foreground window changes (class name)
  - whether the taskbar was above VLC (`IsBelow`)
  - every `SetWindowPos` the helper does, with flags
  - `PinOnce` firing
  - the `ReadShape` result when it changes

  Rate-limit repeated identical lines and cap the file at about 1 MB.
- Compile-check with Mono (`mcs -langversion:5`, stub the UIA types as in the existing stubs; see the memory note or T1). Document the switch in the README.

### T4 - Docs consistency pass (Haiku)
- Read README.md and BACKLOG.md against the code. Fix outdated statements: `--full-width` and the `Titlebar-taskbar-*` files no longer exist; there are 4 layouts of equal size; PL/EQ state lives in flag windows; Setup.cmd exists. Also fix broken numbering and duplicated sentences.
- Do not change any behaviour or code. Keep the item numbers stable.

### T5 - Lua API fact check (Haiku)
Answer from the VLC 3.0.x source (`modules/lua/libs/*.c`, `share/lua/intf/*.lua`, `share/lua/README.txt`), with file:line references:
1. Does Lua have `vlc.var.add_callback` / `del_callback` in 3.0.x, and can it watch the libvlc `key-pressed` variable?
2. What does `modules/lua/libs/equalizer.c` export (function names, arguments)? Can it set presets or bands live?
3. How does a Lua interface read and seek the input time (`vlc.object.input()`, `vlc.var.get(input, "time")`, units)?
4. How do you list playlist items with their URIs and jump to one (`vlc.playlist.get`, `vlc.playlist.gotoitem`)?
5. How is a Lua interface started next to skins2 (`--extraintf luaintf --lua-intf <name>`), and where does the script go on Windows (`%APPDATA%\vlc\lua\intf\`)?

Write the answers into section 2 of this file and replace each *unverified* mark with the answer.

### T6 - Lua interface prototype (Sonnet)
Only after T5 and after the user chooses option A + D for items 4, 5 and 2.
- `lua/intf/titlebar.lua`:
  - A-B loop: the first key press sets A, the second sets B and loop playback between them, the third clears.
  - Next / previous folder: jump to the first playlist item whose directory differs from the current item's.
  - EQ presets: cycle through a fixed list.

  Trigger everything through hotkeys, using the mechanism T5 confirmed.
- Setup (`vlc-taskbar.ps1 -Setup`) copies the script and adds `extraintf=luaintf`, `lua-intf=titlebar` to vlcrc.
- Verify with T1 on Linux: send keys with xdotool and check time / playlist position through the log or `vlc.msg` output.

### T7 - Tray icon for the helper (Sonnet)
Item 11.
- `VlcDock.cs`: add a NotifyIcon (System.Windows.Forms; it needs a message loop, and the helper already has one) with a menu: Dock on / off (replaces the hotkey, but keep the hotkey), Pin now, Open debug log (if T3 is done), Quit helper. Use a simple generated icon, not a file.
- `vlc-taskbar.ps1`: add System.Windows.Forms and System.Drawing to `-ReferencedAssemblies`.
- Compile-check with Mono. Untestable here, so keep it minimal and document what to check on Windows.

### T8 - Taller taskbar strip option (Sonnet)
Item 12.
- Generator: a `--bar-height` option (default 24; taskbar use 32-36) that scales the strip vertically: buttons, LCDs, fonts and the time box. Width layout and right-edge offsets stay logical-px based.
- The helper must use the same bar height: read it from the skin filename or pass it in, because `P(24)` is hard-coded in `ReadShape`, `Place` and `PinOnce`.
- Verify with T1 at 100 % and 150 %, including the helper's shape rule (T1 `shape`).

### T9 - Fix 15 (Opus)
Needs the user's answers (was the helper running, gone for good or back after a moment, what was clicked) and ideally a T3 log from Windows. Then either fix the z-order re-assertion in `Place()`, or prototype `SetParent` onto `Shell_TrayWnd` for the bare strip (un-parent for panels / full player). Decide based on the log; do not guess.

### T10 - Patched skins2 spike (Opus)
Only if the user chooses option C.
- Find out whether a `libskins2_plugin.dll` built from 3.0.x sources with mingw-w64 loads in the official Windows VLC 3.0.x build (version and ABI match, plugin cache).
- Add one trivial new action (for example `vlc.abLoop()`, implemented in the core input like Qt's A-B, or a log line) as the proof.
- Report the build steps, size, time, and the risk on each VLC update. Do not start the full feature set.
