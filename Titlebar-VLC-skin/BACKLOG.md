# Titlebar skin: backlog

Last updated 2026-10-31 (T19-T20 added; items 26-31 and T21-T23 from the Windows test; 32-33 and T25 from the second test). Status key:

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

## 1. Items

| # | Item | Status | Approach / workaround | Effort |
|---|------|--------|-----------------------|--------|
| 7 | PL / EQ attached to the bar, same width | **DONE** | Panels are now part of the main window's layouts (4 layouts: strip / full x panels below / above; PL and EQ are shown inside them). | done |
| 7a | Taskbar mode with panels open | **DONE, confirmed by the user on Windows 2026-10-31** | Panels open above or below the bar, chosen with the arrow on the panel header (one skin file, no separate taskbar build). The helper reads the window region (`GetWindowRgn`) to see whether the bar is at the top or bottom and whether the strip or full player is showing. Rule checked against real VLC window shapes at 100 % and 150 %; compiled with Mono (C# 5). Placement itself still needs a run on Windows. | done |
| 7b / 13 | Same width with playlist open / closed | **DONE** | All 4 layouts (strip / full x panels below / above) have the same size, so VLC carries the dragged width between them (verified in `setActiveLayout`). Unused space is transparent and click-through (window region). PL / EQ are shown / hidden inside the layout via invisible 1x1 "flag" windows whose visibility VLC saves. Tested in VLC: drag +120 px, open PL+EQ, expand, flip, collapse, quit, restart: width, panels, side and time mode all restored. Cost: playlist height is fixed. | done |
| 14 | Choose where PL / EQ open (above / below), bar must not move | **DONE** | Arrow on the PL / EQ header flips both panels to the other side; remembered across restarts. The bar no longer moves when panels open or close. Flipping itself moves the bar to the other end of the window (one-time re-drag). Both panels share the side; a per-panel side would need 4 more layouts. | done |
| 1 | Double-click on a file opens a second VLC with the default skin | **DONE, confirmed by the user on Windows 2026-10-31** | You start VLC from files / folders. `taskbar\Setup.cmd` writes `vlcrc`: `intf=skins2`, `skins2-last=<skin for the display scale>`, `one-instance=1`, `one-instance-when-started-from-file=1`, `playlist-enqueue=0`. Backs up the old file as `vlcrc.before-titlebar`. Cause of the bug: the instance started by the launcher was not started from a file and had `one-instance=0`, so it never listened for files and Explorer started a second, normal VLC. | done |
| 3 | Show elapsed time, countdown on click | **DONE** | Elapsed by default; click the time (strip or full player) for time left. The time background is a checkbox bound to a flag window, the texts use `focus="false"` so the click reaches it (an Image only reacts to double-click, a Text takes the whole rectangle: both verified in source). Remembered across restarts. Tested in VLC. | done |
| 4 | A-B loop | **DONE (hotkey + tray + taskbar hover buttons confirmed on Windows 2026-10-31; hover buttons added for folders only)** | `lua/intf/titlebar.lua`: Ctrl+Shift+A (action `subsync-markaudio`) or the helper's tray menu Playback > A-B loop (web `key` command). Loops about 0.2 s after B. State only in VLC's log; the skin cannot show it (skins2 reads the title once per track). See README "Lua extras", docs/architecture.md "Lua interface". | done |
| 5 | Next / previous folder (and slower / faster out of the strip) | **DONE (Linux-tested via harness; Windows untested)** | Same script: Ctrl+Shift+Right / Left (`viewpoint-roll-clock` / `-anticlock`), tray menu Playback. Walks the playlist by `file://` directory, local files only; folders must be contiguous. No skin buttons possible. Strip part (T2): slower / faster removed from the strip, title / seek window 48 px wider, `MIN_W` 420. | done |
| 6 | Odd button resize on mouse-over (screenshot) | **DONE (needs a check on Windows)** | Cause: strip and full player bitmaps had ids differing only by case (`b_slower` / `B_slower`, `t_play` / `T_play` ...). VLC unpacks the .vlt to disk, and on Windows (case-insensitive) one PNG overwrote the other, so strip buttons showed the full player's larger images. Renamed to `fb_*` / `ft_*`; the build now fails on any case-only collision. Linux never showed it. | done |
| 8 | Playlist: show duration, optional columns | **BLOCKED** | The skins2 Playtree control draws one text column (verified: no column support in `ctrl_tree`). Workarounds: (a) accept; (b) a Lua *playlist rename* that appends the duration to item titles (changes titles, clunky); (c) PATCH: add a column renderer to the Playtree control (large). | L / XL |
| 9 | Empty space in the full player LCD, meaning of the numbers | **DONE** | Big number = time left, `12:22 / 18:34` = elapsed / total, `SPEED 1x` = playback speed. Full player is now 122 px (was 146): toggles and speed share one row under the bitrate line, empty boxes gone. Tested in VLC. | done |
| 10 | Timer wider than 59:59 (hours) | **DONE** | Strip time box 50 -> 86 px at a 24 px bar (96 px at 36; `bar_metrics` `tw`; the minimum strip width is now 420, item 5); full player time column widened to 126 px. Tested with a 63-minute track in VLC: `-1:03:16` fits both. Tracks of 10 h+ would still overflow. | done |
| N2 | Playlist stretch only from the bottom-left corner | **Superseded by 13** (playlist height is now fixed; width follows the bar) | skins2 only has `resizeS`, `resizeE`, `resizeSE` (verified in the builder): **no west or south-west resize**, so a bottom-left handle cannot resize leftwards. Options: (a) one grip in the bottom-*right* corner, height only; (b) bottom-left grip that uses `resizeSE` (drag right/down, feels wrong); (c) PATCH: add `resizeSW`. Also decide: should the playlist ever change width on its own, or only follow the bar? Proposed default: remove the right and bottom edge handles, keep a single bottom-corner grip that changes the height only. | S |
| N3 | "Knihovna medii" (Media Library) node does nothing | **DONE (untested on Windows)** | Setup writes `media-library=0` (verified in VLC: the node disappears). | done |
| N1 | Start pinned to top (always on top) | **DONE, pin confirmed by the user on Windows 2026-10-31** | Option (b): the helper posts a mouse click to the skin's own pin button 1.5 s after VLC's window appears, once per VLC start, so VLC's state and the lit pin agree. Pin positions checked by clicking in VLC at 150 %. Setup can start the helper with Windows in watch mode (`-Watch`, waits for VLC, also when VLC is started from a file), with or without docking (`-NoDock`). Untested: that skins2 on Windows accepts the posted messages (the source handles WM_MOUSEMOVE / WM_LBUTTONDOWN / UP from the message queue, so it should). | done |
| 2 | EQ presets | **DONE (Linux-tested via harness; Windows untested)** | Same script: Ctrl+Shift+Up / Down (`viewpoint-fov-in` / `-out`), tray menu Playback > Next EQ preset. Cycles VLC's 18 presets, re-applies on new tracks; the skin's EQ panel follows. Bonus: bitrate for FLAC and other lossless files (the script sets the input's `bit-rate` variable). The sample rate stays whole kHz (skins2 limit). | done |
| 15 | Clicking the taskbar hides the player even when pinned | **FIXED (see 33), confirmed on Windows 2026-10-31** | Windows behaviour: when the taskbar is clicked it moves itself to the top of the "always on top" group, so any pinned window lying over it is covered. VLC's pin (`vlc.onTop`) sets topmost once and never re-asserts it, so without the helper this is expected. The helper re-asserts topmost when the taskbar is above VLC (on every foreground change and every 250 ms), so with the helper the player should come back within a fraction of a second. If it does not: (a) check the helper is running (started via `VLC in taskbar.cmd`); (b) debug the z-order check on Windows. Stronger fix: (c) re-parent the strip into the taskbar window (`SetParent` onto `Shell_TrayWnd`, the technique TrafficMonitor uses on Windows 11), so the taskbar can never cover it. Cost: only while the bare strip shows (a child window is clipped to the taskbar, so panels / full player need it un-parented again), plus the cross-process input coupling risks of SetParent. Questions: helper running? Gone for good or back after a moment? Clicked an empty taskbar spot, an app icon, or VLC's own taskbar button (that one minimizes)? | S-M |
| 16 | Project under version control | **DONE** | Git repository in `Titlebar-VLC-skin/`, first commit = state before the launcher setup. | done |
| 17 | Seek from the strip (no rewind / fast-forward before) | **DONE** | The strip's title window is a seek slider over the song name: the played part fills it (51 frames, `FILL_FRAMES`, plus a play-head line), a click jumps to that point and can drag, the mouse wheel steps 5 %. The title text uses `focus="false"` so the click reaches the slider. Verified in source (`CtrlSliderBg`: click = jump, wheel = variable step 0.05) and in VLC: a click at 50 % went to 1:41 of 3:20, at 25 % on a wider strip to 0:51. Keyboard also works: VLC's hotkeys (Shift / Alt / Ctrl + arrow keys) jump 3 s / 10 s / 1 min while the player has focus. | done |
| 18 | Light / dark theme + 3 colours each, switch in the full player title bar; then (6th list) one button only, more coordinated variations, own colour; then (7th list) minimal: keep the dark blue one | **DONE** | **Release skins carry only Midnight** (`DEFAULT_THEMES`, the user's choice). The generator builds 10 themes plus Custom (`--themes`, README "More themes"): each theme is a full set of controls in the same 4 layouts, shown by its own flag window (`th0`, `th1`, ...). The full player's title bar has one theme button that steps to the next theme (tooltip: current / next); it is left out when one theme is built. Memory and start-up figures: [architecture.md](docs/architecture.md#bitmaps-atlases) and README Limits. Custom: any accent, recoloured exactly from a red reference (item 23). Tested in VLC: switching, persistence, panels in all themes. | done |
| 11 | Tray icon for the helper (replace the Ctrl+Alt+Shift+V hotkey) | **DONE (T7), confirmed by the user on Windows 2026-10-31** | NotifyIcon with Dock / Pin now / Play / pause / Playback (A-B, folder jump, EQ preset) / Open debug log / Quit; compile-checked. | done |
| 12 | Taller strip for the taskbar (36 px) | **DONE, confirmed by the user on Windows 2026-10-31** | Generator `--bar-height N` (default 24, 36 = taskbar build); release files `Titlebar-taskbar-{100,125,150,200}.vlt` (36 px; naming `Titlebar-taskbar-NNN` / `Titlebar-bar<N>-NNN`). Widths and right-edge offsets unchanged (min width 420 at every bar height); window height is the same for all 4 layouts. Setup and the helper prefer the taskbar file when docking and read the bar height from the file name (`VlcDock.BarHeight` replaces `P(24)` in ReadShape / Place / ClickPin). Tested in VLC at 100 % and 150 % (shape rule, clicks, panels above / below); the Windows placement is untested. Pin stays (the helper clicks it). | done |
| 19 | Play / pause / prev / next when hovering VLC's taskbar button (Windows) | **DONE, hover buttons confirmed by the user on Windows 2026-10-31** (T12; end of `VlcDock.cs`, `$TaskbarButton` in `vlc-taskbar.ps1`) | skins2's taskbar button belongs to its hidden 0 x 0 root window and Windows sends thumbnail clicks only to the owning window, so the helper shows its **own** button (invisible `WS_EX_APPWINDOW` window: layered alpha 0, click-through, off-screen) and VLC's is hidden (`skins2-taskbar=0` from Setup when the helper starts with Windows, `--no-skins2-taskbar` from the launcher; a leftover VLC button is removed with `DeleteTab`). Built: 3 thumbnail buttons (icons drawn at runtime, follow Windows dark / light), progress in the button (green / yellow paused / none; interpolated from 21's 500 ms polls), hover preview card (title, artist, time; `DwmSetIconicThumbnail`), title "Artist - Title", VLC's icon. Click = VLC to the front (restored if minimized, `SC_RESTORE` to skins2's root window); "Close window" = `SC_CLOSE` = VLC quits normally. App id: VLC 3 sets none, so the helper uses the id Windows derives from vlc.exe's path plus relaunch properties (`$TaskbarAppId` overrides). Mono compile (strict) + unit tests of layouts / GUIDs / drawing. *Unverified:* everything at runtime; 13-step checklist in README. | L |
| 20 | Windows media integration: media flyout (volume / media keys), Quick Settings media card, lock screen, hardware media keys | **DONE in Setup (T13), confirmed by the user on Windows 2026-10-31** (card shows title / artist, previous, pause, next) | Setup asks, finds VLC's architecture from vlc.exe's PE header, offers the VC++ runtime (Microsoft download, Authenticode checked), downloads the pinned v5.0.0 zip (SHA-256 = GitHub's release digests), copies the DLL (one UAC prompt; none for a writable portable VLC) and adds `win10smtc` to `extraintf` (module name from `plugin.h`, `PLUGIN_SHORTNAME`; `extraintf` is the option behind Qt's "Control interfaces" box). This is the "integrate it into Windows" option (System Media Transport Controls, SMTC). VLC 3 has none. The community plugin [vlc-win10smtc](https://github.com/spmn/vlc-win10smtc) adds it: GPL-3.0, maintained (v5.0.0, 2026-09-08, supports VLC 3.0.x and 4), Windows 10 1607+ / 11, x64 / x86 / ARM64 builds. It needs the Visual C++ 2022 redistributable matching VLC's architecture (VLC's, not Windows'). Install: copy `libwin10smtc_plugin.dll` to `<VLC>\plugins\misc` (Program Files, so admin once), then Advanced Preferences > Interface > Control interfaces > "Windows SMTC integration". It is a control interface, so it runs next to skins2: VLC starts `extraintf` / `control` modules whatever the main interface is (verified, `src/libvlc.c`). It creates its own hidden window, so it does not depend on the skin. The exact `extraintf` value (expected `win10smtc`) and the behaviour with skins2 are *unverified* until tested on Windows. Covers most of what 19 asks for in Windows' own UI; 19 adds the buttons on the taskbar hover itself. | M |
| 21 | Control channel from the helper to VLC (prerequisite for 19, and for menu-style controls in section 2 D) | **DONE, confirmed on Windows 2026-10-31 (taskbar buttons use it)** (T11; `VlcRemote` in `VlcDock.cs`, Setup keys in `vlc-taskbar.ps1`) | VLC's built-in web interface on localhost: `extraintf=http`, `http-host=127.0.0.1`, a random `http-password` written by Setup. `requests/status.json` gives play state, time, length, title / artist and the art URL; commands like `?command=pl_pause` / `pl_next` / `pl_previous` / `seek`. Alternative: the `rc` interface over TCP (`liboldrc_plugin`): simpler, but without a password any local program can control VLC. Works the same on Linux, but Linux has MPRIS (22b) anyway. **Built (T11)**, verified on Linux with real VLC 3.0.20 + skins2 (curl and the C# client under Mono: status, pl_pause, pl_next, pl_previous, pl_stop, seek, wrong password = 401, closed port): `http-host` and `http-port` are core options (vlcrc `[core]`, `src/libvlc-module.c`); `http-password` belongs to the Lua module (`[lua]`, `modules/lua/vlc.c`); `extraintf` is `[core]`. The web interface runs next to skins2. `status.json` has `time` and `length` in whole seconds only (a progress bar must interpolate between polls) and `information.category.meta` with `title` / `artist` / `filename` (no title tag: the helper falls back to the file name). A command's answer can still show the old state (next, stop), so read the status again. *Unverified (needs Windows)*: the whole helper side, and that the Windows Firewall shows no prompt for a loopback-only listener (expected none). An already running helper must be restarted after Setup to pick up the web interface settings. | S-M |
| 22 | Linux as a first-class platform (you use it on Linux too) | **LINUX** | The skin itself runs on Linux X11 today (every test and screenshot is from Linux VLC 3.0.20). Missing: setup, desktop integration, pin on start, and Wayland. Sub-items 22a-22d below. **Decided 2026-10-31:** distro unknown, so everything must be universal (any distro, any desktop, native / Flatpak / Snap VLC, X11 and Wayland via XWayland, only tools present everywhere). First goal: floating strip, pinned on start; no panel docking for now. | - |
| 22a | Linux setup script | **DONE (tested in Xvfb; Flatpak / Snap / Wayland unverified)** | `linux/setup.sh` / `--uninstall` (T14): detects native / Flatpak / Snap VLC, writes the same vlcrc keys as Windows (shared table in `docs/architecture.md`, "vlcrc keys"; `skins2-taskbar` is Windows-only), picks the skin from `GDK_SCALE` / `QT_SCALE_FACTOR` / `Xft.dpi` / KDE / GNOME (`--scale N` overrides), backs up `vlcrc.before-titlebar`, refuses while VLC runs. The `vlc` launcher forces `--media-library` (`bin/vlc.c`), so setup writes `~/.local/share/applications/vlc-titlebar.desktop` ("VLC (Titlebar)", `--no-media-library`) and optionally makes it the default for `audio/*` (not folders). Harness-checked: Media Library node gone, second start hands its file to the first instance over D-Bus, uninstall restores vlcrc byte for byte. Optional pin autostart (T16); installs the Lua extras and `lua/vlcrc-keys.txt`. *Unverified:* Flatpak paths, Snap fallbacks, scale under Wayland. | M |
| 22b | Linux media controls (MPRIS) | **DONE** | Documented in README ("Media controls", Linux). Verified: `org.mpris.MediaPlayer2.vlc`, `Next` and `PlayPause` over D-Bus with the skin. *Unverified:* KDE Plasma's hover buttons on the task manager entry (`WM_CLASS` vs the "VLC (Titlebar)" desktop entry); untagged files show the file name only. | XS |
| 22c | Linux: start pinned and dock into a panel | **PIN DONE (T16, tested on Xvfb only), docking postponed** | `linux/titlebar-pin.py` (Python 3 standard library + ctypes on libX11 / libXext, no xdotool): finds the skin's main window (class `Vlc`, name `VLC (TopWindow)`, largest viewable), reads the Shape extension (same rule as `ReadShape`), takes the scale from the window height / `.vlt` name, and clicks the skin's own pin with synthetic `ButtonPress` / `ButtonRelease` via `XSendEvent`, so the pointer never moves (checked in source: the X11 loop ignores `send_event`; `findHitControl` sends the checkbox its `enter`). Verified in VLC 3.0.20 under Xvfb at 100 % and 150 %, strip / full, bar top / bottom: pin lit, pointer unchanged, `_NET_WM_STATE_ABOVE` set under a fake EWMH window manager. `--watch` (polls `/proc` every 2 s), `--install-autostart` / `--uninstall-autostart`. Docking into a panel postponed. Unverified: real window managers / compositors (22d). | M |
| 22d | Wayland | **LINUX**, *unverified* | skins2 is Xlib only, so on Wayland the skin runs through XWayland; `titlebar-pin.py` talks to that X server and never places windows. **Checklist for the user** (`linux/titlebar-pin.py -v` with VLC started): 1. GNOME Wayland: "_NET_WM_STATE_ABOVE is set", player stays above other windows, pin stays lit. 2. KDE Plasma Wayland: same. 3. `--install-autostart`: the watcher runs after login (DISPLAY set) on GNOME, KDE, XFCE, Cinnamon. 4. Click-through in the transparent area. 5. Moving the window by its grip. 6. 125 / 150 % fractional scaling: size and pin position. 7. Flatpak / Snap VLC. 8. Tiling WMs (windows may not float). Record the results here. | ? |
| 23 | Custom accent colour: pick any colour for the Custom theme, Windows and Linux | **DONE (Linux tested / Windows untested)** | `custom-colour/`: `custom-colour.py` (Python 3 standard library only, own PNG decoder / encoder; Pillow only as a speed-up, `--no-pil`; picker: `zenity`, `kdialog`, `yad`, tkinter, then the terminal; `--reset`; atomic rewrite of the `.vlt`) and `Custom colour.cmd` + `custom-colour.ps1` (Windows PowerShell 5.1, C# 5 pixel loop with `System.Drawing` `LockBits` `Format32bppArgb`, `ColorDialog`, built-in `tar.exe`). Uses `custom-ref/` of the `.vlt` (see `docs/architecture.md`, Custom theme); a `.vlt` built before that existed is skipped with a message. **Verified on Linux**: recoloured 100 / 150 / 200 % skins to `#33ff99` with the pure-Python path and compared with the generator's own `--custom "#33ff99"` build: every `img/` pixel identical (max channel difference 0 over 1.1 / 2.6 / 4.8 million pixels, alpha identical), `theme.xml` byte-identical, all other `.vlt` members byte-identical; pure path == Pillow path == generator for 8 colours (incl. `#000000`, `#ffffff`, `#ff0000` = identity); PNG decoder tested with all 5 filters (and the skin's PNGs use all of them) plus error cases; time 0.3 s (100 %), 0.9 s (150 %), 1.6 s (200 %) per `.vlt` pure, 0.4 s with Pillow; real VLC 3.0.20: recoloured skin, Custom theme shows the chosen green. C# class compiled with Mono `mcs -langversion:5` and run under Mono + libgdiplus: PNG output identical to the generator's, XML identical. *Unverified (needs Windows)*: the PowerShell script as a whole (`tar.exe` pack / unpack, the colour dialog, `[IO.File]::Replace`), the C# class on Microsoft's GDI+ (expected the same: `Format32bppArgb` is straight alpha), and that VLC reads the `tar.exe`-packed file (`--format ustar`, files only, as the generator writes). The GUI pickers `zenity` / `kdialog` / `yad` / tkinter were only tested with stand-in scripts for their output format. | done |
| 24 | Online configurator for the skin's look | **PHASE 2 (spec from user)** | A static web page that builds one `.vlt`: either **one theme** (memory stays at the Midnight level) or **one theme as a light + dark pair with a switcher** (the round theme button in the full player; ~+10 MB at 100 %, +20 MB at 150 %), optionally **following the system's light / dark setting** (item 25). Options: **size** (display scaling 100 / 125 / 150 / 200 %, default from the browser's `devicePixelRatio`), **font** (curated open-licence fonts, OFL; times need tabular / monospace digits; optional own TTF), **light / dark** base, **primary colour** (accent: LCD text, progress, active buttons), **secondary colour** (indicator LEDs: pin, PL / EQ lights, toggles). Preview, then download. Route: run `build_skin.py` in the browser with Pyodide (Pillow is available there), so the generator stays the single source of truth. Needs generator options first: `--font`, `--mode`, `--accent`, `--led` (today themes are named seeds). *Unverified*: Pyodide load size (~10-15 MB) and build time per scale. Brief: T17. *Step 1 done*: `build_skin.py --mode dark|light --accent #rrggbb --led #rrggbb --font <ttf>` builds one theme named "Theme" (base tint = accent hue at Midnight's saturation, grey for a grey accent; LED defaults to a lightened accent); the font replaces DejaVu Sans Mono for all LCD text and ships as `fonts/lcd.ttf|otf` (DejaVu licence file is then left out). Default builds are unchanged (stage dir identical). Checked in VLC 3.0.20 (light, #ff8800, #00ccff, bold font): renders, no skins2 warnings. Tabular digits of a custom font are not checked. *Steps 2 + 3 done*: static page in `configurator/` (Pyodide 314.0.7 + Pillow 12.2.0 from jsDelivr, worker, `glue.py` keeps the spike's normalisations and ships the font licence in the `.vlt`; fonts DejaVu Sans Mono, JetBrains Mono, Roboto Mono, Source Code Pro). Built under node and tested in VLC 3.0.20 (light, Source Code Pro); the page itself was not run in a browser. *Step 4 + own-TTF done (2026-10-31)*: the page has a "Light + dark" checkbox (`--pair`) and a font file input (read in the page, written to `/work/fonts/own.ttf|otf` by the worker, no licence file: the page warns about the licence and about non-monospaced digits); the page's copy of `build_skin.py` was synced (video window, fullscreen controller). Verified under node + Pyodide 314.0.7 (pair + JetBrains Mono: builds, `th1` present, 5.4 s at 100 %); the page itself still has not been run in a browser (Edge from WSL: devtools port not reachable). | M |
| 25 | Follow the system's light / dark setting (for a light + dark pair) | **Windows DONE (2026-10-31), live switch in the full player confirmed by the user; Linux prototype DONE (`linux/follow-system-theme.sh`)**. Windows: `$FollowSystemTheme` in `vlc-taskbar.ps1`; `VlcDock.cs` (`SyncVlcrcTheme`, `FollowSystemTheme`) rewrites th0 / th1 in vlcrc while VLC is closed (checked every 5 s) and, while VLC runs with the full player showing, clicks the theme button when the panel brightness (3 sampled pixels) disagrees with `AppsUseLightTheme`. The strip has no theme button, so it follows when expanded. `make-windows-package.sh` rebuilds the .vlt files as Midnight + Paper (`PAIR=0` keeps Midnight only). Start-up sync (VLC closed, then a file opened) confirmed too. Old status: | **Linux prototype (done, works today with `--themes midnight,paper`; README "Linux: follow the system's light / dark setting"):** the script reads the setting (portal via `gdbus`, else `gsettings`, default dark), and only if VLC is not running rewrites the last field of the `th0` / `th1` entries of `skins2-config` in vlcrc, then execs `vlc` (or `--exec CMD`); `--install` / `--uninstall` wrap / unwrap every Exec line of `vlc-titlebar.desktop`; `--dark-theme` / `--light-theme` map themes. Verified in real VLC 3.0.20 under Xvfb (tools/vlc-test.sh, stub `gdbus`): dark start showed Midnight, stub flipped to light and restart showed Paper, flipped back and restart showed Midnight again; while VLC ran the script left vlcrc untouched. *Unverified*: real portal / gsettings output, Flatpak / Snap paths, the wrapped launcher from a real desktop, a system switch while VLC runs (not handled: next start follows). First start with no saved `skins2-config` shows th0. Original spec: skins2 cannot read the OS setting. But VLC stores each theme flag window's visibility in `skins2-config` in vlcrc (seen in a test run: `["th0" "th0-l" 639 511 1 1 0]["th1" "th1-l" 639 511 1 1 1]`, last field = shown), and reads it at start. So: **at VLC start** a helper / launcher rewrites th0 / th1 in vlcrc while VLC is not running. Windows: `HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize\AppsUseLightTheme` (helper in `-Watch` mode, before VLC starts; but VLC started from Explorer starts without the helper getting a chance first, so this only works for the next start, or via a launcher). Linux: `gdbus call` to the XDG desktop portal (`org.freedesktop.appearance` `color-scheme`), fallback `gsettings get org.gnome.desktop.interface color-scheme`; a wrapper in the `.desktop` file (22a) runs before VLC. **While VLC runs** (system switches at sunset): the helper posts a click on the theme button (like `PinOnce`), which only exists in the full player; the strip would need a small switch too (design question). VLC rewrites `skins2-config` when it exits, so the helper must not edit it while VLC runs. *Unverified*: posted clicks on Windows (same risk as N1). | M |
| 26 | Windows test 2026-10-31: docking in the taskbar flashes and moves around | **FIXED, verified on Windows 2026-10-31 (T25)** | Cause (verified on X11, same skins2 code): skins2 keeps its own idea of the window position and never notices outside moves, so every expand / collapse / flip / resize put the window back at VLC's old position and the helper pulled it back. The corner-radius suspicion was wrong. Fix: the helper moves VLC with a posted drag on its grip (skins2 then knows the new position; `SetWindowPos` only as fallback), never while a mouse button is down. **Second test log (125 % scaling):** the helper (DPI-unaware PowerShell) reads VLC's window alternately in physical and DPI-virtualized coordinates (734x545 vs 587x436, Start button 1358 vs 1086) and moves it back and forth 4 times a second. Fix: force one DPI awareness context (per-monitor v2) around all window calls. Probably also the cause of item 33 (strip pushed off-screen). Third test log (helper per-monitor DPI aware): one coordinate system (734x545 at 125 %, VLC 120 dpi), the taskbar skin (`Titlebar-taskbar-125.vlt`) detected, docked with one posted drag, pin clicked and on, resizing by the grip works (width 734 -> 754, right edge back at Start on release), a drag away snaps back on release. | M |
| 27 | Windows: making the player wider is hardly possible | **SKIN PART DONE (T23); helper part FIXED (T21)** | Docked with `DockTo=start`, the helper right-aligns the strip to the Start button, so while you drag the right edge wider the window moves left under the mouse (helper). The `resizeE` grip is also only a few px wide, and the flat style made it hard to see (skin). Skin: a 10 px grip tab with ribs at the right end of strip, full player, EQ and playlist (`resize_handle()`); drag verified in the harness at 100 / 150 % and the taskbar build. | Helper: no re-placing while a mouse button is down; with `DockTo=start` the right edge returns to the Start button on release, so the strip grows to the left. A width change after an outside move no longer snaps back to the minimum (same root cause as 26). | S-M |
| 28 | Windows: unpin does not work | **FIXED (T21), confirmed by the user on Windows 2026-10-31** | `Move()` always re-applied `HWND_TOPMOST`. The helper now reads VLC's pin state and only re-raises while pinned. Exception (**confirmed by the user 2026-10-31**): the bare strip docked in the taskbar stays topmost even when unpinned, because a non-topmost strip is always hidden behind the taskbar; unpin applies to the full player. | S |
| 29 | Windows: the buttons look weird | **FIXED (T23, likely cause), needs the user's confirmation** | Found in skins2 source: PNGs are premultiplied on load (`file_bitmap.cpp`) and `AlphaBlend` is fine, but buttons / checkboxes / thumbs / slider backgrounds are drawn into a blank offscreen bitmap and then copied without blending (`drawGraphics`), so a semi-transparent pixel becomes opaque and on Windows takes whatever the blank bitmap held (`CreateCompatibleBitmap` does not guarantee black): bright dots at the rounded corners. Simulation in `docs/img/windows-sim/` (`tools/windows-sim.py`). Fix: the generator composites those bitmaps over the panel colour (`solid()`, flat style), so every pixel is opaque; Linux looks the same. | S-M |
| 30 | Windows: "Media Library" (Knihovna medii) still in the playlist | **FIXED (T22), confirmed by the user on Windows 2026-10-31** | Verified cause: `bin/winvlc.c:189` puts `--media-library` before the user's arguments, so vlcrc's `media-library=0` is overridden (Linux: same, `bin/vlc.c`). Setup now writes per-user overrides `HKCU\Software\Classes\<ProgID>\shell\<verb>\command` (VLC.<ext>, VLC.OPENFolder, Directory, AudioCD, ... read from HKLM, only commands running this vlc.exe with `--started-from-file`) with `--no-media-library` added, listed in `%LOCALAPPDATA%\Titlebar-VLC-skin\file-associations.txt`; Uninstall removes exactly those. The helper's VLC start and a new Start menu "VLC (Titlebar)" shortcut pass the flag too. VLC's own Start menu / pinned icon still show the node (cannot be changed per user). | M |
| 31 | Windows: with EQ / playlist open the player cannot collapse back into the taskbar | **FIXED, confirmed by the user on Windows 2026-10-31 (T21 + T25)** | If the helper's bar height (36) differs from the skin VLC actually uses (24), the old test called "strip + PL / EQ" the full player. New `DockShape.Classify` derives the state from the visible height and infers bar height and scale (768 cases pass). Panels that would open below the screen now get one automatic flip click (`$FlipPanels`). **User 2026-10-31: the strip stayed *above* the taskbar** instead of going into it, which matches the suspected misclassification (placed like the full player). Still wanted: the log's `helper started: scale=.. barHeight=..` line and which .vlt VLC uses. | S-M |
| 32 | Flipping the panels (above / below) moves the strip | **FIXED on Windows, confirmed by the user 2026-10-31 (T25); Linux: limitation** | Cause (known since item 14): the 4 layouts have one size, the bar sits at the top in "dn" and at the bottom in "up", and a skin action cannot move the window. Fix (`KeepBarOnFlip`, `DockShape.FlipOffset` / `BarTop` / `ClampVisible`): the helper sees the bar-side change of the same kind (strip / full) and, not docked, moves the window by the difference with T21's posted drag, clamped to the work area; never while a mouse button is down, not on strip <-> full, not when the window moved as well. Docked, `Place` keeps the strip in the taskbar as before; a 50 ms timer while the mouse is over VLC makes the jump short. The full player with both panels now has a known direction too (seam test in `Classify`). Unit-tested under Mono with real shapes (80 dn / up pairs, 3493 checks). Linux: same idea in `titlebar-pin.py --watch` is harder (skins2 ignores outside moves and synthetic motion on X11); stays a limitation for now. README "second Windows test" steps 9-10. User: flipping is OK now. | S-M |
| 33 | Second Windows test: a click on the taskbar still hides the player; it only comes back from VLC's tray icon | **FIXED, confirmed by the user on Windows 2026-10-31 (T25)** | **First Windows log (125 %)**: the DPI-unaware helper (powershell.exe) read VLC's window alternately in physical and DPI-scaled coordinates (734x545 / 587x436, Start at 1358 / 1086), depending on which window's message called `Place`, and moved VLC back and forth between them (also the flashing); a position from the wrong system can push the strip off the screen, where skins2 keeps it until the tray icon re-shows it at its own stored position. No hide / minimize was logged at the taskbar click. Fix: the helper's thread is per-monitor DPI aware (V2) from the start and at every entry point (`DpiEnter`), so all coordinates are physical; `dpi:` / `DPI:` log lines. The same log: VLC used `Titlebar-125.vlt` (24 px) while the helper assumed the 36 px build; the script now takes scale / bar height from vlcrc's `skins2-last` when it does not start VLC (cause of the mismatch not visible in the script: Setup writes the taskbar build when docking was answered Yes and the file exists; VLC also saves the skin it last had on exit). User: it happens on a click on an empty taskbar spot or another app's / Windows' icon (not VLC's button, not show desktop). Source facts (3.0.x): skins2 has no `WM_ACTIVATE` / `WM_ACTIVATEAPP` / `WM_KILLFOCUS` handling, so activation changes cannot hide it; its windows are hidden only by minimizing the root window (`vlc.minimize()`, `SC_MINIMIZE` to the root), a skin change or `window.hide()`. Tray icon: single click = `raiseAll` (`SetForegroundWindow`; helps only if VLC was *covered*), double click = `SW_RESTORE` on the root (helps if *minimized*). The root never gets a taskbar button with `skins2-taskbar=0`. So either (a) something minimizes the root (Windows; unknown what), or (b) the strip stays behind the taskbar although the helper re-raises it (Windows 11 z-order; then item 15's `SetParent` is the next step). Fix: while docked, the helper restores a minimized VLC at once (`SC_RESTORE` to the root, as the tray double-click); the full player's own minimize button still minimizes (cursor on the full player at that moment); undocked nothing changes. A raise that does not take is logged with the windows above VLC and retried (NOTOPMOST, TOPMOST). New log lines: `foreground: ... (process); VLC root ... main ...`, `VLC window event: root window ... minimized`, `VLC hidden: ...`, `restore: ...`, `the taskbar is still above VLC after the raise`. Still needed: the log of one occurrence and whether a single or only a double click on the tray icon brings it back (README steps 11-15). User: no longer hides after the DPI fix. | M |
| 34 | Video does not play (audio only) | **DONE on Windows, confirmed by the user 2026-10-31** (cause of the first failure: VLC's saved `skins2-config` had the new window as hidden; skins2 attaches video only to a *shown* window. The helper now sets `["video" ...]` to shown in vlcrc while VLC is closed (`SyncVlcrcTheme`). Title bar with full screen + shrink-to-bar buttons, resize by the corner, and a full-screen control panel (window `fullscreenController`: seek, previous / play / next, volume, leave) all confirmed by the user on Windows 2026-10-31; the helper also resets a saved `video-min` layout to `video-l`. *Open:* the same fix for Linux (`linux/setup.sh`), and for a Windows install without the helper running). Old status: | The skin had no `<Video>` control, and skins2 shows video only inside one. New window `video` (`build_skin.py`, `vlay`): themed frame (drag, resize E / S / SE) and a Video control, every control `visible="vlc.hasVout"`, so it is invisible without video (same trick as the flag windows). Autoresize: the window follows the video size. The helper's `FindMain` now ignores it (the main window is always 436 logical px high). Verified in VLC 3.0.20 under Xvfb: no skin warnings, window invisible without video. *Not verified:* a real video (the test VLC has no video output plugin and no libavformat), the window on Windows, fullscreen, moving / resizing, theme switch while a video plays. | M |

Numbers 1-10 follow your first list; N1-N3 your second list; 13-14 your third list (13 = width, 14 = panel side); 15 and 17 your fourth and fifth; 18 the themes; 19-22 your sixth list (taskbar hover buttons, Windows integration, Linux); 7a, 7b, 11, 12, 16, 21 were added during analysis.

---

## 2. Plugin and extension options

Common problem: **a skin button can only run actions that skins2 knows** (verified list: `dialogs.*`, `dvd.*`, `playlist.*`, `vlc.play/pause/stop/faster/slower/mute/volume/minimize/onTop/snapshot/toggleRecord/nextFrame/quit/fullscreen`, `equalizer.enable/disable`, `*.setLayout/show/hide/maximize`). There is no "run script", no custom action, and no way to send a key. So any feature built outside the skin needs a bridge from the button to that feature. The options:

### A. Lua interface script (`lua/intf/titlebar.lua`, started with `--extraintf luaintf --lua-intf titlebar`)

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
| Playlist columns | no | no | yes (large) | no | accept or C |
| West / SW resize | no | no | yes | no | C or accept |
| Media Library node | n/a | n/a | n/a | n/a | CONFIG (Linux: `.desktop` override, 22a) |
| Taskbar hover buttons (Windows) | no | no | no (skins2 owns no real taskbar window) | yes (own taskbar button + 21) | D |
| Windows media flyout / media keys | no | no | no | possible via WinRT, fiddly | third-party plugin (20) |
| Linux media controls | n/a | n/a | n/a | n/a | built in (MPRIS, 22b) |
| Runs on Linux | yes | - | yes (own build) | no | A |

---

## 3. Suggested order

Docs: user guide in README.md, internals in [docs/architecture.md](docs/architecture.md).
Most items are built. What is left needs a Windows machine, the user's answers, or phase 2.

1. **Windows test (next):** run `taskbar\Setup.cmd`, then open a file from Explorer: skin, one
   window, no Media Library entry, player pinned (pin lit). Then the 13-step taskbar button
   checklist in README ("Testing the taskbar button"). Record the results in the *untested* marks
   of items 1, 7a, 11, 12, 15, 19, 20, 21 and 23.
2. **T9 (fix 15, taskbar click hides the player):** needs the user's answers to item 15 and the
   helper's debug log (T3) from that Windows run. Decide from the log; do not guess.
3. **Phase 2:** T17 (online configurator, item 24), then T18 (follow the system light / dark, item 25;
   needs T17 step 4 and the Linux launcher from T14).

Waiting on the user, no code: the Wayland and real window manager checklist (item 22d).
Parked: T10 (patched skins2), only if the user chooses option C in section 2.

Agent-sized work packages for these steps are in section 5.

## 4. Open questions

1. Item 15: the answers from the Windows run. Was the helper running? Does the player come back
   after a moment? What exactly was clicked? Needed for T9, together with the debug log.
2. Item 22d: the Wayland and window manager checklist (GNOME, KDE, XFCE, tiling WMs, Flatpak and
   Snap VLC). Record the results in item 22d.

Answered (for the record):

- Items 4, 5, 2 (2026-10-31): the Lua route, A + D (Lua interface script, hotkeys, helper tray menu).
  Built as T6.
- Item 20 (2026-10-31): yes, Setup downloads and installs the SMTC plugin (T13).
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
- Read `README.md` and this file first. The generator is `source/build_skin.py`. Release skins are `Titlebar-{100,125,150,200}.vlt` (24 px) and `Titlebar-taskbar-{100,125,150,200}.vlt` (36 px) in the repo root. Rebuild them with `--scale 1 / 1.25 / 1.5 / 2` (add `--bar-height 36` for the taskbar set), `--out` to a temp folder, then copy the `.vlt` files and `preview-100.png` -> `preview.png`.
- skins2 limits are listed in items 7b/13, 3, and section 2. Check the VLC 3.0.x source (github.com/videolan/vlc, branch `3.0.x`, `modules/gui/skins2`) before relying on any skins2 behaviour; do not guess.
- Windows scripts keep CRLF line endings and plain ASCII. `VlcDock.cs` must stay C# 5 (Windows PowerShell 5.1 `Add-Type`).
- Never `pkill vlc` / `killall`: kill only PIDs you started. No `sudo`.
- Commit on your own worktree branch, with the attribution line. Never commit to the main branch, never push, and do not merge: whoever integrates the branches does that. Update this backlog's item row when done.

| ID | Task | Model | Depends on | Size |
|----|------|-------|------------|------|
| T1 | Test harness in the repo | **DONE** (merged; `tools/`) | - | M |
| T2 | Move slower / faster to the full player | **DONE** (merged) | T1 | S |
| T3 | Helper debug log (for 15) | **DONE** (merged) | - | S |
| T4 | Docs consistency pass | Haiku | after others | XS |
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
| T17 | Online configurator (24), **phase 2**; steps 1 and 4 DONE (generator options, `--pair` in T24); steps 2-3 DONE: `configurator/` page, node + VLC verified, **no browser run yet**; still open: own-TTF upload, light + dark pair in the page | Opus (design), Sonnet (build) | - | M |
| T18 | Follow system light / dark (25), **phase 2** | Sonnet | T17 step 4, T14 (Linux launcher) | M |
| T19 | Font check for the configurator: which OFL fonts skins2 renders, tabular digits (report only) | Sonnet | - | S |
| T20 | Flatpak / Snap VLC paths and options, from docs and sources (report only, for 22a) | **DONE (report; mostly unverified, see brief)** | - | S |
| T24 | **DONE** (branch `worktree-agent-a8554c6a9e035c677`, not merged): generator reproducibility (`_truetype` forces `Layout.BASIC`; tar `filter=` + `GzipFile(mtime=0)`; sorted dirs / files) and T17 step 4 (`--pair`). Verified: two native builds byte-identical; Pyodide 314.0.7 + Pillow 12.2.0 via `tools/pyodide-spike/run.mjs ... 1 0` (no normalising wrapper) byte-identical to a native Pillow 12.2.0 build (a native Pillow 13.0 build differs in PNG bytes only). Release staged PNGs vs before: only `atlas_t0` and `t0_eq_bands` differ (glyph pixels, 0.8 % / 1.9 % of those images at 100 %, max channel delta ~200); looked right in VLC 3.0.20. Release `.vlt` files NOT rebuilt | Sonnet | T17 step 1 | M |
| T21 | Helper docking fixes: flashing, unpin, resize while docked, collapse with panels, item 15 (26, 27, 28, 31, T9) | **DONE** (untested on Windows; README "second Windows test" checklist) | - | M |
| T22 | Media Library off on Windows: file association overrides (30) | **DONE** (untested on Windows) | - | M |
| T23 | Skin: Windows bitmap rendering check + wider resize grip (29, 27) | **DONE** (Windows unverified) | - | S-M |
| T25 | Helper: keep the bar in place when the panels flip (32); find and fix why a taskbar click hides the player (33, 15) | **DONE** (confirmed on Windows) | - | M |

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
Done (2026-10-31): README, this file, `docs/` and `tools/README.md` checked against the code. Stale
numbers, duplicate sections and broken links fixed. For the next pass: check each claim against
`source/build_skin.py`, `taskbar/`, `linux/`, `lua/` and `tools/`; keep one section per topic and
link to it from elsewhere; do not change behaviour or code; keep the item numbers stable.

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
Done: `--bar-height`, `Titlebar-taskbar-NNN.vlt`, `VlcDock.BarHeight`, harness bar-height awareness, docs. To check on Windows: Setup picks the taskbar file when docking; the 36 px strip is centred in the taskbar; the pin click lands (pin lights); log line `barHeight=36`.

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
- `linux/setup.sh` (POSIX sh or bash, no sudo): detect native / Flatpak / Snap VLC and the matching vlcrc path, back up vlcrc as `vlcrc.before-titlebar`, set the same keys as the Windows setup (shared list, documented in architecture.md), and pick `Titlebar-NNN.vlt` from `GDK_SCALE`, `Xft.dpi` (`xrdb -query`) or `gsettings get org.gnome.desktop.interface scaling-factor`.
- Write `~/.local/share/applications/vlc-titlebar.desktop` (copy of the system `vlc.desktop` with `--no-media-library` added to `Exec`) and offer `xdg-mime default` for audio MIME types. Reason: the Linux launcher forces `--media-library` (`bin/vlc.c`), so vlcrc alone cannot remove the Media Library node.
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
3. Page (GitHub Pages): size, font (curated OFL list with licences shipped in the `.vlt`), light / dark, primary and secondary pickers; live preview (`preview_layout`); download; a note on which `Titlebar-NNN.vlt` name to use so Setup picks it up.
4. Light / dark pair (phase 2 option): the generator builds the same design twice (light and dark base, same primary / secondary colours, adjusted for contrast), theme button toggles them; checkbox "follow system setting" adds item 25 (helper on Windows, launcher wrapper on Linux).
- Keep the generator the single source of truth; no second renderer in JS.

### T19 - Font check (Sonnet, report only)
For T17 step 1. From the VLC 3.0.x skins2 source (`modules/gui/skins2/src/ft2_font.cpp` or similar) and by running the harness (T1): can skins2 load a `.ttf` / `.otf` named in `theme.xml`, how is the file looked up inside the `.vlt`, and are digits tabular? Test 4-6 OFL candidates (for example DejaVu Sans Mono, JetBrains Mono, Roboto Mono, Inter, Source Sans 3) by rendering the time at 100 % and 150 %. Report which work, licence file requirements, and file sizes. No repo changes except a short note in `docs/`.

### T20 - Flatpak / Snap facts (Haiku, report only)
For item 22a. Find, from VLC's Flathub and Snap packaging and docs: the vlcrc path, whether skins2 is shipped, how a skin in `~/.local/share/vlc/skins2` is seen inside the sandbox, and the right way to pass `--no-media-library`. Give links; mark anything not confirmed from a source as unverified.

Result (2026-10-31, Haiku, from docs only, nothing run): Flatpak (Flathub `org.videolan.VLC`, VLC 3.0.23): `--socket=x11` only, so XWayland; `--filesystem=host`; launcher `vlc.sh` runs `vlc.bin $VLC_ARGS "$@"`, so `flatpak run org.videolan.VLC --no-media-library %U` works (or `--env=VLC_ARGS=--no-media-library`). *Inferred, not confirmed:* vlcrc at `~/.var/app/org.videolan.VLC/config/vlc/vlcrc`, user skins at `~/.var/app/org.videolan.VLC/data/vlc/skins2`. *Unverified:* whether skins2 is compiled into the Flatpak and the Snap, Snap vlcrc location (`$SNAP_USER_COMMON/vlcrc`, i.e. `~/snap/vlc/common/`, per a 2018 commit), Snap dot-directory access, `--no-media-library` in Snap. Snap forces `QT_QPA_PLATFORM=xcb` (XWayland). Next step: test with real Flatpak / Snap VLC on a machine that has them.

### Flat style (default since 2026-10-31; `--classic` = old look)
Flat = solid fills, no bevels / glow (preview in `flat-preview/`). Strip: no separate volume slider any more - the time box is `[+/- mode switch | volume fill]` (click / drag / wheel sets the volume; `thumb_none` = no knob).
- Panning / balance in the EQ window: NOT possible in skins2 (no pan, balance or stereo-mode variable in `libskins2_plugin.so`; no custom actions). Would need a Lua extension or a VLC audio filter plus a separate UI.
