# skins2: per-row background bitmaps for the Playtree

**Status:** draft, not filed. **Affects:** VLC 3.0.x, skins2 interface (the playlist control).
**Tested on:** VLC 3.0.20 (Linux, X11). Source read on branch `3.0.x`.

## Problem

A skin wants each playlist row to have a rounded background and a border, with a stronger look for
the selected and hovered row. skins2 colours the rows only with flat fills; there is no per-row
shape, so the rows are plain bands.

## Current behaviour and evidence

- `modules/gui/skins2/controls/ctrl_tree.cpp` (`3.0.x`), `CtrlTree::makeImage()`:
  - with `m_pBgBitmap` (the `bgimage` attribute): one bitmap, scaled to the whole control, drawn once at
    (0, 0). It is not drawn per row.
  - selected rows get a `fillRect` in `m_selColor` over it;
  - without a bitmap: the area is filled with `bgcolor1`, rows alternate `bgcolor1` / `bgcolor2`,
    selected rows use `selcolor`.
  - the row icon can be `itemimage` / `openimage` / `closedimage`, one bitmap each, not per row.
- The `<Playtree>` attribute list (`parser/skin_parser.cpp`) has `bgimage`, `itemimage`, `openimage`,
  `closedimage` and the four colours: no row-state images (normal, hover, selected).
- Our fork's note: `docs/vlc-feature-requests.md`, "Per-item hover / selection styling".

## Proposed API

- Attributes on `<Playtree>`: `rowimage` (normal row), `rowimage-sel` (selected), `rowimage-play`
  (playing), each a 9-slice-capable bitmap that is stretched to the row rectangle (height = row
  height, width = control width minus the scroll bar).
- The image is drawn before the text; the text colour rules stay as they are.
- Optional `rowmargin="6"` to inset the row image from the control edge (to match a skin margin rule).

## Example theme XML (proposed)

```xml
<Playtree id="pt" x="12" y="40" width="300" height="200" font="lcd10"
          rowimage="row_normal" rowimage-sel="row_sel" rowimage-play="row_play"
          rowmargin="6" fgcolor="#d8f0ff" selcolor="#1f4a5c" />
```

## Acceptance criteria

1. Each row shows `rowimage`, the selected row shows `rowimage-sel`, the playing row `rowimage-play`.
2. A row image stretched to a 16 px row height keeps its 4 px corners (9-slice, or a fixed radius
   documented in the request).
3. A skin without the attributes renders exactly as before (pixel compare).
4. No measurable CPU change for a 200-row list while scrolling.
