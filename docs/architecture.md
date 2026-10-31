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
                    VLC skins2 interface  <--  vlcrc (intf=skins2, skins2-last=...)  <--  taskbar/Setup.cmd
                                          |
               taskbar/VlcDock.cs (Windows) moves / pins VLC's window, read via its window region
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

## The Windows helper (`taskbar/`)

- `vlc-taskbar.ps1 -Setup` writes `vlcrc` (UTF-8 without BOM): `intf=skins2`,
  `skins2-last`, `one-instance=1`, `one-instance-when-started-from-file=1`,
  `playlist-enqueue=0`, `media-library=0`, `skins2-taskbar`, and the control
  channel's `extraintf` (`http`, merged into the colon-separated list with
  `Set-VlcModule`), `http-host=127.0.0.1`, `http-port=48080` (both `[core]`) and
  a random `http-password` (`[lua]`, kept if already set). It also installs the Lua interface
  and its default keys (see "Lua interface"). It rewrites every
  line of a key (vlcrc can hold a commented default and an active line).
  Optionally it creates a Startup shortcut running the helper with `-Watch`
  (and `-NoDock`).
- `VlcDock.cs` finds VLC's `SkinWindowClass` windows (skipping the 1 x 1 flag
  windows), reads the main window's region (`GetWindowRgn`): if the visible
  box reaches the window bottom, the bar is at the bottom; a pixel test at the
  strip's rounded corner tells the strip from the full player. Then it moves
  the window so the strip sits in the taskbar, re-asserts `HWND_TOPMOST` when
  the taskbar is above it, and steps aside for full-screen apps.
- Start pinned: VLC never saves "always on top", so the helper posts a click
  (`WM_MOUSEMOVE` / `WM_LBUTTONDOWN` / `UP`) on the skin's own pin button
  1.5 s after VLC's window appears. The positions in `PinOnce` / `ClickPin` must
  follow the generator's layout.
- Tray icon (NotifyIcon with a classic `ContextMenu`, pumped by the helper's
  own `GetMessage` loop) and an opt-in log (`LogPath`, `-DebugLog`). The menu's
  "Playback" submenu (A-B loop, next / previous folder, next EQ preset) sends
  VLC hotkey actions through the control channel, see "Lua interface".
- Media controls (Setup only): the third-party control-interface plugin
  `libwin10smtc_plugin.dll` (vlc-win10smtc, pinned version and SHA-256 in
  `vlc-taskbar.ps1`) goes into `<VLC>\plugins\misc`, and `win10smtc` into the
  colon-separated `extraintf` list (`Set-VlcModule` keeps other entries).
  VLC starts `extraintf` modules whatever the main interface is
  (`src/libvlc.c`), so it runs next to skins2 and has its own hidden window.
- Linux needs none of this for media controls: the `vlc` launcher always adds
  `--dbus` (and `--media-library`, which overrides `media-library=0` in
  vlcrc; `bin/vlc.c`), so MPRIS is on. Tested with the skin.
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

## Lua interface (`lua/intf/titlebar.lua`)

A-B loop, next / previous folder, equalizer presets and a bitrate for lossless
files: things a skins2 button cannot do (a button can only run skins2's own
action list). A Lua *interface* script runs inside VLC next to the skin, on
Windows and Linux alike. Facts below were checked in the VLC 3.0.x source
(`modules/control/hotkeys.c`, `src/misc/actions.c`, `modules/lua/*`,
`share/lua/*`, `modules/gui/skins2/src/vlcproc.cpp`) and by running real
VLC 3.0.20 under the test harness (`tools/`).

### Start and install (what Setup / `linux/setup.sh` must do)

| What | Value |
|---|---|
| Script | copy `lua/intf/titlebar.lua` to VLC's user Lua folder, `intf/titlebar.lua` |
| Windows folder | `%APPDATA%\vlc\lua\intf\` (create it) |
| Linux folder | `${XDG_DATA_HOME:-$HOME/.local/share}/vlc/lua/intf/` (create it). Flatpak VLC: `~/.var/app/org.videolan.VLC/data/vlc/lua/intf/` (not tested) |
| vlcrc | Windows `%APPDATA%\vlc\vlcrc`; Linux `${XDG_CONFIG_HOME:-$HOME/.config}/vlc/vlcrc` |
| `[core]` `extraintf` | add `luaintf` to the colon-separated list (`http:luaintf`, `win10smtc:http:luaintf`), keep the others |
| `[lua]` `lua-intf` | `titlebar` (the option belongs to the `lua` module, like `http-password`; only set it when it is unset or `dummy`) |
| `[core]` keys | the five `key-...` lines of `lua/vlcrc-keys.txt` (format `<section> <key>=<value>`, `#` comments), written only when vlcrc has no active, non-empty value for the key. Both `vlc-taskbar.ps1 -Setup` and `linux/setup.sh` read this file, so it is the one list to edit |

Both `http` and `luaintf` are interface modules of VLC's one `lua` plugin;
`lua-intf` is read only by `luaintf` (`modules/lua/intf.c`: `http`, `cli` and
`telnet` pass their own script name), so `extraintf=http:luaintf` runs the web
interface and `titlebar.lua` side by side. Checked by running it, from vlcrc
only. The script needs a VLC with Lua (the Windows build and the Ubuntu 24.04
packages used by the harness have it; other distributions: not checked). It also works with Lua 5.1
(Windows) and 5.2 (the Ubuntu 24.04 build used by the harness).

vlcrc lines, exactly (same as `lua/vlcrc-keys.txt` plus the two lines the setups handle themselves; the `[lua]` and `[core]` section headers only matter for
a file that does not have the option yet; VLC reads these keys from any
section):

```
[core]
extraintf=http:luaintf
key-subsync-markaudio=Ctrl+Shift+a
key-viewpoint-roll-clock=Ctrl+Shift+Right
key-viewpoint-roll-anticlock=Ctrl+Shift+Left
key-viewpoint-fov-in=Ctrl+Shift+Up
key-viewpoint-fov-out=Ctrl+Shift+Down
[lua]
lua-intf=titlebar
```

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
