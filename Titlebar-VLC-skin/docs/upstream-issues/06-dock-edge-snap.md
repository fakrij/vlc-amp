# skins2: dock / edge-snap actions (window to top or bottom edge, or to a taskbar segment)

**Status:** draft, not filed. **Affects:** VLC 3.0.x, skins2 interface, Windows and X11.
**Tested on:** VLC 3.0.20 (Linux, X11; Windows tested by the skin author with a helper, not in skins2).
Source read on branch `3.0.x`.

## Problem

A skin author wants buttons that place the player against a screen edge, the way a dock does
(top edge, bottom edge, next to the taskbar), and a way to stay on top. Today this is only
possible by an external helper process on Windows (the author's dock helper); the skin cannot do it.

## Current behaviour and evidence

- `modules/gui/skins2/src/top_window.cpp` (`3.0.x`): no drag-to-move or position logic; position comes
  from the constructor and `GenericWindow`. No dock or snap function. `cmd_on_top.hpp` is included
  there but not used.
- Skin actions for on-top exist: `vlc.onTop()` and the `vlc.isOnTop` variable (`commands/cmd_on_top.cpp`).
  The X11 side is `x11_window.cpp`, `toggleOnTop()`, which sends `_NET_WM_STATE_ABOVE` /
  `NET_WM_STAYS_ON_TOP`. There is no "place at edge" action.
- The `<Theme>` element accepts `magnet`. `builder.cpp` passes it to `WindowManager::setMagnetValue()`.
  `window_manager.cpp`, `checkAnchors()`: when `magnet` is non-zero, windows that move or resize
  are pulled to the **monitor work area** edges (left, top, right, bottom). Default 0 = off.
  This is partial prior art, not a dock: it snaps to the work area only, is set once for the
  whole theme, is not an action, and does not know about the taskbar segment or a chosen side.
  **Unverified:** whether `magnet` behaves as described on X11 (only the common code was read).
- Nothing in the parser handles `dock`, `snap` or `ontop` attributes (`parser/skin_parser.cpp`).
- `x11_window.cpp` has no move-to-edge logic (`moveResize()` only positions).

## Proposed API

- Action `vlc.dock(top|bottom|left|right)`: move the window so its outer edge touches that edge of the
  work area of the current monitor, keeping x (or y) and the size. Repeated calls are idempotent.
- Action `vlc.dock(top|bottom, <offset>)` optional, for a margin.
- Variable `vlc.isDocked` (bool) and `vlc.dockSide` (string), so buttons can show their state.
- Optional `<Theme magnet="...">` stays as it is.
- Windows only, optional: `vlc.dockTaskbar(start|end)` placing the window next to the taskbar segment.
  Left out of the minimum request.

## Example theme XML (proposed)

```xml
<Checkbox id="t_dock" x="300" y="6" width="22" height="16"
          visible="true"
          action="vlc.dock(top)" action2="vlc.dock(bottom)"
          tooltiptext="Dock to top edge" />
```

## Acceptance criteria

1. `vlc.dock(top)` puts the window's top edge on the work-area top, x unchanged, on X11 and Windows.
2. A window moved by the user is not moved back by skins2 (no fight with the window manager).
3. Repeating the action does not move the window again.
4. `vlc.isDocked` is true only while the window is at the requested edge.
5. Documented, with a note on multi-monitor behaviour (which monitor is used).
