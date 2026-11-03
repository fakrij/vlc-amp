# VLC Amp: backlog

> **Hi-fi redesign fork:** open items, rules and assignments for the new design are in [BACKLOG-hifi.md](BACKLOG-hifi.md).

Last updated 2026-11-02 (section 8: Jiri's design requests PP23-PP28; section 7: second pass; section 6: pixel-perfect audit, PP1-PP14; 2026-11-01: hi-fi integration verification pass: section 0; docs pass T4; item 35 and T26-T29 from the v1.0 code review; earlier: T19-T20 added; items 26-31 and T21-T23 from the Windows test; 32-33 and T25 from the second test). Status key:

- **DONE**: built and tested in real VLC 3.0.20 (Linux, skins2).
- **SKIN**: doable in the skin generator alone.
- **CONFIG**: doable with VLC settings / launcher arguments, no code.
- **HELPER**: needs the Windows dock helper (PowerShell/C#).
- **PLUGIN**: needs a third-party VLC plugin (not ours, installed next to VLC).
- **LINUX**: Linux-specific work (the skin itself already runs on Linux; all our tests run there).
- **LUA**: needs a Lua interface script running next to the skin.
- **PATCH**: needs a patched `libskins2_plugin` (own build of VLC's skin engine).
- **BLOCKED**: not possible with any of the above without a trade-off (see notes).

"Verified" means checked in the VLC 3.0.x skins2 source or by running it. Anything marked *unverified* is from memory and must be tested before we rely on it.

---

## 0. What the hi-fi redesign changed (item 38)

The statements in the rows below were written for the earlier flat skin and are kept as history; where a row
names a size, a style or a number, the current values are these (details: README, [BACKLOG-hifi.md](BACKLOG-hifi.md),
[docs/architecture.md](docs/architecture.md)):

| Topic | Now | Rows affected |
|---|---|---|
| Style | One style only (thin: flat panels, hairline outlines); `--classic` and the old flat / standard looks are gone | 18, "Flat style" at the end |
| Window | 620 x 676 px at 100 % (strip, full player and panels share it), minimum width **510** at every bar height (was 556 / 420 / 490; 510 keeps the mute speaker clear of Next in the full player, PP2); the helper's `DockShape` constants and click points were derived from the new `theme.xml` | 5, 7b, 10, 12, 13, 27, 34 (the "436 px" window) |
| Strip | 24 px default (title bar); 36 px taskbar build (`VLC-Amp-taskbar-NNN.vlt`) and 40 px `bar40` stay as options | 12 |
| Full player | Rebuilt (232 px bar, hi-fi LCD box, transport row 28 px), no longer 122 px | 9, 10 |
| Seek bars | Title box is still a seek bar (51 fill frames + play-head thumb); the full player's seek bar has 101 frames and is 10 px high | 17 |
| Video window | Same window and features as item 34 in the hi-fi style: 12 px frame, 36 px title bar (name of what plays, fill screen, full screen, shrink, close), control panel docked under the video (minimum width 580), the arrow opens a row below it (A-B via the helper, chapters, snapshot, shuffle / loop / repeat, slower / speed / faster), fullscreen controller with the same row | 34 |
| Memory | Every theme costs about 16 - 17 MB more than with the flat original (one theme: 103.6 MB vs 87.2 MB at 100 %, 141.0 MB vs 102.0 MB at 150 %; each further theme about +32 MB at 100 %, flat: +15), not +10 MB; a light + dark pair costs about twice one theme | 18, 24 |
| Playlist durations | 77 / 75 / 74 / 77 columns at 100 / 125 / 150 / 200 % (620 px window, 12 px font, VLC Amp Mono, playtree `PW - P(50)` since PP8) | 8 |
| Configurator | Part of `main` (not parked): `configurator/build_skin.py` is the generator, kept identical with `configurator/sync.sh` or `tools/sync-configurator.py` | 24 |

---

## 1. Items

| # | Item | Status | Approach / workaround | Effort |
|---|------|--------|-----------------------|--------|
| 7 | PL / EQ attached to the bar, same width | **DONE** | Panels are now part of the main window's layouts (4 layouts: strip / full x panels below / above; PL and EQ are shown inside them). | done |
| 7a | Taskbar mode with panels open | **DONE, confirmed by the user on Windows 2026-10-31** | Panels open above or below the bar, chosen with the arrow on the panel header (one skin file, no separate taskbar build). The helper reads the window region (`GetWindowRgn`) to see whether the bar is at the top or bottom and whether the strip or full player is showing. Rule checked against real VLC window shapes at 100 % and 150 %; compiled with Mono (C# 5). Placement itself still needs a run on Windows. | done |
| 7b / 13 | Same width with playlist open / closed | **DONE** | All 4 layouts (strip / full x panels below / above) have the same size, so VLC carries the dragged width between them (verified in `setActiveLayout`). Unused space is transparent and click-through (window region). PL / EQ are shown / hidden inside the layout via invisible 1x1 "flag" windows whose visibility VLC saves. Tested in VLC: drag +120 px, open PL+EQ, expand, flip, collapse, quit, restart: width, panels, side and time mode all restored. Cost: playlist height is fixed. | done |
| 14 | Choose where PL / EQ open (above / below), bar must not move | **DONE** | Arrow on the PL / EQ header flips both panels to the other side; remembered across restarts. The bar no longer moves when panels open or close. Flipping itself moves the bar to the other end of the window (one-time re-drag). Both panels share the side; a per-panel side would need 4 more layouts. | done |
| 1 | Double-click on a file opens a second VLC with the default skin | **DONE, confirmed by the user on Windows 2026-10-31** | You start VLC from files / folders. `taskbar\Setup.cmd` writes `vlcrc`: `intf=skins2`, `skins2-last=<skin for the display scale>`, `one-instance=1`, `one-instance-when-started-from-file=1`, `playlist-enqueue=0`. Backs up the old file as `vlcrc.before-vlc-amp`. Cause of the bug: the instance started by the launcher was not started from a file and had `one-instance=0`, so it never listened for files and Explorer started a second, normal VLC. | done |
| 3 | Show elapsed time, countdown on click | **DONE** | Elapsed by default; click the time (strip or full player) for time left. The time background is a checkbox bound to a flag window, the texts use `focus="false"` so the click reaches it (an Image only reacts to double-click, a Text takes the whole rectangle: both verified in source). Remembered across restarts. Tested in VLC. | done |
| 4 | A-B loop | **DONE (hotkey + tray + taskbar hover buttons confirmed on Windows 2026-10-31; hover buttons added for folders only)** | `lua/intf/vlcamp.lua`: Ctrl+Shift+A (action `subsync-markaudio`) or the helper's tray menu Playback > A-B loop (web `key` command). Loops about 0.2 s after B. State only in VLC's log; the skin cannot show it (skins2 reads the title once per track). See README "Lua extras", docs/architecture.md "Lua interface". | done |
| 5 | Next / previous folder (and slower / faster out of the strip) | **DONE (Linux-tested via harness; Windows untested)** | Same script: Ctrl+Shift+Right / Left (`viewpoint-roll-clock` / `-anticlock`), tray menu Playback. Walks the playlist by `file://` directory, local files only; folders must be contiguous. No skin buttons possible. Strip part (T2): slower / faster removed from the strip, title / seek window 48 px wider, `MIN_W` 420. | done |
| 6 | Odd button resize on mouse-over (screenshot) | **DONE (needs a check on Windows)** | Cause: strip and full player bitmaps had ids differing only by case (`b_slower` / `B_slower`, `t_play` / `T_play` ...). VLC unpacks the .vlt to disk, and on Windows (case-insensitive) one PNG overwrote the other, so strip buttons showed the full player's larger images. Renamed to `fb_*` / `ft_*`; the build now fails on any case-only collision. Linux never showed it. | done |
| 8 | Playlist: show duration, optional columns | **Durations DONE (2026-11-01, option b, Linux-tested; Windows untested); columns BLOCKED** | The skins2 Playtree control draws one text column (verified: no column support in `ctrl_tree`). Built: (b) `lua/intf/vlcamp.lua` adds the length to the title of every item with a known length, in VLC's memory only, right-aligned by padding (the playlist font is monospaced; width from scale + saved window width, rule measured in VLC; `durations='suffix'` for " (m:ss)"); the playing item keeps its real title (strip, web interface, MPRIS, SMTC stay plain); a suffix so the SORT button (sorts by title) still sorts by name; `lua-config` `vlcamp={durations='off'}`. Source facts and the test: docs/architecture.md "Playlist durations". Still not possible: real columns / right-aligned times ((c) PATCH, large). | done / XL |
| 9 | Empty space in the full player LCD, meaning of the numbers | **DONE** | Big number = time left, `12:22 / 18:34` = elapsed / total, `SPEED 1x` = playback speed. Full player was then 122 px (was 146; **rebuilt by the redesign, see section 0**): toggles and speed share one row under the bitrate line, empty boxes gone. Tested in VLC. | done |
| 10 | Timer wider than 59:59 (hours) | **DONE** | Strip time box 50 -> 86 px at a 24 px bar (96 px at 36; `bar_metrics` `tw`; the minimum strip width was then 420, item 5; **490 since the redesign**, which also rebuilt the full player); full player time column widened to 126 px. Tested with a 63-minute track in VLC: `-1:03:16` fits both. Tracks of 10 h+ would still overflow. | done |
| N2 | Playlist stretch only from the bottom-left corner | **Superseded by 13** (playlist height is now fixed; width follows the bar) | skins2 only has `resizeS`, `resizeE`, `resizeSE` (verified in the builder): **no west or south-west resize**, so a bottom-left handle cannot resize leftwards. Options: (a) one grip in the bottom-*right* corner, height only; (b) bottom-left grip that uses `resizeSE` (drag right/down, feels wrong); (c) PATCH: add `resizeSW`. Also decide: should the playlist ever change width on its own, or only follow the bar? Proposed default: remove the right and bottom edge handles, keep a single bottom-corner grip that changes the height only. | S |
| N3 | "Knihovna medii" (Media Library) node does nothing | **DONE (untested on Windows)** | Setup writes `media-library=0` (verified in VLC: the node disappears). | done |
| N1 | Start pinned to top (always on top) | **DONE, pin confirmed by the user on Windows 2026-10-31** | Option (b): the helper posts a mouse click to the skin's own pin button 1.5 s after VLC's window appears, once per VLC start, so VLC's state and the lit pin agree. Pin positions checked by clicking in VLC at 150 %. Setup can start the helper with Windows in watch mode (`-Watch`, waits for VLC, also when VLC is started from a file), with or without docking (`-NoDock`). Untested: that skins2 on Windows accepts the posted messages (the source handles WM_MOUSEMOVE / WM_LBUTTONDOWN / UP from the message queue, so it should). | done |
| 2 | EQ presets | **DONE (Linux-tested via harness; Windows untested)** | Same script: Ctrl+Shift+Up / Down (`viewpoint-fov-in` / `-out`), tray menu Playback > Next EQ preset. Cycles VLC's 18 presets, re-applies on new tracks; the skin's EQ panel follows. Bonus: bitrate for FLAC and other lossless files (the script sets the input's `bit-rate` variable). The sample rate stays whole kHz (skins2 limit). | done |
| 15 | Clicking the taskbar hides the player even when pinned | **FIXED (see 33), confirmed on Windows 2026-10-31** | Windows behaviour: when the taskbar is clicked it moves itself to the top of the "always on top" group, so any pinned window lying over it is covered. VLC's pin (`vlc.onTop`) sets topmost once and never re-asserts it, so without the helper this is expected. The helper re-asserts topmost when the taskbar is above VLC (on every foreground change and every 250 ms), so with the helper the player should come back within a fraction of a second. If it does not: (a) check the helper is running (started via `VLC in taskbar.cmd`); (b) debug the z-order check on Windows. Stronger fix: (c) re-parent the strip into the taskbar window (`SetParent` onto `Shell_TrayWnd`, the technique TrafficMonitor uses on Windows 11), so the taskbar can never cover it. Cost: only while the bare strip shows (a child window is clipped to the taskbar, so panels / full player need it un-parented again), plus the cross-process input coupling risks of SetParent. Questions: helper running? Gone for good or back after a moment? Clicked an empty taskbar spot, an app icon, or VLC's own taskbar button (that one minimizes)? | S-M |
| 16 | Project under version control | **DONE** | Git repository in `VLC-Amp/`, first commit = state before the launcher setup. | done |
| 17 | Seek from the strip (no rewind / fast-forward before) | **DONE** | The strip's title window is a seek slider over the song name: the played part fills it (51 frames, `FILL_FRAMES`, plus a play-head line), a click jumps to that point and can drag, the mouse wheel steps 5 %. The title text uses `focus="false"` so the click reaches the slider. Verified in source (`CtrlSliderBg`: click = jump, wheel = variable step 0.05) and in VLC: a click at 50 % went to 1:41 of 3:20, at 25 % on a wider strip to 0:51. Keyboard also works: VLC's hotkeys (Shift / Alt / Ctrl + arrow keys) jump 3 s / 10 s / 1 min while the player has focus. | done |
| 18 | Light / dark theme + 3 colours each, switch in the full player title bar; then (6th list) one button only, more coordinated variations, own colour; then (7th list) minimal: keep the dark blue one | **DONE** | **Release skins carry only Midnight** (`DEFAULT_THEMES`, the user's choice). The generator builds 10 themes plus Custom (`--themes`, README "More themes"): each theme is a full set of controls in the same 4 layouts, shown by its own flag window (`th0`, `th1`, ...). The full player's title bar has one theme button that steps to the next theme (tooltip: current / next); it is left out when one theme is built. Memory and start-up figures: [architecture.md](docs/architecture.md#bitmaps-atlases) and README Limits. Custom: any accent, recoloured exactly from a red reference (item 23). Tested in VLC: switching, persistence, panels in all themes. | done |
| 11 | Tray icon for the helper (replace the Ctrl+Alt+Shift+V hotkey) | **DONE (T7), confirmed by the user on Windows 2026-10-31** | NotifyIcon with Dock / Pin now / Play / pause / Playback (A-B, folder jump, EQ preset) / Open debug log / Quit; compile-checked. | done |
| 12 | Taller strip for the taskbar (36 px) | **DONE, confirmed by the user on Windows 2026-10-31** | Generator `--bar-height N` (default 24, 36 = taskbar build); release files `VLC-Amp-taskbar-{100,125,150,200}.vlt` (36 px; naming `VLC-Amp-taskbar-NNN` / `VLC-Amp-bar<N>-NNN`). Widths and right-edge offsets unchanged (min width 420 at every bar height; **490 since the redesign**); window height is the same for all 4 layouts. Setup and the helper prefer the taskbar file when docking and read the bar height from the file name (`VlcDock.BarHeight` replaces `P(24)` in ReadShape / Place / ClickPin). Tested in VLC at 100 % and 150 % (shape rule, clicks, panels above / below); the Windows placement is untested. Pin stays (the helper clicks it). | done |
| 19 | Play / pause / prev / next when hovering VLC's taskbar button (Windows) | **DONE, hover buttons confirmed by the user on Windows 2026-10-31** (T12; end of `VlcDock.cs`, `$TaskbarButton` in `vlc-taskbar.ps1`) | skins2's taskbar button belongs to its hidden 0 x 0 root window and Windows sends thumbnail clicks only to the owning window, so the helper shows its **own** button (invisible `WS_EX_APPWINDOW` window: layered alpha 0, click-through, off-screen) and VLC's is hidden (`skins2-taskbar=0` from Setup when the helper starts with Windows, `--no-skins2-taskbar` from the launcher; a leftover VLC button is removed with `DeleteTab`). Built: 3 thumbnail buttons (icons drawn at runtime, follow Windows dark / light), progress in the button (green / yellow paused / none; interpolated from 21's 500 ms polls), hover preview card (title, artist, time; `DwmSetIconicThumbnail`), title "Artist - Title", VLC's icon. Click = VLC to the front (restored if minimized, `SC_RESTORE` to skins2's root window); "Close window" = `SC_CLOSE` = VLC quits normally. App id: VLC 3 sets none, so the helper uses the id Windows derives from vlc.exe's path plus relaunch properties (`$TaskbarAppId` overrides). Mono compile (strict) + unit tests of layouts / GUIDs / drawing. *Unverified:* everything at runtime; 13-step checklist in README. | L |
| 20 | Windows media integration: media flyout (volume / media keys), Quick Settings media card, lock screen, hardware media keys | **DONE in Setup (T13), confirmed by the user on Windows 2026-10-31** (card shows title / artist, previous, pause, next) | Setup asks, finds VLC's architecture from vlc.exe's PE header, offers the VC++ runtime (Microsoft download, Authenticode checked), downloads the pinned v5.0.0 zip (SHA-256 = GitHub's release digests), copies the DLL (one UAC prompt; none for a writable portable VLC) and adds `win10smtc` to `extraintf` (module name from `plugin.h`, `PLUGIN_SHORTNAME`; `extraintf` is the option behind Qt's "Control interfaces" box). This is the "integrate it into Windows" option (System Media Transport Controls, SMTC). VLC 3 has none. The community plugin [vlc-win10smtc](https://github.com/spmn/vlc-win10smtc) adds it: GPL-3.0, maintained (v5.0.0, 2026-09-08, supports VLC 3.0.x and 4), Windows 10 1607+ / 11, x64 / x86 / ARM64 builds. It needs the Visual C++ 2022 redistributable matching VLC's architecture (VLC's, not Windows'). Install: copy `libwin10smtc_plugin.dll` to `<VLC>\plugins\misc` (Program Files, so admin once), then Advanced Preferences > Interface > Control interfaces > "Windows SMTC integration". It is a control interface, so it runs next to skins2: VLC starts `extraintf` / `control` modules whatever the main interface is (verified, `src/libvlc.c`). It creates its own hidden window, so it does not depend on the skin. The exact `extraintf` value (expected `win10smtc`) and the behaviour with skins2 are *unverified* until tested on Windows. Covers most of what 19 asks for in Windows' own UI; 19 adds the buttons on the taskbar hover itself. | M |
| 21 | Control channel from the helper to VLC (prerequisite for 19, and for menu-style controls in section 2 D) | **DONE, confirmed on Windows 2026-10-31 (taskbar buttons use it)** (T11; `VlcRemote` in `VlcDock.cs`, Setup keys in `vlc-taskbar.ps1`) | VLC's built-in web interface on localhost: `extraintf=http`, `http-host=127.0.0.1`, a random `http-password` written by Setup. `requests/status.json` gives play state, time, length, title / artist and the art URL; commands like `?command=pl_pause` / `pl_next` / `pl_previous` / `seek`. Alternative: the `rc` interface over TCP (`liboldrc_plugin`): simpler, but without a password any local program can control VLC. Works the same on Linux, but Linux has MPRIS (22b) anyway. **Built (T11)**, verified on Linux with real VLC 3.0.20 + skins2 (curl and the C# client under Mono: status, pl_pause, pl_next, pl_previous, pl_stop, seek, wrong password = 401, closed port): `http-host` and `http-port` are core options (vlcrc `[core]`, `src/libvlc-module.c`); `http-password` belongs to the Lua module (`[lua]`, `modules/lua/vlc.c`); `extraintf` is `[core]`. The web interface runs next to skins2. `status.json` has `time` and `length` in whole seconds only (a progress bar must interpolate between polls) and `information.category.meta` with `title` / `artist` / `filename` (no title tag: the helper falls back to the file name). A command's answer can still show the old state (next, stop), so read the status again. *Unverified (needs Windows)*: the whole helper side, and that the Windows Firewall shows no prompt for a loopback-only listener (expected none). An already running helper must be restarted after Setup to pick up the web interface settings. | S-M |
| 22 | Linux as a first-class platform (you use it on Linux too) | **LINUX** | The skin itself runs on Linux X11 today (every test and screenshot is from Linux VLC 3.0.20). Missing: setup, desktop integration, pin on start, and Wayland. Sub-items 22a-22d below. **Decided 2026-10-31:** distro unknown, so everything must be universal (any distro, any desktop, native / Flatpak / Snap VLC, X11 and Wayland via XWayland, only tools present everywhere). First goal: floating strip, pinned on start; no panel docking for now. | - |
| 22a | Linux setup script | **DONE (tested in Xvfb; Flatpak / Snap / Wayland unverified)** | `linux/setup.sh` / `--uninstall` (T14): detects native / Flatpak / Snap VLC, writes the same vlcrc keys as Windows (shared table in `docs/architecture.md`, "vlcrc keys"; `skins2-taskbar` is Windows-only), picks the skin from `GDK_SCALE` / `QT_SCALE_FACTOR` / `Xft.dpi` / KDE / GNOME (`--scale N` overrides), backs up `vlcrc.before-vlc-amp`, refuses while VLC runs. The `vlc` launcher forces `--media-library` (`bin/vlc.c`), so setup writes `~/.local/share/applications/vlc-amp.desktop` ("VLC Amp", `--no-media-library`) and optionally makes it the default for `audio/*` (not folders). Harness-checked: Media Library node gone, second start hands its file to the first instance over D-Bus, uninstall restores vlcrc byte for byte. Optional pin autostart (T16); installs the Lua extras and `lua/vlcrc-keys.txt`. *Unverified:* Flatpak paths, Snap fallbacks, scale under Wayland. | M |
| 22b | Linux media controls (MPRIS) | **DONE** | Documented in README ("Media controls", Linux). Verified: `org.mpris.MediaPlayer2.vlc`, `Next` and `PlayPause` over D-Bus with the skin. *Unverified:* KDE Plasma's hover buttons on the task manager entry (`WM_CLASS` vs the "VLC Amp" desktop entry); untagged files show the file name only. | XS |
| 22c | Linux: start pinned and dock into a panel | **PIN DONE (T16, tested on Xvfb only), docking postponed** | `linux/vlc-amp-pin.py` (Python 3 standard library + ctypes on libX11 / libXext, no xdotool): finds the skin's main window (class `Vlc`, name `VLC (TopWindow)`, largest viewable), reads the Shape extension (same rule as `ReadShape`), takes the scale from the window height / `.vlt` name, and clicks the skin's own pin with synthetic `ButtonPress` / `ButtonRelease` via `XSendEvent`, so the pointer never moves (checked in source: the X11 loop ignores `send_event`; `findHitControl` sends the checkbox its `enter`). Verified in VLC 3.0.20 under Xvfb at 100 % and 150 %, strip / full, bar top / bottom: pin lit, pointer unchanged, `_NET_WM_STATE_ABOVE` set under a fake EWMH window manager. `--watch` (polls `/proc` every 2 s), `--install-autostart` / `--uninstall-autostart`. Docking into a panel postponed. Unverified: real window managers / compositors (22d). | M |
| 22d | Wayland | **LINUX, not tested: skipped by the user 2026-11-01** (stays a documented limitation; the checklist below is for anyone who can run it) | skins2 is Xlib only, so on Wayland the skin runs through XWayland; `vlc-amp-pin.py` talks to that X server and never places windows. **Checklist for the user** (`linux/vlc-amp-pin.py -v` with VLC started): 1. GNOME Wayland: "_NET_WM_STATE_ABOVE is set", player stays above other windows, pin stays lit. 2. KDE Plasma Wayland: same. 3. `--install-autostart`: the watcher runs after login (DISPLAY set) on GNOME, KDE, XFCE, Cinnamon. 4. Click-through in the transparent area. 5. Moving the window by its grip. 6. 125 / 150 % fractional scaling: size and pin position. 7. Flatpak / Snap VLC. 8. Tiling WMs (windows may not float). Record the results here. | ? |
| 23 | Custom accent colour: pick any colour for the Custom theme, Windows and Linux | **DONE (Linux tested / Windows untested)** | `custom-colour/`: `custom-colour.py` (Python 3 standard library only, own PNG decoder / encoder; Pillow only as a speed-up, `--no-pil`; picker: `zenity`, `kdialog`, `yad`, tkinter, then the terminal; `--reset`; atomic rewrite of the `.vlt`) and `Custom colour.cmd` + `custom-colour.ps1` (Windows PowerShell 5.1, C# 5 pixel loop with `System.Drawing` `LockBits` `Format32bppArgb`, `ColorDialog`, built-in `tar.exe`). Uses `custom-ref/` of the `.vlt` (see `docs/architecture.md`, Custom theme); a `.vlt` built before that existed is skipped with a message. **Verified on Linux**: recoloured 100 / 150 / 200 % skins to `#33ff99` with the pure-Python path and compared with the generator's own `--custom "#33ff99"` build: every `img/` pixel identical (max channel difference 0 over 1.1 / 2.6 / 4.8 million pixels, alpha identical), `theme.xml` byte-identical, all other `.vlt` members byte-identical; pure path == Pillow path == generator for 8 colours (incl. `#000000`, `#ffffff`, `#ff0000` = identity); PNG decoder tested with all 5 filters (and the skin's PNGs use all of them) plus error cases; time 0.3 s (100 %), 0.9 s (150 %), 1.6 s (200 %) per `.vlt` pure, 0.4 s with Pillow; real VLC 3.0.20: recoloured skin, Custom theme shows the chosen green. C# class compiled with Mono `mcs -langversion:5` and run under Mono + libgdiplus: PNG output identical to the generator's, XML identical. *Unverified (needs Windows)*: the PowerShell script as a whole (`tar.exe` pack / unpack, the colour dialog, `[IO.File]::Replace`), the C# class on Microsoft's GDI+ (expected the same: `Format32bppArgb` is straight alpha), and that VLC reads the `tar.exe`-packed file (`--format ustar`, files only, as the generator writes). The GUI pickers `zenity` / `kdialog` / `yad` / tkinter were only tested with stand-in scripts for their output format. | done |
| 24 | Online configurator for the skin's look | **DONE (2026-11-01), live at <https://fakrij.github.io/vlc-amp/>** | A static web page that builds one `.vlt`: either **one theme** (memory stays at the Midnight level) or **one theme as a light + dark pair with a switcher** (the round theme button in the full player; ~+10 MB at 100 %, +20 MB at 150 % with the flat skin; **about +32 MB (100 %) with the hi-fi skin: Midnight + Paper 135.8 vs 103.6 MB**), optionally **following the system's light / dark setting** (item 25). Options: **size** (display scaling 100 / 125 / 150 / 200 %, default from the browser's `devicePixelRatio`), **font** (curated open-licence fonts, OFL; times need tabular / monospace digits; optional own TTF), **light / dark** base, **primary colour** (accent: LCD text, progress, active buttons), **secondary colour** (indicator LEDs: pin, PL / EQ lights, toggles). Preview, then download. Route: run `build_skin.py` in the browser with Pyodide (Pillow is available there), so the generator stays the single source of truth. Needs generator options first: `--font`, `--mode`, `--accent`, `--led` (today themes are named seeds). *Unverified*: Pyodide load size (~10-15 MB) and build time per scale. Brief: T17. *Step 1 done*: `build_skin.py --mode dark|light --accent #rrggbb --led #rrggbb --font <ttf>` builds one theme named "Theme" (base tint = accent hue at Midnight's saturation, grey for a grey accent; LED defaults to a lightened accent); the font replaces DejaVu Sans Mono for all LCD text and ships as `fonts/lcd.ttf|otf` (DejaVu licence file is then left out). Default builds are unchanged (stage dir identical). Checked in VLC 3.0.20 (light, #ff8800, #00ccff, bold font): renders, no skins2 warnings. Tabular digits of a custom font are not checked. *Steps 2 + 3 done*: static page in `configurator/` (Pyodide 314.0.7 + Pillow 12.2.0 from jsDelivr, worker, `glue.py` keeps the spike's normalisations and ships the font licence in the `.vlt`; fonts DejaVu Sans Mono, JetBrains Mono, Roboto Mono, Source Code Pro). Built under node and tested in VLC 3.0.20 (light, Source Code Pro); the page itself was not run in a browser. *Step 4 + own-TTF done (2026-10-31)*: the page has a "Light + dark" checkbox (`--pair`) and a font file input (read in the page, written to `/work/fonts/own.ttf|otf` by the worker, no licence file: the page warns about the licence and about non-monospaced digits); the page's copy of `build_skin.py` was synced (video window, fullscreen controller). Verified under node + Pyodide 314.0.7 (pair + JetBrains Mono: builds, `th1` present, 5.4 s at 100 %); *the page itself was run in Edge (2026-11-01, `configurator/test/browser-test.mjs`, Windows node + puppeteer-core): single build 2.4 s, pair 3.3 s, own font 3.2 s, no errors*. *Hosted (2026-11-01)* on GitHub Pages, <https://fakrij.github.io/vlc-amp/> (`.github/workflows/pages.yml`); the live page run in headless Edge: build 3.5 s (8.6 s with Pyodide loading), full preview rendered, Download button shown. *Download checked (2026-11-01)*: headless Edge on the live page, light base, accent `#e0402a`, 150 %: build 3.8 s, Download saved `VLC-Amp-150.vlt` (286 KB), which real VLC 3.0.20 loaded and played with no skins2 warnings (light strip, red accent). | M |
| 25 | Follow the system's light / dark setting (for a light + dark pair) | **Windows DONE (2026-10-31), live switch in the full player confirmed by the user; Linux prototype DONE (`linux/follow-system-theme.sh`)**. Windows: `$FollowSystemTheme` in `vlc-taskbar.ps1`; `VlcDock.cs` (`SyncVlcrcTheme`, `FollowSystemTheme`) rewrites th0 / th1 in vlcrc while VLC is closed (checked every 5 s) and, while VLC runs with the full player showing, clicks the theme button when the panel brightness (3 sampled pixels) disagrees with `AppsUseLightTheme`. The strip has no theme button, so it follows when expanded. `make-windows-package.sh` rebuilds the .vlt files as Midnight + Paper (`PAIR=0` keeps Midnight only). Start-up sync (VLC closed, then a file opened) confirmed too. Old status: | **Linux prototype (done, works today with `--themes midnight,paper`; README "Linux: follow the system's light / dark setting"):** the script reads the setting (portal via `gdbus`, else `gsettings`, default dark), and only if VLC is not running rewrites the last field of the `th0` / `th1` entries of `skins2-config` in vlcrc, then execs `vlc` (or `--exec CMD`); `--install` / `--uninstall` wrap / unwrap every Exec line of `vlc-amp.desktop`; `--dark-theme` / `--light-theme` map themes. Verified in real VLC 3.0.20 under Xvfb (tools/vlc-test.sh, stub `gdbus`): dark start showed Midnight, stub flipped to light and restart showed Paper, flipped back and restart showed Midnight again; while VLC ran the script left vlcrc untouched. *Unverified*: real portal / gsettings output, Flatpak / Snap paths, the wrapped launcher from a real desktop, a system switch while VLC runs (not handled: next start follows). First start with no saved `skins2-config` shows th0. Original spec: skins2 cannot read the OS setting. But VLC stores each theme flag window's visibility in `skins2-config` in vlcrc (seen in a test run: `["th0" "th0-l" 639 511 1 1 0]["th1" "th1-l" 639 511 1 1 1]`, last field = shown), and reads it at start. So: **at VLC start** a helper / launcher rewrites th0 / th1 in vlcrc while VLC is not running. Windows: `HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize\AppsUseLightTheme` (helper in `-Watch` mode, before VLC starts; but VLC started from Explorer starts without the helper getting a chance first, so this only works for the next start, or via a launcher). Linux: `gdbus call` to the XDG desktop portal (`org.freedesktop.appearance` `color-scheme`), fallback `gsettings get org.gnome.desktop.interface color-scheme`; a wrapper in the `.desktop` file (22a) runs before VLC. **While VLC runs** (system switches at sunset): the helper posts a click on the theme button (like `PinOnce`), which only exists in the full player; the strip would need a small switch too (design question). VLC rewrites `skins2-config` when it exits, so the helper must not edit it while VLC runs. *Unverified*: posted clicks on Windows (same risk as N1). | M |
| 26 | Windows test 2026-10-31: docking in the taskbar flashes and moves around | **FIXED, verified on Windows 2026-10-31 (T25)** | Cause (verified on X11, same skins2 code): skins2 keeps its own idea of the window position and never notices outside moves, so every expand / collapse / flip / resize put the window back at VLC's old position and the helper pulled it back. The corner-radius suspicion was wrong. Fix: the helper moves VLC with a posted drag on its grip (skins2 then knows the new position; `SetWindowPos` only as fallback), never while a mouse button is down. **Second test log (125 % scaling):** the helper (DPI-unaware PowerShell) reads VLC's window alternately in physical and DPI-virtualized coordinates (734x545 vs 587x436, Start button 1358 vs 1086) and moves it back and forth 4 times a second. Fix: force one DPI awareness context (per-monitor v2) around all window calls. Probably also the cause of item 33 (strip pushed off-screen). Third test log (helper per-monitor DPI aware): one coordinate system (734x545 at 125 %, VLC 120 dpi), the taskbar skin (`VLC-Amp-taskbar-125.vlt`) detected, docked with one posted drag, pin clicked and on, resizing by the grip works (width 734 -> 754, right edge back at Start on release), a drag away snaps back on release. | M |
| 27 | Windows: making the player wider is hardly possible | **SKIN PART DONE (T23); helper part FIXED (T21)** | Docked with `DockTo=start`, the helper right-aligns the strip to the Start button, so while you drag the right edge wider the window moves left under the mouse (helper). The `resizeE` grip is also only a few px wide, and the flat style made it hard to see (skin). Skin: a 10 px grip tab with ribs at the right end of strip, full player, EQ and playlist (`resize_handle()`); drag verified in the harness at 100 / 150 % and the taskbar build. | Helper: no re-placing while a mouse button is down; with `DockTo=start` the right edge returns to the Start button on release, so the strip grows to the left. A width change after an outside move no longer snaps back to the minimum (same root cause as 26). | S-M |
| 28 | Windows: unpin does not work | **FIXED (T21), confirmed by the user on Windows 2026-10-31** | `Move()` always re-applied `HWND_TOPMOST`. The helper now reads VLC's pin state and only re-raises while pinned. Exception (**confirmed by the user 2026-10-31**): the bare strip docked in the taskbar stays topmost even when unpinned, because a non-topmost strip is always hidden behind the taskbar; unpin applies to the full player. | S |
| 29 | Windows: the buttons look weird | **FIXED (T23, likely cause), needs the user's confirmation** | Found in skins2 source: PNGs are premultiplied on load (`file_bitmap.cpp`) and `AlphaBlend` is fine, but buttons / checkboxes / thumbs / slider backgrounds are drawn into a blank offscreen bitmap and then copied without blending (`drawGraphics`), so a semi-transparent pixel becomes opaque and on Windows takes whatever the blank bitmap held (`CreateCompatibleBitmap` does not guarantee black): bright dots at the rounded corners. Simulation by `tools/windows-sim.py` (legacy; its images in `docs/img/windows-sim/` were removed with the redesign; `tools/bitmap-audit.py` is the current check). Fix: the generator composites those bitmaps over the panel colour (`solid()`, flat style), so every pixel is opaque; Linux looks the same. | S-M |
| 30 | Windows: "Media Library" (Knihovna medii) still in the playlist | **FIXED (T22), confirmed by the user on Windows 2026-10-31** | Verified cause: `bin/winvlc.c:189` puts `--media-library` before the user's arguments, so vlcrc's `media-library=0` is overridden (Linux: same, `bin/vlc.c`). Setup now writes per-user overrides `HKCU\Software\Classes\<ProgID>\shell\<verb>\command` (VLC.<ext>, VLC.OPENFolder, Directory, AudioCD, ... read from HKLM, only commands running this vlc.exe with `--started-from-file`) with `--no-media-library` added, listed in `%LOCALAPPDATA%\VLC-Amp\file-associations.txt`; Uninstall removes exactly those. The helper's VLC start and a new Start menu "VLC Amp" shortcut pass the flag too. VLC's own Start menu / pinned icon still show the node (cannot be changed per user). | M |
| 31 | Windows: with EQ / playlist open the player cannot collapse back into the taskbar | **FIXED, confirmed by the user on Windows 2026-10-31 (T21 + T25)** | If the helper's bar height (36) differs from the skin VLC actually uses (24), the old test called "strip + PL / EQ" the full player. New `DockShape.Classify` derives the state from the visible height and infers bar height and scale (768 cases pass). Panels that would open below the screen now get one automatic flip click (`$FlipPanels`). **User 2026-10-31: the strip stayed *above* the taskbar** instead of going into it, which matches the suspected misclassification (placed like the full player). Still wanted: the log's `helper started: scale=.. barHeight=..` line and which .vlt VLC uses. | S-M |
| 32 | Flipping the panels (above / below) moves the strip | **FIXED on Windows, confirmed by the user 2026-10-31 (T25); Linux: limitation** | Cause (known since item 14): the 4 layouts have one size, the bar sits at the top in "dn" and at the bottom in "up", and a skin action cannot move the window. Fix (`KeepBarOnFlip`, `DockShape.FlipOffset` / `BarTop` / `ClampVisible`): the helper sees the bar-side change of the same kind (strip / full) and, not docked, moves the window by the difference with T21's posted drag, clamped to the work area; never while a mouse button is down, not on strip <-> full, not when the window moved as well. Docked, `Place` keeps the strip in the taskbar as before; a 50 ms timer while the mouse is over VLC makes the jump short. The full player with both panels now has a known direction too (seam test in `Classify`). Unit-tested under Mono with real shapes (80 dn / up pairs, 3493 checks). Linux: same idea in `vlc-amp-pin.py --watch` is harder (skins2 ignores outside moves and synthetic motion on X11); stays a limitation for now. README "second Windows test" steps 9-10. User: flipping is OK now. | S-M |
| 33 | Second Windows test: a click on the taskbar still hides the player; it only comes back from VLC's tray icon | **FIXED, confirmed by the user on Windows 2026-10-31 (T25)** | **First Windows log (125 %)**: the DPI-unaware helper (powershell.exe) read VLC's window alternately in physical and DPI-scaled coordinates (734x545 / 587x436, Start at 1358 / 1086), depending on which window's message called `Place`, and moved VLC back and forth between them (also the flashing); a position from the wrong system can push the strip off the screen, where skins2 keeps it until the tray icon re-shows it at its own stored position. No hide / minimize was logged at the taskbar click. Fix: the helper's thread is per-monitor DPI aware (V2) from the start and at every entry point (`DpiEnter`), so all coordinates are physical; `dpi:` / `DPI:` log lines. The same log: VLC used `VLC-Amp-125.vlt` (24 px) while the helper assumed the 36 px build; the script now takes scale / bar height from vlcrc's `skins2-last` when it does not start VLC (cause of the mismatch not visible in the script: Setup writes the taskbar build when docking was answered Yes and the file exists; VLC also saves the skin it last had on exit). User: it happens on a click on an empty taskbar spot or another app's / Windows' icon (not VLC's button, not show desktop). Source facts (3.0.x): skins2 has no `WM_ACTIVATE` / `WM_ACTIVATEAPP` / `WM_KILLFOCUS` handling, so activation changes cannot hide it; its windows are hidden only by minimizing the root window (`vlc.minimize()`, `SC_MINIMIZE` to the root), a skin change or `window.hide()`. Tray icon: single click = `raiseAll` (`SetForegroundWindow`; helps only if VLC was *covered*), double click = `SW_RESTORE` on the root (helps if *minimized*). The root never gets a taskbar button with `skins2-taskbar=0`. So either (a) something minimizes the root (Windows; unknown what), or (b) the strip stays behind the taskbar although the helper re-raises it (Windows 11 z-order; then item 15's `SetParent` is the next step). Fix: while docked, the helper restores a minimized VLC at once (`SC_RESTORE` to the root, as the tray double-click); the full player's own minimize button still minimizes (cursor on the full player at that moment); undocked nothing changes. A raise that does not take is logged with the windows above VLC and retried (NOTOPMOST, TOPMOST). New log lines: `foreground: ... (process); VLC root ... main ...`, `VLC window event: root window ... minimized`, `VLC hidden: ...`, `restore: ...`, `the taskbar is still above VLC after the raise`. Still needed: the log of one occurrence and whether a single or only a double click on the tray icon brings it back (README steps 11-15). User: no longer hides after the DPI fix. | M |
| 34 | Video does not play (audio only) | **DONE on Windows, confirmed by the user 2026-10-31** (cause of the first failure: VLC's saved `skins2-config` had the new window as hidden; skins2 attaches video only to a *shown* window. The helper now sets `["video" ...]` to shown in vlcrc while VLC is closed (`SyncVlcrcTheme`). Title bar with full screen + shrink-to-bar buttons, resize by the corner, and a full-screen control panel (window `fullscreenController`: seek, previous / play / next, volume, leave) all confirmed by the user on Windows 2026-10-31; the helper also resets a saved `video-min` layout to `video-l`. *Also fixed* (commit e9fdd60): Setup repairs the saved video window entry itself, on Linux with `repair_video_window` in `linux/setup.sh` and on Windows with `Repair-VideoWindow` in `vlc-taskbar.ps1` Setup, so neither needs the helper running; tested on Linux and by `tools/test-repair-video-window.ps1`, not by a real video on Linux). Old status: | The skin had no `<Video>` control, and skins2 shows video only inside one. New window `video` (`build_skin.py`, `vlay`): themed frame (drag, resize E / S / SE) and a Video control, every control `visible="vlc.hasVout"`, so it is invisible without video (same trick as the flag windows). Autoresize: the window follows the video size. The helper's `FindMain` now ignores it (the main window is always 436 logical px high; **676 since the redesign**). Verified in VLC 3.0.20 under Xvfb: no skin warnings, window invisible without video. *Not verified:* a real video (the test VLC has no video output plugin and no libavformat), the window on Windows, fullscreen, moving / resizing, theme switch while a video plays. | M |
| 35 | Code review of v1.0 (2026-11-01): 10 findings | **FIXED (T26); Linux tested, Windows compiled / parsed only; the Windows checks were skipped by the user 2026-11-01** | (1, 2) Setup run twice on a machine with no vlcrc backed up its *own* vlcrc, so uninstall restored the skin settings (Windows: and pointed VLC at the deleted folder). Now Linux skips the backup when `rc_created=1` for the same `rc`; Windows leaves `vlcrc.vlc-amp-created` and makes no backup. (3) Linux setup refuses a second VLC flavor until `--uninstall`. (4) Linux setup leaves a foreign `lua-intf` alone (as Windows). (5) `follow-system-theme.sh` uses the vlcrc from the setup state. (6) `vlc-amp-pin.py` also reads `~/snap/vlc/common/vlcrc`. (7) `VlcDock.CheckVlc` prefers the vlc.exe with the skin's root window and keeps the one it follows (`PickVlc`). (8) `Set-VlcOption` finds `[core] # ...` headers. (9) the helper no longer passes an empty `--skins2-last`. (10) `Find-Vlc` shared in `taskbar/find-vlc.ps1`. *Unverified (needs Windows):* Setup twice on a PC without vlcrc, then Uninstall (vlcrc gone, marker gone); the helper with two vlc.exe running. | done |
| 36 | Rename the project to **VLC Amp** (MMD3-inspired skin with a title bar mode); nobody had installed it, so no migration | **DONE (2026-11-01), released as v1.2** | Folder `VLC-Amp/`, skins `VLC-Amp-NNN.vlt` / `VLC-Amp-taskbar-NNN.vlt` (rebuilt: only the `ThemeInfo` name changed), `%LOCALAPPDATA%\VLC-Amp`, Start menu and launcher "VLC Amp" (`vlc-amp.desktop`), Lua `vlcamp.lua` (`lua-intf=vlcamp`), `linux/vlc-amp-pin.py`, backups `vlcrc.before-vlc-amp`, packages `VLC-Amp-windows.zip` / `VLC-Amp-linux.tar.gz`. The test cache `~/.cache/titlebar-test` keeps its name. Verified: Linux setup / uninstall in a test home, real VLC 3.0.20 with `VLC-Amp-150.vlt` (Lua `[vlcamp] interface started`, pin found), `check-windows-helper.sh` (compiles, 0 parse errors). Windows not run. | done |
| 37 | The helper did not come with VLC (user, 2026-11-01: started VLC, helper was off; the login-started helper had gone, cause unknown: no log without `-DebugLog`) | **FIXED (v1.4); launcher tested on Windows with a stub, the full install not run** | (1) The file association commands and the Start menu entry "VLC Amp" run VLC through `taskbar/launch.vbs` (wscript, no console), which starts the helper like the Startup shortcut does when that shortcut exists and no helper runs. VLC's own Start menu entry / pinned icon still bypass it. (2) Start, exit with reason, and crash lines always go to `%TEMP%\vlc-amp-helper.log` (`VlcDock.Note`, script `trap`, Setup / Install note a stopped helper), so the next disappearance can be explained. Details: docs/architecture.md "The Windows helper". | done |
| 38 | Hi-fi redesign (~/dev/vlc-modular, 74 commits on the pre-rename history) integrated into VLC Amp | **DONE (2026-11-01, branch `integrate-hifi`)** | Squashed onto the equivalent base (63f2602, same tree as the fork's base 1ea8b7e; noreply author), merged; hi-fi generator as the base with VLC Amp's video window ported to its style (title bar, docked panel with the seek bar 12 px under the video, extra row with A-B, fullscreen controller), VLC Amp names applied to all incoming text, `assert` checks as `SystemExit`; playlist-length rule re-measured for the 620 px / 12 px font playlist (76 at 100 %, 74 at 125 %, one more cut); configurator synced with `tools/sync-configurator.py` (all builds identical). Open items of the redesign: [BACKLOG-hifi.md](BACKLOG-hifi.md). *Unverified:* the merged helper and video window on Windows. | done |

Numbers 1-10 follow your first list; N1-N3 your second list; 13-14 your third list (13 = width, 14 = panel side); 15 and 17 your fourth and fifth; 18 the themes; 19-22 your sixth list (taskbar hover buttons, Windows integration, Linux); 7a, 7b, 11, 12, 16, 21 were added during analysis.

---

## 2. Plugin and extension options

Common problem: **a skin button can only run actions that skins2 knows** (verified list: `dialogs.*`, `dvd.*`, `playlist.*`, `vlc.play/pause/stop/faster/slower/mute/volume/minimize/onTop/snapshot/toggleRecord/nextFrame/quit/fullscreen`, `equalizer.enable/disable`, `*.setLayout/show/hide/maximize`). There is no "run script", no custom action, and no way to send a key. So any feature built outside the skin needs a bridge from the button to that feature. The options:

### A. Lua interface script (`lua/intf/vlcamp.lua`, started with `--extraintf luaintf --lua-intf vlcamp`)

- Runs inside VLC beside skins2, on Windows and Linux. Can read and control playback, the playlist, and the input (time, seek).
- Good for: A-B loop, next/prev folder, EQ presets (via the Lua equalizer library), sleep timer, "remember position", extra hotkeys.
- Hotkeys: libvlc exposes the integer variables `key-pressed` and `key-action` (verified in `src/misc/actions.c`). **Verified (T5, docs/lua-api-notes.md): Lua in 3.0.x has no `vlc.var.add_callback`**, so a Lua interface must poll `key-action` in its loop and reset it. Keys reach VLC from the skin through the Qt dialogs provider (`Dialogs::sendKey`). This is the only bridge that works without code outside VLC, but it is keyboard-only.
- Verified APIs (T5): `vlc.equalizer` (`setpreset`, `presets`, `equalizerset`, `preampset`), time via `vlc.var.get(vlc.object.input(), "time")` in microseconds, playlist via `vlc.playlist.get()` (item `path` = URI) and `vlc.playlist.gotoitem(id)`. Full notes with source references: [docs/lua-api-notes.md](docs/lua-api-notes.md).
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

### F. Operating-system media integration (items 19-22)

- **Windows:** the SMTC plugin (20) for the media flyout, lock screen and media keys, plus the helper's own taskbar button for the hover buttons (19). Both are outside the skin; the helper talks to VLC through 21.
- **Linux:** VLC's built-in MPRIS (22b, verified with the skin) already does the desktop's part.
- **Effect on the choice for 4 / 5 / 2:** Linux use favours A (Lua runs inside VLC on both systems) over D (the helper is Windows-only). C would need a build per platform: on Linux it must match your distro's VLC 3.0.x package, which is easier than the Windows cross-build.

### E. Own player on libvlc (outside the current scope)

- A new app (C#/WPF or Qt) using libvlc, with its own title-bar strip, playlist with columns, A-B loop, presets, folder navigation, media keys. Removes every skins2 limit. It is a different project, not an upgrade of this skin. Mentioned only as the long-term clean option.

### Evaluation summary

| Feature | A Lua | B Ext | C Patch | D Helper | Best fit |
|---------|:-----:|:-----:|:-------:|:--------:|----------|
| A-B loop | yes (logic) | no | yes | yes (via A) | C for a button, A + hotkey for a quick version |
| Next/prev folder | yes (logic) | no | yes | yes (via A) | same |
| EQ presets | yes (API verified, T5) | no | yes | yes (via A) | same |
| Start on top | no | no | yes | yes | D |
| Playlist columns | durations only (title suffix) | no | yes (large) | no | A for durations (built), C for real columns |
| West / SW resize | no | no | yes | no | C or accept |
| Media Library node | n/a | n/a | n/a | n/a | CONFIG (Linux: `.desktop` override, 22a) |
| Taskbar hover buttons (Windows) | no | no | no (skins2 owns no real taskbar window) | yes (own taskbar button + 21) | D |
| Windows media flyout / media keys | no | no | no | possible via WinRT, fiddly | third-party plugin (20) |
| Linux media controls | n/a | n/a | n/a | n/a | built in (MPRIS, 22b) |
| Runs on Linux | yes | - | yes (own build) | no | A |

---

## 3. Suggested order

Docs: user guide in README.md, internals in [docs/architecture.md](docs/architecture.md).
Everything that can be built and checked on Linux is built. After the hi-fi integration: re-run `tools/sync-configurator.py` after every generator change; the Windows test of the merged skin and helper is BACKLOG-hifi.md H3. What is open needs a Windows machine,
a real desktop, a browser or a decision by the user.

1. **T17 (item 24):** the configurator is hosted on GitHub Pages
   (<https://fakrij.github.io/vlc-amp/>, workflow `.github/workflows/pages.yml`). Live page
   checked in headless Edge; a downloaded build loads in real VLC. Done. T18 / item 25 follow-system theme is
   built (Windows helper, Linux prototype).
2. **T10** (patched skins2) is parked: only if the user chooses option C in section 2.

Skipped by the user (2026-11-01): the Windows checks for item 35 and the item 22d Wayland / window
manager checklist. They stay recorded in their rows.

Agent-sized work packages for these steps are in section 5.

## 4. Open questions

1. T10: is option C (own skins2 build) wanted at all? Until the answer is yes it stays parked.

Answered (for the record):

- Items 4, 5, 2 (2026-10-31): the Lua route, A + D (Lua interface script, hotkeys, helper tray menu).
  Built as T6.
- Item 20 (2026-10-31): yes, Setup downloads and installs the SMTC plugin (T13).
- T17 hosting (2026-11-01): GitHub Pages on a new public repository (github.com/fakrij/vlc-amp).
- Item 35 Windows checks and item 22d (2026-11-01): skipped.
- Item 22 (2026-10-31): distro unknown, so it must be universal. Floating and pinned first, no panel
  docking.

---

## 5. Subtasks for agents

Self-contained work packages, sized for one agent each. Each brief says what to read, what to change, how to verify, and what not to do.

**Model guide**
- **Haiku**: mechanical, fully specified, easy to check (docs, lookups with a known answer shape).
- **Sonnet**: normal implementation with a clear spec and a test path (generator, helper, scripts).
- **Opus**: open-ended design, root-cause work on unclear bugs, or large, risky spikes.

**Rules for every agent**
- Read `README.md` and this file first. The generator is `source/build_skin.py`. Release skins are `VLC-Amp-{100,125,150,200}.vlt` (24 px) and `VLC-Amp-taskbar-{100,125,150,200}.vlt` (36 px) in the repo root. Rebuild them with `--scale 1 / 1.25 / 1.5 / 2` (add `--bar-height 36` for the taskbar set), `--out` to a temp folder, then copy the `.vlt` files and `preview-100.png` -> `preview.png`.
- skins2 limits are listed in items 7b/13, 3, and section 2. Check the VLC 3.0.x source (github.com/videolan/vlc, branch `3.0.x`, `modules/gui/skins2`) before relying on any skins2 behaviour; do not guess.
- Windows scripts keep CRLF line endings and plain ASCII. `VlcDock.cs` must stay C# 5 (Windows PowerShell 5.1 `Add-Type`).
- Never `pkill vlc` / `killall`: kill only PIDs you started. No `sudo`.
- Commit on your own worktree branch, with the attribution line. Never commit to the main branch, never push, and do not merge: whoever integrates the branches does that. Update this backlog's item row when done.

| ID | Task | Model | Depends on | Size |
|----|------|-------|------------|------|
| T1 | Test harness in the repo | **DONE** (merged; `tools/`) | - | M |
| T2 | Move slower / faster to the full player | **DONE** (merged) | T1 | S |
| T3 | Helper debug log (for 15) | **DONE** (merged) | - | S |
| T4 | Docs consistency pass | **DONE** (2026-11-01; second pass, see the brief) | after others | XS |
| T5 | Lua API fact check (for 4, 5, 2) | **DONE** (merged; `docs/lua-api-notes.md`) | - | S |
| T6 | Lua interface: A-B loop, folder jump, EQ presets, bitrate | **DONE** (merged; Windows untested) | T1, T5 | L |
| T7 | Tray icon for the helper (11) | **DONE** (merged) | - | M |
| T8 | Taller taskbar strip option (12) | **DONE** (untested on Windows) | T1, T2 | M |
| T9 | Fix 15 (taskbar click hides the player) | **DONE via T21 / T25** (confirmed on Windows) | Windows answers + T3 log | M |
| T10 | Patched skins2 feasibility spike (option C) | Opus | decision on 4/5/2 | XL |
| T11 | Control channel: helper talks to VLC's web interface (21) | **DONE (untested on Windows)** | T1 | S-M |
| T12 | Helper's own taskbar button with hover buttons, progress, preview (19) | **DONE (untested on Windows)** | T11 | L |
| T13 | SMTC plugin install in Setup (20) | **DONE** (untested on Windows) | - | M |
| T14 | Linux setup script (22a) | **DONE** (merged; Flatpak / Snap paths unverified) | T1 | M |
| T15 | Linux docs: MPRIS, setup, limits (22b) | **DONE** | T14 | XS |
| T16 | Linux pin on start + Wayland check (22c, 22d; docking postponed) | **DONE** (Xvfb-tested; Wayland / real WMs need the 22d checklist) | T14 | M |
| T17 | Online configurator (24), **phase 2**; steps 1 and 4 DONE (generator options, `--pair` in T24); steps 2-3 DONE: `configurator/` page (own-TTF upload and light + dark pair included), node + VLC verified, headless Edge run OK (2026-11-01); hosted on GitHub Pages; live download loaded in VLC | **DONE** (2026-11-01) | - | M |
| T18 | Follow system light / dark (25), **phase 2** | **DONE** (item 25: Windows helper, confirmed by the user; Linux prototype `linux/follow-system-theme.sh`) | T17 step 4, T14 (Linux launcher) | M |
| T19 | Font check for the configurator: which OFL fonts skins2 renders, tabular digits (report only) | **DONE (report in `docs/font-notes.md`)**: DejaVu, JetBrains, Roboto Mono, Source Code Pro (.otf) render and are tabular; Inter is not tabular (reject), Source Sans 3 tabular but thin | - | S |
| T20 | Flatpak / Snap VLC paths and options, from docs and sources (report only, for 22a) | **DONE (report; mostly unverified, see brief)** | - | S |
| T24 | **DONE** (branch `worktree-agent-a8554c6a9e035c677`, not merged): generator reproducibility (`_truetype` forces `Layout.BASIC`; tar `filter=` + `GzipFile(mtime=0)`; sorted dirs / files) and T17 step 4 (`--pair`). Verified: two native builds byte-identical; Pyodide 314.0.7 + Pillow 12.2.0 via `tools/pyodide-spike/run.mjs ... 1 0` (no normalising wrapper) byte-identical to a native Pillow 12.2.0 build (a native Pillow 13.0 build differs in PNG bytes only). Release staged PNGs vs before: only `atlas_t0` and `t0_eq_bands` differ (glyph pixels, 0.8 % / 1.9 % of those images at 100 %, max channel delta ~200); looked right in VLC 3.0.20. Release `.vlt` files NOT rebuilt | Sonnet | T17 step 1 | M |
| T21 | Helper docking fixes: flashing, unpin, resize while docked, collapse with panels, item 15 (26, 27, 28, 31, T9) | **DONE** (untested on Windows; README "second Windows test" checklist) | - | M |
| T22 | Media Library off on Windows: file association overrides (30) | **DONE** (untested on Windows) | - | M |
| T23 | Skin: Windows bitmap rendering check + wider resize grip (29, 27) | **DONE** (Windows unverified) | - | S-M |
| T25 | Helper: keep the bar in place when the panels flip (32); find and fix why a taskbar click hides the player (33, 15) | **DONE** (confirmed on Windows) | - | M |
| T26 | v1.0 code review fixes (35) | **DONE** (Linux tested; Windows: compiled / parsed, needs the item 35 checks) | - | M |
| T27 | Linux setup: a re-run drops `follow-system-theme.sh --install`'s Exec wrap; `lua/vlcrc-keys.txt` hotkeys written even when the Lua extras are skipped | **DONE** (merged; setup re-run keeps the wrap and says so; keys only with the Lua extras. Verified in a private HOME: setup, `--install`, setup -> Exec still wrapped, `--uninstall` removes the file; `lua-intf=mine` -> warning, no `key-` lines; plain setup writes 5 keys; `sh -n`. Only the basic-launcher path: no system `vlc.desktop` on the test machine) | T26 | S |
| T28 | `vlc-amp-pin.py --watch`: only this user's VLC processes | **DONE** (merged; `py_compile` OK; throwaway test with `proc_comm` patched to "vlc": own pid present, pid 1 filtered out; no VLC started or killed; not run against real VLCs of other users) | T26 | XS |
| T29 | Generator: input checks with `assert` vanish under `python -O` | **DONE** (merged; `assert` -> `raise SystemExit("error: ...")`, same messages. Verified: VLC-Amp-100 `.vlt` from the original commit and after the change are byte-identical (`cmp`); forced case collision under `python3 -O` exits 1 with the error (temporary break reverted, not committed); `configurator/build_skin.py` synced, `diff` clean. Not run: the Custom-theme and element-id failures under `-O`, and the 150/200 % and taskbar builds) | - | XS |

### T27 - Linux setup re-run keeps the theme wrap; keys only with Lua (Sonnet)
From the v1.0 review. Files: `linux/setup.sh`, `linux/follow-system-theme.sh`, docs/architecture.md (Linux setup section).
- `make_desktop` rewrites `vlc-amp.desktop` from the system launcher on every run, so after `follow-system-theme.sh --install` a second `setup.sh` silently removes the `Exec="<...>/follow-system-theme.sh" --exec ...` wrap. Keep it: if the old file's Exec lines carry the wrap, re-apply it to the new file (same rule as `do_install`), and say so.
- Windows writes `lua/vlcrc-keys.txt` only when its Lua extras are installed (`Set-VlcDefaults` inside the Lua block of `vlc-taskbar.ps1`); Linux writes them always, also when the Lua extras are skipped because `lua-intf` names another script. Match Windows.
- Verify against a private HOME (`HOME=<tmp> XDG_*_HOME= sh linux/setup.sh --vlc native --ignore-running --no-default-player --no-pin-autostart --scale 150`): setup, `follow-system-theme.sh --install`, setup again -> Exec still wrapped; `--uninstall` still removes the file. A vlcrc with `lua-intf=mine` gets no `key-...` lines.

### T28 - Pin watcher: only this user's VLCs (Haiku)
`linux/vlc-amp-pin.py`: `vlc_pids()` says "of this user" but returns every process named vlc. Filter by `os.stat("/proc/<pid>").st_uid == os.getuid()`. Verify with `python3 -m py_compile` and a small test that `vlc_pids()` skips a pid owned by root (for example pid 1 renamed via a monkeypatched `proc_comm`).

### T29 - Generator checks without assert (Haiku) - **DONE**
`source/build_skin.py` `main()` checks case-only bitmap id collisions, the Custom theme's grey + red rule and element ids with `assert`; `python -O` drops them and a broken `.vlt` is written. Replace with `raise SystemExit("error: ...")` (same messages). Then run `configurator/sync.sh` (or `tools/sync-configurator.py`) so the page's copy matches. Verify: `python3 source/build_skin.py --out <tmp>` builds a `.vlt` byte-identical to one built before the change (same Pillow), and `python3 -O` still fails on a forced collision (temporarily, not committed).
Result: done as briefed; see the T29 row above for what was verified and what was not.

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
- `vlc-taskbar.ps1`: add `$DebugLog = $false` and pass it to `[VlcDock]::LogPath` (`$env:TEMP\vlc-amp-helper.log` when on).
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
Done (2026-10-31): README, this file, `docs/` and `tools/README.md` checked against the code. Stale
numbers, duplicate sections and broken links fixed. For the next pass: check each claim against
`source/build_skin.py`, `taskbar/`, `linux/`, `lua/` and `tools/`; keep one section per topic and
link to it from elsewhere; do not change behaviour or code; keep the item numbers stable.

Done again (2026-11-01): README, `docs/architecture.md`, `tools/README.md`, this file checked after the v1.0
review fixes (item 35, T27, T28): `vlcrc.vlc-amp-created`, one VLC flavor per Linux setup, a foreign `lua-intf`
(and then no `lua/vlcrc-keys.txt` keys), the theme wrap kept on a setup re-run, `follow-system-theme.sh` using
the setup's vlcrc, `taskbar/find-vlc.ps1`, the helper's choice among several vlc.exe (`PickVlc`), the pin
watcher's own-user filter; item 34's Linux / no-helper fix, T17's row, sections 3 and 4 brought up to date.
Left alone: `docs/font-notes.md` and the T19 row (another agent).

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
- `lua/intf/vlcamp.lua`:
  - A-B loop: the first key press sets A, the second sets B and loop playback between them, the third clears.
  - Next / previous folder: jump to the first playlist item whose directory differs from the current item's.
  - EQ presets: cycle through a fixed list.

  Trigger everything through hotkeys, using the mechanism T5 confirmed.
- Setup (`vlc-taskbar.ps1 -Setup`) copies the script and adds `extraintf=luaintf`, `lua-intf=vlcamp` to vlcrc.
- Verify with T1 on Linux: send keys with xdotool and check time / playlist position through the log or `vlc.msg` output.

### T7 - Tray icon for the helper (Sonnet)
Item 11.
- `VlcDock.cs`: add a NotifyIcon (System.Windows.Forms; it needs a message loop, and the helper already has one) with a menu: Dock on / off (replaces the hotkey, but keep the hotkey), Pin now, Open debug log (if T3 is done), Quit helper. Use a simple generated icon, not a file.
- `vlc-taskbar.ps1`: add System.Windows.Forms and System.Drawing to `-ReferencedAssemblies`.
- Compile-check with Mono. Untestable here, so keep it minimal and document what to check on Windows.

### T8 - Taller taskbar strip option (Sonnet)
Done: `--bar-height`, `VLC-Amp-taskbar-NNN.vlt`, `VlcDock.BarHeight`, harness bar-height awareness, docs. To check on Windows: Setup picks the taskbar file when docking; the 36 px strip is centred in the taskbar; the pin click lands (pin lights); log line `barHeight=36`.

### T9 - Fix 15 (Opus)
Needs the user's answers (was the helper running, gone for good or back after a moment, what was clicked) and ideally a T3 log from Windows. Then either fix the z-order re-assertion in `Place()`, or prototype `SetParent` onto `Shell_TrayWnd` for the bare strip (un-parent for panels / full player). Decide based on the log; do not guess.

### T10 - Patched skins2 spike (Opus)
Only if the user chooses option C.
- Find out whether a `libskins2_plugin.dll` built from 3.0.x sources with mingw-w64 loads in the official Windows VLC 3.0.x build (version and ABI match, plugin cache).
- Add one trivial new action (for example `vlc.abLoop()`, implemented in the core input like Qt's A-B, or a log line) as the proof.
- Report the build steps, size, time, and the risk on each VLC update. Do not start the full feature set.

### T11 - Control channel to VLC (Sonnet)
Item 21. Gives the helper a way to read VLC's state and send commands.
- Setup (`vlc-taskbar.ps1 -Setup`): add `http` to `extraintf` without dropping existing entries (colon-separated, for example `win10smtc:http`), and set `http-host=127.0.0.1`, `http-port` (default 8080; pick a free one such as 48080 to avoid clashes) and a random `http-password` (store it only in vlcrc; the helper reads it from there).
- `VlcDock.cs`: a small client class (`HttpWebRequest`, Basic auth with an empty user name, 1 s timeout). It polls `requests/status.json` every 500 ms while VLC runs, parses state / time / length / title / artist (no JSON library in C# 5 Add-Type: use `System.Web.Script.Serialization.JavaScriptSerializer` from System.Web.Extensions, or a minimal parser), and sends commands (`pl_pause`, `pl_next`, `pl_previous`, `seek`).
- Verify on Linux with T1: start VLC with `--extraintf http --http-host 127.0.0.1 --http-password x` and the skin, then `curl` the same requests the C# client sends (status, pause, next). Check that the web interface's Lua files are in the test root (`share/vlc/lua/http`). Compile-check the C# with Mono.
- Do not expose the interface beyond 127.0.0.1.

### T12 - Helper's own taskbar button (Opus)
Item 19. Needs T11. Untestable outside Windows, so design carefully and keep a kill switch (`$TaskbarButton = $true` in the ps1).
- A helper window with `WS_EX_APPWINDOW`, VLC's icon (`ExtractIcon` from vlc.exe), title = current track. Set the window's AppUserModel ID to VLC's (`SHGetPropertyStoreForWindow`, `PKEY_AppUserModel_ID`, plus `RelaunchCommand` = vlc.exe), so it groups with a pinned VLC instead of PowerShell. Find VLC's actual app id on Windows first; do not guess it.
- `ITaskbarList3` via COM interop (C# 5): after the registered `TaskbarButtonCreated` message, call `ThumbBarAddButtons` (prev, play / pause, next; icons drawn at runtime like the tray icon), `SetProgressState` / `SetProgressValue` from T11's time / length, `SetOverlayIcon` for play / pause. Handle `WM_COMMAND` + `THBN_CLICKED` and send T11 commands.
- Hover preview: `DwmSetWindowAttribute(DWMWA_FORCE_ICONIC_REPRESENTATION, DWMWA_HAS_ICONIC_BITMAP)` and answer `WM_DWMSENDICONICTHUMBNAIL` with a rendered bitmap (title, artist, time, accent colour).
- A click on the button activates VLC's main skin window (or restores it if minimized). Setup sets `skins2-taskbar=0` when this option is on, so there is a single VLC button.
- Compile-check with Mono; write a Windows test checklist into the README troubleshooting section.

### T13 - SMTC plugin in Setup (Sonnet)
Item 20. Only after the user answers question 4.
- `vlc-taskbar.ps1 -Setup`: optional step "Windows media controls". Find VLC's install folder (registry `HKLM\SOFTWARE\VideoLAN\VLC`, `InstallDir`) and its architecture (PE header of vlc.exe). Download `libwin10smtc_plugin_v5.0.0_<arch>.zip` from the GitHub release, check a SHA-256 pinned in the script, and copy the DLL to `plugins\misc` through one elevated PowerShell call. Check that the VC++ 2022 redistributable is installed (registry `HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\<arch>`); if not, tell the user where to get it, and do not install it silently.
- Add the plugin's module to `extraintf`, merged with existing entries (shared helper with T11). Read the module name from the plugin source (`vlc-win10smtc/plugin.h`, `PLUGIN_SHORTNAME` / module name) and record it in the backlog.
- Undo: `-Uninstall` removes the DLL (elevated) and the `extraintf` entry.
- README: manual install steps as the alternative. The behaviour needs the user's Windows test (media keys, flyout with title, lock screen).

### T14 - Linux setup script (Sonnet)
Item 22a.
- `linux/setup.sh` (POSIX sh or bash, no sudo): detect native / Flatpak / Snap VLC and the matching vlcrc path, back up vlcrc as `vlcrc.before-vlc-amp`, set the same keys as the Windows setup (shared list, documented in architecture.md), and pick `VLC-Amp-NNN.vlt` from `GDK_SCALE`, `Xft.dpi` (`xrdb -query`) or `gsettings get org.gnome.desktop.interface scaling-factor`.
- Write `~/.local/share/applications/vlc-amp.desktop` (copy of the system `vlc.desktop` with `--no-media-library` added to `Exec`) and offer `xdg-mime default` for audio MIME types. Reason: the Linux launcher forces `--media-library` (`bin/vlc.c`), so vlcrc alone cannot remove the Media Library node.
- `--uninstall` restores the backup and removes the desktop file.
- Verify with T1: run the script against the harness's private HOME, start VLC the way the desktop file would (`--started-from-file`), and check that the skin loads, the Media Library node is gone, and a second start with a file reaches the first instance (`dbus-run-session`).

### T15 - Linux docs (Haiku)
Item 22b. After T14.
- README: Linux install section (setup script and manual), a "Media controls" section (MPRIS: desktop media widget, media keys, `playerctl`; tested 2026-10-31 with the skin), Linux limits (X11 / XWayland, no helper yet). Update the "Windows only" line in Limits.
- architecture.md: the `bin/vlc.c` gotcha (`--media-library`, `--dbus` forced) and MPRIS.

### T16 - Linux pin on start, Wayland (Opus design, Sonnet build)
Items 22c, 22d. Universal (any distro / desktop), floating only; panel docking is postponed.
- Design: a Linux helper that waits for VLC's skin window and clicks the skin's pin once (same offsets as `PinOnce`), so the pin lights up. Must not need extra packages: `xdotool` and python-xlib are not installed everywhere. Preferred: `python3` with `ctypes` on `libX11` (present wherever VLC's skin runs), sending a synthetic `ButtonPress` / `ButtonRelease` with `XSendEvent` to the window, so the user's pointer does not move. Check first in skins2's X11 event loop (`x11/x11_loop.cpp`) that it does not ignore `send_event` events. Fallback when the click is ignored: `xdotool` if present.
- Autostart via `~/.config/autostart/*.desktop`.
- Wayland: write a checklist for the user (shape click-through, move, pin, scaling) and record the results in 22d. The helper may not be able to place windows on Wayland; say so instead of working around it.

### T17 - Online configurator (Opus design, Sonnet build)
Item 24. Output: one `.vlt` with exactly one theme.
1. Generator: add `--mode dark|light`, `--accent #rrggbb` (primary), `--led #rrggbb` (secondary), `--font <ttf>` (used for every LCD text; labels may keep DejaVu Sans Bold or follow it), building a single theme from these seeds (`_theme(mode, hue, sat, accent, led)` already does the colours; derive the base tint hue from the accent or keep neutral). Check that skins2 renders the font (FreeType; .ttf and .otf) and that digits are tabular (otherwise the time jitters); warn in the UI if not.
2. Spike: Pyodide + Pillow in a page, run `build_skin.py` unchanged with those options, measure load size and build time per scale in Chrome / Firefox, package the `.vlt` (the generator's tar code on Pyodide's file system) as a download.
3. Page (GitHub Pages): size, font (curated OFL list with licences shipped in the `.vlt`), light / dark, primary and secondary pickers; live preview (`preview_layout`); download; a note on which `VLC-Amp-NNN.vlt` name to use so Setup picks it up.
4. Light / dark pair (phase 2 option): the generator builds the same design twice (light and dark base, same primary / secondary colours, adjusted for contrast), theme button toggles them; checkbox "follow system setting" adds item 25 (helper on Windows, launcher wrapper on Linux).
- Keep the generator the single source of truth; no second renderer in JS.

### T19 - Font check (Sonnet, report only)
For T17 step 1. From the VLC 3.0.x skins2 source (`modules/gui/skins2/src/ft2_font.cpp` or similar) and by running the harness (T1): can skins2 load a `.ttf` / `.otf` named in `theme.xml`, how is the file looked up inside the `.vlt`, and are digits tabular? Test 4-6 OFL candidates (for example DejaVu Sans Mono, JetBrains Mono, Roboto Mono, Inter, Source Sans 3) by rendering the time at 100 % and 150 %. Report which work, licence file requirements, and file sizes. No repo changes except a short note in `docs/`.

### T20 - Flatpak / Snap facts (Haiku, report only)
For item 22a. Find, from VLC's Flathub and Snap packaging and docs: the vlcrc path, whether skins2 is shipped, how a skin in `~/.local/share/vlc/skins2` is seen inside the sandbox, and the right way to pass `--no-media-library`. Give links; mark anything not confirmed from a source as unverified.

Result (2026-10-31, Haiku, from docs only, nothing run): Flatpak (Flathub `org.videolan.VLC`, VLC 3.0.23): `--socket=x11` only, so XWayland; `--filesystem=host`; launcher `vlc.sh` runs `vlc.bin $VLC_ARGS "$@"`, so `flatpak run org.videolan.VLC --no-media-library %U` works (or `--env=VLC_ARGS=--no-media-library`). *Inferred, not confirmed:* vlcrc at `~/.var/app/org.videolan.VLC/config/vlc/vlcrc`, user skins at `~/.var/app/org.videolan.VLC/data/vlc/skins2`. *Unverified:* whether skins2 is compiled into the Flatpak and the Snap, Snap vlcrc location (`$SNAP_USER_COMMON/vlcrc`, i.e. `~/snap/vlc/common/`, per a 2018 commit), Snap dot-directory access, `--no-media-library` in Snap. Snap forces `QT_QPA_PLATFORM=xcb` (XWayland). Next step: test with real Flatpak / Snap VLC on a machine that has them.

### Flat style (history: default 2026-10-31, `--classic` = old look; both replaced by the one thin hi-fi style, section 0)
Flat = solid fills, no bevels / glow (preview in `flat-preview/`). Strip: no separate volume slider any more - the time box is `[+/- mode switch | volume fill]` (click / drag / wheel sets the volume; `thumb_none` = no knob).
- Panning / balance in the EQ window: NOT possible in skins2 (no pan, balance or stereo-mode variable in `libskins2_plugin.so`; no custom actions). Would need a Lua extension or a VLC audio filter plus a separate UI.

---

## 6. Pixel-perfect audit 2026-11-02

Audit of the hi-fi skin at commit 4e61517 (branch `design-tuning`, mute icon 16 px included), done with the
`/pixel-perfect` procedure on real VLC 3.0.20 + Xvfb (`tools/vlc-test.sh`, own instance `ppaudit`, display :141,
root window painted magenta so the window shape is visible). Nothing was fixed.

**Rendered for real:** Midnight at 100 / 125 / 150 / 200 % (24 px strip): all 14 layout x panel combinations (strip / full,
panels below / above, none / PL / EQ / both), window corners mirror-compared (identical in every case), seam columns
scanned; hover and pressed state of every button / toggle of the full player, EQ and playlist headers, playlist footer
and strip at 100 %; window widened by +157 px (100 %) / +137 px (150 %) and narrowed to the 490 px minimum; taskbar
build (36 px) at 100 / 150 %; Paper at 100 / 150 %; video window (`video-l`, resized, `video-x`) by loading a copy of
`theme.xml` with `vlc.hasVout` replaced by `not vlc.isMute`; volume fill with `--aout afile` (the dummy output
reports 0 %). **Approximated:** fullscreen controller (generator `preview_layout`, skins2 shows it only over a full screen
video), muted look (bitmaps composited; `vlc.mute()` had no effect with the afile output), `video-min`.
**Not checked:** Windows rendering, the other 8 themes and Custom, the 40 px strip, hover states at 125 - 200 %.

Screenshots: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/shots/` (`m<pct>_<layout>.png` = Midnight, `p` = Paper, `tb` = taskbar, `v` = video), per-state crops
`/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/states/`, zoomed evidence `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/`. Scripts (driver, crop + zoom, ink / mirror check, corner check):
`/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/tools/`.

Design rules used: BACKLOG-hifi.md "Design rules" (12 px margins, 1 px lines, radii 6 / 4 / 3, content centred in its band)
plus: icon and label groups centred in their button; siblings evenly spaced; a stretchable slice's middle piece must be plain
(skins2 tiles it, `resize="mosaic"`); what a layout switch keeps (size) must not jump.

**Serialization.** Every open task edits `source/build_skin.py` and must end with `tools/sync-configurator.py`
(`configurator/build_skin.py`), so run at most one task of the same group at a time and rebase the next one; tasks of
different groups touch different functions and can run in parallel worktrees (merge conflicts only in `configurator/`,
which is regenerated):
- **G-pan** (section backgrounds / panel layout: `add_eq`, `add_pl`, `hslice` / `nslice` callers): PP1, PP6, PP8
- **G-full** (`add_full`, `MIN_W`): PP2, PP7
- **G-bmp** (bitmap factories / icons: `make_strip_button`, `resize_handle`, `make_title_thumb`, `_icon`): PP4, PP5, PP9, PP12
- **G-video** (`video_layout`, `extra_row`, the video `Layout`s): PP3, PP10, PP11
- **G-font** (`source/fonts/`, `<Font>` ids, `docs/font-notes.md`): PP13

| ID | P | Task | Model | Group | Status |
|----|---|------|-------|-------|--------|
| PP1 | P1 | EQ header: half a grip dot repeats in the tiled middle of the EQ background when the window is wider than 620 px | Haiku, low | G-pan | done (branch worktree-agent-ad27b063c09dbf0c3, merged into design-tuning): eq_bg caps 14 / 12; real VLC at 100 % (+150 px) header has no stray pixels (unfixed baseline: 10 px at x 610-611); 150 % (+150 logical) clean; build check passes at 100 / 125 / 150 / 200 %; atlas_t0 repacks, all other staged bitmaps identical. Whitelisted (check off, not fixed): strip_bg, full_bg (resize tab column), pl_bg (vertical), video_bg (PP3). **2nd pass 2026-11-02:** fixed: widened +150 logical px at 100 / 125 / 150 / 200 %, full player + EQ + playlist and strip: no stray pixel column in any stretched background (scan for short non-panel runs: only labels / text); the whitelisted strip_bg / full_bg (tab column) show nothing either. `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp1-eq-header-wide-150-after.png` |
| PP2 | P1 | Full player at the minimum width: the mute speaker zone covers half of the Next button (below about 505 px) | Sonnet, medium | G-full | done (branch worktree-agent-a33a182194de58c28, merged into design-tuning): `MIN_W` 490 -> 510, quotes updated. Verified in real VLC 3.0.20: full player at 510 px at 100 % (drag of the tab to the minimum) and 150 % (built at 510): Next fully drawn, 6 px to the speaker; Next click plays song2; the zone at the speaker did not trigger Next (mute itself not visible, volume was 0 %); strip at 510 fine. Helper and Lua do not hard-code the minimum.. **2nd pass 2026-11-02:** fixed: real minimum 510 / 638 / 765 / 1020 px at 100 / 125 / 150 / 200 % (tab dragged): Next fully drawn, speaker 10 / 13 / 15 / 20 px to its right. `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp2-min-width-transport.png` |
| PP3 | P1 | Video window: a second set of grip dots appears on the left frame when the window is taller than its default | Sonnet, medium | G-video | done (branch worktree-agent-a7327e4a32f69d58b, merged into design-tuning): title bar is its own `hslice` (`video_title`, 36 px) over the frame 9-slice; dots centred (y 11, also in video-min). Real VLC (Xvfb :155): video-l and video-x at 100 % and 150 %, resized +200 x +400: left frame columns identical on every row below the title bar, dots only in the title bar. **2nd pass 2026-11-02:** fixed: video-l and video-x resized +200 x +400 logical at 100 / 125 / 150 / 200 %: left frame columns uniform below the title bar. `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp3-video-left-frame-150-after.png` |
| PP4 | P2 | STRIP button: icon + label group 5.5 px left of centre (7 px left pad, 16 px right) | Haiku, low | G-bmp | done (branch `worktree-agent-aabb88f8f98f5b19c`, merged into design-tuning): group centred, ink padding L/R 12/12, 15/14, 17/16, 24/23 at 100-200 %; no live VLC check. **2nd pass 2026-11-02:** fixed (live VLC, 4 scales): icon + label centred. `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp4-pp7-strip-button-grip-dots-after.png` |
| PP5 | P2 | Resize tab ribs unevenly spaced / split over two columns at 125 % (and other fractional scales) | Sonnet, medium | G-bmp | done (branch worktree-agent-a06b2e9846e168a01, merged into design-tuning): ribs drawn in device px (odd tab width, equal ribs / gaps / margins); 100 % staged bitmaps byte-identical to design-tuning; real VLC crops at 125 / 150 / 200 % (strip, full, EQ, playlist) measured: ribs equal brightness, gaps and margins symmetric; drag on the tab still resizes (150 %). Not checked: video window, taskbar 36 px strip. **2nd pass 2026-11-02:** fixed for strip / full / EQ / playlist tabs: margins / ribs / gaps 2-1-1-1-1-1-2 (100), 3-1-1-1-1-1-3 (125), 4-1-2-1-2-1-4 (150), 5-1-3-1-3-1-5 (200). The video window's corner tab is a separate problem: PP16. `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp5-tab-after.png` |
| PP6 | P2 | EQ faders alternate 56 / 58 px (150 %) and 47 / 48 px (125 %) apart | Sonnet, medium | G-pan | done (branch worktree-agent-a891d626f47ed710c, merged into design-tuning): `add_eq` computes `pitch = P(38)` once; the 10 band faders sit at `b0 + k * pitch` (span centred on the old rounded span, preamp unchanged); dB labels, band names, divider and 0 dB ticks use the same device x. Verified: slider-groove centre scan constant pitch 38 / 48 / 57 / 76 at 100 / 125 / 150 / 200 %; 100 % staged output byte-identical to the design-tuning build; real VLC at 150 %: all 11 faders respond to a click, 6x crop clean. Release `.vlt`, `preview.png`, `configurator/` not rebuilt. **2nd pass 2026-11-02:** fixed: groove-centre pitch 38 / 48 / 57 / 76 constant over all 10 bands; the 125 % block is centred as before (no clipping of 16K). `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp6-eq-pitch-after.png` |
| PP7 | P3 | Full player title-bar grip dots sit 1 px above the button row's centre | Haiku, low | G-full | not merged (branch `worktree-agent-a0236b38bfcaff27b`): the error was 0.5 px, not 1 px; the 11-row dot group cannot be centred on the 22-row button band with whole pixels (y 13 = 0.5 px low at 100 %, 0.5 px high at 150 %), so it stays as is: limit. **2nd pass 2026-11-02:** **re-judged: real, reopened (section 7).** Measured in VLC: dot rows 14..23 (10 rows, centre 18.5) vs button rows 9..30 (centre 19.5) = 1 px high at 100 / 125, 1.5 px at 150 / 200. The "11-row group" was a miscount: `grip_dots(c, 4, 13)` centres exactly at 100 / 125 / 150 and leaves 0.5 px at 200. `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp4-pp7-strip-button-grip-dots-after.png` **3rd pass: done (branch `worktree-agent-a2016cbce276a126d`, merged into design-tuning), see section 7.** |
| PP8 | P3 | Playlist: row stripes stop 16 px before the scroll track (6 px gutter elsewhere) | Opus, high (touches the Lua width rule) | G-pan | done (branch worktree-agent-a836868085151e0b2, merged into design-tuning): `add_pl` playtree width `PW - P(50)` (= 570 / 713 / 855 / 1140 px; `P(W - 50)` would be 712 at 125 %), `vlcamp.lua` `PL_MARGIN` 50, tree = `w - P(50)`. Real VLC 3.0.20 (Xvfb :163), Midnight, with the Lua extras: gap stripes -> track = left gutter at every scale (6 / 7 / 9 / 12 px at 100 / 125 / 150 / 200 %; at 125 % plus the track's anti-aliased column, as on its right side), 8x crops looked at; durations right-aligned at 77 / 75 / 74 / 77 columns (`columns=` +1 cut with "..." at each scale) and at 99 in a window widened to 777 px (100 cut). VlcDock.cs shares the window width only: unchanged. Docs: architecture.md, font-notes.md, BACKLOG item table. Not done: `configurator/` sync, release `.vlt`, Windows, taskbar 36 px build (same x geometry). **2nd pass 2026-11-02:** fixed: stripes end 6 / 7 / 9 / 12 px before the scroll track = the track's right gutter; durations right-aligned at all 4 scales (Lua 77 columns at 100 %). `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp8-pl-right-after.png` |
| PP9 | P3 | Title progress thumb hides the half-pixel row of the box outline at 125 / 150 %: a notch in the top / bottom edge right of the playhead | Opus, high | G-bmp | done (branch `worktree-agent-a2c4eb62aa541fb29`, merged into design-tuning): `make_title_thumb`'s right half copies a middle column of the unlit box (`lcd()`, h + 2 high, from `inset()`), still fully opaque (hit area unchanged). Verified in VLC 3.0.20 (Xvfb :156): strip + full title box at 150 / 125 %, playhead 0 / 50 / 93 %: top / bottom edge rows right of the playhead one colour each (before: 13 px notch at 150 %); 12x crops looked at; 100 / 200 % staged bitmaps and `.vlt` (24 + 36 px) byte-identical to `design-tuning`; only `atlas_t0` changes at 125 / 150 %; `bitmap-audit.py` (BH=24) 0. Not done: `configurator/` sync, release `.vlt`. **2nd pass 2026-11-02:** fixed: 125 / 150 % title box with the playhead at about 50 %: the half-bright outline row continues uniformly right of the playhead (row 66 at 125 %: 161 px `0f1718`; rows 79 / 118 at 150 %). `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp9-title-thumb-150-after.png` |
| PP10 | P2 | Video window: opening the extra row (`video-x`) throws away the user's window size (820 x 839 -> 620 x 439) | Sonnet, medium | G-video | done (branch worktree-agent-a075a4843c929c6d0, merged into design-tuning): `isTightlyCoupledWith` (3.0.x) compares original size AND min / max w / h; `video-l` and `video-x` now share `minh` (`VMINH = VT + PH + RH + 90`). Real VLC 3.0.20 (Xvfb :164, theme with `vlc.hasVout` -> `not vlc.isMute`), 100 % 620 x 441 resized to 778 x 568: arrow to `video-x` and back keeps 778 x 568; 150 % resized to 995 x 719: kept. Maximized size / `FitMaximizedVideo` not run (no Windows). Release `.vlt` not rebuilt. **2nd pass 2026-11-02:** fixed: 100 %: 820 x 841 kept from video-x to video-l; 150 %: 1230 x 1262 kept in video-x. `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp10-video-l-after-toggle-820x841.png` |
| PP11 | P3 | Video / fullscreen controls: transport row 10 px from the bottom edge (12 elsewhere); mute is a framed button in the video panel but a bare speaker in the full player and fullscreen controller | Sonnet, medium | G-video | done (branch worktree-agent-a075a4843c929c6d0, merged into design-tuning): (a) `PH` 68 -> 70: transport row 12 px above the bottom edge; `video-x` row 8 px under the transport row (as seek bar -> transport) and 12 px above the edge; (b) video panel uses the bare `c_mute_*` speaker (22 x 28 zone at `VW - 191`, as in the fullscreen controller), `ft_mute` bitmaps removed. Real VLC at 100 / 150 %, 8x crops: 12 px bottom margin in video-l and video-x, speaker matches the full player's. Fullscreen controller untouched (already `c_mute`, same x); `preview_layout` of it not rendered. Release `.vlt` not rebuilt. **2nd pass 2026-11-02:** fixed: bottom margin 12 / 15 / 18 / 24 device px (incl. outline) in video-l and video-x at 100 / 125 / 150 / 200 %; transport -> extra row 8 px; speaker = full player style. `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp11-video-panel-bottom-150-after.png` |
| PP12 | P3 | 16 px mute speaker: the two sound waves merge into one blurred oval at 100 % | Opus, high | G-bmp | done (branch `worktree-agent-a4a788f0f19302fbf`, merged into design-tuning): new `_speaker()` lays the speaker out in whole device px (waves 2+ px apart, inner wave radius 3 units, outer wave no taller than the cone; muted cross = exact 45-degree pixel steps, ends where the waves end); ink centred on the glyph box (offset 0 / 0.5 px parity). Verified: 16x crops of `c_mute_*` off / on x up / over / down and `ft_mute` at 100 / 125 / 150 / 200 %: two separate arcs, clean X; `icon-symmetry.py` 660 renders, 0 asymmetric; `speaker_off` also 0 up-down; only the 24 `c_mute_*` / `ft_mute_*` bitmaps differ (Midnight + Paper, 100 / 150 %, 24 / 36 px); real VLC 3.0.20 at 100 %: full player waves clean (muted state not shown in VLC: dummy audio). Release `.vlt`, `preview.png` and `configurator/` not rebuilt (sync needed at merge). **2nd pass 2026-11-02:** fixed: two separate arcs at 100 / 125 / 150 / 200 %, up-down mirror 0; ink centre offset 0.5 / 1.0 / 0 / 0 px (125 %: 1 px right of the zone centre, not logged). `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp12-speaker-after.png` |
| PP13 | P1 | Text: skins2 places some glyphs several px left of their cell ("00: 24", "Lights. wav", "Nor thbound", "- 02:30") | Opus, high | G-font | **done (branch `worktree-agent-aa3c539887a091043`, merged into design-tuning)**: cause confirmed (`ft2_font.cpp:270` draws at `pos[n]`, never `bitmap_left`); fix = shipped font `fonts/VLCAmpMono.ttf` (DejaVu, glyph boxes = cell, `tools/make-cell-font.py`), `vlcamp.lua` dot rule. Verified in VLC 3.0.20, 100 / 150 %: colon gaps 9/9, 2/3, 2/3 (30/10/12 px) and 13/13, 4/4, 5/6; "." in the 14 px title 3/3, 6/5; time position steady over 8 shots; durations right-aligned, 75 / 72 columns max (76 / 73 cut). Not run: 125 / 200 %, Windows. `configurator/build_skin.py` NOT synced (run `tools/sync-configurator.py` when merging). **2nd pass 2026-11-02:** fixed at all 4 scales: big time colon gaps 9/9, 11/11, 12/13, 17/18; "of 03:21" 2/2 .. 5/5; title dot gaps equal within 1 px; time steady. Side effect: PP17 (format chip shows a sliver of the 5th-last character at 125 %). `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp13-time-after.png`, `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp13-title-after.png` |
| PP14 | - | Limits seen again, not tasks: 1.25 / 1.5 px outlines (two-row lines at seams and button edges at 125 / 150 %), stair-stepped outer corners | - | - | limit |

Not logged (checked and fine): corner shapes of all 14 layouts at all 4 scales (mirror-identical); one 1 px line per
section junction; hover / pressed bitmaps cover exactly the control rect (pixel diff at 100 %); icons of the transport, header
and strip buttons mirror-symmetric and centred (ink box centre offset 0); time and title text vertically centred within
0.5 px at every scale; EQ band block centred at 620 and 777 px; playlist footer labels centred; no semi-transparent
bitmap pixels (`tools/bitmap-audit.py` with `BH=24`: 0).

### PP1 - EQ header: stray grip-dot column when widened (Haiku, low) - P1
- **Where:** EQ section header, every layout, every scale, window wider than its 620 px default: x = 610, y = EQ top + 14..19
  at 100 % (x = 915 at 150 %). Midnight and Paper.
- **Problem:** `add_eq` cuts `eq_bg` with `hslice(..., 10, 10)` (left cap 10 logical px), but `grip_dots(c, 4, 12, 2)`
  draws its right dot column at x = 9..11, so one column of each dot lies in the middle piece, which skins2 tiles
  (`resize="mosaic"`); the next tile starts at x = 10 + (W - 20) and shows the half dots as a ":" left of the flip button.
  Breaks "a slice middle must be plain". Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/eq-header-stray-dots-100-wide.png`,
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/eq-header-stray-dots-150-wide.png` (screens `m100_wide_full_pleq.png`, `m150_wide_full_pleq.png`).
- **Fix hint:** give `eq_bg` the same left cap as the other sections (14, as `strip_bg` / `full_bg`), or better add a check
  in `hslice` / `nslice` that the middle piece is one colour per row (column-uniform) and raise `SystemExit` otherwise,
  so the rule cannot break again (PP3 is the same rule vertically).
- **Verify:** build 100 / 150 %, `tools/vlc-test.sh start`, open EQ, `drag` the resize tab +150 px, crop the EQ header at
  8x: plain panel colour between the label and the flip button. Byte-compare `stage-*`: only the `eq_bg*` slices change.

### PP2 - Full player at minimum width: mute covers Next (Sonnet, medium) - P1
- **Where:** full player transport row, window width 490 .. about 505 px (any scale), y 195..222 (100 %).
- **Problem:** the mute zone sits at `F(282)` (W - 282, 22 px wide) and Next ends at x = 221; at W = 490 the mute zone starts at
  208 and is drawn over the right half of Next (the Next button is cut, the speaker sits on its face). `MIN_W` (490) was
  chosen for the strip only. Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/full-min-width-next-mute-overlap-100.png` (screen
  `m100_min_full_pleq.png`).
- **Fix hint:** either raise `MIN_W` so that W - 282 >= 222 + 6 (W >= 510; then update the places that quote 490: README,
  `docs/architecture.md`, BACKLOG-hifi.md, section 0 above; the helper reads the shape, not the number), or keep 490 and
  give the full player a narrower volume group below a threshold (not possible per width in skins2: one layout, so it would
  mean a shorter fixed volume groove, `vol100` 100 -> 80 px, for every width). Decide with Jiri; the first is the small change.
- **Verify:** `drag` the full player's tab to the minimum, crop the transport row at 6x at 100 and 150 %: Next fully drawn, at
  least 6 px between Next and the speaker; click Next and mute at that width.

### PP3 - Video window: repeated grip dots on the left frame (Sonnet, medium) - P1
- **Where:** video window (`video-l`, `video-x`), any size taller than the default (also maximized), left frame at
  y = 14 + n * (VH - 28) logical px; seen at 100 %, 820 x 839 window: second dots at y = 440.
- **Problem:** `video_layout` cuts the whole background with `nslice(..., VB + 2)` (14 px caps), but `grip_dots(c, 4, 12)` in the
  title bar spans y = 14..23, i.e. the top of the middle-left piece, which skins2 tiles vertically; every repeat shows the dots
  again. Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/video-window-repeated-grip-100.png` (screens `v100_video.png`, `v100_video_big.png`).
- **Fix hint:** draw the title bar (dots included) as its own non-stretching piece (an `hslice` 36 px high at the top, like the
  main window's bars) and keep the 9-slice for the frame only; or move the dots into the 14 px corner (they do not fit
  centred in a 36 px bar). Same rule check as PP1.
- **Verify:** load a copy of the stage `theme.xml` with `vlc.hasVout` replaced by `not vlc.isMute` (how this audit did it), drag
  the corner tab +200 x +400, crop the left frame: dots only in the title bar. Check `video-x` and 150 %.

### PP4 - STRIP button content off-centre (Haiku, low) - P2
- **Where:** full player title bar, STRIP button (x 16..83, y 9..30 at 100 %), all states, all scales, all themes.
- **Problem:** `make_strip_button` places the icon at x = 7 and the text at x = 23 with a fixed offset; the ink group spans 23..66
  (logical 7..50 inside the 68 px button): 7 px left, 16 px right, centre 5.5 px left of the button centre. Every other labelled
  button centres its group (`make_toggle` with `use_led`). Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/strip-button-label-off-centre-100.png`.
- **Fix hint:** measure the label with `_truetype(FONT_BOLD, P(9)).getlength("STRIP") / S` and centre icon (10) + gap (6) + text as
  one group, as `make_toggle` does for LED + text.
- **Verify:** `ink.py`-style check (or crop at 10x): left and right padding equal within 1 px at 100 / 125 / 150 / 200 %;
  only `b_strip_*` bitmaps change.
- **Status: done (branch worktree-agent-aabb88f8f98f5b19c, merged into design-tuning).** `make_strip_button` centres icon (10) + gap (6) + text
  as one group; the text's ink is measured by rendering it (`getlength` counts side bearings and left the group 2 px off at 200 %).
  Ink left / right padding of `t0_b_strip_*` (atlas crop, ring excluded), before -> after: 100 %: 7 / 17 -> 12 / 12;
  125 %: 9 / 20 -> 15 / 14; 150 %: 11 / 21 -> 17 / 16; 200 %: 15 / 31 -> 24 / 23 (all within 1 px). Staged output
  of Midnight-only builds at 100 / 125 / 150 / 200 %: only `atlas_t*.png` pixels inside the `b_strip_*` rects differ, `theme.xml` identical.
  10x crop checked. Not run in a live VLC session.

### PP5 - Resize tab ribs at fractional scales (Sonnet, medium) - P2
- **Where:** the resize tab of strip, full player, EQ, playlist and video window at 125 % (and 150 %): e.g. full player x 761..772.
- **Problem:** `resize_handle` draws three 1 px ribs at x + 2 / 4 / 6 logical; at 125 % that is 2.5 / 5 / 7.5 device px, so one rib
  is crisp, one is split over two half-bright columns and the gaps are 3 and 2 px; the tab edges get anti-aliased columns too.
  At 100 % the ribs are crisp and even. Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/resize-tab-ribs-uneven-125.png` (row y = 100 of
  `m125_full_dn_pleq.png`: 52, 57, 78, **139**, 57, **119, 98**, 78, **139**, 57).
- **Fix hint:** draw the tab in device pixels: width `P(9)`, ribs 1 device px wide at evenly spaced device columns centred in the
  tab (same idea as the crisp icons, H22). `grip_tab` crops the same pixels, so the hit zone follows.
- **Verify:** crops at 125 / 150 / 200 %: three ribs of equal brightness, equal gaps, symmetric margins; 100 % byte-identical.

### PP6 - EQ fader spacing alternates at 125 / 150 % (Sonnet, medium) - P2
- **Where:** EQ band block, 125 % and 150 %, every layout and theme.
- **Problem:** fader positions are `P(cx - 15)` with cx = 48 + 38 i; 38 x 1.5 = 57 rounds alternately, giving spacings
  58, 56, 58, 56, ... (150 %) and 47, 48, 47, ... (125 %), measured on the groove centres; dB labels and band names follow.
  Siblings must be evenly spaced. Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/eq-fader-spacing-alternates-150.png`.
- **Fix hint:** compute the device-pixel pitch once (`pitch = round(38 * S)`) and place fader i at `x0 + i * pitch` in `add_eq`
  and in the `eq_bands` drawing (labels and 0 dB ticks), keeping the block centred.
- **Verify:** groove-centre scan (row through the fills) gives one constant pitch at every scale; clicks on each fader still hit
  (`tools/vlc-test.sh click`); 100 % byte-identical.

### PP7 - Full player grip dots 1 px high (Haiku, low) - P3
- **Where:** full player title bar, left grip (x 5..10), all scales.
- **Problem:** `grip_dots(c, 4, 12)` puts the dots at rows 14..23 (centre 18.5); the STRIP / header buttons are rows 9..30
  (centre 19.5). In the strip and the panel headers the dots are centred. Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/full-grip-dots-1px-high-100.png`.
- **Fix hint:** `grip_dots(c, 4, 13)` in `add_full` (and the same check for `video_layout`'s title bar, which centres on 18).
- **Verify:** dot rows 15..24 at 100 %; crop at 10x.

### PP8 - Playlist stripes vs scroll track gap (Opus, high; decision) - P3
- **Where:** playlist list box, every scale: stripes x 18..577, scroll track x 594..601 at 100 %.
- **Problem:** the left gutter is 6 px (`PL_GUTTER`), the scroll track sits 6 px from the right edge, but the rows end 16 px before
  the track, so the list looks pushed left. Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/playlist-stripe-scroll-gap-100.png`.
- **Fix hint:** Playtree width `P(W - 60)` -> `P(W - 50)` (6 px gap to the track). **The Lua duration padding depends on this width**
  (`lua/intf/vlcamp.lua` `pl_columns`, rule measured in VLC, 76 / 74 / 73 / 77 columns, docs/architecture.md "Playlist durations"):
  the rule must be re-measured and the docs updated, so it needs Jiri's OK first.
- **Verify:** stripes end 6 px before the track at every scale; durations right-aligned again at 100 / 125 / 150 / 200 % (harness +
  Lua, as item 8).

### PP9 - Title thumb notch at fractional scales (Opus, high) - P3
- **Where:** strip title box and full player title box, 125 / 150 %, on the 15 px (150 %) right of the playhead.
- **Problem:** the box outline is 1.5 device px (one full row + one half-bright row). Fills start `inset()` = 1 px in and cover the
  half row (by design), but the thumb's right half (box colour) covers it too, so the outline is two rows thick everywhere except a
  1-row notch 15 px long right of the playhead. Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/title-thumb-outline-notch-150.png`.
- **Fix hint:** make the thumb's right half one row shorter at top and bottom when `P(1) != int(S)` (so the half-bright outline row
  stays visible), or give the thumb transparent top / bottom rows (transparent pixels are not drawn by skins2 but still take
  clicks: check the hit area stays). Visual judgement needed against the fill side.
- **Verify:** 150 % crop at 12x: top and bottom edges of the box uniform across the playhead at 0 / 50 / 93 %; 100 / 200 % unchanged.

### PP10 - Video extra row resets the window size (Sonnet, medium) - P2
- **Where:** video window, arrow button (`fb_more` / `fb_less`), any scale.
- **Problem:** resized to 820 x 839, a click on the arrow showed `video-x` at 620 x 439 (screens `v100_video_big.png` ->
  `v100_video_x.png`). skins2 carries the size only between tightly coupled layouts (same original size **and** min / max limits,
  `GenericLayout::isTightlyCoupledWith`); `video-l` has `minh = VT + PH + 90`, `video-x` `VT + PH + RH + 90`. The docs say the
  size is carried. Evidence: the two screenshots in `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/shots/`.
- **Fix hint:** give both layouts the same `minh` (the larger one) in `build()`; check the source of
  `isTightlyCoupledWith` (3.0.x `modules/gui/skins2/src/generic_layout.cpp`) first.
- **Verify:** resize the video window, toggle the row both ways: size kept; maximized size kept (helper `FitMaximizedVideo`).

### PP11 - Video / fullscreen panel consistency (Sonnet, medium; decision) - P3
- **Where:** video control panel and fullscreen controller, all scales.
- **Problem:** (a) the transport row ends 10 px above the window's bottom edge (`ty = pb + 30`, 28 px buttons, `PH` = 68), the
  sides keep 12 (margin rule); in `video-x` the row and the extra row are only 4 px apart. (b) The mute control is a framed
  30 x 28 button (`ft_mute`) in the video panel but the bare speaker (`c_mute`) in the full player and the fullscreen
  controller. Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/video-panel-bottom-margin-100.png`, `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/mute-style-video-vs-fsc-100.png`.
- **Fix hint:** (a) `PH` 70 or the seek bar 2 px higher so the margins are 12; (b) pick one mute style (Jiri) and use it in all
  three places.
- **Verify:** video window crops (forced visible as in PP3) and `preview_layout` for the controller.

### PP12 - 16 px mute speaker waves merge (Opus, high) - P3
- **Where:** full player mute (`c_mute_*`), 100 % (and 125 %), all themes; commit 4e61517 made it 16 px.
- **Problem:** the two arcs of the `speaker` glyph are about 1 device px apart at 16 px, so at 100 % they render as one blurred
  oval with dark holes, unlike the clean 12 / 13 px icons; the ink is 14 x 10 and 1 px right of the zone centre. Evidence:
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/mute-speaker-16px-waves-100.png`.
- **Fix hint:** in `_icon` (`name == "speaker"` / `speaker_off`), space the arcs by whole device pixels at small sizes (or draw one
  arc below 18 px), and centre the ink, not the 16 px box.
- **Verify:** 16x crops at 100 / 125 / 150 %: two separate arcs; `tools/icon-symmetry.py` still 0 up-down.

### PP13 - Glyphs placed left of their cell by skins2 (Opus, high) - P1
- **Where:** every `<Text>` and the Playtree (all fonts lcd10 / 12 / 14 / 30), all scales, all themes: big time "00: 24", "of
  03: 21", strip time "01: 51", countdown "- 02:30", "Lights. wav", ". wav" chip, playlist "Nor thbound. wav".
- **Problem:** measured on the 30 px time at 100 %: digits keep their 18 px pitch, but the colon's ink starts 10 px left of
  where FreeType / Pillow put it (3 px after the "0", 14 px before the "2"; Pillow: 9 / 9), and the digits after it move 2 px left.
  Narrow glyphs with a large left bearing (`:`, `.`, `r`, `-`) leave a hole after them. Pillow-rendered labels (bitmaps) are
  fine. `docs/font-notes.md` says the gap is the monospace cell; the measurement says it is the glyph position. Likely cause:
  skins2 `ft2_font.cpp` draws each glyph bitmap at the pen position without `bitmap_left` (and hints the advance). Evidence:
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/skins2-glyph-bearing-time-100.png`, `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit1/evidence/skins2-glyph-bearing-playlist-100.png`.
- **Fix hint:** first confirm in the 3.0.x source (`modules/gui/skins2/src/ft2_font.cpp`, `drawString`). If the bearing is dropped,
  a font-side workaround is possible: ship a modified DejaVu Sans Mono (renamed, as its licence requires for modified versions)
  in which every glyph has a zero-area point at x = 0 (FreeType's control box then starts at the cell edge, so the bitmap carries
  the bearing). Needs fontTools (not installed in the venv). If that fails it becomes a limit + an upstream draft
  (`docs/upstream-issues/`), and `docs/font-notes.md` must be corrected either way.
- **Verify:** real VLC: colon centred between digits (gaps equal within 1 px) at 10 / 12 / 14 / 30 px and at 100 / 150 %; digits still
  tabular (time does not jitter); playlist durations still right-aligned.
- **Done 2026-11-02** (see `docs/font-notes.md` "Glyph placement" for source lines, method and measurements): the bearing is
  dropped (`drawString` line 270 uses `top`, never `left`). `source/fonts/VLCAmpMono.ttf` = DejaVu Sans Mono where each glyph is a
  composite of the unchanged original plus zero-area points at x = 0 and x = advance (hinting untouched; ink and advances identical
  to DejaVu at 8-64 px in FreeType 2.13.2). Generator: `FONT_CELL` / `FONT_FILE` / the copy in `main` only; Pillow keeps
  `DejaVuSansMono.ttf` (bitmaps byte-identical). `vlcamp.lua` `pl_columns`: dot = `ceil(px x 1233 / 2048)` (one column fewer:
  75 / 73 / 72 / 76). Configurator stages the new font (Pyodide build checked: theme.xml and font identical to the CLI build).
  The configurator's other fonts and own TTFs still have the bug (unmodified files).

### PP14 - Limits (not tasks)
- 1.25 / 1.5 px outlines at 125 / 150 %: every 1 px line is one full row plus an anti-aliased row (seams `3e434a` + `2a303a`),
  button outlines look heavier on two sides (BACKLOG-hifi.md "Known limits"). Snapping all lines to whole device pixels would change
  every bitmap at fractional scales; not proposed.
- Outer window corners are stair-stepped (binary window shape, H18).

## 7. Pixel-perfect audit 2026-11-02, second pass

Second `/pixel-perfect` pass on `design-tuning` at 0721270 (after the PP1-PP6, PP8-PP13 merges; release `.vlt` files
byte-identical to a fresh build of `source/build_skin.py` at all 4 scales). Real VLC 3.0.20 + Xvfb (`tools/vlc-test.sh`,
instances `ppaudit2` on :171 and `ppaudit2v` on :172, root painted magenta), Lua extras loaded
(`--extraintf luaintf --lua-intf vlcamp`, `--aout afile`). Each PP row above got a "2nd pass" verdict. Nothing was fixed.

**Rendered for real:** Midnight (release builds) at 100 / 125 / 150 / 200 %: all 14 layout x panel combinations, corners
mirror-compared (identical everywhere, also Paper / Sage / 36 / 40 px strip); widened by +150 logical px and dragged to the
minimum width (510 / 638 / 765 / 1020 px), stretched backgrounds scanned for stray columns; hover + pressed of every full player,
EQ, playlist and strip control at 125 / 150 / 200 % (diff of each state inside the control rect; the VLC menu button left out:
its press opens the Qt popup); video window (theme copy with `vlc.hasVout` -> `not vlc.isMute`) video-l, video-x, resized
+200 x +400, video-min at all 4 scales; Paper 125 / 200 %, Sage 100 / 150 %; 40 px strip and taskbar 36 px at 100 / 150 %;
volume fill (strip time box and full player) at 100 %.
**Approximated / not checked:** fullscreen controller (needs a real full-screen video), muted icon (dummy / afile audio cannot
mute), Windows rendering, the other 7 themes and Custom, hover states of the video window and the 40 / 36 px strips,
hover / pressed at 100 % (first pass), the menu button's pressed look.

Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/` (screens `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/shots/`: `m<pct>_<layout>` Midnight, `p` Paper, `g` Sage,
`b` 40 px strip, `t` taskbar, `w` widened / minimum, `v` video; states `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/states/`;
scripts `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/tools/`: `stray.py` stray-column scan, `ctrldiff.py` state rect diff, `sc.py` same region at 4 scales,
`runs.py` / `rowrun.py` / `textbox.py` measurements). Note for reusing the first pass's `states.sh`: its centre formula
was wrong at scales other than 100 % (`p "$x + $w/2"` multiplied only `$w/2`), fixed in the audit2 copy.

**Checked and fine (not logged):** no stray pixels in any stretched background (incl. the whitelisted `strip_bg` / `full_bg`;
`pl_bg`'s vertical middle is never tiled: the playlist height is fixed); hover / pressed bitmaps change only the face inside the
outline, same rect for every control at 125 / 150 / 200 %; EQ / playlist header grip dots centred on their buttons (0 / 0.5 px);
video title bar dots, title and buttons share centre row 17.5; video-min margins 12 and centred; big time centred in the card
within 1 px; volume fill crisp in the strip time box and the full player.

**Limits seen (not tasks):** playlist durations end about 3 cells before the stripe end (skins2's "..." reserve, PP8 / vlcamp.lua
rule); on Linux the durations keep the start width's column count when the window is resized (live width only through the
Windows helper); the strip's 18 px boxes sit 1 px low in the 24 px bar at 150 % (36 - 27 px leaves an odd row).

**Serialization** (same rule as section 6): G-pan PP15, PP19, PP22 (`add_pl`, `make_eq_frames`, `add_eq`); G-full PP7, PP17
(`add_full`); G-strip PP20 (`add_strip`); G-video PP16, PP21 (`video_layout`, `extra_row`); G-bmp PP18 (`make_thumb`,
`make_eq_thumb`). Every task ends with `tools/sync-configurator.py`; rebuild release `.vlt` / `preview.png` once after the merges.

| ID | P | Task | Model | Group | Status |
|----|---|------|-------|-------|--------|
| PP7 | P3 | (reopened, see the row above) full player grip dots 1 - 1.5 px above the button row's centre | Haiku, low | G-full | done (branch `worktree-agent-a2016cbce276a126d`, merged into design-tuning): `grip_dots(c, 4, 13)` in `add_full`; verified in VLC 3.0.20 at 100 / 125 / 150 / 200 %: dot rows 15..24 / 18..31 / 22..37 / 30..49 (centre 19.5 / 24.5 / 29.5 / 39.5) vs button band centre 19.5 / 24.5 / 30 / 39.5 (was 1 / 1 / 1.5 / 2 px high); 10x before/after crops in the scratchpad `fix2/pp7-dots-*.png` |
| PP15 | P2 | Playlist: the last row stripe is cut to a sliver at the bottom of the list box at 125 / 150 / 200 % | Sonnet, medium | G-pan | done (branch worktree-agent-a98bcef7be5427fb2, merged into design-tuning): playtree height = whole rows (pitch ceil(1.2*P(12)) = 15/18/22/29, floor rows in P(194)); checked in real VLC at 100/125/150/200 %, Midnight + Paper, top and scrolled: last row whole, no sliver, scroll thumb reaches the end; duration column not seen (width unchanged) |
| PP16 | P2 | Video window: the corner resize tab covers the bottom outline and the rounded bottom-right corner | Sonnet, medium | G-video | done (branch worktree-agent-a3bca826b8f533ced, merged into design-tuning): tab is now 9 x 9 logical px at x VW-13..VW-4, y VH-13..VH-4 (3 px to the right and bottom outline), inside the `br` piece (cap 14; a taller tab at VH-14 trips the generator's tiled-middle seam check at 150 %). Real VLC (Xvfb :185): 12x crops at 100 / 125 / 150 / 200 %: bottom outline and the rounded corner arc intact, tab clear of both; dragging the tab resized the window at all four scales (height +80 x scale; width clipped by the 1280 px screen). Window size unchanged, helpers untouched. Release `.vlt` not rebuilt. |
| PP17 | P2 | Format chip (".wav"): a 1 px sliver of the previous character at the left edge at 125 %; text right of the chip centre at 150 / 200 % | Sonnet, medium | G-full | done (branch `worktree-agent-a2016cbce276a126d`, merged into design-tuning): text box = exactly 4 device cells (`4 * round(P(10) * 0.6021)`) centred on the chip; verified in VLC 3.0.20 at 100 / 125 / 150 / 200 % with .wav, .flac, .mp3 after a wide letter ("Glass Elevator"): no sliver, ink within 1 px of the chip centre (12x crops `fix2/pp17-chip-*.png`) |
| PP18 | P2 | Light themes: slider knobs (EQ, seek, volume) have a light outline that vanishes on the light box / groove | Sonnet, medium | G-bmp | done (branch worktree-agent-a16427824160c7542, merged into design-tuning): `thumb_rim(b)` in `make_thumb` / `make_eq_thumb`: light themes get `mix(b, black, 0.6)` rim (contrast 5.9-7.5 vs box on Paper/Sand/Sage/Rose, 100 and 150 %, 12x crops checked); dark themes unchanged (Midnight 100/150 .vlt byte-identical to design-tuning); 0 semi-transparent pixels |
| PP19 | P3 | EQ fader fill 3 px with half-pixel edges at 100 / 150 % (soft columns), groove anti-aliased at 125 % | Sonnet, medium | G-pan | done (branch worktree-agent-a59a049c1f5a63ecb, merged into design-tuning): `make_eq_frames` draws groove and fill on whole device px, both centred on x = P(15); fill = P(3) widened to the groove's parity (4 / 4 / 5 / 6 px over groove 2 / 2 / 3 / 4 at 100 / 125 / 150 / 200 %), fill top on a whole row. Verified in real VLC: rows through groove and fill show only the 2 colours at 4 scales, same centre; 12x crops `pp19-after-*.png` in scratchpad fix2. Release `.vlt` not rebuilt. |
| PP20 | P3 | Strip time text 1.5 px right of the time box centre at 150 % | Haiku, low | G-strip | done (branch worktree-agent-aca4b81e4cad46b8e, merged into design-tuning): `add_strip` text width `P(TW) - 2 * P(TIME_ZONE) + 1`. Real VLC, ink centre minus box centre: 150 % 1.5 -> +0.5 px, 200 % 0.0, 125 % 0.0, 100 % 0.0 (100 / 125 % skin byte-identical to before; 150 / 200 % only the time text width in theme.xml changes; no bitmap changed). Not tested: hour format (dummy audio does not play the long file, so `1:0x:xx` not seen); the 36 / 40 px strips not measured; `configurator/` not synced |
| PP21 | P3 | Video extra row: SNAP 48 px among 44 px siblings, group gaps 10 / 12 / 5 px | Sonnet, medium (decision) | G-video | done (branch worktree-agent-a3bca826b8f533ced, merged into design-tuning): all four buttons 44 px (`xb_snap` bitmap 48 -> 44), both group gaps 12, speed box 4 px from slower / faster, 4 px inside groups, row's left edge kept (right end 518 -> 516). Real VLC 3.0.20 (Xvfb :185, `hasVout` -> `not isMute`), video-x at 100 / 150 %: run-length scan along the row: widths 44 x 4, 52 x 3, 30 / 60 / 30 (x1.5 at 150 %), gaps 4 4 4 12 4 4 12 4 4 (6 / 18 at 150 %); labels (A-B, CH-, CH+, SNAP) fit. Release `.vlt` not rebuilt. |
| PP22 | P3 | EQ band block: ink 3 logical px left of the box centre (dB scale on the left, nothing on the right) | Haiku, low (decision) | G-pan | done (branch worktree-agent-a59a049c1f5a63ecb, merged into design-tuning): decision = centre the ink. `add_eq` measures the ink extent of the `eq_bands` bitmap and places the panel so it is centred in the band box in device px (a fixed +3 logical px was 1 - 2 px off at 125 / 150 %). Verified in real VLC (ink pad L / R): 100 % 81 / 80, 125 % 100 / 100, 150 % 121 / 121, 200 % 160 / 161, 777 px wide at 100 % 159 / 159; all 11 faders at 150 % respond to a click (values -13). Click zones are in the panel and move with it. Release `.vlt` not rebuilt. |

### PP7 (reopened) - Full player grip dots 1 px high (Haiku, low) - P3
- **Where:** full player title bar, left grip (x 4..11 logical), every layout / theme / scale.
- **Problem:** measured in VLC: dots rows 14..23 at 100 % (centre 18.5), STRIP / header buttons rows 9..30 (centre 19.5): 1 px high;
  125 %: 17..30 vs 11..38 (1 px); 150 %: 21..36 vs 14..46 (1.5 px); 200 %: 28..48 vs 18..61 (1.5 px). Strip, EQ and playlist headers
  are centred. Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp4-pp7-strip-button-grip-dots-after.png`.
- **Fix hint:** `grip_dots(c, 4, 13)` in `add_full` (the dots move 1 logical px down: 0 / 0 / 0 / 0.5 px error). The earlier
  "cannot be centred" verdict counted 11 rows; the group is 10.
- **Verify:** `runs.py` rows of the dot column vs the STRIP button column at 4 scales; only `full_bg*` slices change.

### PP15 - Playlist: last stripe cut at the bottom (Sonnet, medium) - P2
- **Where:** playlist list box, all layouts / themes, 125 / 150 / 200 %: last visible row y 777..784 (125 %, 8 of 18 px),
  937..941 (150 %, 5 of 22 px), 1245..1255 (200 %, 11 of 29 px), then the 6 / 8 / 10 px gap to the box edge. At 100 % the cut row
  is an unstriped one (invisible).
- **Problem:** the Playtree is `P(194)` high, not a whole number of rows (row pitch 15 / 18 / 22 / 29 px: 12.9 / 13.5 / 13.2 /
  13.4 rows), so skins2 draws a partial stripe: a thin bar that looks like a stray line, clearly visible in Paper. Breaks "content
  ends cleanly in its box". Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp15-pl-last-stripe-cut-paper-125.png`,
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp15-pl-last-stripe-cut-midnight-150.png`.
- **Fix hint:** in `add_pl`, height of the playtree = `rows * pitch` with pitch = the skins2 line height of `lcd12` at this scale
  (measure: 15 / 18 / 22 / 29) and rows = the most that fit in `P(194)`; keep the top at `P(38)` (the leftover goes to the bottom
  gap) or centre it in the box. The scroll bar points may follow the new height. Check that the Lua width rule (`PL_MARGIN`) is
  untouched (width only).
- **Verify:** `colscan.py` at x = P(30) through the list box at 4 scales: last stripe full height, then plain box colour to the edge;
  Paper 125 % crop; scroll bar still reaches the last row with 30+ items.

### PP16 - Video window: corner tab over the bottom outline and corner (Sonnet, medium) - P2
- **Where:** video window (video-l, video-x), bottom-right corner, every scale and theme: tab x VW-11..VW-3, y VH-13..VH-1 (logical).
- **Problem:** `video_layout` draws `resize_handle(c, grip_x(VW), VH - 13, 12)`: the 12 px tab ends on the window's last row, so it
  replaces the 1 px bottom outline under it and fills the rounded corner (radius 6) with tab colour: the outline stops 11 px before
  the corner and the corner arc becomes a stepped block of tab colour. Every other tab keeps 2 - 3 px to the edges (margin rule,
  corners rule). Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp16-video-corner-tab-all-scales.png` (100 / 125 / 150 / 200 %),
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/video-corner-tab-100.png` (12x).
- **Fix hint:** move the tab up into the right frame so it ends above the corner arc (e.g. `y = VH - 12 - h` with h 12 - 18,
  same x as now) or make it a small square tab inside the 12 x 12 corner (`grip_dev` sizes, 2 - 3 px gap to the bottom and right
  edges, ribs in device px as PP5). It must stay inside the `br` corner piece of the 9-slice (cap `VB + 2` = 14) or the
  `mr` piece would tile it (PP3 rule); the `br` piece keeps `resizeSE`.
- **Verify:** video window forced visible (theme copy, see section 6 PP3), 12x crops of the corner at 4 scales: bottom outline and
  corner arc identical to the bottom-left corner mirrored (`corners.py` on the video crop); drag on the tab still resizes.

### PP17 - Format chip: sliver of the previous character (Sonnet, medium) - P2
- **Where:** full player display, format chip (`chip_fmt` x 358, text `$F` at x 367, w 24 logical), 125 % (sliver), 150 / 200 %
  (offset); any file whose name has a character before the extension (".wav" of "Glass Elevator.wav": a 1 px tick of the "r").
- **Problem:** the text box is `P(24)` = 30 px at 125 %, but 4 cells of `lcd10` are 4 x 7 = 28 px; right-aligned, the box shows 2 px
  of the 5th-last cell, where the "r" arm now sits (since PP13 glyphs are drawn at their real position; before, the bearing bug moved
  the ink out of view). At 150 / 200 % the 4 cells are 1 - 2 px right of the chip centre (ink pad 17.5 / 15.5 px at 200 %).
  Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp17-fmt-chip-sliver-all-scales.png`, `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/fmt-chip-sliver-125.png` (12x).
- **Fix hint:** in `add_full`, text width = exactly 4 device cells (`4 * round(P(10) * 0.6021)`, the advance rule `vlcamp.lua`
  uses) and x = chip x + (chip width - that width) // 2, so the box holds whole cells only and is centred; check the kbps / kHz
  chips with the same rule (centred text, no clipping there).
- **Verify:** files with 3- and 4-letter extensions after a wide letter (".wav" after "r", ".flac", ".mp3"): no sliver, ink
  centred within 1 px at 4 scales; other bitmaps unchanged (only `theme.xml` changes).

### PP18 - Light themes: knob edge invisible (Sonnet, medium) - P2
- **Where:** EQ faders, seek bar, volume slider (full player, video, fullscreen controller) knobs, light themes (Paper, Sage; also
  Sand, Rose), all scales.
- **Problem:** `make_thumb` / `make_eq_thumb` outline the knob with `mix(b, "#ffffff", 0.5)` in every theme: on the light LCD /
  groove the white top half and light rim merge with the background, the knob reads as a floating grey bar. Breaks "light themes use
  dark outlines" (`box_edge`). Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp18-light-knob-edge-paper-125.png`,
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp18-light-knob-edge-sage-100.png`.
- **Fix hint:** pick the rim from the mode: dark themes keep the light rim; light themes use a dark rim (`box_edge(0.13)`-like
  value or `EDGE`); keep the face gradient. Recheck contrast with `tools/theme-audit.py`.
- **Verify:** Paper / Sage 100 / 150 %, 8x crops of an EQ knob at 0 dB and the seek / volume knob: edge visible on all four sides;
  dark-theme knobs byte-identical.

### PP19 - EQ fill half-pixel edges (Sonnet, medium) - P3
- **Where:** EQ band and preamp fills, 100 % and 150 % (soft fill edges), 125 % (soft groove), all themes.
- **Problem:** `make_eq_frames` draws the fill at x 13.5 w 3 and the groove at x 14 w 2: at 100 % the fill is 2 bright columns plus
  one half-bright column each side (`33717c` | `5fd3e8` x 2 | `33717c`), at 150 % 1 + 3 + 1, while at 125 / 200 % it is crisp
  (4 / 6 px); the groove is crisp at 100 % but 1 + 2 + 1 at 125 %. Breaks the crisp-icon / device-pixel rule (H22, PP5).
  Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp19-eq-fill-halfpx-100.png`.
- **Fix hint:** draw fill and groove in device px centred on the fader's device centre (as `resize_handle` / `grip_dev` do): fill
  width `P(3)` rounded to the groove's parity so both share one centre column pair.
- **Verify:** `rowrun.py` through a fill and through the groove at 4 scales: only full-colour columns, fill and groove centred on the
  same x; knob position and click zones unchanged.

### PP20 - Strip time text off centre at 150 % (Haiku, low) - P3
- **Where:** strip time box (elapsed / countdown text), 150 % (1.5 px), 125 % (0.5 px); all bar heights.
- **Problem:** the text box is `tx + P(TIME_ZONE)` wide `P(TW - TIME_ZONE)`: it starts 1 logical px inside the box but ends at the
  box edge, so its centre is 0.5 logical px right of the box centre; at 150 % ink pad 25 / 22 px. Evidence:
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp20-strip-time-offcentre-150.png`.
- **Fix hint:** `add_strip`: width `P(TW) - 2 * P(TIME_ZONE)` (symmetric inset), same x.
- **Verify:** `textbox.py` on the box interior: L / R pad equal within 1 px at 4 scales and in the 36 / 40 px strips.

### PP21 - Video extra row spacing (Sonnet, medium; decision) - P3
- **Where:** video-x extra row, all scales: x 22..528 at 100 % (window-relative 12..518).
- **Problem:** A-B, CH-, CH+ are 44 px wide, SNAP 48; gaps 4, 4, 4 | 10 | 4, 4 | 12 | 5, 5 (button groups separated by 10 and
  12 px, the speed box by 5 instead of 4). Siblings should share width and the group gap should repeat. Evidence:
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp21-video-extra-row-spacing-100.png`.
- **Fix hint:** `extra_row`: SNAP 44 px (or all four 48), one group gap (10 or 12) for both breaks, 4 px around the speed box
  (`x_speed_bg` x 424 -> 422 or width + 2); decide with Jiri whether the row should also end at the volume group's right edge.
- **Verify:** `runs.py` along the row at 100 / 150 %: equal widths, gaps 4 inside groups and one value between groups.

### PP22 - EQ band block off centre (Haiku, low; decision) - P3
- **Where:** EQ band box, every scale / theme / width: ink 90..523 in the box 12..607 at 100 % (pad 78 / 84), 200 % 156 / 168.
- **Problem:** the fixed-width band block (`EQ_BW` 446) is centred, but its ink is not: the dB scale labels ("+20", "0", "-20")
  stick out on the left and nothing on the right, so the bands look 3 logical px left of centre. Evidence:
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit2/evidence/pp22-eq-block-offcentre-200.png`.
- **Fix hint:** `add_eq`: panel x `P((W - EQ_BW) // 2 + 3)` (centre the ink, not the box), or a matching element on the right;
  decide with Jiri (optical centring vs the box).
- **Verify:** ink pads equal within 1 px at 4 scales and at 777 px width; click zones move with the panel.

## 8. Design requests from Jiri, 2026-11-02 (after the two audits)

Screenshots from Jiri (probably their Windows install of `main`, not this branch; scale unknown, likely 125 %):
`/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/user-progress-bottom.png` (title box with the progress fill, "Glass Elevator.wav"),
`/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/user-wav-chip.png` (format chip "·.wav" with a stray tick before the dot).

| ID | P | Task | Model | Group | Status |
|----|---|------|-------|-------|--------|
| PP23 | P1 | Remove the Stop button everywhere (strip, full player, fullscreen controller; not the video window's close): "it doesn't make sense". Re-space the remaining transport buttons by the design rules; update MIN_W comment / docs | Sonnet, medium | G-full + G-strip | done (branch worktree-agent-a392538058ebf4bbb, merged into design-tuning): Stop existed only in the full player (strip, video panel and fullscreen controller never had one); `fb_stop` bitmap and the `stop` icon removed, transport now prev 12 / slower 46 / play 80 / faster 124 / next 158 (4 px gaps, same as the video panel); mute / volume stay right-anchored, `MIN_W` kept 510 (strip title limit; Next now 40 px clear of the mute); README and MIN_W comment updated; the video windows' close (`vlc.stop()`) kept. Verified in real VLC 3.0.20 at 100 / 125 / 150 / 200 %, normal and 510 px width: run-length scan gaps 4,4,4,4 / 5,4,5,5 / 6,6,6,6 / 10,9,9,10 px, 8x crops looked at, all 5 transport buttons click (screen changes), strip at 510 clean. Not checked: Windows; `docs/img-thin/*.png` (README screenshots) still show the old Stop button **3rd pass 2026-11-03:** fixed: no Stop anywhere (full player, strip, video panel, fullscreen controller preview); run-length scan of the transport row, Midnight: gaps 4,4,4,4 / 5,4,5,5 / 6,6,6,6 / 8,8,8,8 px at 100 / 125 / 150 / 200 % (the 200 % "10,9,9,10" above counted the anti-aliased outline); the 4 px gap between slower and play at 125 % is a rounding step, logged as PP35 (P3); 510 px minimum: Next clear of the speaker. `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp23-transport-4scales.png` |
| PP24 | P1 | Remove the orange LED dot from all toggle buttons (PL, EQ, ON, SHUF, LOOP, REP1, ...): "it doesn't make sense". Active state stays visible by the button's other on-look (frame / text colour); label centred alone | Sonnet, medium | G-bmp (`make_toggle`) | done (branch worktree-agent-abb2d875ef8ce90a6, merged into design-tuning): LED removed from `make_toggle` and `make_chip_toggle` (SHUF / LOOP / REP1 chips), `led()` deleted, `use_led` argument and its 5 caller uses dropped. Labels centred by measured ink (`_ink_x`), not advance box. On-look unchanged (accent frame + accent text; chips: accent frame, tint, brighter text), clearly different from off in 10x crops. Verified in VLC at 100 / 125 / 150 / 200 % (Midnight; light single theme at 150 %): all states, label dx within 1 device px; bitmap-audit BH=24: 0 semi-transparent. Not captured: ON and playlist-panel toggles (same factory), real Paper theme **3rd pass 2026-11-03:** fixed: no LED left (full player PL / EQ, strip PL / EQ / pin, EQ ON, playlist footer, SHUF / LOOP / REP1 chips, video extra row); labels ink-centred within 1 device px at 4 scales (Midnight, on and off); hover / pressed change only the face inside the outline (Paper 100 %, all controls). **But on light themes "on" reads weaker than "off"** (Paper: accent text 3.7:1 on the face vs 9.0:1 for the off label, pale ring): PP30; the light chips' pressed face turns dark grey: PP31. `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp24-p-100-pleq-off-on.png`, `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp24-p-100-footer-off-on.png` |
| PP25 | P1 | Playlist must show a song length column. Today: `vlcamp.lua` pads titles with " (m:ss)" right-aligned (item 8; real columns need T10). Check it works on this branch (PP8 / PP13 changed width and font), why Jiri may not see it (Windows install, Lua extras, `lua-config`), show it in `preview_layout`, and make it look like a column | Opus, high | G-pan + Lua | done (branch worktree-agent-ae5b2bad6d0af1b6a, merged into design-tuning): **on this branch it worked** (PP8 / PP13 / PP15: no regression; real VLC 3.0.20, Xvfb :193, instance pp25, Lua extras, 100 / 125 / 150 / 200 %: every length ends at the same x within 1 px, 24 / 32 / 35 / 56 px before the playtree end = skins2's "..." reserve). **Likely why Jiri saw none** (docs/architecture.md "Why the column may not show"): the playing item is kept plain, so a playlist of one opened file shows no length; a renamed skin file (`VLC-Amp-125 (1).vlt`, browser re-download) made the script assume 100 % and every length was cut to `4:..` (reproduced in VLC, fixed); the Lua extras come only with Setup (not with a bare `.vlt` / configurator download) and are skipped when vlcrc names another `lua-intf`. Windows install read: Install.cmd -> install.ps1 (robocopy incl. `lua/`) -> `vlc-taskbar.ps1 -Setup` copies vlcamp.lua, adds `luaintf` to extraintf, `lua-intf=vlcamp`, no lua-config (default = right-aligned); durations come from the core's auto-preparse (default on, local files, `src/playlist/item.c:735`), the same on Windows; Lua cannot force a preparse. **Changed:** `vlcamp.lua` scale from the last `-NNN` in the file name (`skin_scale`); lengths in one right-aligned field as wide as the widest length (min 5), title column cut with "…" at the same column in every row; `vlc-taskbar.ps1 -Setup` says in its Done message when the Lua extras were skipped (CRLF / ASCII kept; `tools/check-windows-helper.sh`: compiles, 0 parse errors); `preview_layout` playlist drawn as skins2 + Lua do (row pitch, stripes, text 7 px in, bottom-aligned, lengths by the Lua rule, playing row plain): per-row ink boxes identical to real VLC at 100 / 150 %; README (durations bullet, Limits line that said "no duration column"), architecture.md, lua-api-notes.md. Playing item: kept plain on purpose (title meta is shown live by the web interface / MPRIS / SMTC; skins2's `$N` reads it once per track; Next race won 6/6). **Verified** in VLC: short, 95-char, hour-long, unknown (missing file), UTF-8 titles, the playing item, Next x6, saved 777 px window (99 columns), renamed `.vlt` old vs new Lua; release `.vlt` byte-identical (preview only). **Not verified:** Windows run (helper width file, SMTC flyout), live resize on Linux (still the saved width), configurator not synced (`tools/sync-configurator.py`), release preview.png not rebuilt. **New finding (skins2 bug, not fixable here):** a folder or `.m3u` given at start expands into a list that draws no rows until scrolled / resized (`ctrl_tree.cpp` `m_firstPos`). Crops: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/fix3/pp25-*.png` **3rd pass 2026-11-03:** fixed: real VLC with the Lua extras, 26 items (short, 95-char, hour-long, missing file, UTF-8): one right-aligned column at 100 / 125 / 150 / 200 % (Midnight, Paper) and Sand / Sage / Rose / Ember at 100 %; `1:03:00` right-aligned with `m:ss`, missing file plain, scrolling fine; after quit at 770 px and restart: 98 columns, the column follows the right edge. Found: on Linux a live narrowing cuts every length to "..." (PP36); Lua cuts titles with "…" while skins2 cuts the plain playing row with "..." (PP37). The playing row (plain on purpose) runs past the column end: limit. `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp25-m-lengths-4scales.png`, `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp25-wide-770-restart-100.png` |
| PP26 | P1 | Title box progress fill: the bottom edge looks wrong (fill does not meet the bottom outline the way it meets the top; see the PP9 2nd-pass note "fill covers the top half-bright row but not the bottom one at 150 %"). Make the fill sit symmetrically in the box at every scale, strip and full player | Opus, high | G-bmp (title fill frames) | done (branch `worktree-agent-ad36d9e9ab6fb20bb`, merged into design-tuning): cause: fills were `P(h)` high at `inset()` inside a `P(h + 2)` box, one row short when `P(h + 2) - P(h) = 3`: full-player title at 125 % (box 35 rows, fill 32: Jiri's screenshot, the `0f1718` quarter-bright row under the fill) and at 150 % (42 / 39), strip title and strip time-box volume fill at 150 % (27 / 24). New `inner(v)` = `P(v + 2) - 2 * inset()` for `make_title_frames`, `make_title_thumb` (fill side, playhead and the PP9 unlit half), the `title_slider` path and `make_progress_frames` (strip volume fill, same root cause). Seek bar / full-player volume (`make_fill_frames`) not affected: groove and fill are one bitmap, all frames mirror-equal at 4 scales. Verified in VLC 3.0.20 (Xvfb :194, instance pp26), Midnight + Paper, 100 / 125 / 150 / 200 %, playhead ~30 % and ~90 %, volume ~45 %: strip title, full title and time box, columns lit / at the playhead / thumb's right half / unlit: top and bottom row scans mirror-equal in all 48 cases (before: 16 asymmetric, 125 full and all of 150); 12x crops looked at (`scratchpad/fix3/pp26-*.png`, `pp26-compare-*.png`). 100 / 200 % staged output byte-identical (24 and 36 px), `bitmap-audit.py` 0 (BH 24 / 36). Not done: 36 px strip in VLC, `configurator/` sync, release `.vlt` **3rd pass 2026-11-03:** fixed: strip and full-player title fill at about 30 % and 90 %, 4 scales, Midnight + Paper: top and bottom edge rows mirror-equal in every column of the box (16 / 16 boxes, `fillsym.py`); strip time-box volume fill vertically symmetric at 4 scales; 36 / 40 px strips at 100 / 150 % look the same. numeric scan (`/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/tools/fillsym.py`) of `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/shots/m150_full30.png` and the other `[mp]<pct>_{strip,full}{30,90}.png` |
| PP27 | P1 | Format chip still shows a tick before ".wav" in Jiri's screenshot (PP17 fixed it on Linux at 4 scales; check Windows-like rendering and longer / shorter extensions). Make it robust: nothing of the preceding character can ever show (e.g. an opaque cover piece over the chip's left padding drawn above the text, or another way) | Sonnet, medium | G-full (`add_full`) done (branch worktree-agent-a392538058ebf4bbb, merged into design-tuning): text box now reaches one cell left of the 4 extension cells and an opaque piece of the chip (new bitmap `chip_fmt_pad`, cropped from `chip_fmt`, the chip's left padding) is drawn above the text (skins2 draws same-layer controls in file order, checked in `generic_layout.cpp` 3.0.x), so anything the renderer puts left of the first cell is covered whatever the FreeType version. Verified in real VLC 3.0.20 at 100 / 125 / 150 / 200 % with "Glass Elevator" .wav / .mp3 / .flac / .opus / .m4a: 12x crops looked at, ink starts at the first cell edge or later, same pixels as before the change; stress build with the text moved 4 px left: cover hides it, no tick. Not checked: real Windows FreeType rendering (the cover only helps if the stray ink is left of the first cell; a renderer with a smaller advance than `0.6021 em` would still shift the 4 cells) **3rd pass 2026-11-03:** fixed: 9 files (.wav, .mp3, .flac, .opus, .m4a, .WAV, .ogg, "Mmmm.a.wav", no extension) after a wide letter, 4 scales: no tick or sliver anywhere. A file without an extension shows its last 4 letters ("sion"): PP39 (P3, decision). `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp27-chip-9files-4scales.png` |
| PP28 | P2 | Video window extra row: right-align the speed control with the volume group's right edge (Jiri; PP21 kept the row left) | Sonnet, medium | G-video (`extra_row`) | done (branch worktree-agent-a7a007f9c87b74e35, merged into design-tuning): `extra_row` speed group (slower / box / faster, 128 px) anchored rightbottom at x = VW - 140 .. VW - 12, the same right edge as the volume group's % text box (VW - 12); A-B / CH / SNAP / shuffle groups unchanged. Real VLC 3.0.20 (Xvfb :195, `hasVout` -> `not isMute`), video-x: column scan, faster button's last pixel at 100 % x = 607 (edge 608 = VW - 12) and after +200 px wider x = 807 (808); at 150 % x = 911 (912) and after +150 px wider x = 1061 (1062); the volume row's box edge moves with it; slower / faster clicks change the speed box (1x, 1.5x, 2x). Note: the visible % text ends 12 px (logical) left of the box edge ("100%" ends at 595). Release `.vlt` not rebuilt. **3rd pass 2026-11-03:** fixed: video-x (real VLC) and fullscreen controller row (preview): faster button ends at VW - 12 = the volume group's box edge. Side effect: in video-x the faster button's bottom-right corner now touches the window's corner resize tab: PP34. `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp34-videox-tab-touches-faster-100.png` |
| PP29 | P2 | skins2: after a folder or `.m3u` given at start expands, the Playtree draws no rows until it is scrolled (found while doing PP25). Check the 3.0.x Playtree refresh on item-appended / expand events; workaround from Lua or the skin (e.g. a forced refresh) if possible, else a limit + upstream draft | Opus, high | G-pan + Lua | open |

## 9. Pixel-perfect audit 2026-11-03, final pass

Third `/pixel-perfect` pass on `design-tuning` at e68615f (after the PP23 - PP28 merges; release `.vlt` files byte-identical to a
fresh build at all 4 scales, also `VLC-Amp-taskbar-100.vlt`). Real VLC 3.0.20 + Xvfb (`tools/vlc-test.sh`, instance `ppaudit3`,
display :201, root painted green), Lua extras loaded (`--extraintf luaintf --lua-intf vlcamp`, `--aout afile`), 26-item playlist
(short, 95-char, hour-long, missing file, UTF-8 titles). Each PP23 - PP28 row above got a "3rd pass" verdict. Nothing was fixed.

**Rendered for real:** Midnight (release) and Paper at 100 / 125 / 150 / 200 %: strip with the title fill at about 30 / 90 %, full
player at 30 / 90 %, full + PL + EQ, toggles off / on (PL, EQ, ON, SHUF / LOOP / REP1 chips and footer toggles); hover + pressed of
every full-player, EQ, playlist and strip control with the toggles off and on (Paper 100 %); Sand, Sage, Rose, Ember at 100 % and
Sage at 150 % (same views); format chip with 9 file names at 4 scales; widened +150 px and dragged to the minimum (100 / 150 %),
quit at 770 px and restarted (saved width); 36 and 40 px strips at 100 / 150 %; video window (theme copy with `vlc.hasVout` ->
`not vlc.isMute`) video-l / video-x / resized / video-min at 100 %, hover + pressed of every video-l and video-x control at 150 %.
**Approximated:** fullscreen controller (with and without the extra row) and video-min at 4 scales through the generator's
`preview_layout`; muted look not seen (afile audio). **Not checked:** Windows rendering, Custom, Forest / Nord / Dusk / Carbon,
hover / pressed at 125 / 200 % (factory unchanged except the LED removal; 150 % done for the video window), the menu button's pressed
look, live resize of the length column on Windows (helper width file).

Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/` (screens `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/shots/`: `m<pct>` Midnight, `p` Paper,
`sand100` / `sage100` / `rose100` / `ember100`, `w<pct>` widened / minimum, `vmid-<pct>` video, `pv_*` previews; states
`/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/states/`; scripts `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/tools/`: `pass.sh` (fills, toggles),
`statesrun.sh`, `vstates.sh`, `chips.sh`, `fillsym.py` (top / bottom mirror of a box), `pv.py` (preview of the fullscreen
controller / video layouts), `btnruns.py`, `tink.py`).

**Regression spot checks of PP1 - PP22 (all still fixed):** PP1 / PP5 stretched backgrounds and tab ribs at +150 px (stray scan: only
labels); PP2 Next clear at 510 / 765 px; PP3 / PP16 video left frame and corner tab (100 %, +200 x +400); PP4 / PP7 STRIP button and grip
dots (125 / 150 / 200 %); PP6 / PP19 EQ fill widths 4 / 4 / 5 / 6 px, pitch 38 / 48 / 57 / 76 constant; PP8 / PP15 stripes end before
the track, last row whole at 125 / 150 / 200 %; PP9 / PP26 title box edge rows uniform right of the playhead at 125 / 150 %; PP10 820 x 841
kept video-x -> video-l; PP12 two speaker arcs; PP13 / PP20 strip time ink pad L / R 18/18, 22/22, 26/26, 36/36 (and 20/21, 29/29 in the
36 / 40 px strips); PP17 / PP27 chip; PP18 knob rims on Paper / Sand / Sage / Rose; PP21 / PP28 extra row; PP22 EQ ink centre offset
+1.0 / 0 / +0.5 / 0 px. Window corners mirror-identical at 4 scales (strip, full, full + panels, Paper 150 %, minimum width).

**Limits seen again (not tasks):** length column ends about 3 cells before the stripe end (skins2's "..." reserve); the plain playing
row runs past the column; the strip's 18 px boxes 1 px low in the 24 px bar at 150 %; 1.25 / 1.5 px outlines (PP14); a volume fill at
125 % leaves the box's quarter-bright right outline column unfilled at 100 % volume (same PP14 rounding).

**Serialization:** G-bmp PP30, PP31 (`make_toggle`, `ring_colour`, `make_chip_toggle`); G-video PP32, PP33, PP34 (`video_layout`,
`extra_row`, the fullscreen controller block, `resize_handle` call of the video frame); G-full PP35 (`add_full` transport; the
video panel uses the same x values, so do PP35 after PP32 or in the same branch); G-strip PP38 (`add_strip`); Lua PP36, PP37
(`lua/intf/vlcamp.lua`; PP36 first, PP37 is a one-liner in the same file); PP39 decision only. Every generator task ends with
`tools/sync-configurator.py`; rebuild release `.vlt` / `preview.png` once after the merges.

| ID | P | Task | Model | Group | Status |
|----|---|------|-------|-------|--------|
| PP30 | P2 | Light themes: a toggle's "on" look (accent text + pale accent ring) is weaker than its "off" look (dark label), so on reads like disabled | Sonnet, medium | G-bmp | open |
| PP31 | P2 | Light themes: SHUF / LOOP / REP1 chips turn a dark grey block with dark text while pressed | Haiku, low | G-bmp | open |
| PP32 | P2 | Volume group spacing differs: speaker -> groove ink gap 6 px (full player), 19 px (video panel), 3 px (fullscreen controller); fullscreen controller rhythm 12 / 10 / 10 px vs 12 / 8 / 12 in the video panel | Sonnet, medium | G-video | done (branch worktree-agent-a3eeb0756dde075ba, unmerged): video panel and fullscreen controller volume group follows the full player's rule (speaker zone, 4 px, 100 px groove, 8 px, % text; more / less button VW - 213, speaker VW - 182, groove VW - 156); fullscreen controller same x, transport y 30 (preview rows 12 / 8 / 12 px, FSH 70). Real VLC (Xvfb :212, `hasVout` -> `not isMute`): run-length scans speaker -> groove / groove -> text 7 / 8, 9 / 10, 12 / 13, 16 / 17 px identical in full player, video-l and video-x at 100 / 125 / 150 / 200 %; fullscreen controller via `preview_layout` (100 / 150 %). `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/fix4/pp32-*.png` |
| PP33 | P2 | Video panel and fullscreen controller show the time in hour format ("0:00:14 / 0:02:56") while the strip and full player show "01:32" | Haiku, low | G-video | done (branch worktree-agent-a3eeb0756dde075ba, unmerged): `$t / $d` in video_layout and the fullscreen controller. Real VLC: "00:10 / 03:34" (short file), "1:00:16 / 1:02:05" fits (long.wav, 100 %). `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/fix4/pp33-*.png` |
| PP34 | P2 | video-x: the corner resize tab touches the faster button's bottom-right corner (side effect of PP28) | Sonnet, medium (decision) | G-video | done (branch worktree-agent-a3eeb0756dde075ba, unmerged): `corner_handle` 7 x 7 at VW - 11 / VH - 11 (video-l and video-x), 1 px clear of the Faster button; `br` cap / seam checks pass at 100 / 125 / 150 / 200 % builds. Real VLC 12x crops at 4 scales: tab clear of button and outline; dragging the tab at 150 % resized 930 x 662 -> 1050 x 752. `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/fix4/pp34-*.png` |
| PP35 | P3 | Full player transport gaps 5 / 4 / 5 / 5 px at 125 % (rounded logical positions) | Haiku, low | G-full | done (branch worktree-agent-a3eeb0756dde075ba, unmerged): `row_x` places the transport in device px (x0 = P(12), next = prev + P(w) + P(4)) in add_full, video_layout and the fullscreen controller. Real VLC run-length scans: gaps 4 / 5 / 6 / 8 px, all equal, in full player and video-l at 100 / 125 / 150 / 200 % (125 % was 5, 4, 5, 5). `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/fix4/pp35-*.png` |
| PP36 | P2 | Linux: narrowing the window live cuts every playlist length to "..." (the Lua keeps the start width's column count) | Opus, high (decision) | Lua | done (branch worktree-agent-a93949b36f829d011, unmerged): option (a): `pl_columns` without a width (Linux) pads for `PL_MIN_W` = 510 x scale (documented with `MIN_W` of build_skin.py, change both); Windows path (width file, else saved width) unchanged. Verified in real VLC 3.0.20, Lua extras, Xvfb :213, instance pp36, 100 / 150 %: 61 / 59 columns; start 620 / 930, narrowed to 510 / 765, widened +150: lengths never "...", column further left. Crops `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/fix4/pp36-*.png` |
| PP37 | P3 | Playlist: Lua cuts long titles with "…" (one glyph), skins2 cuts the plain playing row with "..." | Haiku, low | Lua | done (branch worktree-agent-a93949b36f829d011, unmerged): Lua cuts with "..." (title cut to room - 3 + "..."), same style as skins2; DejaVu has the dot. Verified in VLC 100 / 150 %: cut rows and the plain playing row both end "...", lengths stay in one column. Crops `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/fix4/pp37-*.png` |
| PP38 | P3 | Strip time / title text 1 px below the box centre at 150 % (ink pad top 7 / bottom 5) | Haiku, low | G-strip | done (branch worktree-agent-a162246a3e949a7b5, unmerged): time box at 150 % pads T 5 / B 5 (was 6 / 4 in the same measure, 7 / 5 in the audit's); 125 % T 3 / B 4 (whole pixels, was the same bytes); 200 % T 7 / B 7; 100 % and 200 % (and 125 %) `.vlt` byte-identical to design-tuning. Fix: `add_strip` text y in device px from the box's device centre |
| PP39 | P3 | Format chip shows the last 4 letters of a name without extension ("No extension" -> "sion") | Haiku, low (decision) | G-full | **limit** (investigated 2026-11-03, branch worktree-agent-af9627ba016c54cb2, unmerged; no code changed): no clean workaround. Evidence (VLC 3.0.x, read from the source; not rendered, nothing changed): `utils/var_text.cpp` `VarText::get` (about lines 110-121) expands only `$N` `$F` `$B` etc. by plain string replace, `$F` = `getStreamURIVar()`, set in `vlcproc.cpp` `update_current_input` (about line 713) from `vlc_uri2path` or `input_item_GetURI`: no extension variable, no substring / conditional. The only booleans a `visible=` can test (`vlcproc.cpp` ctor, about lines 89-119): `playlist/playtree.isRandom/isLoop/isRepeat`, `vlc.isPlaying/isStopped/isPaused/isSeekable/canRecord/isRecording/isFullscreen/hasVout/hasAudio/isMute`, `dvd.isActive`, `equalizer.isEnabled`: none depends on the name, and Lua could only flip them by changing real playback state. Lua (`vlc.*`) has `item:set_meta` but no URI setter, and `$F` is the URI, not a meta; the skin cannot read a meta into the chip (`$N` is the title format, computed once per input). Normal .wav / .mp3 / .flac / .opus / .m4a unchanged. Documented in docs/vlc-feature-requests.md |
### PP30 - Light themes: "on" weaker than "off" (Sonnet, medium) - P2
- **Where:** every `make_toggle` label toggle (full player PL / EQ, strip PL / EQ, EQ ON, playlist SHUF / LOOP / REP1, video row
  SHUF / LOOP / REP1, A-B), light themes; worst on Paper (all scales), then Sand / Sage / Rose. Dark themes fine (Carbon borderline).
- **Problem:** since PP24 the only on-cue is accent text + `ring_colour(CYAN)` (accent mixed 45 % into BG_BOT). On a light face the
  accent label has 3.7:1 (Paper; Sand / Sage / Rose about 5:1) against 9.0:1 for the off label, and the ring (2.2:1) is barely darker
  than the grey off outline, so the lit button looks paler / greyed out next to its off siblings: breaks "active state stays visible
  and reads as active". Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp24-p-100-pleq-off-on.png`,
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp24-p-100-footer-off-on.png`, `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp30-paper-toggle-states-100.png` (up / over / down, on).
- **Fix hint:** `make_toggle` (and `ring_colour` for light mode): on light themes use the full accent for the ring (no mix with
  BG_BOT) and a darker label (`CYAN_TXT`-like, mix(accent, black, 0.25), >= 4.5:1), optionally a faint accent tint of the face
  (`mix(face, CYAN, 0.10)`, as the chips do); dark themes unchanged (byte-identical). Check with `tools/theme-audit.py`.
- **Verify:** Paper / Sand / Sage / Rose at 100 / 150 %: off / on pairs side by side, on clearly stronger; on-label contrast >= 4.5:1;
  Midnight `.vlt` byte-identical; `bitmap-audit.py` 0.

### PP31 - Light chips pressed: dark grey block (Haiku, low) - P2
- **Where:** SHUF / LOOP / REP1 chips in the full player display, pressed (off and on), light themes, all scales.
- **Problem:** `make_chip_toggle` darkens the pressed face with `mix(face, black, 0.35)` in every theme: on the light LCD that is a
  mid-grey (Paper about #8f9aa3) with dark accent text on it (low contrast), unlike every other pressed look on light themes (slightly
  darker face). Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp31-paper-chip-pressed-100.png` (top row: off up / over / down; bottom: on).
- **Fix hint:** light mode: `mix(face, black, 0.08)` or `mix(face, CYAN, 0.25)`; keep 0.35 for dark themes.
- **Verify:** Paper / Sage 100 / 150 %: pressed chip close to its hover look in lightness, text >= 4.5:1; dark themes byte-identical.

### PP32 - Volume group spacing: full player vs video panel vs fullscreen controller (Sonnet, medium) - P2
- **Where:** transport rows, all scales / themes: full player (speaker zone F(282), groove F(256), % F(148)); video-l / video-x panel
  (speaker VW - 191, groove VW - 152, % VW - 48); fullscreen controller (speaker W - 191, groove W - 168, no %; leave-full-screen W - 42).
- **Problem:** the same speaker + groove group has three spacings: speaker ink -> groove 6 px (full), 19 px (video panel), 3 px (fsc);
  groove -> % text 8 px (full) vs 4 px (video). PP11 replaced the video panel's framed mute with the bare speaker but left the groove where
  the old button needed it. Also the fullscreen controller keeps the old vertical rhythm: seek bar 12 px from the top, 10 px seek ->
  transport, 10 px bottom margin (FSH 70, transport y 32), while PP11 set the video panel to 12 / 8 / 12. Evidence:
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp32-volume-group-fsc-vs-video-100.png` (top: fullscreen controller preview, bottom: video panel),
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/fsc-m100-x2.png`.
- **Fix hint:** one rule for the group (as the full player: zone, 4 px, 100 px groove, 8 px, % text): video panel groove at VW - 165
  (% at VW - 57 or keep the group right-anchored at VW - 12 and move the speaker / more button right); fsc the same, with the
  leave-full-screen button 12 px from the edge as now; fsc transport y 30 and FSH 70 (12 / 8 / 12), the extra row offset with it.
- **Verify:** `btnruns.py` along the three rows at 100 / 150 %: identical speaker -> groove and groove -> text gaps; fsc preview rows 12 /
  8 / 12 px; clicks on mute / groove still work in the video window (theme copy, real VLC).

### PP33 - Video / fullscreen time in hour format (Haiku, low) - P2
- **Where:** video-l / video-x panel time text and fullscreen controller time text (`" / "`, lcd14), all scales / themes.
- **Problem:** real VLC shows "0:00:14 / 0:02:56" (skins2's $T / $D always print hours) while the strip and the full player show
  "01:32" / "of 04:12" ($t / $d); the generator's sample text "1:02 / 4:12" (preview) does not match the real look. Evidence:
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp33-video-time-hours-100.png`.
- **Fix hint:** `video_layout` and the fullscreen controller block: `"$t / $d"` (the seek bar tooltips may keep $T / $D). Check the
  text box still fits "1:03:00 / 1:03:00" (hour-long file) at P(150) / P(170).
- **Verify:** real VLC video window with `long.wav` and a short file: "00:14 / 02:56" and "1:00:14 / 1:03:00" fully visible at 100 /
  150 %; preview unchanged.

### PP34 - video-x: corner tab touches the faster button (Sonnet, medium; decision) - P2
- **Where:** video-x (and a resized video-x), bottom-right corner, all scales: faster button x VW - 42 .. VW - 12, bottom VH - 12; resize
  tab x VW - 13 .. VW - 4, y VH - 13 .. VH - 4.
- **Problem:** since PP28 the extra row's last button ends at the 12 px margin, and the corner tab (PP16, 3 px from the outline) starts
  1 px left of / above that margin: the tab's top-left corner meets the button's bottom-right corner, no gap (looks like one shape).
  Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp34-videox-tab-touches-faster-100.png` (8x).
- **Fix hint:** decide with Jiri: (a) a smaller tab (7 x 7 at VW - 11 / VH - 11, inside the 12 px margin, 1 px gap), (b) the row's
  right edge at VW - 16 only in video-x, or (c) no tab in video-x (the frame edges still resize). (a) keeps every other layout; recheck
  the `br` cap (PP16 note: the generator's middle-seam check at 150 %).
- **Verify:** video-x at 100 / 125 / 150 / 200 %, 12x crop: at least 1 px of panel between tab and button; tab drag still resizes.

### PP35 - Transport gaps at 125 % (Haiku, low) - P3
- **Where:** full player transport (prev 12, slower 46, play 80, faster 124, next 158 logical), 125 %; video-l panel uses the same x.
- **Problem:** positions are `P(x)` of logical values: at 125 % P(46) = 58 (57.5 rounds to even) and the slower -> play gap is 4 px
  while the others are 5 (run-length scan 15-52, 58-95, 100-149, 155-192, 198-235). Breaks "siblings evenly spaced". Evidence:
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp23-transport-4scales.png` (second row).
- **Fix hint:** in `add_full` (and `video_layout`), place the buttons in device px: x0 = P(12), next = previous + P(width) + P(4).
- **Verify:** `btnruns.py` at 4 scales: equal gaps; the row's right end changes by at most 1 px; only `theme.xml` changes.

### PP36 - Linux: narrowing cuts every length to "..." (Opus, high; decision) - P2
- **Where:** playlist, Linux (no helper width file), any scale, window made narrower than the width VLC saved at its last exit.
- **Problem:** the Lua pads titles to the start width's column count; when the window is narrowed live, skins2 cuts every padded row
  at the playtree end and all lengths become "..." (510 px after starting at 620: 7 / 7 rows). Widening only leaves the column short of
  the right edge (2nd-pass limit), but narrowing loses the column completely. Evidence:
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp36-linux-narrowed-lengths-cut-100.png`.
- **Fix hint:** decide: (a) on Linux (no width file) pad to the minimum width's column count (`MIN_W` 510 at the skin's scale):
  never cut, column sits further left when wider; (b) a Linux width source (python-xlib helper like `vlc-amp-pin.py` writing the
  same width file); (c) document. (a) is a few lines in `pl_columns` / `pl_follow_width`.
- **Verify:** real VLC 100 / 150 %: start at 620, narrow to the minimum and widen +150: lengths never "..."; Windows path unchanged.

### PP37 - Two ellipsis styles in the playlist (Haiku, low) - P3
- **Where:** playlist rows with a title longer than the column (Lua cut, "…") vs the plain playing row cut by skins2 ("..."), all scales.
- **Problem:** the same list ends cut titles in two different ways ("row…" next to "any p..."). Evidence:
  `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp37-ellipsis-lua-vs-skins2-100.png`, `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/overall-full-pleq-lengths-100.png`.
- **Fix hint:** `vlcamp.lua` title cut: "..." (3 cells) instead of "…" (adjust the cut length by 2 cells).
- **Verify:** long titles end in "..." everywhere, lengths still in one column at 100 / 150 %.

### PP38 - Strip text 1 px low at 150 % (Haiku, low) - P3 - **DONE** (branch worktree-agent-a162246a3e949a7b5, unmerged)
- **Where:** strip time box and title box text (`ty = round(BH / 2 - 0.582 * font)`), 150 %, 24 px bar.
- **Problem:** digits' ink rows 12..24 in the box interior 5..29: pad top 7, bottom 5 (1 px low; 100 / 125 / 200 % within 0.5 px; 36 / 40
  px strips: 14 / 13 and 17 / 16). The box itself is the 1 px-low limit in the bar; the text should follow the box, not the bar.
  Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp38-strip-time-1px-low-150.png`.
- **Fix hint:** `add_strip`: text y in device px from the box's device centre (P(BY) + P(BT) / 2 - line height / 2).
- **Verify:** `tink.py` on the time box at 4 scales and 36 / 40 px: top / bottom pad equal within 1 px (0.5 px ideal).
- **Done:** `ty` is now `round(P(BY) + P(BT) / 2 - 0.582 * P(font))` in device px (passed without a second `P()`). Verified in real VLC
  3.0.20 (Xvfb :214, instance pp38): time box ink pads at 150 % T 5 / B 5 (baseline build: 6 / 4 by the same script; the audit's 7 / 5
  was measured with a different interior), 200 % T 7 / B 7, 125 % T 3 / B 4 (18-row interior, 11-row ink: 0.5 px is the best whole
  pixels allow). 100 %, 125 % and 200 % `.vlt` are byte-identical to design-tuning; only 150 % changes. Title text moves with the
  time text (same `ty`), crops checked 10x. 36 / 40 px strips not re-measured; the formula gives the same y at 100 % there. Not rebuilt:
  release `.vlt`, `preview.png`, `configurator/build_skin.py` (sync not run).

### PP39 - Format chip without an extension (Haiku, low; decision) - P3
- **Where:** full player format chip, a file name with no "." in it (or a URL), all scales.
- **Problem:** `$F` right-aligned shows the last 4 characters of the name ("sion" of "4 No extension"), which reads as a format.
  Evidence: `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp39-chip-no-extension-100.png`, `/tmp/claude-1000/-home-jirif-dev-vlc/faf994bb-5ca0-4a91-9498-6937152c4065/scratchpad/audit3/evidence/pp27-chip-9files-4scales.png`.
- **Fix hint:** skins2 has no extension variable; options: leave as a limit, or let `vlcamp.lua` expose the format some other way
  (not possible without changing $F); likely: document as a limit.
- **Verify:** decision recorded; nothing to render.
- **Result 2026-11-03:** limit, see the row in the table above (no clean workaround; source lines there).
