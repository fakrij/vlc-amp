# Titlebar skin: backlog

Last updated 2026-10-31. Status key:

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
| 7 | PL / EQ attached to the bar, same width | **DONE** | Panels are now part of the main window's layouts (8 layouts: strip/full x EQ x PL). | done |
| 7a | Taskbar mode with panels open | **DONE (skin) / helper untested on Windows** | Panels open above or below the bar, chosen with the arrow on the panel header (one skin file, no separate taskbar build). The helper reads the window region (`GetWindowRgn`) to see whether the bar is at the top or bottom and whether the strip or full player is showing. Rule checked against real VLC window shapes at 100 % and 150 %; compiled with Mono (C# 5). Placement itself still needs a run on Windows. | done |
| 7b / 13 | Same width with playlist open / closed | **DONE** | All 4 layouts (strip / full x panels below / above) have the same size, so VLC carries the dragged width between them (verified in `setActiveLayout`). Unused space is transparent and click-through (window region). PL / EQ are shown / hidden inside the layout via invisible 1x1 "flag" windows whose visibility VLC saves. Tested in VLC: drag +120 px, open PL+EQ, expand, flip, collapse, quit, restart: width, panels, side and time mode all restored. Cost: playlist height is fixed. | done |
| 14 | Choose where PL / EQ open (above / below), bar must not move | **DONE** | Arrow on the PL / EQ header flips both panels to the other side; remembered across restarts. The bar no longer moves when panels open or close. Flipping itself moves the bar to the other end of the window (one-time re-drag). Both panels share the side; a per-panel side would need 4 more layouts. | done |
| 1 | Double-click on a file opens a second VLC with the default skin | **DONE (untested on Windows)** | You start VLC from files / folders. `taskbar\Setup.cmd` writes `vlcrc`: `intf=skins2`, `skins2-last=<skin for the display scale>`, `one-instance=1`, `one-instance-when-started-from-file=1`, `playlist-enqueue=0`. Backs up the old file as `vlcrc.before-titlebar`. Cause of the bug: the instance started by the launcher was not started from a file and had `one-instance=0`, so it never listened for files and Explorer started a second, normal VLC. | done |
| 3 | Show elapsed time, countdown on click | **DONE** | Elapsed by default; click the time (strip or full player) for time left. The time background is a checkbox bound to a flag window, the texts use `focus="false"` so the click reaches it (an Image only reacts to double-click, a Text takes the whole rectangle: both verified in source). Remembered across restarts. Tested in VLC. | done |
| 4 | A-B loop in the full player | **LUA** or **PATCH** | skins2 has no A-B action (verified: no such action in the interpreter). VLC 3.0 has no A-B code at all (T5); any A-B loop must be written by us. A Lua interface can implement it by watching the input time and seeking back (*unverified*, expect ~100 ms jitter). The skin button still needs a way to talk to it, see section 2. | L |
| 5 | Replace the strip's slower/faster buttons with next/prev *folder* (speed buttons move to the full player, a layout-only change) | **LUA** or **PATCH** | No folder concept in skins2 actions (verified). A Lua interface can walk the playlist, compare the directory of each item URI, and jump (`vlc.playlist.gotoitem(id)`). Works for local files only. Button problem as in 4. | M-L |
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
| 18 | Light / dark theme + 3 colours each, switch in the full player title bar; then (6th list) one button only, more coordinated variations, own colour; then (7th list) minimal: keep the dark blue one | **DONE** | **Release skins now carry only Midnight** (user's choice; `DEFAULT_THEMES`; measured on Linux at 100 %: Midnight alone 136 MB RSS, + Paper 146 MB, all 11 240 MB, VLC's default skin 131 MB; at 150 %: 146 / 167 / 360 MB; start-up 1.7 / 1.7 / 4.6 s). The other themes stay in the generator (`--themes`, README "More themes"). Before that: 10 coordinated themes (6 dark, 4 light, each with its own tinted base, accent and LED) + Custom, rendered into the same layouts, shown via flag windows `th0..th10`; one button in the full player's title bar steps to the next theme (tooltip: current / next). Custom: any accent, recoloured exactly from a red reference (item 23). Memory now ~190 MB at 100 %, ~310 MB at 150 % (fill frames cut from 101 to 51 to keep it there); `--themes` builds a lighter subset. Earlier: 6 themes, sun / moon + dots. Needed two fixes found in VLC's source: explicit ids for every element (generated ids repeat after 999 and crash VLC) and bitmap atlases (`<SubBitmap>`: startup 12 s -> 1.5 s). Cost: ~150 MB RSS at 100 %, 240 MB at 150 %. Tested in VLC: switching, persistence, panels in all themes. | done |
| 11 | Tray icon for the helper (replace the Ctrl+Alt+Shift+V hotkey) | **DONE (T7, untested on Windows)** | NotifyIcon with Dock / Pin now / Open debug log / Quit; compile-checked. | done |
| 12 | Taller strip for the taskbar (e.g. 36 px), hide the pin in taskbar mode | **SKIN + HELPER** | Listed in the original open items. | S |
| 19 | Play / pause / prev / next when hovering VLC's taskbar button (Windows) | **HELPER** (needs 21) | Verified in the 3.0.x source: VLC's normal (Qt) interface adds these buttons (`ThumbBarAddButtons` in `qt/main_interface_win32.cpp`); skins2 does not. With skins2, the taskbar button belongs to a hidden 0 x 0 window at -200,-200 (`skins2/win32/win32_factory.cpp`), so the hover preview is empty and nothing in VLC would handle button clicks. Windows sends a button click only to the window that owns the taskbar button, inside VLC's process, so the helper cannot add the buttons to VLC's own button. Plan: the helper shows its **own** taskbar button, and VLC's is hidden (`skins2-taskbar=0`, already a helper setting). It carries 3 thumbnail buttons, the track progress drawn in the taskbar button (`SetProgressValue`), a play / pause overlay icon, a custom hover preview (title + time, `DwmSetIconicThumbnail`) and VLC's icon. With VLC's app id set on the window, it groups with a pinned VLC icon. Clicking the button brings VLC forward. Commands go to VLC through 21. | L |
| 20 | Windows media integration: media flyout (volume / media keys), Quick Settings media card, lock screen, hardware media keys | **DONE in Setup (T13, untested on Windows)** | Setup asks, finds VLC's architecture from vlc.exe's PE header, offers the VC++ runtime (Microsoft download, Authenticode checked), downloads the pinned v5.0.0 zip (SHA-256 = GitHub's release digests), copies the DLL (one UAC prompt; none for a writable portable VLC) and adds `win10smtc` to `extraintf` (module name from `plugin.h`, `PLUGIN_SHORTNAME`; `extraintf` is the option behind Qt's "Control interfaces" box). This is the "integrate it into Windows" option (System Media Transport Controls, SMTC). VLC 3 has none. The community plugin [vlc-win10smtc](https://github.com/spmn/vlc-win10smtc) adds it: GPL-3.0, maintained (v5.0.0, 2026-09-08, supports VLC 3.0.x and 4), Windows 10 1607+ / 11, x64 / x86 / ARM64 builds. It needs the Visual C++ 2022 redistributable matching VLC's architecture (VLC's, not Windows'). Install: copy `libwin10smtc_plugin.dll` to `<VLC>\plugins\misc` (Program Files, so admin once), then Advanced Preferences > Interface > Control interfaces > "Windows SMTC integration". It is a control interface, so it runs next to skins2: VLC starts `extraintf` / `control` modules whatever the main interface is (verified, `src/libvlc.c`). It creates its own hidden window, so it does not depend on the skin. The exact `extraintf` value (expected `win10smtc`) and the behaviour with skins2 are *unverified* until tested on Windows. Covers most of what 19 asks for in Windows' own UI; 19 adds the buttons on the taskbar hover itself. | M |
| 21 | Control channel from the helper to VLC (prerequisite for 19, and for menu-style controls in section 2 D) | **DONE (untested on Windows)** (T11; `VlcRemote` in `VlcDock.cs`, Setup keys in `vlc-taskbar.ps1`) | VLC's built-in web interface on localhost: `extraintf=http`, `http-host=127.0.0.1`, a random `http-password` written by Setup. `requests/status.json` gives play state, time, length, title / artist and the art URL; commands like `?command=pl_pause` / `pl_next` / `pl_previous` / `seek`. Alternative: the `rc` interface over TCP (`liboldrc_plugin`): simpler, but without a password any local program can control VLC. Works the same on Linux, but Linux has MPRIS (22b) anyway. **Built (T11)**, verified on Linux with real VLC 3.0.20 + skins2 (curl and the C# client under Mono: status, pl_pause, pl_next, pl_previous, pl_stop, seek, wrong password = 401, closed port): `http-host` and `http-port` are core options (vlcrc `[core]`, `src/libvlc-module.c`); `http-password` belongs to the Lua module (`[lua]`, `modules/lua/vlc.c`); `extraintf` is `[core]`. The web interface runs next to skins2. `status.json` has `time` and `length` in whole seconds only (a progress bar must interpolate between polls) and `information.category.meta` with `title` / `artist` / `filename` (no title tag: the helper falls back to the file name). A command's answer can still show the old state (next, stop), so read the status again. *Unverified (needs Windows)*: the whole helper side, and that the Windows Firewall shows no prompt for a loopback-only listener (expected none). An already running helper must be restarted after Setup to pick up the web interface settings. | S-M |
| 22 | Linux as a first-class platform (you use it on Linux too) | **LINUX** | The skin itself runs on Linux X11 today (every test and screenshot is from Linux VLC 3.0.20). Missing: setup, desktop integration, pin on start, and Wayland. Sub-items 22a-22d below. **Decided 2026-10-31:** distro unknown, so everything must be universal (any distro, any desktop, native / Flatpak / Snap VLC, X11 and Wayland via XWayland, only tools present everywhere). First goal: floating strip, pinned on start; no panel docking for now. | - |
| 22a | Linux setup script | **LINUX** | `linux/setup.sh`, counterpart of `Setup.cmd`: writes `~/.config/vlc/vlcrc` (`intf=skins2`, `skins2-last`, `one-instance=1`, `one-instance-when-started-from-file=1`, `playlist-enqueue=0`) and picks the scale from `GDK_SCALE` / `Xft.dpi` / GNOME `scaling-factor`. **Verified gotcha:** the Linux `vlc` launcher always adds `--media-library` and `--dbus` before your arguments (`bin/vlc.c`; Windows' `winvlc.c` does not), so `media-library=0` in vlcrc is overridden. Fix: a user copy of `vlc.desktop` in `~/.local/share/applications/` with `--no-media-library` in `Exec`, set as default for audio types with `xdg-mime`. Flatpak / Snap keep vlcrc elsewhere (`~/.var/app/org.videolan.VLC/config/vlc/`, `~/snap/vlc/common/.config/vlc/`); detect them. On Linux, one-instance goes through D-Bus. | M |
| 22b | Linux media controls (MPRIS): desktop media widget, media keys, lock screen, KDE taskbar hover buttons | **DONE in VLC (verified) / docs** | **Tested today with the skin:** VLC registers `org.mpris.MediaPlayer2.vlc` (the launcher forces `--dbus`), and `Next` and `PlayPause` sent over D-Bus worked. So GNOME's top-bar media card, KDE's media controller, `playerctl` and media keys work with no work from us. KDE Plasma's task manager also shows prev / play / next when hovering the app's taskbar entry, which is Linux's version of 19 (*unverified* that Plasma matches the skin window to the `vlc` desktop entry; check `WM_CLASS`). Metadata shows title / artist only for tagged files. To do: document it, and check the KDE hover on your machine. | XS |
| 22c | Linux: start pinned and dock into a panel | **LINUX** | X11: VLC's pin works (tested in Xvfb). Start pinned needs a small helper, as on Windows, that clicks the skin's pin once VLC's window appears (`xdotool`, the same click our test harness does). Docking into a panel depends on the desktop (GNOME has none); **postponed** (decision 2026-10-31: floating + pin first). | M |
| 22d | Wayland | **LINUX**, *unverified* | skins2 uses Xlib only, so on a Wayland session VLC's skin runs through XWayland. Expected to work: shaped (click-through) windows, moving the window, always-on-top on GNOME / KDE. Risks: fractional scaling (blurry or wrong size), "always on top" ignored by some compositors, a Linux helper unable to place windows outside XWayland. Needs a test on your machine. | ? |
| 23 | Custom accent colour: pick any colour for the Custom theme, Windows and Linux | **DONE (Linux tested / Windows untested)** | `custom-colour/`: `custom-colour.py` (Python 3 standard library only, own PNG decoder / encoder; Pillow only as a speed-up, `--no-pil`; picker: `zenity`, `kdialog`, `yad`, tkinter, then the terminal; `--reset`; atomic rewrite of the `.vlt`) and `Custom colour.cmd` + `custom-colour.ps1` (Windows PowerShell 5.1, C# 5 pixel loop with `System.Drawing` `LockBits` `Format32bppArgb`, `ColorDialog`, built-in `tar.exe`). Uses `custom-ref/` of the `.vlt` (see `docs/architecture.md`, Custom theme); a `.vlt` built before that existed is skipped with a message. **Verified on Linux**: recoloured 100 / 150 / 200 % skins to `#33ff99` with the pure-Python path and compared with the generator's own `--custom "#33ff99"` build: every `img/` pixel identical (max channel difference 0 over 1.1 / 2.6 / 4.8 million pixels, alpha identical), `theme.xml` byte-identical, all other `.vlt` members byte-identical; pure path == Pillow path == generator for 8 colours (incl. `#000000`, `#ffffff`, `#ff0000` = identity); PNG decoder tested with all 5 filters (and the skin's PNGs use all of them) plus error cases; time 0.3 s (100 %), 0.9 s (150 %), 1.6 s (200 %) per `.vlt` pure, 0.4 s with Pillow; real VLC 3.0.20: recoloured skin, Custom theme shows the chosen green. C# class compiled with Mono `mcs -langversion:5` and run under Mono + libgdiplus: PNG output identical to the generator's, XML identical. *Unverified (needs Windows)*: the PowerShell script as a whole (`tar.exe` pack / unpack, the colour dialog, `[IO.File]::Replace`), the C# class on Microsoft's GDI+ (expected the same: `Format32bppArgb` is straight alpha), and that VLC reads the `tar.exe`-packed file (`--format ustar`, files only, as the generator writes). The GUI pickers `zenity` / `kdialog` / `yad` / tkinter were only tested with stand-in scripts for their output format. | done |
| 24 | Online configurator for the skin's look | **PHASE 2 (spec from user)** | A static web page that builds one `.vlt`: either **one theme** (memory stays at the Midnight level) or **one theme as a light + dark pair with a switcher** (the round theme button in the full player; ~+10 MB at 100 %, +20 MB at 150 %), optionally **following the system's light / dark setting** (item 25). Options: **size** (display scaling 100 / 125 / 150 / 200 %, default from the browser's `devicePixelRatio`), **font** (curated open-licence fonts, OFL; times need tabular / monospace digits; optional own TTF), **light / dark** base, **primary colour** (accent: LCD text, progress, active buttons), **secondary colour** (indicator LEDs: pin, PL / EQ lights, toggles). Preview, then download. Route: run `build_skin.py` in the browser with Pyodide (Pillow is available there), so the generator stays the single source of truth. Needs generator options first: `--font`, `--mode`, `--accent`, `--led` (today themes are named seeds). *Unverified*: Pyodide load size (~10-15 MB) and build time per scale. Brief: T17. | M |
| 25 | Follow the system's light / dark setting (for a light + dark pair) | **PHASE 2, HELPER (Windows) + launcher (Linux)** | skins2 cannot read the OS setting. But VLC stores each theme flag window's visibility in `skins2-config` in vlcrc (seen in a test run: `["th0" "th0-l" 639 511 1 1 0]["th1" "th1-l" 639 511 1 1 1]`, last field = shown), and reads it at start. So: **at VLC start** a helper / launcher rewrites th0 / th1 in vlcrc while VLC is not running. Windows: `HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize\AppsUseLightTheme` (helper in `-Watch` mode, before VLC starts; but VLC started from Explorer starts without the helper getting a chance first, so this only works for the next start, or via a launcher). Linux: `gdbus call` to the XDG desktop portal (`org.freedesktop.appearance` `color-scheme`), fallback `gsettings get org.gnome.desktop.interface color-scheme`; a wrapper in the `.desktop` file (22a) runs before VLC. **While VLC runs** (system switches at sunset): the helper posts a click on the theme button (like `PinOnce`), which only exists in the full player; the strip would need a small switch too (design question). VLC rewrites `skins2-config` when it exits, so the helper must not edit it while VLC runs. *Unverified*: posted clicks on Windows (same risk as N1). | M |

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
| EQ presets | yes (*unverified API*) | no | yes | yes (via A) | same |
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

1. **Windows test of the setup:** run `Setup.cmd`, then open a file from Explorer: skin, single window, Media Library gone, player pinned (pin lit).
2. **Fix 15** (taskbar click hides the player): needs the answers to its questions.
3. **Strip layout:** move slower / faster to the full player (part of 5). That frees 48 px in the strip for the title or for the folder buttons later.
4. **Decision point:** features 4, 5, 2 (A-B loop, folder jump, EQ presets). Choose between A + D (Lua script + hotkeys / tray menu, no skin buttons) and C (patched skins2 plugin with real buttons).
5. **Playlist columns (8):** only if C is chosen.
6. **Windows integration:** SMTC plugin in Setup (20, T13) first: it is cheap and covers media keys, the flyout and the lock screen. Then the control channel (21, T11), then the taskbar hover buttons (19, T12).
7. **Linux:** after your answers to question 3: setup script (22a, T14), MPRIS docs (22b, T15), then pin / panel docking and the Wayland check (22c, 22d, T16).

Agent-sized work packages for these steps are in section 5.

## 4. Open questions

1. Items 4, 5, 2: is a hotkey / tray-menu solution acceptable, or do you want real buttons in the skin (patched plugin)?
2. Item 15: is the helper running, does the player come back after a moment, and what exactly was clicked?
3. ~~Linux (22)~~ **Answered 2026-10-31:** distro unknown, make it universal; floating + pinned first, no panel docking.
4. ~~Item 20~~ **Answered 2026-10-31:** yes, Setup downloads and installs the SMTC plugin.

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
| T1 | Test harness in the repo | **DONE** (merged; `tools/`) | - | M |
| T2 | Move slower / faster to the full player | Sonnet | T1 | S |
| T3 | Helper debug log (for 15) | **DONE** (merged) | - | S |
| T4 | Docs consistency pass | Haiku | after others | XS |
| T5 | Lua API fact check (for 4, 5, 2) | **DONE** (merged; `docs/lua-api-notes.md`) | - | S |
| T6 | Lua interface prototype: A-B loop, folder jump, EQ presets via hotkeys | Sonnet | T1, T5, decision on 4/5/2 | L |
| T7 | Tray icon for the helper (11) | **DONE** (merged) | - | M |
| T8 | Taller taskbar strip option (12) | Sonnet | T1 | M |
| T9 | Fix 15 (taskbar click hides the player) | Opus | Windows answers + T3 log | M |
| T10 | Patched skins2 feasibility spike (option C) | Opus | decision on 4/5/2 | XL |
| T11 | Control channel: helper talks to VLC's web interface (21) | **DONE (untested on Windows)** | T1 | S-M |
| T12 | Helper's own taskbar button with hover buttons, progress, overlay (19) | Opus | T11 | L |
| T13 | SMTC plugin install in Setup (20) | **DONE** (untested on Windows) | - | M |
| T14 | Linux setup script (22a) | Sonnet | T1 | M |
| T15 | Linux docs: MPRIS, setup, limits (22b) | Haiku | T14 | XS |
| T16 | Linux pin on start + Wayland check (22c, 22d; docking postponed) | Opus (design), Sonnet (build) | T14 | M |
| T17 | Online configurator (24), **phase 2** | Opus (design), Sonnet (build) | - | M |
| T18 | Follow system light / dark (25), **phase 2** | Sonnet | T17 step 4, T14 (Linux launcher) | M |

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
