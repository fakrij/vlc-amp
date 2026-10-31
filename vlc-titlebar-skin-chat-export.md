# VLC "Titlebar" skin: chat export and handoff

Exported 2026-10-30. Attach `Titlebar-VLC-skin.zip` (from this chat) when continuing elsewhere; it holds all code and built files.

---

## 1. Conversation log

### 1.1 Request: design a VLC music skin based on MMD3
**Jiri:** Create a VLC skin for playing music, based on the MMD3 skin. Key feature from MMD3: it collapses into a bar that fits into a standard Windows title bar. Collapsed bar must have: expand-to-full-player, previous, slower, play/pause, faster, next, song name window (rotating if too long), playtime countdown window, volume slider, buttons to open playlist and equalizer. Suggest a design.

**Claude:** Built an interactive design canvas: [VLC Titlebar Skin](https://claude.ai/artifact/BWECZ6kPYa4J5o5LQALu8G) with 3 artboards:
- Collapsed strip 556 x 24 px (light and dark title bar at real size, 2x anatomy with numbered legend)
- Expanded player 400 x 146 px
- EQ + playlist docked under the strip

Look: dark graphite bevels, cyan LCD readouts (#63D8EC on #061114), amber LEDs for toggles. MMD3 "spirit from memory", not a pixel copy.

### 1.2 Request: add always-on-top button
**Claude:** Added a pin toggle (amber when on) to the strip (far right, after EQ), the expanded player (top bar) and the panels artboard. Title display shrank 196 -> 172 px so the strip stayed 556 px.

### 1.3 Request: build it, make width variable, can it go into the taskbar left of the Windows icon?
**Claude:** Built the real skin (skins2 `.vlt`), verified against VLC source, tested in real VLC 3.0.20 (Linux, same skins2 engine). Delivered `Titlebar-VLC-skin.zip`. Answered taskbar question: possible only as a floating window kept on top; true embedding not possible on Windows 11.

### 1.4 Question: "what about the widget?"
**Claude:** Two readings: (1) the Widgets/weather button at the left of the Win11 taskbar, which occupies that space and can be turned off; (2) a real Windows 11 Widgets-board widget, possible via Windows App SDK but lives in the Win+W panel, not the taskbar, and VLC 3 has no Windows media integration ([VLC issue #26155](https://code.videolan.org/videolan/vlc/-/issues/26155)). Mentioned community plugin [vlc-win10smtc](https://github.com/spmn/vlc-win10smtc) (unverified on current Win11). Source on third-party widgets: [BetaNews](https://betanews.com/2022/10/06/windows-11-build-25217-third-party-widgets/).

### 1.5 Request: option 1, and the player must be integrated into the bar
**Claude:** Wrote a taskbar dock helper (PowerShell + embedded C#), added to the zip under `taskbar/`. Not tested on Windows (no Windows machine available); C# compile-checked.

### 1.6 Question: complete rework or upgrade?
**Claude:** Upgrade. The `.vlt` skin files are unchanged; the zip only gained the optional `taskbar/` folder and a README section.

---

## 2. Package contents (`Titlebar-VLC-skin.zip`)

```
Titlebar-VLC-skin/
  Titlebar-100.vlt  Titlebar-125.vlt  Titlebar-150.vlt  Titlebar-200.vlt   # pick by Windows display scaling
  README.md
  preview.png
  source/build_skin.py          # parametric generator (Python 3 + Pillow)
  source/fonts/                 # DejaVuSansMono.ttf, DejaVuSans-Bold.ttf, LICENSE-DejaVu.txt
  taskbar/VLC in taskbar.cmd    # double-click launcher
  taskbar/vlc-taskbar.ps1       # settings + launches VLC + loads C#
  taskbar/VlcDock.cs            # docking logic (C# 5, for Windows PowerShell 5.1 Add-Type)
```

Rebuild: `python3 build_skin.py --scale 1.5 --width 480 --full-width 420 --preview`
(`--width` min 428, `--full-width` min 340; output in `dist/`).

Install skin only: VLC > Tools > Preferences > Interface > Use custom skin > choose .vlt > Save > restart.

---

## 3. Skin spec (logical px at 100%; multiply by scale)

### Windows and layouts
| Window id | Layout id | Default size | Resizable | Notes |
|---|---|---|---|---|
| `main` | `strip` | 556 x 24 | width 428 to 4000 | **Default layout = last in XML** (VLC sets active layout on each add) |
| `main` | `full` | 400 x 146 | width 340 to 4000 | |
| `eqwin` | `eqwin-main` | 556 x 116 | width 420 to 4000 | 400 px band block in a Panel with xkeepratio (stays centered) |
| `plwin` | `plwin-main` | 556 x 198 | both, min 300 x 110 | 9-slice background |

### Strip (x positions at width 556; right group anchored `righttop`)
grip 0..14 (bg left cap, move) | expand 16 (22x18) | prev 44 | slower 68 | play/pause 92 (26x18 checkbox) | faster 120 | next 144 | title LCD 172..336 (stretches) | time LCD at W-216 (50x18, text `-$l`) | volume slider at W-160 (64 px, 65 fill frames) | PL at W-90 (26x18) | EQ at W-62 | on-top pin at W-34 (22x18) | resize grip = right cap 10 px (`resizeE`).

### Full player
Top row: NOW PLAYING label, menu (`dialogs.popup()`), pin, collapse, minimize, quit (18x12 each, right-anchored).
LCD: big `-$l` (26 pt), `$t / $d`, `SPEED $Rx`, title `$N` (stretches), `$B kbps  $S kHz`, LCD toggles SHUF / LOOP / REP1.
Seek bar (`time`, 101 fill frames, stretches), transport 28x22 buttons, speaker icon, volume 90 px, PL / EQ 30x22.

### Actions and variables used (all verified in VLC 3.0.x source)
- Transport: `vlc.play()`, `vlc.pause()`, `vlc.faster()`, `vlc.slower()`, `playlist.previous()`, `playlist.next()`, `vlc.minimize()`, `vlc.quit()`, `vlc.onTop()`, `dialogs.popup()`
- Layouts / windows: `main.setLayout(full|strip)`, `eqwin.show()/hide()`, `plwin.show()/hide()`; actions chain with `;`
- Expand action: `eqwin.hide();plwin.hide();main.setLayout(full)`; collapse mirrors it (panels hidden so the taller player does not overlap them)
- State vars: `vlc.isPlaying`, `vlc.isOnTop`, `plwin.isVisible`, `eqwin.isVisible`, `equalizer.isEnabled`, `playlist.isRandom/isLoop/isRepeat`
- Playlist: `playlist.add()/del()/sort()/load()/save()`, `playlist.setRandom|setLoop|setRepeat(true|false)`
- EQ: `equalizer.enable()/disable()`, sliders `equalizer.preamp`, `equalizer.band(0..9)`
- Slider values: `volume`, `time`, `playtree.slider` (implicit in Playtree)
- Text codes: `$N` name, `$l`/`$L` time left, `$t`/`$T` elapsed, `$d`/`$D` duration, `$V` volume, `$B` bitrate, `$S` sample rate, `$R` speed
- Image actions: `move`, `resizeE`, `resizeS`, `resizeSE`; `resize="mosaic"` default
- Checkbox: state false shows `*1` images, true shows `*2`
- Anchors: strip/full bottom segment priority 30; EQ top point 20 + bottom segment 20; PL top point 10 (zero-gap stacking)
- VLC saves per window: position, active layout, width, height, visibility (`skins2-config`)

### Palette
bg #2c3137 to #1a1d21, outline #08090b, highlight #48505a; buttons #3a4047/#262a2f (hover #454c54/#2e3339, down #1d2125/#2a2f35), icons #c3cbd3 / hover #fff / active #5fd3e8; LCD #061114, text #63d8ec, secondary #4fb3c6, dim #2f6f7c; LED #f2a93b / off #4a3a1c.

---

## 4. Test results (real VLC 3.0.20, skins2, Linux under Xvfb)
Verified: theme loads with no warnings; strip is default; EQ and PL dock exactly under the strip (y 348 / 372 / 488); play/pause toggles; drag-resize 556 -> 710 works and is remembered across expand/collapse; PL window resize works (9-slice correct); pin toggles; expand/collapse work; menu button opens VLC's full menu (Qt).

Fixes made during testing:
- Default layout was `full` -> reordered layouts (`strip` last).
- Small text on transparent PNGs lost pixels on X11 -> labels baked onto opaque background crops; LCD toggles and EQ band labels drawn on LCD color.
- Double-click actions (`action2`) on the grip and title did not fire (Text control intercepts) -> removed, not documented.

Not verified: rendering on Windows itself (fonts, alpha edges), volume slider with real audio (dummy audio output showed 0).

---

## 5. Taskbar dock helper (`taskbar/`)

Why a helper: Windows 11 has no deskbands; VLC skins cannot embed in Explorer's taskbar. The helper keeps VLC's own skin windows positioned in/above the taskbar.

Behavior:
- Finds VLC windows: class `SkinWindowClass`, owned by vlc.exe, visible, excluding `WS_EX_APPWINDOW` (video/fullscreen) and `WS_EX_TOOLWINDOW` (tooltips, hidden parent). Classifies by height: 24 = strip, 146 = full, 116 = EQ, other >= 100 = playlist (all x scale; scale read from skin filename, e.g. `Titlebar-150.vlt` -> 1.5).
- Strip: vertically centered in taskbar, right edge `Gap` px left of the Start button (found via UI Automation, AutomationId `StartButton`, refreshed every 2 s). Fallback: left end of taskbar.
- Full player, EQ, playlist: stacked upward above the taskbar (downward if taskbar is at the top).
- Re-places windows on `EVENT_OBJECT_LOCATIONCHANGE` (VLC process) and every 250 ms, because skins2 does not track external moves (no WM_MOVE handling; it re-applies its stored position on resize/layout change, so a brief flicker is possible).
- Re-asserts `HWND_TOPMOST` only when a window is below `Shell_TrayWnd` in z-order (avoids covering VLC's own popup menu).
- Fullscreen foreground app: drops to NOTOPMOST and behind it; restores after.
- Hotkey Ctrl+Alt+Shift+V toggles docking. Exits 5 s after VLC exits. Single instance (mutex).
- Launcher starts VLC with `--intf skins2 --skins2-last="<vlt>" --no-skins2-taskbar` (normal VLC stays Qt).

Settings (top of `vlc-taskbar.ps1`): `$Skin`, `$DockTo` (`start` | `left` | `right` next to tray), `$Gap`, `$OffsetY`, `$HideVlcTaskbarButton`, `$StartVlc`.

Setup: Settings > Personalization > Taskbar > Widgets: Off; close VLC; double-click `VLC in taskbar.cmd`. Autostart: shortcut in `shell:startup`.

Status: **untested on Windows.** C# compile-checked with Mono (`-langversion:5`, UIA stubs). Least certain parts: UIA lookup of the Start button, staying above the taskbar after it is clicked.

---

## 6. Open items / next steps
1. Run taskbar mode on Windows 11 and report: does the strip land left of Start, stay above the taskbar, flicker on expand?
2. Check skin rendering on Windows (edges, fonts); pick the right scale build.
3. Possible tweaks: a taller taskbar-specific strip (e.g. 36 px), hiding the pin button in taskbar mode, a tray icon for the helper instead of a hotkey.
4. Known limitations: no EQ presets / reset / playlist search (not supported by skins2); always-on-top starts off (VLC-controlled); videos open in VLC's separate video window.

## Sources
- VLC skins2 source (3.0.x branch): [videolan/vlc on GitHub](https://github.com/videolan/vlc/tree/3.0.x/modules/gui/skins2)
- [VLC feature request #26155: Windows media controls](https://code.videolan.org/videolan/vlc/-/issues/26155)
- [vlc-win10smtc](https://github.com/spmn/vlc-win10smtc)
- [Windows 11 third-party widgets (BetaNews)](https://betanews.com/2022/10/06/windows-11-build-25217-third-party-widgets/)
- Design canvas: [VLC Titlebar Skin](https://claude.ai/artifact/BWECZ6kPYa4J5o5LQALu8G)
