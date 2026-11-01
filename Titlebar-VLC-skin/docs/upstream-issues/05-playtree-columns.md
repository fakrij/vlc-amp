# skins2: multi-column Playtree (number, title, duration, artist)

**Status:** draft, not filed. **Affects:** VLC 3.0.x, skins2 interface (the playlist control).
**Tested on:** VLC 3.0.20 (Linux, X11). Source read on branch `3.0.x`.

## Problem

The playlist shows one text per row: the title or the file name. A skin author wants a number
column, a title column and a right-aligned duration column (and optionally an artist column), as
every player's playlist has. The duration is the most asked for: the user wants to see the length of
each track in the list.

## Current behaviour and evidence

- `modules/gui/skins2/controls/ctrl_tree.cpp` (`3.0.x`), `CtrlTree::makeImage()`: each row draws one
  string from `it->getString()` with `m_rFont.drawString()`, width capped at
  `width - bitmapWidth * depth`. There is no column loop, no column width, no second string.
- The `<Playtree>` element accepts: id, font, visible, flat, x, y, width, height, position, xoffset,
  yoffset, xmargin, ymargin, lefttop, rightbottom, xkeepratio, ykeepratio, bgimage, itemimage,
  openimage, closedimage, fgcolor, playcolor, bgcolor1, bgcolor2, selcolor, help
  (`parser/skin_parser.cpp`). No `columns`, no column definition.
- The row text is produced by the playlist item name, so there is no duration or number to draw.
- The skin's own notes: BACKLOG.md item 8 (BLOCKED) and `docs/vlc-feature-requests.md` (playlist note).
- Lua can read the duration: `vlc.playlist.get` items have `duration` in seconds, -1 if unknown
  (`docs/lua-api-notes.md` Q4). The skin cannot display it.

## Proposed API

```xml
<Playtree id="pt" ...>
  <PlaytreeColumn var="number"   width="32"  align="right" />
  <PlaytreeColumn var="title"    width="*"   align="left" />
  <PlaytreeColumn var="duration" width="48"  align="right" />
</Playtree>
```

- `var` values: `number` (1-based position in the list), `title` (the current row text), `duration`
  (`mm:ss` or `h:mm:ss`, from the item duration), `artist` (item meta, empty when missing).
- `width="*"` takes the remaining width; fixed widths are in skin pixels (scaled like other sizes).
- Without `<PlaytreeColumn>` the control behaves as today (one column).

## Example theme XML (proposed)

```xml
<Playtree id="pt" x="12" y="40" width="300" height="200" font="lcd10"
          fgcolor="#d8f0ff" playcolor="#7fe6ff" bgcolor1="#0b1a22" bgcolor2="#0e2029" selcolor="#1f4a5c">
  <PlaytreeColumn var="number"   width="32" align="right" />
  <PlaytreeColumn var="title"    width="*"  align="left" />
  <PlaytreeColumn var="duration" width="48" align="right" />
</Playtree>
```

## Acceptance criteria

1. With the three columns, every row shows its number, title and duration on one line; the duration
   is right-aligned at the same x for all rows.
2. A title wider than its column is cut (or scrolls) inside the title column and never draws over the
   duration column.
3. Unknown duration shows an empty cell, not `-1`.
4. A skin without `<PlaytreeColumn>` renders exactly as before (regression: pixel compare of an existing skin).
5. Selection, play colour and the scroll bar work across all columns.
