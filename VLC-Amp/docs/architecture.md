# How the VLC Amp skin works

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
source/build_skin.py  --(Pillow)-->  VLC-Amp-NNN.vlt  (tar.gz: theme.xml + img/*.png + fonts/; custom-ref/ when Custom is built)
                                          |
                    VLC skins2 interface  <--  vlcrc (intf=skins2, skins2-last=...)  <--  taskbar/Setup.cmd (Windows)
                                                              linux/setup.sh (Linux)
                                          |
               taskbar/VlcDock.cs (Windows) moves / pins VLC's window, read via its window region
               linux/vlc-amp-pin.py (Linux X11 / XWayland) pins it on start by clicking the skin's pin
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
to the other end of the window (on Windows the helper moves the window back,
see [The Windows helper](#the-windows-helper-taskbar)).

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
for title and time), grip
rows and the resize grip. Widths do **not** grow, so the right-edge offsets
(`R(34)` pin, `R(62)` / `R(90)` EQ / PL, `R(96)` end of the time box) and the pin's x stay
as they were; only the time box widens when the bigger font needs it
(`tw`: 86 px at 24, 96 px at 36, from `bar_metrics`). `MIN_W` stays 420 at every
height: `bar_metrics` returns the same `min_w` for all bar heights.

Build names carry the height: `VLC-Amp-NNN` (24), `VLC-Amp-taskbar-NNN` (36,
`BAR_TASKBAR`), `VLC-Amp-bar<N>-NNN` (any other); `ThemeInfo` reads
"VLC Amp 150% bar 36". The helper gets the height from the file name
(`Get-SkinInfo` in `vlc-taskbar.ps1`, `$TaskbarBarHeight` = 36 for `taskbar`),
and `Setup` / the helper pick the `taskbar` file when docking if it exists
(`Get-SkinPath -Taskbar`). The test harness reads the same names
(`skin_bar` in `tools/vlc-test.sh`).

## State without layouts: flag windows

Opening PL / EQ, the time mode and the theme are not layouts (that would
multiply them). They are **tiny 1 x 1 windows** with no visible pixels:
`eqflag`, `plflag`, `tflag`, and one `th<i>` per theme built (`th0`, `th1`, ...;
the release skins have `th0` only). Shown = on.

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
with a single theme the theme button is left out. The generator renders the
whole skin once per theme, into the same 4 layouts:

- bitmap ids get the prefix `t<i>_` (`Skin.prefix`, applied by `Skin.add` and
  the `Layout` methods);
- every control of theme `i` gets `th<i>.isVisible and ...` (`Layout.theme_vis`); theme 0 instead
  gets `not th1.isVisible and ... not th<last>.isVisible`, so a saved state with no theme flag
  shown (nothing drawn = no window shape = invisible and unmovable) falls back to theme 0;
- theme `i`'s button (full player title bar) selects theme `i + 1` (wrapping
  around) with `th<i+1>.show();th<j>.hide();...` (shows first, so something is
  always drawn).

Cost: about 2400 bitmaps and 4800 controls (Image, Button, Checkbox, Slider,
Text, Playtree, ...) with all 11 themes. See the next sections for what
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
Hence `FILL_FRAMES = 51` (2 % steps); the earlier 101-frame sheets cost about 80 MB more at 150 %.
Start-up: 1.7 s with Midnight alone, 4.6 s with all 11 themes (under Xvfb).

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

- Read in VLC 3.0.x `modules/gui/skins2`: `FileBitmap` premultiplies every PNG on
  load (`b * a / 255`). Windows `drawBitmap` ignores the `blend` flag and
  always uses `AlphaBlend` with `AC_SRC_ALPHA` (premultiplied, so right); X11 only
  blends when `blend` is true (`CtrlText` does; buttons, checkboxes, thumbs and images do not). The window
  shape is every pixel with alpha > 0 on both (`a > 0` in both `drawBitmap`s, then
  `SetWindowRgn` / XShape). Buttons are drawn into a blank `OSGraphics`
  (`createOSGraphics`), then copied with `drawGraphics` (BitBlt / XCopyArea, no
  blending). So a pixel with alpha 1..254 is opaque and darker on Linux, and on
  Windows it is the premultiplied colour plus the blank bitmap's start content
  (`CreateCompatibleBitmap`, not guaranteed black): bright dots at button corners
  if it is not. `solid()` in the generator composites such bitmaps over the panel
  colour (flat style), so every platform gets the same pixels:
  `tools/windows-sim.py` writes the comparison to `docs/img/windows-sim/`. Window
  outlines use hard alpha (`Canvas.done(hard_edges=True)`), small text is drawn on
  opaque crops of the background (`label_on`), and the LCD progress fill frames
  have hard edges.
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
| `skins2-last` | skins2 | absolute path of `VLC-Amp-NNN.vlt` | yes | yes | Which skin; NNN from the display scale |
| `one-instance` | core | `1` | yes | yes | Files opened from the file manager go to the running player (Windows: window message; Linux: D-Bus, see below) |
| `one-instance-when-started-from-file` | core | `1` | yes | yes | Same, for launches with `--started-from-file` (what the launchers pass) |
| `playlist-enqueue` | core | `0` | yes | yes | ...and the file starts playing |
| `media-library` | core | `0` | yes | yes | No "Media Library" node in the playlist. **VLC's launcher overrides it on both systems** (`bin/vlc.c`, `bin/winvlc.c`): Linux setup writes a launcher with `--no-media-library`, Windows setup adds the flag to the file association commands, the helper's VLC start and a Start menu shortcut (see "File associations") |
| `skins2-taskbar` | skins2 | `0` when the helper docks VLC or starts with Windows (it has its own button), else `1` | yes | no | Windows-only option (it does not exist in VLC's Linux build) |
| `extraintf` | core | colon list: `http`, `luaintf` (when `lua/intf/vlcamp.lua` exists), plus `win10smtc` (Windows, media controls) | yes | yes | Control interfaces started next to skins2 |
| `http-host` | core | `127.0.0.1` | yes | yes | Web interface for this computer only |
| `http-port` | core | `48080` | yes | yes | An unusual port |
| `http-password` | lua | random, 24 letters and digits; kept if already set | yes | yes | Locks the web interface. Windows: the helper's control channel uses it. Linux: nothing uses it yet, it is there for later helpers (`--no-web` skips the three web keys) |
| `lua-intf` | lua | `vlcamp` | yes | yes | Which script the `luaintf` interface runs (`modules/lua/vlc.c`: `lua-intf` and `lua-config` belong to the primary `lua` module) |
| `key-subsync-markaudio` ... `key-viewpoint-fov-out` | core | the five lines of `lua/vlcrc-keys.txt` | yes | yes | Default keys of the Lua extras; written only when unset |

Both setups read `lua/vlcrc-keys.txt` (`<section> <key>=<value>`), only when
the Lua extras were installed, so more
default keys can be added there without changing either setup.

## The Linux setup (`linux/setup.sh`)

POSIX `sh` + `awk` / `sed` / `grep` (run with dash and bash; `shellcheck` was
not available when it was written). Python is only needed for the optional
`linux/vlc-amp-pin.py` (start pinned). Every path honours `HOME`,
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
one is backed up once as `vlcrc.before-vlc-amp` (`cp -p`), edited in a
temporary copy and written back in one go. Edits are done by the `rc_edit` awk
function (values go through the environment so backslashes survive). Running
the setup twice changes nothing; a `vlcrc` that an earlier run created
(`rc_created=1` for the same `rc`) is never backed up, so `--uninstall` still
removes it. The state file records one VLC: setting up another flavor is
refused until `--uninstall` has run.

**Scale.** `--scale N` (`150` or `1.5`), else the first of these that gives a
number: `GDK_SCALE`, `QT_SCALE_FACTOR`, `Xft.dpi` / 96 from `xrdb -query`,
`kreadconfig6` / `kreadconfig5 --group KScreen --key ScaleFactor`, GNOME
`scaling-factor` and `text-scaling-factor` (`gsettings`, only values above 1).
All values found are printed. The nearest of 100 / 125 / 150 / 200 is used;
nothing found means 100. skins2 draws in real X pixels, so which file is right
under XWayland with compositor scaling is unverified.

**Media Library gotcha.** The Linux `vlc` program (`bin/vlc.c`) builds its
argument list as `--no-ignore-config --media-library [--dbus] <your arguments>`
(`--dbus` when built with D-Bus; Windows' `winvlc.c` has the same
`--media-library --no-ignore-config` and no `--dbus`, see "File associations"
in the Windows section), so `media-library=0` in `vlcrc` loses. A later `--no-media-library` on the command
line wins over the earlier `--media-library`. Hence the launcher
`~/.local/share/applications/vlc-amp.desktop`: a copy of the system
launcher (`vlc.desktop`, Flatpak's `org.videolan.VLC.desktop`, Snap's
`vlc_vlc.desktop`; searched in `XDG_DATA_DIRS` plus the usual Flatpak and snapd
export dirs) with `Name=VLC Amp`, `--no-media-library` inserted before
`--started-from-file` (or the first file placeholder) in every `Exec=`, the
translated `Name[..]` lines and `DBusActivatable` removed (a launcher that
activates over D-Bus would skip `Exec`), and the marker line
`X-VLC-Amp=1` (uninstall only deletes a file that has it). With no system
launcher, a basic one is generated (Flatpak: `flatpak run --file-forwarding
org.videolan.VLC --no-media-library --started-from-file @@u %U @@`).
If the old launcher's `Exec=` lines carry the `follow-system-theme.sh --install`
wrap, a re-run of setup re-applies it (same script path, `Exec="<script>" --exec
<original>`) and says so.
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
vlc-amp.desktop <type>`. `inode/directory` and the video types are left
alone on purpose: as the default for folders VLC would open every time a folder
is opened in the file manager. The previous default (`xdg-mime query default`,
which also reports fallbacks) is stored per type in the state file.

**State and undo.** `~/.local/state/vlc-amp/linux-setup.state`
(`flavor`, `rc`, `rc_created`, `desktop`, `lua`, `mime` and `pin` lines) records
what was changed. `--uninstall` refuses while VLC runs, then: saves the current
`vlcrc` as `vlcrc.vlc-amp-removed` and restores `vlcrc.before-vlc-amp` byte
for byte (when there was no `vlcrc` before the setup, the current one is moved
to `.vlc-amp-removed` and VLC makes a new one); puts each audio type back to
its recorded default, or removes our line from `mimeapps.list`, if the default
is still ours (this runs before the launcher is deleted, because `xdg-mime`
only reports a default whose file exists); removes the launcher and the Lua
files; runs `vlc-amp-pin.py --uninstall-autostart`. `follow-system-theme.sh`
edits the `rc` recorded in this state file (an explicit `VLCRC` wins, and with no
state file it takes the first `vlcrc` it finds), so it follows the VLC that was set up.

**Start pinned.** If `linux/vlc-amp-pin.py` exists the setup asks (or
`--pin-autostart` / `--no-pin-autostart`; `--yes` means yes) and runs
`python3 linux/vlc-amp-pin.py --install-autostart`. The autostart entry points
at that file's real path, so the setup must be run again after the folder is
moved. The setup neither copies nor edits that script.

**Lua extras.** If `lua/intf/vlcamp.lua` exists and `lua-intf` is unset,
`dummy` or `vlcamp` (another script is left alone, as on Windows), all `lua/intf/*.lua` are
copied to the flavor's Lua dir, `luaintf` is merged into `extraintf` and
`lua-intf=vlcamp` is set (section `lua`). Only when these extras were
installed (as on Windows; not when another `lua-intf` script made setup skip
them), `lua/vlcrc-keys.txt`, if it exists,
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

- `taskbar/find-vlc.ps1` (`Find-Vlc`: the installer's registry key, else the
  usual Program Files folders) is dot-sourced by `install.ps1` and
  `vlc-taskbar.ps1`, so both find `vlc.exe` the same way.
- `vlc-taskbar.ps1 -Setup` writes `vlcrc` (UTF-8 without BOM): the keys of the
  table [vlcrc keys](#vlcrc-keys-what-both-setups-write), with `Set-VlcOption`
  and `Set-VlcModule`. It also installs the Lua interface and its default keys (see "Lua
  interface"). Optionally it creates a Startup shortcut running the helper
  with `-Watch` (and `-NoDock`). When there is no `vlcrc` yet, Setup writes
  one and a marker `vlcrc.vlc-amp-created` next to it, and a second run makes
  no backup of its own file; `uninstall.ps1` then deletes the `vlcrc` and the
  marker instead of restoring a backup.
- The helper with VLC: the per-user file association commands and the Start
  menu entry "VLC Amp" run `wscript.exe taskbar\launch.vbs "<vlc.exe>" <args>`.
  `launch.vbs` starts VLC at once (arguments re-quoted when they contain a space),
  then, only if the Startup shortcut "VLC Amp helper.lnk" exists (Setup: start
  the helper with Windows) and no `powershell.exe` / `pwsh.exe` runs
  `vlc-taskbar.ps1` (WMI `Win32_Process`, a running `-Setup` does not count),
  runs that shortcut's target and arguments hidden. So a helper that was quit
  or crashed comes back with the next VLC; the helper's own mutex guards against
  a race. `wscript.exe` has no console, so nothing flashes. Uninstall finds these
  commands by their `--no-media-library` flag as before. Tested on Windows with a
  stub program (2026-11-01): arguments with spaces and parentheses intact, no
  second helper when one runs, the shortcut's command when none runs.
- Start / exit / crash notes: `VlcDock.Note` writes the start line, the exit
  line with its reason (tray Quit, VLC gone when not `-Watch`, message loop
  ended) and an unhandled exception to `%TEMP%\vlc-amp-helper.log` even
  without `-DebugLog` (`EventLogPath`; the debug log is the same file). The
  script adds a line for its own errors before the helper runs (`trap`), and
  Setup / Install add one when they stop a running helper.
- Which `vlc.exe`: with several running (a second one with another interface,
  or one still exiting) `VlcDock.PickVlc` takes the one that owns the skin's
  root window (`HasSkinRoot`) and keeps following it while it qualifies,
  instead of the first one `GetProcessesByName` returns.
- `VlcDock.cs` finds VLC's `SkinWindowClass` windows (skipping the 1 x 1 flag
  windows) and reads the main window's region (`GetWindowRgn` +
  `GetRegionData`). `DockShape.Classify` (pure code, tested with the X11
  shapes of the real skin) decides from the visible height: strip `bar`,
  `bar + EQ`, `bar + PL`, `bar + EQ + PL` or full `122 + ...` tells strip /
  full and which panels are open, and the visible part touching the window's
  top or bottom gives "dn" / "up". The full player with both panels fills the
  window; then the seam tells: where the full player meets the panel next to it,
  both have rounded corners, so the left edge is transparent in rows `f-1` / `f`
  ("dn", `f` = 122 x scale) or `hh-f-1` / `hh-f` ("up"); without such a seam
  (square corners) the direction is kept from before. The old pixel test at the strip's
  rounded corner only breaks ties (bar 40: strip + PL = full + EQ). A height
  that fits a strip of another height than `BarHeight` is taken as such (the
  helper's skin file differs from VLC's; with the old test that made a strip
  with PL / EQ open count as the full player, placed above the taskbar).
- Moving: skins2 keeps its own copy of the window position and never notices
  moves from outside (no `WM_MOVE` handling in `win32_loop.cpp`), and every
  later move or resize it does starts from that copy
  (`GenericWindow::resize` -> `MoveWindow(m_left, m_top, ...)`). A window moved
  with `SetWindowPos` therefore jumps back on every expand / collapse / flip and
  during a resize drag (whose width is computed from client coordinates, so it
  collapses to the minimum). Verified on X11, which has the same logic. So the
  helper posts a drag on the skin's grip (`WM_LBUTTONDOWN`, `WM_MOUSEMOVE` by
  the offset, `WM_LBUTTONUP` at client 6, bar / 2; `CtrlMove` moves by the
  client offset and updates its copy). A stale copy makes the first drag land
  off by as much; the next one corrects it. `SetWindowPos` only as a fallback
  (2 drags without effect, or 4 misses in a row). No moves while a mouse
  button is down (`GetAsyncKeyState`): with `DockTo=start` the right edge goes
  back to Start after a resize, so the strip grows to the left.
- DPI: `powershell.exe` is DPI-unaware and VLC is DPI-aware, so Windows scales
  what an unaware thread sees of VLC's windows (at 125 %: 587 x 436 instead of
  734 x 545, positions and the Start button / 1.25). A thread handling a message
  for a window takes that window's awareness, so before T25 the helper read VLC
  in either system depending on the path that called `Place`, and moved it back
  and forth (the flashing of the second Windows test; drags missed by the
  ratio). `Run` makes the helper's thread per-monitor aware first
  (`SetThreadDpiAwarenessContext(PER_MONITOR_AWARE_V2)`, else V1; so its own
  windows are too), and every entry point that touches windows sets it again
  (`DpiEnter` / `DpiLeave`: `Tick`, the tray menu, the hotkey, the taskbar
  button's timer and activation, the WinEvent log). Everything is then in
  physical pixels, like `GetWindowRgn` and VLC's client coordinates for the
  posted drags and clicks. Before Windows 10 1607: `SetProcessDpiAwareness(2)`,
  else `SetProcessDPIAware`. Logged: `dpi:` in `helper started`, and
  `DPI: VLC's window N dpi, W x H px; helper thread ...` on change. The script
  also reads VLC's actual skin from `skins2-last` in vlcrc when it does not
  start VLC itself (`-Watch`), for `Scale` / `BarHeight` (`skinFile=` in the log).
- Panels flip (item 32): the PL / EQ header arrow switches `strip-dn` <->
  `strip-up` (`full-dn` <-> `full-up`), which moves the bar by about the window
  height minus the bar. `KeepBarOnFlip` compares each shape with the last one of
  known direction: same kind (strip / full), other side, same window size and
  position = a flip, and `DockShape.FlipOffset` gives the move (`BarTop` = the
  bar's top row from the visible rows: at 125 % the full player ends one row
  above the window's bottom). Not docked, the window is moved by that much with
  the same posted drag as above, clamped (`ClampVisible`) so the visible part
  stays on the monitor's work area. Docked, `Place` already keeps the strip in
  the taskbar (and the full player's visible part above it). Not while a mouse
  button is down (that also cancels a move on its way), not on strip <-> full,
  not when the window moved as well, at most 2 s. The timer runs every 50 ms
  while the mouse is over VLC's window (else 250 ms), so the jump after a click
  is short. Tested under Mono with real shapes (`VLC-Amp-100/125`,
  `VLC-Amp-taskbar-100/150` and the T21 captures, classic style too): for all
  80 dn / up pairs the bar's pixel rows land on the same screen rows.
- VLC hidden (item 33). From the 3.0.x source: skins2 hides its windows only
  by minimizing its root window (`Win32Factory::minimize` =
  `ShowWindow(root, SW_MINIMIZE)`, from `vlc.minimize()` or a
  `WM_SYSCOMMAND SC_MINIMIZE` to the root; Windows then hides every window the
  root owns), on a skin change (`hideAll`), or by a skin's `window.hide()`. Its
  window procedures handle no `WM_ACTIVATE` / `WM_ACTIVATEAPP` / `WM_KILLFOCUS`
  (`win32_loop.cpp`, `Win32Factory::Win32Proc`): activation changes do nothing in
  skins2. The tray icon: a single click is `WindowManager::raiseAll` =
  `SetForegroundWindow` on each skin window (brings back a covered window, not
  a minimized one), a double click is `CmdRestore` = `ShowWindow(root,
  SW_RESTORE)`, the same as `SC_RESTORE` to the root. With `skins2-taskbar=0` the
  root keeps `WS_EX_TOOLWINDOW` from `init()` and never gets a taskbar button
  (only `addInTaskBar` gives it `WS_EX_APPWINDOW`; T12's `DeleteTab` only runs on
  a `WS_EX_APPWINDOW` root). While docked, `KeepVisible` (decision in
  `HidePolicy`) sends `SC_RESTORE` to the root (and `ShowWindowAsync(SW_SHOWNOACTIVATE)`
  if it is still minimized) when the main window is not visible and the root is
  minimized, unless the minimize came from the full player's own minimize button
  (the full player was showing and the mouse is on it: then it stays minimized
  until the taskbar button or tray icon restores it; the strip has no minimize
  button). Not while a mouse button is down, at most once a second, and it
  gives up after 6 restores in a minute. Hidden without a minimized root is only
  logged. Not docked: never restored. The log has every foreground change (with
  the process and VLC's root / main state: visible, minimized, topmost, DWM
  cloaked), WinEvents for minimize / restore / show / hide / cloak of VLC's root
  and main windows (`EVENT_SYSTEM_MINIMIZESTART`, `EVENT_OBJECT_HIDE`, ...,
  with mouse position and foreground), the windows still above VLC when a raise
  above the taskbar did not take (then it is inserted again: `NOTOPMOST`, then
  `TOPMOST`), and `WM_ACTIVATE` / `WM_SYSCOMMAND` reaching the helper's own
  taskbar window. *Unverified on Windows*: what actually hides the player after
  a taskbar click; if the log shows it is only covered (a single tray click
  helps), the next step is item 15's `SetParent` onto the taskbar.
- Z-order: VLC's pin is the `WS_EX_TOPMOST` of its 1 x 1 flag windows
  (`WindowManager::setOnTop` sets every top-level skin window; the helper never
  touches those). The main window is kept topmost while VLC is pinned or the
  strip is in the taskbar (the taskbar is topmost, a non-topmost strip would be
  behind it), re-raised when the taskbar comes above it (item 15), and made
  non-topmost again for an unpinned full player. Before, `Move()` always
  inserted `HWND_TOPMOST`, which re-pinned VLC right after an unpin. It steps
  aside for full-screen apps.
- A docked strip with PL / EQ open on the side away from the screen (the "dn"
  layouts under a bottom taskbar) gets a posted click on the flip arrow of the
  panel next to the strip (`FlipPanels`, at most 3 tries).
- Start pinned: VLC never saves "always on top", so the helper posts a click
  (`WM_MOUSEMOVE` / `WM_LBUTTONDOWN` / `UP`) on the skin's own pin button
  1.5 s after VLC's window appears (no click if the flag windows say it is
  pinned already). The click points (pin, grip, flip arrows) are in
  `DockShape.PinPoint` / `GripPoint` / `FlipPoint` and must follow the
  generator's layout (`build_skin.py`: `add_strip`, `add_full`, `flip_button`).
  The strip's height is `VlcDock.BarHeight` (set by the script from the skin
  file name; 24 or 36 / `--bar-height`), unless the shape shows another one; the
  full player's 122 px stay fixed.
- Tray icon (NotifyIcon with a classic `ContextMenu`, pumped by the helper's
  own `GetMessage` loop) and an opt-in log (`LogPath`, `-DebugLog`). The menu's
  "Playback" submenu (A-B loop, next / previous folder) sends
  VLC hotkey actions through the control channel, see "Lua interface".
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
- Taskbar button (item 19; the `partial` part of `VlcDock` at the end of
  `VlcDock.cs`, plus `VlcTaskbarView`, `TbNative`, `ITaskbarList3`). skins2's own
  taskbar button belongs to its hidden root window: class `SkinWindowClass`,
  title "VLC Media Player" (the other skin windows say "VlC Media Player"),
  0 x 0 at -200,-200, owner of every skin window (`win32/win32_factory.cpp`,
  `win32_window.cpp`). Windows sends thumbnail-button clicks (`WM_COMMAND` +
  `THBN_CLICKED`) only to the window that owns the button, so the helper owns
  a button instead: an invisible top-level window (`WS_POPUP`,
  `WS_EX_APPWINDOW`, layered with alpha 0, click-through, 192 x 108 at
  -32000,-32000, kept at the bottom of the z-order), and VLC's button is off
  (`skins2-taskbar=0`: Setup writes it when the helper starts with Windows, the
  launcher passes `--no-skins2-taskbar`; if VLC still shows one, the helper
  removes it with `ITaskbarList::DeleteTab`). After the registered
  `TaskbarButtonCreated` message (again after an Explorer restart) it adds 3
  thumbnail buttons with `ITaskbarList3` (icons drawn at runtime at
  `SM_CXSMICON`, white or dark per `SystemUsesLightTheme`), and keeps the
  play / pause icon, the title ("Artist - Title") and the progress
  (`SetProgressValue`, interpolated between the 500 ms polls; NORMAL playing,
  PAUSED paused, NOPROGRESS stopped / streams / offline) up to date on a 250 ms
  timer. No overlay icon (the progress colour already shows the state). Hover
  preview: `DWMWA_FORCE_ICONIC_REPRESENTATION` + `DWMWA_HAS_ICONIC_BITMAP`;
  `WM_DWMSENDICONICTHUMBNAIL` (max width in the high word of `lParam`, height
  in the low word) is answered with a card GDI+ draws straight into a 32-bit
  top-down DIB section as `Format32bppPArgb` (premultiplied, as DWM requires),
  `DwmSetIconicThumbnail`; `DwmInvalidateIconicBitmaps` whenever the card's
  text changes (once a second while playing). Peek is switched off
  (`DWMWA_DISALLOW_PEEK`): there is nothing to show. Clicks:
  activating our window (button, preview, Alt+Tab) makes the helper the
  foreground process, so it may `SetForegroundWindow` VLC's main skin window;
  a minimized VLC (skin minimize = `ShowWindow(root, SW_MINIMIZE)`, which hides
  the owned skin windows) is first restored with `WM_SYSCOMMAND SC_RESTORE` to
  the root window, which skins2 handles (`Win32Factory::Win32Proc`). "Close
  window" = `WM_SYSCOMMAND SC_CLOSE` to the root window = `libvlc_Quit`, the
  same as VLC's own button. `WM_CLOSE` would be wrong: skins2 does not handle
  it, so `DefWindowProc` would destroy the window under VLC. The button exists
  while VLC's root window exists and the web interface is configured.
- App id of that button (`TaskbarAppIdFor`). Windows groups buttons by
  AppUserModelID. VLC 3 sets none: nothing in `bin/winvlc.c` or the Qt module,
  and the installer's shortcuts (`extras/package/win32/NSIS/vlc.win32.nsi.in`)
  carry none. Windows then derives one from the exe path, a known folder
  replaced by its GUID, for example
  `{6D809377-6AF0-444B-8957-A3773F02200E}\VideoLAN\VLC\vlc.exe` (Program Files,
  64-bit) or `{7C5A40EF-...}\...` (Program Files (x86)); `Get-StartApps` lists
  the same form. The helper computes that id for the running vlc.exe
  (`QueryFullProcessImageName`; longest matching known folder, else the full
  path) and sets it with `SHGetPropertyStoreForWindow`, after
  `RelaunchCommand` = `"vlc.exe"`, `RelaunchDisplayNameResource` = "VLC media
  player", `RelaunchIconResource` = `vlc.exe,0` (so pinning the button pins
  VLC, not PowerShell); they are cleared before the window is destroyed.
  *Unverified on Windows*: that the taskbar uses exactly this id for a pinned
  VLC. If it does not, the button stands next to the pinned icon instead of on
  it (nothing else breaks), and `$TaskbarAppId` sets the id by hand. A fixed
  id of our own would never group with a pinned VLC.
- With `skins2-taskbar=0` and no helper, a minimized VLC is only reachable
  through skins2's own tray icon (`skins2-systray`, on by default,
  `src/skin_main.cpp`; double-click restores). That is why Setup turns VLC's
  button off only when the helper starts with Windows.

**File associations (Media Library on Windows).** `bin/winvlc.c` (3.0.x) builds
libvlc's argument list as `--media-library --no-ignore-config <your
arguments>` (`argv[j++] = FromWide(L"--media-library")` and
`L"--no-ignore-config"` come first, then the command line), so
`media-library=0` in `vlcrc` loses, exactly as on Linux; a later
`--no-media-library` wins. VLC's NSIS installer
(`extras/package/win32/NSIS/vlc.win32.nsi.in`, `helpers/extensions.nsh`) writes
under `HKLM\SOFTWARE\Classes`:

- one ProgID per extension, named `VLC` + extension, so `VLC.mp3`, `VLC.flac`
  ..., with `shell\Open\command` = `"<dir>\vlc.exe" --started-from-file "%1"`
  and, with the context menu option, the verbs `shell\PlayWithVLC\command`
  (`... --started-from-file --no-playlist-enqueue "%1"`) and
  `shell\AddToPlaylistVLC\command` (`... --playlist-enqueue "%1"`);
- the same two verbs under `Directory`, and `PlayWithVLC` under `AudioCD` and
  `DVD` (`... --started-from-file cdda:///%1`);
- `Applications\vlc.exe\shell\Open\command` ("Open with"), and the
  AutoPlay ProgIDs `VLC.DVDMovie`, `VLC.CDAudio`, `VLC.VCDMovie`,
  `VLC.SVCDMovie`, `VLC.OPENFolder`, `VLC.Bluray`;
- the skin file types `VLC.vlt` / `VLC.wsz` (`-Iskins --skins2-last "%1"`),
  which Setup skips because the command has no `--started-from-file`.

Setup (`Set-VlcFileAssociations`) reads those keys (`Get-HklmClassesRoots`
opens both the 64-bit and the 32-bit registry view with
`RegistryKey.OpenBaseKey`; a 64-bit VLC writes to the 64-bit one) and, for
every `shell\<verb>\command` of `VLC.*`, `Applications\vlc.exe`, `Directory`,
`AudioCD` and `DVD` that runs this `vlc.exe` with `--started-from-file` and has
no flag yet, writes the same command with ` --no-media-library` inserted after
`vlc.exe` to `HKCU\Software\Classes\<same path>` (default value, `REG_SZ`).
`HKCU` wins over `HKLM` in the merged `HKCR`, needs no admin, and the verb's
label and icon still come from `HKLM`. The paths written go, one per line
relative to `HKCU`, into `%LOCALAPPDATA%\VLC-Amp\file-associations.txt`
(`install.ps1` keeps it when it mirrors the package folder: `robocopy /XF`).
A second Setup writes identical values (the flag is never doubled: the source
is the `HKLM` command, and a key that already has the flag is refreshed, one
without it that is already in `HKCU` is the user's own and is left alone).
Windows' "default app" (`UserChoice` under
`HKCU\...\FileExts\<ext>`) is never read or written: it names a ProgID, and
if that is another program's, files open its way. `uninstall.ps1` deletes
exactly the listed keys, only if the command still contains
`--no-media-library`, then the verb, `shell` and ProgID keys if they are empty.
`HKLM` is never written.

The other ways VLC starts: the helper's own start passes `--no-media-library`
(`$vlcArgs` in `vlc-taskbar.ps1`); `install.ps1` adds the Start menu shortcut
"VLC Amp" (`vlc.exe --no-media-library`, in the VLC Amp
folder). Not covered: VLC's own Start menu shortcuts and desktop icon (all-users
folders, admin needed to edit) and a VLC icon pinned to the taskbar (a copy of
the shortcut in `User Pinned\TaskBar`; rewriting those pins is not safe, so
the user can unpin it and pin "VLC Amp" instead). *Unverified on
Windows*: the whole path was written from VLC's installer source and could
not be run (no Windows here).

### Linux: pin on start

`linux/vlc-amp-pin.py` (Python 3 standard library + ctypes on libX11 / libXext)
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
  scales (100 / 125 / 150 / 200); else the `VLC-Amp-NNN.vlt` name from
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

## Lua interface (`lua/intf/vlcamp.lua`)

A-B loop, next / previous folder, equalizer presets, a bitrate for lossless
files and durations in the playlist: things a skins2 button cannot do (a button can only run skins2's own
action list). A Lua *interface* script runs inside VLC next to the skin, on
Windows and Linux alike. Facts below were checked in the VLC 3.0.x source
(`modules/control/hotkeys.c`, `src/misc/actions.c`, `modules/lua/*`,
`share/lua/*`, `modules/gui/skins2/src/vlcproc.cpp`) and by running real
VLC 3.0.20 under the test harness (`tools/`).

### Playlist durations

The Playtree control draws one text column per item: `input_item_GetTitleFbName`
(the title meta, else the name; `modules/gui/skins2/vars/playtree.cpp:355`,
`src/input/item.c:280-300`, empty title = name). It redraws an item on the
playlist's `item-change` variable (`vlcproc.cpp:175`), which a meta change
raises (`src/playlist/item.c:228-233, 316`). Every entry of
`vlc.playlist.get()` carries an `item` userdata of the `input_item` metatable
(`modules/lua/libs/playlist.c`, `luaopen_input_item`), whose `set_meta` works
on any item, not only the playing one (`modules/lua/libs/input.c:354-441`).

So every 2 s the script walks the playlist and sets the title of each item with
a known `duration` (seconds, `-1` = unknown) to `<title or name>`, spaces, and
the length (`m:ss`, `h:mm:ss` from an hour), filling the line: right-aligned
by padding, because the playlist font (DejaVu Sans Mono) gives every character
the same advance. The line width in characters (`pl_columns`, at start): the
Playtree draws a flat list's text 7 px in (`ctrl_tree.cpp` `makeImage`,
`itemImageWidth` = 5 + 2) and cuts what does not fit with "..." (`ft2_font.cpp`
`drawString`, glyph advance = FreeType's hinted `advance.x >> 6`); the skin's
playtree is `P(42)` narrower than the main window, its font `P(11)` =
`round(11 x scale)` px (Python rounding, half to even: 16 at 150 %), and the
advance `round(px x 0.6021)` = 7 / 8 / 10 / 13 px at 100 / 125 / 150 / 200 %
(measured with FreeType for digits, space, "…" and accented letters). Scale
comes from the `-NNN.vlt` name in `skins2-last`, the width from the `"main"`
entry of `skins2-config` (both read with `vlc.config.get`; the width is the one
VLC saved at its last exit). Columns = `(width - P(42) - 7 - 2 x advance) /
advance`: two characters less than the arithmetic, measured in VLC 3.0.20 (70
fit at 100 % and 71 are clipped; 74 / 75 at 150 %; 91 at 100 % with a 706 px
window). A title longer than the room is cut to leave an ellipsis and two
spaces. `durations='suffix'` gives the plain ` (m:ss)` suffix instead,
`columns=N` overrides the width. It remembers the original title meta per item id
(`""` when there was none) and the text it set; a title that differs from that
text (VLC re-read the tags, the user renamed it) is decorated afresh. The
playing item is never decorated: on a track change the original title goes
back at once (strip, web interface, MPRIS and SMTC read the current item's
title) and the previous item is decorated in the same tick. Why a suffix: the
skin's SORT button runs `playlist_RecursiveNodeSort(..., SORT_TITLE, ...)`
(`commands/cmd_playtree.cpp:41`), so a prefix would sort by length (trailing
spaces do not change the order). A title that already ends in a length (a
playlist saved with lengths: ` (m:ss)` or two or more spaces and `m:ss`) is
stripped first. `lua-config` `vlcamp={durations='off'}` turns it off (the interface gets its
own table as the global `config`, `modules/lua/intf.c:323-353`).
Verified in VLC 3.0.20 under the harness (2026-11-01): unplayed items show
lengths (incl. `1:03:00`), the playing one stays plain in the playlist and the
strip, Next moves the plain title along, SORT sorts by name, no doubled
suffixes, `off` shows none; right-aligned at 100 % (70 columns, a 120-character
title cut with "…") and with a saved 706 px window (91 columns).

### Start and install (what Setup / `linux/setup.sh` must do)

| What | Value |
|---|---|
| Script | copy `lua/intf/vlcamp.lua` to VLC's user Lua folder, `intf/vlcamp.lua` |
| Windows folder | `%APPDATA%\vlc\lua\intf\` (create it) |
| Linux folder | `${XDG_DATA_HOME:-$HOME/.local/share}/vlc/lua/intf/` (create it). Flatpak VLC: `~/.var/app/org.videolan.VLC/data/vlc/lua/intf/` (not tested) |
| vlcrc | Windows `%APPDATA%\vlc\vlcrc`; Linux `${XDG_CONFIG_HOME:-$HOME/.config}/vlc/vlcrc` |
| `[core]` `extraintf` | add `luaintf` to the colon-separated list (`http:luaintf`, `win10smtc:http:luaintf`), keep the others |
| `[lua]` `lua-intf` | `vlcamp` (the option belongs to the `lua` module, like `http-password`; only set it when it is unset or `dummy`) |
| `[core]` keys | the five `key-...` lines of `lua/vlcrc-keys.txt` (format `<section> <key>=<value>`, `#` comments), written only when vlcrc has no active, non-empty value for the key. Both `vlc-taskbar.ps1 -Setup` and `linux/setup.sh` read this file, so it is the one list to edit |

Both `http` and `luaintf` are interface modules of VLC's one `lua` plugin;
`lua-intf` is read only by `luaintf` (`modules/lua/intf.c`: `http`, `cli` and
`telnet` pass their own script name), so `extraintf=http:luaintf` runs the web
interface and `vlcamp.lua` side by side. Checked by running it, from vlcrc
only. The script needs a VLC with Lua (the Windows build and the Ubuntu 24.04
packages used by the harness have it; other distributions: not checked). It also works with Lua 5.1
(Windows) and 5.2 (the Ubuntu 24.04 build used by the harness).

The keys the setups write (`extraintf`, `lua-intf`, the five `key-...` lines of
`lua/vlcrc-keys.txt`) are listed once, in the [vlcrc keys](#vlcrc-keys-what-both-setups-write)
table. VLC reads them from any section; the section headers only matter when a
key is added to a file that does not have it yet.

### The trigger bridge

Lua in VLC 3.0 has no callbacks (see [lua-api-notes.md](lua-api-notes.md)), so
the script polls the libvlc integer variable `key-action` (the id of the hotkey
action VLC last ran) every 100 ms (50 ms while an A-B loop runs) and sets it
back to 0 (`hotkeys.c` ignores 0). It can only react to action ids that exist
in `src/misc/actions.c`, and VLC still runs the action's normal handler
(`PutAction` in `hotkeys.c`). So the five triggers are actions whose handler
does nothing for music:

| Trigger | VLC action (`key-` prefix in vlcrc) | VLC's own handler | Default key |
|---|---|---|---|
| A-B loop | `subsync-markaudio` | stores a time stamp for subtitle sync (only used by `subsync-apply`, which needs `subsync-marksub` too; nothing visible, no `p_vout` needed) | `Ctrl+Shift+a` (VLC default `Shift+h`) |
| Next folder | `viewpoint-roll-clock` | `if( p_vout )` 360 degree view roll; no default key | `Ctrl+Shift+Right` |
| Previous folder | `viewpoint-roll-anticlock` | same; no default key | `Ctrl+Shift+Left` |
| Next EQ preset | `viewpoint-fov-in` | 360 degree zoom, only when a vout can change viewpoint (`input.c` `viewpoint-changeable`); VLC default `Page Up` | `Ctrl+Shift+Up` |
| Previous EQ preset | `viewpoint-fov-out` | same; VLC default `Page Down` | `Ctrl+Shift+Down` |

Why these: candidates were checked one by one in `PutAction`.
`set-bookmark1..10` writes a bookmark into the configuration, `play-bookmark1..10`
jumps in the playlist, `record`, `wallpaper`, `disc-menu`, `nav-*`, `title-*`,
`chapter-*`, `program-sid-*`, `audio-track`, `subsync-reset` (dereferences a
missing input) and `subpos-*` (dereferences a missing vout) have effects or
risks with audio; `crop*`, `zoom*`, `aspect-ratio`, `deinterlace*`,
`subtitle-text-scale-*` only act when a video output exists but would change
real video. The `viewpoint-*` actions need a vout *and* a 360 degree video
(`viewpoint-changeable`), so they do nothing for audio and for normal video;
two of them have no default key. `subsync-markaudio` has no effect at all
unless the user runs the subtitle sync workflow.

Default keys avoid every VLC default (VLC uses plain letters, `Shift+letter`,
`Alt+letter`, `Ctrl+arrows`, `Ctrl+Alt+arrows`, F keys; checked in
`src/libvlc-module.c`) and `Ctrl+Alt+...` (which is AltGr on many keyboards).
Replacing the keys of `viewpoint-fov-in` / `-out` (Page Up / Down) and
`subsync-markaudio` (`Shift+h`) takes those defaults away; only subtitle sync
and 360 degree video use them.

Ways to trigger an action:

- **Keyboard**, while the skin has focus: VLC's hotkeys. Skin key presses reach
  VLC through the Qt dialogs provider (`Dialogs::sendKey`), so the Qt plugin
  must be there (standard on Windows and in distribution packages). Tested
  with `xdotool` against the harness (Qt plugin present).
- **Global hotkeys** (VLC not focused): VLC's `global-key-<action>` options, for
  example `global-key-subsync-markaudio=Ctrl+Alt+F9`, in Tools > Preferences >
  All > Hotkeys, or vlcrc. Not set by default (a system-wide key can collide
  with other programs). Windows: `globalhotkeys/win32.c`; Linux: X11 only
  (`globalhotkeys/xcb.c`). Not tested (the harness has no desktop to grab
  keys from).
- **Web interface**: `requests/status.json?command=key&val=<action name without
  "key-">` (`httprequests.lua` calls `common.hotkey("key-"..val)`, which sets
  `key-action`). Needs the http password:
  `curl -u :PASSWORD "http://127.0.0.1:48080/requests/status.json?command=key&val=subsync-markaudio"`.
  The Windows helper's tray menu "Playback" uses this through
  `VlcDock.Remote.SendAsync("key", ...)`.

Limits of the bridge: `key-action` is a single slot, so two triggers within one
poll period (100 ms) lose one; only keys that VLC maps to an action reach
the script.

### What the script does

- **A-B loop**: 1st trigger stores A (current `time`, microseconds, from
  `vlc.var.get(vlc.object.input(), "time")`), 2nd stores B (at least 0.5 s after
  A) and seeks to A, from then on `time >= B` seeks to A; 3rd clears. Also
  cleared when the track changes or playback stops. Measured: the loop turns
  about 0.2 s after B (harness, WAV files); A and B are read from the
  same variable, so the loop length stays right. State goes to
  the log (`vlc -v`; `-vv` also logs each turn). **The
  skin cannot show it**: skins2 computes the title text (`$N`) once, when an
  input starts (`VlcProc::update_current_input`), so changing the title meta
  from Lua would not reach it (and would rename the playlist entry). The only
  live text fields are the bitrate and sample-rate (`$B`, `$S`); using them for
  A-B state would be a hack and was not done.
- **Next / previous folder**: flattens `vlc.playlist.get("playlist")` in play
  order, takes the directory of each item's `file://` URI (case-folded on
  Windows, percent-escapes normalised), then `vlc.playlist.gotoitem(id)` to the
  first item of a different directory (next), or to the first item of the
  previous directory group (previous). Streams and other schemes are skipped.
  Folders must be contiguous in the playlist. With random on it still follows
  the list order. From a stopped player it starts playing there.
- **EQ presets**: index kept in the script (starts at Flat), `vlc.equalizer.enable(true)`
  then `vlc.equalizer.setpreset(i)` (18 presets; the filter must be loaded and
  an audio output exist, `setpreset` returns nil otherwise: then it retries for
  6 s). It re-applies the preset when a new track starts, as long as the
  equalizer is on. The skin's EQ panel follows (its sliders watch the same
  variables), so the change is visible. The name goes to the log.
- **Bitrate** (`$B kbps` in the full player): skins2 shows the input's
  `bit-rate` variable (`/ 1000`), VLC sets it only from a bitrate the codec
  declares (`es_out.c`, `fmt->i_bitrate`), so FLAC and other lossless files showed
  an empty value. When it is 0 the script sets it once per track to file size x 8 /
  duration (local files; else bytes read x 8 / seconds played, after 5 s), in
  whole kbps. Nothing else reads `bit-rate` except `$B` in title formats
  (`src/text/strings.c`), and the core only writes it when the codec declares
  one. The sample rate (`$S`) stays integer kHz ("44" for 44.1 kHz): skins2
  does `sample-rate / 1000` in integer arithmetic (`vlcproc.cpp`) and
  the skin has no other source for it, so neither Lua nor the skin can show "44.1".
- Robustness: every part runs in `pcall`; an error is logged (once per 5 s per
  message) and the loop goes on. Nothing playing, empty playlist, stop / start,
  playlist changes were tried. The loop ends when VLC quits (`vlc.misc.mwait`
  raises "Interrupted"). CPU: 0.1 % more over 30 s while playing (harness).

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
- Release: build all four scales (`--scale 1 / 1.25 / 1.5 / 2`) twice, the 24 px
  set and the taskbar set (`--bar-height 36`, `VLC-Amp-taskbar-NNN.vlt`), copy
  the `.vlt` files to the repo root, run `tools/doc-shots.sh` if the look changed.

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
