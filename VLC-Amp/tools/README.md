# Test harness

Run real VLC 3.0.20 with the skin under Xvfb, click it and take screenshots.
No sudo, no root, no system packages installed. Written for Ubuntu 24.04
(WSL), where VLC is not installed.

## Quick start

```bash
tools/setup-test-env.sh                       # once; about 1 minute, 80 MB download
~/.cache/titlebar-test/venv/bin/python source/build_skin.py --out /tmp/skin   # needs Pillow: use the venv
tools/vlc-test.sh start /tmp/skin/VLC-Amp-100.vlt
tools/vlc-test.sh click 479 12                # PL button of the strip at 100 %
tools/vlc-test.sh shot playlist               # prints the PNG path; view it with an image viewer
tools/vlc-test.sh quit                        # clean exit, VLC saves its state
tools/vlc-test.sh xvfb-stop
```

`tools/vlc-test.sh build [scale] [bar-height]` does the build step for you into
`~/.cache/titlebar-test/skins` (`scale` 1, 1.25, 1.5, 2; bar height 24, or 36 for
the taller taskbar strip; width from `TB_WIDTH`, default 620)
and prints the path.

## Commands

| Command | What it does |
|---|---|
| `start <vlt> [files...]` | Starts Xvfb if needed, then VLC with the skin. VLC's config is reset first (`TB_KEEP_CONFIG=1` keeps it). Default files: `song1.wav`, `song2.wav`, `song3.wav`. |
| `shot <name> [x,y,w,h]` | Screenshot to `<run dir>/shots/<name>.png`, prints the path. Crop is in screen pixels; the default is the main window. |
| `click <x> <y>` | Left click. Coordinates are relative to the main window's top-left, i.e. the skin's own pixel coordinates (the window is 620x676 at 100 % with the default width). |
| `drag <x> <y> <dx> <dy>` | Press at x,y, move by dx,dy in 10 steps, release. Moving the window by its grip: `drag 10 12 50 60`. |
| `park` | Moves the pointer off the skin (no hover state, tooltips disappear). |
| `geometry` | `X Y W H` of the main window on the screen. |
| `shape` | The X11 shape (the visible, clickable part) of the main window: bounding box, whether the bar is at the bottom, whether the full player is showing. Same height rule as `DockShape.Classify` in `taskbar/VlcDock.cs` (full player or strip from the window height, not from a pixel test); with the full player, EQ and playlist all open the window is solid and up / down cannot be read (the Windows helper keeps the last known direction, `vlc-amp-pin.py` assumes the top). |
| `quit` | Expands the strip if needed and clicks the full player's quit button, so VLC writes `skins2-config` into its `vlcrc`. Prints that line. |
| `stop` | Kills only the VLC PID this script saved. VLC does not save its state this way. |
| `xvfb-stop` | Kills only the Xvfb PID this script saved. |
| `build [scale] [bar-height]` | Builds a skin with the venv Python (see above); `build 1.5 36` makes `VLC-Amp-taskbar-150.vlt`, `build 1 40` makes `VLC-Amp-bar40-100.vlt`. |

`quit` finds the buttons from the generator's 100 % positions times the scale,
which it reads from `VLC-Amp-<n>.vlt` on VLC's command line (else `TB_SCALE`,
default 100). `shape` and `quit` also read the strip height from the file name
(`VLC-Amp-taskbar-<n>.vlt` = 36, `VLC-Amp-bar<h>-<n>.vlt` = h, else 24; `skin_bar`). `TB_WIDTH` sets the build width (default 620).
With a taller strip, the strip's buttons are centred at `bar / 2` (bar at the top)
or `window height - bar / 2` (panels above); x positions do not change. If the layout of the strip or full player changes,
update the numbers in `cmd_quit`.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `TITLEBAR_TEST_CACHE` | `~/.cache/titlebar-test` | Where everything lives. |
| `TB_DISPLAY_NUM` | `99` | X display number. `start` refuses a display that another X server already uses. |
| `TB_SCREEN` | `1280x1024x24` | Xvfb screen. |
| `TB_INSTANCE` | `default` | Name of the session: pid files, logs, VLC's private home and screenshots live in `<cache>/run-<name>/`. |
| `TB_KEEP_CONFIG` | unset | `1` = do not reset VLC's config on `start`. |
| `TB_VLC_ARGS` | unset | Extra VLC options for `start`, split on spaces (no quoting), for example `--extraintf http --http-host 127.0.0.1 --http-port 48080 --http-password x` to test the helper's control channel. |
| `TB_SCALE` | `100` | Scale in percent for `quit` and `shape` when the running skin's file name is not on VLC's command line (`VLC-Amp-<n>.vlt`). |

Several agents at the same time (they share the downloaded packages): give
each its own `TB_INSTANCE` and `TB_DISPLAY_NUM`, for example
`export TB_INSTANCE=a TB_DISPLAY_NUM=91`.

## Files

- `setup-test-env.sh`: downloads the packages with `apt-get download`
  (vlc-bin, vlc-plugin-base, vlc-plugin-skins2, xvfb, xdotool, imagemagick,
  x11-xkb-utils and their recursive dependencies that are not installed),
  unpacks them with `dpkg-deb -x` into `<cache>/root`, creates a Python venv
  with Pillow and python-xlib, and generates test audio: `song1.wav` (3:10),
  `song2.wav` (4:12), `song3.wav` (2:05) and `long.wav` (1:03:00, to test
  hour formats; pass it to `start`). Safe to run again; `FORCE=1` redoes the
  extract and venv steps.
- `vlc-test.sh`: the commands above.
- `vlc-env.sh`: paths and the environment for the extracted programs (sourced
  by both scripts).
- `xshape.py`: reads the X11 shape (used by `shape` and `quit`).
- `doc-shots.sh`: regenerates the three images `docs/img-thin/{strip,strip-panels,full-eq}.png` from a
  build in one command (620 px window, 24 px strip; `BAR=40` for the concept
  strip). Uses `TB_DISPLAY_NUM` / `TB_INSTANCE` like the other commands.
- `bitmap-audit.py`: scans every bitmap of the builds (4 scales,
  4 themes) for semi-transparent pixels, which X11 turns black. Use this instead of
  `windows-sim.py`.
- `theme-audit.py`: contrast table of every theme.
- `icon-symmetry.py`: mirror-diffs every icon (left-right / up-down alpha difference per icon, bar height
  and scale); `python tools/icon-symmetry.py <source dir> <out.json>`, needs numpy.
- `make-cell-font.py`: makes `source/fonts/VLCAmpMono.ttf` (the `<Font>` file in every `.vlt`) from
  `DejaVuSansMono.ttf`: glyph boxes widened to the cell, because skins2 drops FreeType's `bitmap_left`
  (PP13, `docs/font-notes.md` "Glyph placement"). Needs fontTools in its own venv
  (`python3 -m venv /tmp/ft && /tmp/ft/bin/pip install fonttools`); output is deterministic.
- `sync-configurator.py`: copies `source/build_skin.py` and the font files (DejaVu, VLCAmpMono) into `configurator/` and
  verifies that the CLI and the copy build identical skins (8 option sets; `--pyodide <dir> <pillow wheel>`
  adds the Pyodide build). Run it after every generator change. `configurator/sync.sh` is its dependency-free
  copy-only twin.
- `windows-sim.py`: **legacy**. Models how skins2 on X11 and on Windows would blend the old (pre hi-fi)
  semi-transparent bitmaps (the comparison images it wrote are no longer in the repository); no VLC needed,
  uses the harness venv's Pillow. Kept for reference only; the bitmap scan above replaces its role.
- `make-windows-package.sh`: builds `dist/VLC-Amp-windows/` (and a zip)
  to copy to a Windows PC. Not part of the test harness.
- `make-linux-package.sh`, `make-package.sh`: build `dist/VLC-Amp-linux/` (and a
  `.tar.gz`); `make-package.sh [windows|linux|all]` runs one or both.
- `check-windows-helper.sh`, `test-repair-video-window.ps1`, `test-sync-vlcrc.ps1`:
  Windows helper checks, see the end of this file.
- `pyodide-spike/`: a spike (node + Pyodide) that checks whether the generator
  runs unchanged in the browser. Its own README has the details.

The extracted tree has the Qt plugin (`libqt_plugin.so`), which skin keyboard input needs.

## Gotchas (all handled by the scripts)

- Xvfb runs `xkbcomp` from `/usr/bin`, which is not installed. `start` mounts
  an overlay on `/usr/bin` inside a user namespace
  (`unshare -Urm`) that adds the extracted `xkbcomp`. The server is started
  with `exec`, so the saved PID is Xvfb itself.
- The extracted programs need `LD_LIBRARY_PATH`, `VLC_PLUGIN_PATH`,
  `VLC_DATA_PATH`, `QT_PLUGIN_PATH`, and for ImageMagick `MAGICK_CONFIGURE_PATH`
  and `MAGICK_CODER_MODULE_PATH`. `vlc-env.sh` sets them only inside the
  scripts, not in your shell.
- VLC runs with a private `HOME`, so your own VLC config is never read or
  changed.
- Screenshots are taken with ImageMagick's `import` as PPM and cropped and
  saved as PNG with Pillow. Pillow is not installed system-wide (PEP 668),
  hence the venv.
- VLC only writes `skins2-config` (window position, layout, open panels) on a
  clean exit, so use `quit`. `kill` loses it. It is stored as the
  `skins2-config` line of `<run dir>/home/.config/vlc/vlcrc`.
- Never use `pkill vlc` or `killall`: they can hit someone else's VLC. The
  scripts only kill the PIDs they saved, and check `/proc/<pid>/comm` first.
- `setsid cmd &` makes `$!` the wrong PID, so the scripts do not use it.
- VLC's log (`<run dir>/vlc.log`) has `cannot load module` warnings for
  PulseAudio, SID, libavformat and similar plugins. The packages' optional
  dependencies are not downloaded; none of them matter for the skin
  (audio goes to the dummy output, no video).
- The mouse pointer is parked at 5,5 after `start` so no button shows hover.
  Tooltips appear after a click (the pointer stays on the button).

## Limits

- Only for Linux skins2; it cannot test the Windows helper (`taskbar/`).
- Audio is a dummy output: it plays, but you hear nothing.

`tools/check-windows-helper.sh` (WSL): compiles `taskbar/VlcDock.cs` with the Windows C# compiler and parses the PowerShell scripts; run it after every helper edit.

Windows-only checks, run from WSL after `tools/check-windows-helper.sh` (it builds the DLL the second one loads):
`powershell.exe -File tools/test-repair-video-window.ps1 -Src taskbar/vlc-taskbar.ps1` (Setup's `Repair-VideoWindow`) and
`powershell.exe -File tools/test-sync-vlcrc.ps1` (the helper's `SyncVlcrcTheme`, on a temporary `APPDATA`; pass full Windows paths).
