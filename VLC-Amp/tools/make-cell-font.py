#!/usr/bin/env python3
"""Make source/fonts/VLCAmpMono.ttf from source/fonts/DejaVuSansMono.ttf (PP13).

skins2 (VLC 3.0.x, modules/gui/skins2/src/ft2_font.cpp, FT2Font::drawString) draws each glyph
bitmap at the pen position and ignores the bitmap's left offset (bitmap_left), so a glyph's
left side bearing is lost: ":" "." "r" "-" sit at the left edge of their cell and leave a hole
after them. FreeType's bitmap starts at the left edge of the outline's control box. This script
gives every glyph whose ink starts right of the cell edge one extra point at x = 0, so the
control box (and the bitmap) start at the cell edge and the bearing travels inside the bitmap.
Glyphs whose ink ends left of the advance get a second point at x = advance (1233 units): every
such glyph's box is then 0 .. ceil(1233 x px / 2048) px wide, so a string's bitmap has the same
width whatever its last character (skins2 sizes it pen + last glyph's box width), and centred or
right-aligned text no longer moves by 1 px when the last digit changes. The box is 1 px wider
than the hinted advance (round(1233 x px / 2048)) at most sizes: FreeType's v40 interpreter
(default since 2.7) does not round component x offsets, so the point cannot sit on the pixel
grid; the extra column is empty and only widens the string bitmap and skins2's "..." test by 1 px.

How, without touching the hinting: the original glyph is kept unchanged as "<name>.base" and
"<name>" becomes a composite of "<name>.base" (offset 0, USE_MY_METRICS: hinted advance from
the original) plus "cellorigin", a glyph made of one point, placed at (0, middle of the glyph's
height) and, for the right edge, at (advance, same height). TrueType instructions address
points by number (the phantom points come right after the outline's own points), so appending a point to the original would shift them; components
are hinted on their own, with their own numbering. Existing composites are pointed at the
".base" glyphs for the same reason. The point has no area, so nothing is painted; advances
(all 1233 units) and the hinted ink stay identical (checked with FreeType at 8-64 px).
Glyphs whose ink already starts at or left of x = 0 and ends at or right of the advance are left
alone (ink outside the cell cannot be helped: skins2 still shifts it by its overhang).

The Bitstream Vera licence requires a modified font to be renamed (no "Bitstream", no "Vera");
it is renamed to "VLC Amp Mono" (the "DejaVu" name is dropped too, to avoid confusion with the
original). Copyright and licence strings are kept.

Needs fontTools (not in the harness venv):  python3 -m venv /tmp/ft && /tmp/ft/bin/pip install fonttools
Usage:  /tmp/ft/bin/python tools/make-cell-font.py [in.ttf] [out.ttf]
The output is deterministic (timestamps copied from the input).
"""
import os
import sys

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import ttProgram
from fontTools.ttLib.tables._g_l_y_f import (Glyph, GlyphComponent, GlyphCoordinates, ROUND_XY_TO_GRID,
                                             USE_MY_METRICS)

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "source", "fonts", "DejaVuSansMono.ttf")
DST = os.path.join(HERE, "..", "source", "fonts", "VLCAmpMono.ttf")
FAMILY = "VLC Amp Mono"
PS_NAME = "VLCAmpMono"
ORIGIN = "cellorigin"


def empty_program():
    p = ttProgram.Program()
    p.fromBytecode(b"")
    return p


def component(name, x, y, flags):
    c = GlyphComponent()
    c.glyphName, c.x, c.y, c.flags = name, x, y, flags
    return c


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else SRC
    dst = sys.argv[2] if len(sys.argv) > 2 else DST
    # recalcBBoxes=False: keep every original glyph's stored bounding box. FreeType places the
    # outline with phantom point pp1.x = stored xMin - lsb, and in some DejaVu glyphs the stored
    # box differs from the points; recomputing it would move those glyphs.
    f = TTFont(src, recalcTimestamp=False, recalcBBoxes=False)
    glyf, hmtx = f["glyf"], f["hmtx"]
    order = list(f.getGlyphOrder())

    move = {}                                 # name -> (left point?, right point?)
    for name in order:
        g = glyf[name]
        if g.numberOfContours == 0:           # empty (space, ...)
            continue
        adv, lsb = hmtx.metrics[name]
        xs = [x + lsb - g.xMin for x, _ in g.getCoordinates(glyf)[0]]   # as FreeType places them
        left, right = min(xs) > 0, max(xs) < adv
        if left or right:
            move[name] = (left, right)
    moved = set(move)

    new_order = order + [ORIGIN] + [n + ".base" for n in move]
    dot = Glyph()
    dot.numberOfContours = 1
    dot.coordinates = GlyphCoordinates([(0, 0)])
    dot.flags = bytearray([1])
    dot.endPtsOfContours = [0]
    dot.program = empty_program()
    dot.xMin = dot.xMax = dot.yMin = dot.yMax = 0
    glyf.glyphs[ORIGIN] = dot
    hmtx.metrics[ORIGIN] = (0, 0)
    for name, (left, right) in move.items():
        b = glyf.glyphs[name]
        adv, lsb = hmtx.metrics[name]
        glyf.glyphs[name + ".base"] = b
        hmtx.metrics[name + ".base"] = (adv, lsb)
        ymid = (b.yMin + b.yMax) // 2
        w = Glyph()
        w.numberOfContours = -1
        w.components = [component(name + ".base", 0, 0, USE_MY_METRICS)]
        if left:
            w.components.append(component(ORIGIN, 0, ymid, ROUND_XY_TO_GRID))
        if right:
            w.components.append(component(ORIGIN, adv, ymid, 0))
        w.xMin = 0 if left else lsb
        w.xMax = adv if right else b.xMax + lsb - b.xMin
        w.yMin, w.yMax = b.yMin, b.yMax
        glyf.glyphs[name] = w
        hmtx.metrics[name] = (adv, w.xMin)        # lsb = xMin, so pp1.x = 0
    # composites keep their original structure (and point numbers): use the unchanged originals
    for name in new_order:
        g = glyf.glyphs[name]
        if g.isComposite() and not (name in moved):
            for c in g.components:
                if c.glyphName in moved:
                    c.glyphName += ".base"
    glyf.glyphOrder = new_order
    f.setGlyphOrder(new_order)
    f["maxp"].recalc(f)                       # more glyphs, deeper composites (not done without recalcBBoxes)
    f["post"].formatType = 3.0                # no glyph names in the file: about 60 KB less, nothing uses them

    for rec in f["name"].names:
        s = rec.toUnicode()
        if rec.nameID in (1, 4, 16, 18):
            rec.string = FAMILY
        elif rec.nameID == 3:
            rec.string = FAMILY + " (DejaVu Sans Mono 2.37, glyph boxes = the cell)"
        elif rec.nameID == 6:
            rec.string = PS_NAME
        elif "DejaVu Sans Mono" in s:
            rec.string = s.replace("DejaVu Sans Mono", FAMILY)
    f.save(dst)
    print("%s: %d glyphs get a left edge point, %d a right edge point" % (
        dst, sum(1 for l, _ in move.values() if l), sum(1 for _, r in move.values() if r)))


if __name__ == "__main__":
    main()
