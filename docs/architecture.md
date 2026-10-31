# How the Titlebar skin works

For people changing the skin, the generator or the Windows helper. User
documentation is in the [README](../README.md); open work in
[BACKLOG.md](../BACKLOG.md).

Everything here was checked against the VLC 3.0.x source
(`modules/gui/skins2`, branch `3.0.x`) or by running VLC 3.0.20. skins2 is
old and lightly documented, so **check the source before relying on any
behaviour**; several "obvious" assumptions turned out wrong (see
[Pitfalls](#skins2-pitfalls-we-hit)).

## Overview

```
source/build_skin.py  --(Pillow)-->  Titlebar-NNN.vlt  (tar.gz: theme.xml + img/*.png + fonts/)
                                          |
                    VLC skins2 interface  <--  vlcrc (intf=skins2, skins2-last=...)  <--  taskbar/Setup.cmd (Windows)
                                                              linux/setup.sh (Linux)
                                          |
               taskbar/VlcDock.cs (Windows) moves / pins VLC's window, read via its window region
               linux/titlebar-pin.py (Linux X11 / XWayland) pins it on start by clicking the skin's pin
```

- **The skin** is generated, never hand-edited. `build_skin.py` draws every
  bitmap with Pillow (supersampled 4x, then reduced), writes `theme.xml`, and
  packs both into a `.vlt` (a gzipped tar). One `.vlt` per display scaling:
  `--scale` multiplies every logical pixel (`P()`), so the 150 % skin is drawn
  at 150 %, not scaled up from 100 %.
- **The helper** (`taskbar/`) is Windows-only: PowerShell 5.1 loads
  `VlcDock.cs` with `Add-Type`, so it must stay C# 5.

## The main window: 4 layouts of one size

skins2 only carries a dragged size from one layout to the next when both have
the same original size and limits (`GenericLayout::isTightlyCoupledWith`,
used in `TopWindow::setActiveLayout`). So all layouts of the main window are
**the same size**: 556 x 436 logical px, the full player (122) + EQ (116) +
playlist (198) stacked.

| Layout | Bar position | Panels |
|---|---|---|
| `strip-dn` (default) | top | below the strip |
| `strip-up` | bottom | above the strip |
| `full-dn` | top | below the full player |
| `full-up` | bottom | above the full player |

Where nothing is drawn the pixels are transparent. skins2 turns the drawn
pixels into the window's shape (`SetWindowRgn` on Windows, the X Shape
extension on X11), so the unused area is invisible and click-through.
Consequences: the window cannot snap to screen edges (its invisible edges
would snap; `magnet="0"`), and flipping between "dn" and "up" moves the bar
to the other end of the window.

Expand / collapse and the flip arrows are `main.setLayout(<id>)` actions.

### Bar height (`--bar-height`)

The window height `HT` (436) does not depend on the strip height: a taller strip
only changes what is drawn inside it, so all four layouts stay the same size
(strip-up puts the bar at `HT - bar`). `bar_metrics(bh)` in `build_skin.py`
derives the strip's parts from `bh` (24 gives the original numbers; the default
build is identical, member by member, to the one before the option existed):
button height `bh - 6` (3 px margin), icon size `12 + (bh-24)//4`, PL / EQ label,
LCD and title window height, the title window's play head, the strip font
(`lcdbar`, `12 + (bh-24)//6`, only declared when it differs from `lcd12`; used
for title and time), the volume slider (own bitmap and thumb `thumb_vs`), grip
rows and the resize grip. Widths do **not** grow, so the right-edge offsets
(`R(34)` pin, `R(62)` / `R(90)` EQ / PL, `R(160)` volume) and the pin's x stay
as they were; only the time box widens when the bigger font needs it
(`tw`, 74 px at 36), which also raises `MIN_W` by the same amount (430).

Build names carry the height: `Titlebar-NNN` (24), `Titlebar-taskbar-NNN` (36,
`BAR_TASKBAR`), `Titlebar-bar<N>-NNN` (any other); `ThemeInfo` reads
"Titlebar 150% bar 36". The helper gets the height from the file name
(`Get-SkinInfo` in `vlc-taskbar.ps1`, `$TaskbarBarHeight` = 36 for `taskbar`),
and `Setup` / the helper pick the `taskbar` file when docking if it exists
(`Get-SkinPath -Taskbar`). The test harness reads the same names
(`skin_bar` in `tools/vlc-test.sh`).

## State without layouts: flag windows

Opening PL / EQ, the time mode and the theme are not layouts (that would
multiply them). They are **tiny 1 x 1 windows** with no visible pixels:
`eqflag`, `plflag`, `tflag`, `th0` ... `th5`. Shown = on.

- Controls test them with `visible="plflag.isVisible and not eqflag.isVisible"`
  (skins2 supports `and`, `or`, `not`; no parentheses; `not` binds tightest).
- Buttons switch them: `plflag.show()`, `plflag.hide()`; actions chain with `;`.
- VLC saves every window's visibility in `skins2-config`, so the state
  survives restarts for free.
- The playlist is placed twice (next to the bar, and beyond the EQ) with
  complementary visibility, because a control cannot move.

## Themes

`THEME_SEEDS` in `build_skin.py`: 10 themes plus Custom, each given by a few
seed colours: dark or light base template (`DARK` / `LIGHT`) tinted with a hue
and saturation (`base_palette`), an accent colour and an LED colour.
`accent_palette()` derives the LCD background, dim and bright text, progress
fill, playlist rows and so on from the accent, **only by mixing it with
neutral colours** (black, white, grey); the Custom theme depends on that (see
below). `apply_theme(i)` sets the module-level colour names (`CYAN*` are the
accent colours, named after the default theme). `--themes` builds a subset
(`set_themes`); the release skins use `DEFAULT_THEMES` (Midnight only), and
with a single theme the theme button is left out. The generator renders the whole skin once per theme, into the
same 4 layouts:

- bitmap ids get the prefix `t<i>_` (`Skin.prefix`, applied by `Skin.add` and
  the `Layout` methods);
- every control of theme `i` gets `th<i>.isVisible and ...` (`Layout.theme_vis`); theme 0 instead
  gets `not th1.isVisible and ... not th<last>.isVisible`, so a saved state with no theme flag
  shown (nothing drawn = no window shape = invisible and unmovable) falls back to theme 0;
- theme `i`'s button (full player title bar) selects theme `i + 1` (wrapping
  around) with `th<i+1>.show();th<j>.hide();...` (shows first, so something is
  always drawn).

Cost: about 2400 bitmaps and 4000 controls with 11 themes. See the next sections for what
that broke and how it is handled.

### Custom theme

One theme, "Custom" (`THEME_SEEDS`), is meant to be recoloured after the build.
It is drawn with the pure red accent `CUSTOM_REF` (`#ff0000`) on a neutral grey
base, and the palette only ever mixes the accent with neutral colours, so every
pixel is `grey + t * red` (`R = n + t*255`, `G = B = n`). The build asserts that.
Any accent `(ar, ag, ab)` follows exactly:

```
R' = G + (R - G) * ar / 255      G' = G + (R - G) * ag / 255      B' = G + (R - G) * ab / 255
```

alpha unchanged, clamped to 0..255 (`recolour()` in `build_skin.py`). The same
formula applies to the `#RRGGBB` attributes in `theme.xml`, but only on lines
that contain `visible="th<slot>.isVisible` (`recolour_xml()`: the Custom
theme's controls). `--custom` sets the accent of a build (`CUSTOM_DEFAULT`,
`#b48cff`).

So that a finished `.vlt` can be recoloured without the generator, it carries
`custom-ref/`: `slot.txt` (`slot=<N>`, `accent=#rrggbb`, the current accent),
`theme.xml` before recolouring, and `img/` with the Custom theme's images
(`atlas_t<N>.png`, `t<N>_*.png`) in red. Recolouring writes every file of
`custom-ref/img` recoloured to `img/` (same name), `recolour_xml(custom-ref/theme.xml)`
to `theme.xml`, and the new accent to `slot.txt`; everything else in the
`.vlt` stays byte-identical. VLC reads the `.vlt` at start, so a restart is
needed. The tools in `custom-colour/` do exactly this:

- `custom-colour.py`: Python 3 standard library only (own PNG decoder for
  8-bit RGBA, all five filters, and encoder; uses Pillow when importable,
  `--no-pil` forces the pure path). The recolour maps every distinct pixel
  value once (cached), so it needs about 1 s for the 200 % skin.
- `custom-colour.ps1` (+ `Custom colour.cmd`): Windows PowerShell 5.1, the
  pixel loop is C# 5 (`Add-Type`, `System.Drawing` `LockBits` with
  `Format32bppArgb`, which is straight alpha), unpack / pack with the built-in
  `tar.exe` (explicit file list with `-T`, so there are no folder entries, as
  in the generator's tar).

## Bitmaps: atlases

VLC starts an image decoder module for every `<Bitmap>`. With 1400 separate
PNGs, startup took 12 s. Small bitmaps are now packed into one atlas per
theme (`pack_atlases`, shelf packing) and cut out with `<SubBitmap>`:
1.5 s. VLC keeps the atlas in memory next to the cut-out copies, so large
bitmaps (the progress fill frame sheets, wide stretch pieces; > 16384 px)
stay separate files to avoid storing them twice.

Memory (RSS of VLC on Linux, 8 s after start, `smaps_rollup`): VLC's own default
skin 131 MB at 100 %; Midnight alone 136 MB, Midnight + Paper 146 MB, all 11
themes 240 MB (150 %: 146 / 167 / 360 MB). About 100 MB is VLC and its
libraries, shared with any skin; each theme adds ~10 MB at 100 %. Most of the per-theme cost is the fill frame
sheets (`title_fill`, `seek`, volume): `CtrlSliderBg` copies its whole frame
sheet into each slider control, so a sheet used in 2 layouts is held 3 times.
Hence `FILL_FRAMES = 51` (2 % steps; 101 frames cost 80 MB more at 150 %).
Start-up grows by roughly 0.4 s per theme (measured under Xvfb).

## Element ids

**Every element has an explicit id** (`next_id`), and the build asserts that
none is missing or repeated. Reason: VLC 3.0's `SkinParser::generateId()`
writes generated ids (`_ReservedId_N`) into a 5-byte buffer with
`snprintf(.., 4, ..)`, so only 3 digits survive. After 999 unnamed elements
the ids repeat, the later control replaces the earlier one in the theme's
control map, the earlier one is freed while its layout still uses it, and VLC
crashes in `GenericLayout::refreshRect`. Two themes stayed under the limit,
three crashed.

## Time readouts

VLC formats the skin's time variables itself (`vars/time.cpp`): elapsed =
`time / 1 s`, total = `length / 1 s`, time left = `(length - time) / 1 s`, each
truncated on its own. Time left therefore ticks at a different moment than
elapsed (offset by the fraction of a second in the track length) and can be one
second off from total - elapsed. The full player shows only one of them big
plus the total ("of 5:16"), never elapsed and time left side by side.

## Clickable things

- An `<Image>` runs `action` only for `move` / `resize*`; any other command runs
  on **double-click** (`CtrlImage::handleEvent`). For a single click use a
  `<Button>` or `<Checkbox>`.
- A `<Text>` takes clicks over its whole rectangle (`CtrlText::mouseOver`).
  Set `focus="false"` to let the click reach what is under it. The time
  readouts (checkbox background + text) and the seek-by-title (slider +
  text) rely on this.
- A slider background: a click jumps there and starts dragging; the wheel
  steps 5 % (`CtrlSliderBg`, `VarPercent` step 0.05).
- Resize actions: only `resizeS`, `resizeE`, `resizeSE` exist.
- Keyboard shortcuts reach VLC through the dialogs provider (`Dialogs::sendKey`,
  normally the Qt module), so they need Qt installed (standard on Windows).

## Rendering notes

- X11 draws bitmaps without alpha blending; Windows uses `AlphaBlend`. Semi
  transparent pixels look black on Linux. Window outlines use hard alpha
  (`Canvas.done(hard_edges=True)`), small text is drawn on opaque crops of
  the background (`label_on`), and the progress fill frames have hard edges.
- An `<Image>`'s size in the default layout is its bitmap's size; stretching
  only comes from `lefttop` / `rightbottom` anchors. That is why stretch pieces
  (`hslice`, `nslice`) are full width and cannot be shrunk to a 1 px column.
- Windows extracts the `.vlt` to disk; on its case-insensitive file system
  `b_x.png` and `B_x.png` collide. Ids differing only by case are rejected by
  the build.

## vlcrc keys (what both setups write)

`taskbar/vlc-taskbar.ps1 -Setup` (Windows) and `linux/setup.sh` (Linux) write
the same settings into VLC's `vlcrc`. VLC ignores the `[section]` headers when
it reads the file (`src/config/file.c` skips lines starting with `#` or `[`),
but both setups keep every key under the section VLC itself writes it in. Both
rewrite every line of a key (the commented default `#key=...` and any active
one; a `vlcrc` written by VLC has both) and only add the key to its section
when no line exists. Colon lists are merged, never replaced.

| Key | Section | Value | Windows | Linux | Why |
|---|---|---|---|---|---|
| `intf` | core | `skins2` | yes | yes | The skin instead of the normal window |
| `skins2-last` | skins2 | absolute path of `Titlebar-NNN.vlt` | yes | yes | Which skin; NNN from the display scale |
| `one-instance` | core | `1` | yes | yes | Files opened from the file manager go to the running player (Windows: window message; Linux: D-Bus, see below) |
| `one-instance-when-started-from-file` | core | `1` | yes | yes | Same, for launches with `--started-from-file` (what the launchers pass) |
| `playlist-enqueue` | core | `0` | yes | yes | ...and the file starts playing |
| `media-library` | core | `0` | yes | yes | No "Media Library" node in the playlist. **On Linux the `vlc` program overrides it**, so the Linux setup also writes a launcher with `--no-media-library` |
| `skins2-taskbar` | skins2 | `1`, or `0` when docked | yes | no | Windows-only option (it does not exist in VLC's Linux build) |
| `extraintf` | core | colon list: `http`, plus `win10smtc` (Windows, media controls) or `luaintf` (Linux, when `lua/intf/titlebar.lua` exists) | yes | yes | Control interfaces started next to skins2 |
| `http-host` | core | `127.0.0.1` | yes | yes | Web interface for this computer only |
| `http-port` | core | `48080` | yes | yes | An unusual port |
| `http-password` | lua | random, 24 letters and digits; kept if already set | yes | yes | Locks the web interface. Windows: the helper's control channel uses it. Linux: nothing uses it yet, it is there for later helpers (`--no-web` skips the three web keys) |
| `lua-intf` | lua | `titlebar` | no | with the Lua script | Which script the `luaintf` interface runs (`modules/lua/vlc.c`: `lua-intf` and `lua-config` belong to the primary `lua` module) |

On Linux more keys can be added without changing `setup.sh`: see
`lua/vlcrc-keys.txt` under "Lua extras" below.

## The Linux setup (`linux/setup.sh`)

POSIX `sh` + `awk` / `sed` / `grep` (run with dash and bash; `shellcheck` was
not available when it was written). Python is only needed for the optional
`linux/titlebar-pin.py` (start pinned). Every path honours `HOME`,
`XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME` and `XDG_DATA_DIRS`, so it
can run against a private home (the test harness does).

**Which VLC.** Native: `command -v vlc`, unless the path is under `/snap/`
(snapd puts `/snap/bin` in `PATH`). Flatpak: `flatpak info org.videolan.VLC`.
Snap: `snap list vlc`. With several it asks (`--yes` takes the first; `--vlc`
chooses). It refuses to run while a VLC of the user is running (it scans
`/proc/*/comm` for `vlc` / `vlc.bin`, and `flatpak ps`), because VLC rewrites
`vlcrc` on exit. `--ignore-running` overrides (the tests need it: other agents'
VLCs run at the same time).

| Flavor | `vlcrc` | Lua dir (`lua/intf`) | Status |
|---|---|---|---|
| Native | `${XDG_CONFIG_HOME:-~/.config}/vlc/vlcrc` | `${XDG_DATA_HOME:-~/.local/share}/vlc/lua/intf` | Verified: VLC's user config / data dir, and `vlclua_dir_list` (`modules/lua/vlc.c`) looks in the user data dir first |
| Flatpak | `~/.var/app/org.videolan.VLC/config/vlc/vlcrc` | `~/.var/app/org.videolan.VLC/data/vlc/lua/intf` | Flatpak's sandbox `XDG_CONFIG_HOME` / `XDG_DATA_HOME` (documented Flatpak behaviour); **not run on a real Flatpak**. The Flathub manifest has `--filesystem=host` (the skin file is readable) and `--own-name=org.mpris.MediaPlayer2.vlc` |
| Snap | `~/snap/vlc/common/vlcrc`; older snaps: `~/snap/vlc/common/.config/vlc/vlcrc`, `~/snap/vlc/current/.config/vlc/vlcrc` (the first that exists wins) | `~/snap/vlc/current/.local/share/vlc/lua/intf` | The first is verified in VLC's snap wrapper (`extras/package/snap/vlc-snap-wrapper.sh` runs `vlc --config=$SNAP_USER_COMMON/vlcrc`). **The other two and the Lua dir are unverified.** The snapcraft.yaml has no `network-bind` plug, so the web interface may not start in the Snap. The Snap reads only non-hidden files under `$HOME`; the setup warns when the skin is elsewhere |

A missing `vlcrc` is created (mode 0600, as VLC does) with only our keys under
their `[section]` headers; VLC fills in the rest at the next exit. An existing
one is backed up once as `vlcrc.before-titlebar` (`cp -p`), edited in a
temporary copy and written back in one go. Edits are done by the `rc_edit` awk
function (values go through the environment so backslashes survive). Running
the setup twice changes nothing.

**Scale.** `--scale N` (`150` or `1.5`), else the first of these that gives a
number: `GDK_SCALE`, `QT_SCALE_FACTOR`, `Xft.dpi` / 96 from `xrdb -query`,
`kreadconfig6` / `kreadconfig5 --group KScreen --key ScaleFactor`, GNOME
`scaling-factor` and `text-scaling-factor` (`gsettings`, only values above 1).
All values found are printed. The nearest of 100 / 125 / 150 / 200 is used;
nothing found means 100. skins2 draws in real X pixels, so which file is right
under XWayland with compositor scaling is unverified.

**Media Library gotcha.** The Linux `vlc` program (`bin/vlc.c`) builds its
argument list as `--no-ignore-config --media-library [--dbus] <your arguments>`
(`--dbus` when built with D-Bus; Windows' `winvlc.c` adds none of them), so
`media-library=0` in `vlcrc` loses. A later `--no-media-library` on the command
line wins over the earlier `--media-library`. Hence the launcher
`~/.local/share/applications/vlc-titlebar.desktop`: a copy of the system
launcher (`vlc.desktop`, Flatpak's `org.videolan.VLC.desktop`, Snap's
`vlc_vlc.desktop`; searched in `XDG_DATA_DIRS` plus the usual Flatpak and snapd
export dirs) with `Name=VLC (Titlebar)`, `--no-media-library` inserted before
`--started-from-file` (or the first file placeholder) in every `Exec=`, the
translated `Name[..]` lines and `DBusActivatable` removed (a launcher that
activates over D-Bus would skip `Exec`), and the marker line
`X-Titlebar-Skin=1` (uninstall only deletes a file that has it). With no system
launcher, a basic one is generated (Flatpak: `flatpak run --file-forwarding
org.videolan.VLC --no-media-library --started-from-file @@u %U @@`).
`update-desktop-database` runs on the folder when present. Checked with the
harness: started like plain `vlc` the playlist shows a "Media Library" node,
started through the launcher's `Exec` it does not.

**One instance on Linux** goes through D-Bus: the first VLC owns
`org.mpris.MediaPlayer2.vlc`; a second one started with a file hands it over
and exits with code 0, the first one's playlist grows and plays the new file.
It needs a session bus (checked inside `dbus-run-session`).

**Default app.** Optional: `--default-player`, `--no-default-player`, a prompt
(`--yes` answers yes; with no terminal and no flag it is skipped). For each
`audio/*` type in the launcher's `MimeType=` it runs `xdg-mime default
vlc-titlebar.desktop <type>`. `inode/directory` and the video types are left
alone on purpose: as the default for folders VLC would open every time a folder
is opened in the file manager. The previous default (`xdg-mime query default`,
which also reports fallbacks) is stored per type in the state file.

**State and undo.** `~/.local/state/titlebar-vlc-skin/linux-setup.state`
(`flavor`, `rc`, `rc_created`, `desktop`, `lua`, `mime` and `pin` lines) records
what was changed. `--uninstall` refuses while VLC runs, then: saves the current
`vlcrc` as `vlcrc.titlebar-removed` and restores `vlcrc.before-titlebar` byte
for byte (when there was no `vlcrc` before the setup, the current one is moved
to `.titlebar-removed` and VLC makes a new one); puts each audio type back to
its recorded default, or removes our line from `mimeapps.list`, if the default
is still ours (this runs before the launcher is deleted, because `xdg-mime`
only reports a default whose file exists); removes the launcher and the Lua
files; runs `titlebar-pin.py --uninstall-autostart`.

**Start pinned.** If `linux/titlebar-pin.py` exists the setup asks (or
`--pin-autostart` / `--no-pin-autostart`; `--yes` means yes) and runs
`python3 linux/titlebar-pin.py --install-autostart`. The autostart entry points
at that file's real path, so the setup must be run again after the folder is
moved. The setup neither copies nor edits that script.

**Lua extras.** If `lua/intf/titlebar.lua` exists, all `lua/intf/*.lua` are
copied to the flavor's Lua dir, `luaintf` is merged into `extraintf` and
`lua-intf=titlebar` is set (section `lua`). `lua/vlcrc-keys.txt`, if it exists,
is read line by line (blank lines and lines starting with `#` are skipped);
the format is

```
<section> <key>=<value>
```

Section, whitespace, key, `=`, and the rest of the line is the value (leading
and trailing spaces trimmed). A key is written only when `vlcrc` has no active,
non-empty value for it, so user choices stay and commented defaults count as
unset. Lines without `=` are reported and skipped. Example:
`core key-play-pause=space`.

**Testing it** (no sudo, see [tools/README.md](../tools/README.md)): start the
harness once so Xvfb runs, run `linux/setup.sh --yes --ignore-running` with
`HOME`, `XDG_CONFIG_HOME` and `XDG_DATA_HOME` pointing into the harness home
(`<cache>/run-<instance>/home`, and `<cache>/root/usr/bin` in `PATH`) and
`XDG_DATA_DIRS` pointing at a folder that has a `vlc.desktop` whose `Exec`
runs the harness's `vlc`. Then, inside `dbus-run-session`, run the generated
launcher's `Exec` (plus `--aout dummy --no-video`) with one file, screenshot,
and run it again with a second file: the second process exits and the playlist
grows. Never run it against your real home unless you want the changes.

## The Windows helper (`taskbar/`)

- `vlc-taskbar.ps1 -Setup` writes `vlcrc` (UTF-8 without BOM): the keys of the
  table [vlcrc keys](#vlcrc-keys-what-both-setups-write), with `Set-VlcOption`
  and `Set-VlcModule`. Optionally it creates a Startup shortcut running the
  helper with `-Watch` (and `-NoDock`).
- `VlcDock.cs` finds VLC's `SkinWindowClass` windows (skipping the 1 x 1 flag
  windows), reads the main window's region (`GetWindowRgn`): if the visible
  box reaches the window bottom, the bar is at the bottom; a pixel test at the
  strip's rounded corner (one bar height from the bar's outer edge) tells the
  strip from the full player. Then it moves
  the window so the strip sits in the taskbar, re-asserts `HWND_TOPMOST` when
  the taskbar is above it, and steps aside for full-screen apps.
- Start pinned: VLC never saves "always on top", so the helper posts a click
  (`WM_MOUSEMOVE` / `WM_LBUTTONDOWN` / `UP`) on the skin's own pin button
  1.5 s after VLC's window appears. The positions in `PinOnce` / `ClickPin` must
  follow the generator's layout. The strip's height is `VlcDock.BarHeight` (set
  by the script from the skin file name; 24 or 36 / `--bar-height`) in
  `ReadShape`, `Place` and `ClickPin`; the full player's 122 px stay fixed.
- Tray icon (NotifyIcon with a classic `ContextMenu`, pumped by the helper's
  own `GetMessage` loop) and an opt-in log (`LogPath`, `-DebugLog`).
- Media controls (Setup only): the third-party control-interface plugin
  `libwin10smtc_plugin.dll` (vlc-win10smtc, pinned version and SHA-256 in
  `vlc-taskbar.ps1`) goes into `<VLC>\plugins\misc`, and `win10smtc` into the
  colon-separated `extraintf` list (`Set-VlcModule` keeps other entries).
  VLC starts `extraintf` modules whatever the main interface is
  (`src/libvlc.c`), so it runs next to skins2 and has its own hidden window.
- Linux needs none of this for media controls: the `vlc` launcher always adds
  `--dbus` (and `--media-library`, which overrides `media-library=0` in
  vlcrc; `bin/vlc.c`), so MPRIS is on. Tested with the skin. Linux setup:
  [The Linux setup](#the-linux-setup-linuxsetupsh).
- Control channel: `VlcRemote` (end of `VlcDock.cs`) talks to VLC's Lua web
  interface. The script reads port and password from vlcrc (`Get-VlcRemote`;
  off, silently, when `extraintf` has no `http` or no password is set) and
  passes them in as `RemotePort` / `RemotePassword`. A background thread polls
  `requests/status.json` every 500 ms while VLC runs (2 s while it does not
  answer) with 1 s timeouts, Basic auth with an empty user name, no proxy.
  `VlcDock.Remote.Status` (any thread) holds state, time and length in whole
  seconds, title (tag, else file name), artist; `Remote.Send("pl_pause" |
  "pl_next" | "pl_previous" | "seek", val)` sends a command (`SendAsync` from
  UI code). VLC answers a command with the status from before its effect for
  some commands (next, stop), so read `Status` again a moment later. JSON is
  read by a small built-in parser, so no System.Web.Extensions reference.
  Test it on Linux with `TB_VLC_ARGS` (see tools/README.md).

### Linux: pin on start

`linux/titlebar-pin.py` (Python 3 standard library + ctypes on libX11 / libXext)
does what `PinOnce` does on Windows, with the same pin offsets (100 % values
times the scale: strip pin centre `W - 34 + 11, 12`, full player `W - 82 + 9, 11`
from the player's top; bar at the bottom: from `H - 24` / `H - 122`).

- **Finding the window.** skins2 creates one X window per skin window, class
  `("vlc", "Vlc")`, name `VLC (TopWindow)`; most are 1 x 1 or 10 x 10
  parked windows. The script takes the viewable one with the largest area
  (556 x 436 at 100 %), searching a few levels below the root because a window
  manager reparents clients into frames. It waits until size and shape stay the
  same for 1 s. In `--watch` mode it pairs the window with the VLC process by
  `_NET_WM_PID` (a Flatpak sandbox's own PID is not in `/proc`, so a window with
  an unknown PID is accepted).
- **Strip or full, bar top or bottom.** The same rule as `ReadShape` /
  `tools/xshape.py`, from the Shape extension's bounding rectangles
  (`XShapeGetRectangles`): bar at the bottom when the shape reaches the
  window's last row; the full player is showing when the point `(0, bar)` from
  the bar's outer edge is inside the shape.
- **Scale.** The window height is `436 * scale`, matched against the shipped
  scales (100 / 125 / 150 / 200); else the `Titlebar-NNN.vlt` name from
  `/proc/<pid>/cmdline` or `skins2-last` in vlcrc (native, Flatpak and Snap
  paths); else the nearest scale.
- **The click is synthetic and the pointer never moves.** Checked in
  `x11/x11_loop.cpp`: `X11Loop::handleX11Event` never looks at `send_event`;
  `ButtonPress` / `ButtonRelease` take their position from `xbutton.x/y` of the
  event itself, and `TopWindow::processEvent(EvtMouse)` calls `findHitControl`,
  which sends the `enter` event to the checkbox (so the state machine goes
  `up -> upOver` by itself; `CtrlCheckbox` then handles `down` and `up` and runs
  the command on release). `MotionNotify` is useless here: skins2 ignores its
  coordinates and calls `XQueryPointer`, which is where the real pointer is. So
  the script sends `ButtonPress`, `ButtonRelease` with `XSendEvent` (empty event
  mask: the event goes to the client that owns the window, VLC), then a
  `LeaveNotify` so the pin does not keep its hover look. Verified with real VLC
  3.0.20: no XTest, no `xdotool` needed (the fallbacks the brief listed were
  not necessary and are not implemented).
- **Check.** `X11Window::toggleOnTop` sends `_NET_WM_STATE` (`ABOVE`, or
  `STAYS_ON_TOP` when the window manager lists it) to the root for every skin
  window, only when `_NET_SUPPORTED` lists the atom. The script treats
  `_NET_WM_STATE_ABOVE` on the window as proof; it also skips the click when it
  is already set. Without a window manager (Xvfb) nothing is set at all, so it
  compares the pixels around the pin before and after (`XGetImage`). It
  retries once when nothing changed and never clicks again when the pin
  changed look, because a second click would unpin.
- **Watch mode.** Polls `/proc/<pid>/comm` every 2 s (`vlc`, `cvlc`, ...), one
  forked child per new VLC (identified by PID and start time) waits up to 60 s
  for its window, so a broken X connection exits only the child. One watcher per
  user (`flock` in `$XDG_RUNTIME_DIR`). The display comes from the VLC
  process's own `DISPLAY` (read from `/proc/<pid>/environ`), then ours, then
  `:0`; `--display` limits the watcher to VLCs on that display.
- Not done on purpose: docking into a panel, or placing windows (Wayland does
  not allow it, and GNOME has no panel to dock into).

## Building and testing

```bash
python3 source/build_skin.py --scale 1.5 --preview   # Python 3 + Pillow
tools/setup-test-env.sh                               # once: VLC + Xvfb without sudo
tools/vlc-test.sh start "$(tools/vlc-test.sh build 1)"
tools/vlc-test.sh click 479 12 && tools/vlc-test.sh shot pl
tools/doc-shots.sh                                    # regenerate docs/img
```

- [tools/README.md](../tools/README.md): the test harness.
- The helper can only be compile-checked on Linux (Mono `mcs -langversion:5`
  with small stubs for the UI Automation types); behaviour needs Windows.
- Release: build all four scales (`--scale 1 / 1.25 / 1.5 / 2`), copy the
  `.vlt` files to the repo root, run `tools/doc-shots.sh` if the look changed.

## skins2 pitfalls we hit

| Assumption | Reality (VLC 3.0) |
|---|---|
| A dragged width applies to the window | Per layout, unless layouts have identical original size and limits |
| Controls can be named freely, or not at all | Unnamed elements get ids that repeat after 999, which crashes VLC |
| One PNG per bitmap is fine | One image decoder per `<Bitmap>`: 1400 bitmaps = 12 s startup |
| `<Image action="...">` reacts to a click | Only to a double-click (except move / resize) |
| An image under a `<Text>` gets the click | The text takes it, unless `focus="false"` |
| A semi-transparent overlay is invisible | X11 draws it opaque (no blending) |
| The theme can set "always on top" | No attribute; not saved either |
| Separate EQ / PL windows can share the width | They cannot; hence one window with 4 equal layouts |
| `b_x.png` and `B_x.png` are different files | Not on Windows |
