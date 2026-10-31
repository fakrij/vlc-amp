# Titlebar - VLC skin

A music skin for VLC (Windows/Linux, skins2 engine) whose main window collapses
into a 24 px strip that fits into a window title bar or the taskbar.

## Install (Windows, recommended)

1. Copy this folder somewhere permanent (for example `Documents\VLC-skin`);
   the setup points VLC at the skin file in it.
2. Close VLC and double-click **`taskbar\Setup.cmd`**. It:
   - picks the skin file for your display scaling (`Titlebar-100/125/150/200.vlt`),
   - makes VLC use it also when you double-click a file or folder in Explorer,
   - sends files you open to the running player (no second VLC window),
   - removes the useless "Media Library" entry from the playlist,
   - asks whether to start the helper with Windows: it pins the player on top
     each time VLC starts, and optionally docks it in the taskbar.
   Your previous VLC settings are saved as `%APPDATA%\vlc\vlcrc.before-titlebar`.

Undo: close VLC, copy `vlcrc.before-titlebar` back over `vlcrc`, and delete
"Titlebar VLC helper" from the Startup folder (Win+R, `shell:startup`).

## Install (manual, any OS)

1. Pick the file matching your display scaling:
   `Titlebar-100.vlt`, `Titlebar-125.vlt`, `Titlebar-150.vlt`, `Titlebar-200.vlt`.
2. VLC > Tools > Preferences > Interface > Look and feel: **Use custom skin**,
   choose the .vlt file, Save, restart VLC.

VLC's own menu (open media, playlist, preferences, skins) is the menu button
in the full player: expand the strip, click the menu icon top right.
To go back to the normal VLC look: menu > Interface > Preferences >
Use native style, then restart VLC.

## Controls

Strip, left to right: grip (drag to move), expand, previous, slower,
play/pause, faster, next, title (scrolls when too long; it is also the seek
bar: the played part fills it, click anywhere in it to jump there or drag,
mouse wheel = 5 % back / forward), time (elapsed;
click it for time left, click again for elapsed; fits tracks over an hour),
volume,
playlist, equalizer, always on top, resize grip (drag the right edge).
Drag & drop files onto any window to play them.

Full player: menu, always on top, collapse, minimize, quit. Display: big
time (elapsed or time left, click to switch, same setting as the strip) with
the other value / total under it; title, bitrate and sample rate, shuffle /
loop / repeat-one toggles and playback speed. Then seek bar, transport,
volume, PL, EQ.

PL and EQ open attached to the player bar (strip or full), inside the same
window, so they always have the bar's width and move with it. The bar does not
move when they open or close. Strip, full player and panels all share one
width: drag the right edge of any of them.

**Above or below:** the small arrow on the PL / EQ header moves both panels to
the other side of the bar (below suits a title bar at the top of the screen,
above suits the taskbar). The bar moves to the other end of the window when you
flip, so drag it back once. VLC remembers the side, the open panels, the time
mode and the width across restarts.

Limits: the playlist has a fixed height (all layouts must have the same size
for VLC to keep the width); change it with `LH` in `build_skin.py`. The window
is invisible where nothing is drawn (clicks go through), so it does not snap
to screen edges.

## Width

- Drag the right edge of the strip. VLC remembers the width.
- Or rebuild with a different default width:
  `python3 build_skin.py --width 480 --scale 1.25 --preview`
  (needs Python 3 and Pillow).

## Credits

Font: DejaVu Sans Mono (license in fonts/LICENSE-DejaVu.txt).

## Taskbar mode (player docked in the taskbar)

The `taskbar` folder has a small helper that places the strip inside the
Windows 11 taskbar, just left of the Start button, and keeps it there.

1. Free the space: Settings > Personalization > Taskbar > **Widgets: Off**.
2. Either run `Setup.cmd` and answer Yes to both questions (the helper then
   starts with Windows and docks VLC whenever it runs, also when started from
   a file), or close VLC and double-click **`taskbar\VLC in taskbar.cmd`**,
   which starts VLC with the skin and docks it for this session.
   (A console window flashes for a moment; that is PowerShell starting.)

What it does:
- Strip sits in the taskbar, vertically centred, its right edge 8 px left of
  Start. It follows Start when taskbar icons shift.
- Flip the panels to open *above* once (arrow on the PL / EQ header); VLC
  remembers it. The strip then stays in the taskbar with PL / EQ above it.
  The expanded player sits just above the taskbar.
- The helper reads which part of VLC's window is visible, so it works with
  every layout without settings.
- Stays above the taskbar even after you click the taskbar.
- Steps behind full-screen apps (games, full-screen video) and comes back after.
- Hides VLC's own taskbar button (the player is already there).
- Pins VLC on top once it starts (it clicks the skin's pin button, so the pin
  lights up). VLC itself always starts unpinned.
- Quits when VLC quits (except when started with Windows: then it waits for
  the next VLC).
- **Ctrl+Alt+Shift+V** undocks / re-docks (undocked, you can drag windows freely).
- The skin's own pin button has no effect while docked.
- A tray icon (dark square with a cyan bar, tooltip "Titlebar VLC helper") has a
  right-click menu: **Dock in taskbar** (checked = docked, same as the hotkey;
  greyed out with `-NoDock`), **Pin VLC on top now** (clicks the skin's pin
  button again, which toggles it) and **Quit helper**. Set `$TrayIcon = $false`
  in `vlc-taskbar.ps1` to turn it off. Windows may hide the icon under the `^`
  overflow arrow until you drag it out.

Settings are at the top of `taskbar\vlc-taskbar.ps1`: which skin file (`auto` =
by display scaling), dock position (`start`, `left`, `right` = next to the
tray icons), gap, vertical nudge, start pinned.

It is still VLC's own window kept in place, not part of Explorer, so it
cannot be pinned like an app icon. To start it with Windows, put a shortcut to
`VLC in taskbar.cmd` in the Startup folder (Win+R, `shell:startup`).
