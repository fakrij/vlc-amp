"""Print the X11 shape (visible area) of a window.

usage: xshape.py <display> <window id> [bar_height] [--state]

The skin's window is invisible and click-through wherever nothing is drawn;
the shape's bounding box is the visible part. The last line applies the same
rule as DockShape.Classify in taskbar/VlcDock.cs: the bar is at the bottom when the box
reaches the window's bottom edge (and not its top), and the full player is showing when the visible
height is 232 / 396 / 512 / 676 logical px (full player + none / EQ / PL / both) rather than
bar / bar + 164 / bar + 280 / bar + 444.
bar_height is the bar's pixel height (24 at 100 %, 36 at 150 %; 36 at 100 % for
the taskbar build, vlc-test.sh passes the right one).
With --state it prints only "bar_at_bottom=0|1 full=0|1" (for shell scripts).
"""
import sys

from Xlib import display
from Xlib.ext import shape

args = [a for a in sys.argv[1:] if a != "--state"]
state_only = len(args) != len(sys.argv) - 1
disp = display.Display(args[0])
wid = int(args[1], 0)
bar = int(args[2]) if len(args) > 2 else 24

win = disp.create_resource_object("window", wid)
geo = win.get_geometry()
rects = win.shape_get_rectangles(shape.SK.Bounding).rectangles
if not rects:
    sys.exit("window has no shape rectangles")

x0 = min(r.x for r in rects)
y0 = min(r.y for r in rects)
x1 = max(r.x + r.width for r in rects)
y1 = max(r.y + r.height for r in rects)


def inside(x, y):
    return any(r.x <= x < r.x + r.width and r.y <= y < r.y + r.height for r in rects)


# The same rule as DockShape.Classify (taskbar/VlcDock.cs): the window is 676 logical px tall in every
# layout (full player 232 + EQ 164 + playlist 280); the visible HEIGHT tells strip from full player
# and which panels are open; the visible part touches the window's top ("dn") or bottom ("up").
# (The old rule, a pixel one bar height from the bar's edge, is only the fallback: the hi-fi
# panels' corners at the seam are not transparent any more.)
TOL = 2
sc = geo.height / 676.0
FULL_H, EQ_H, PL_H = [int(round(v * sc)) for v in (232, 164, 280)]
h = y1 - y0


def match(base):
    for add in (0, EQ_H, PL_H, EQ_H + PL_H):
        if abs(h - base - add) <= TOL:
            return True
    return False


def seam(y):    # the left edge is transparent in one of the rows y-2 .. y+1 (rounded corners meet)
    return any(not inside(0, i) for i in range(y - 2, y + 2))


at_top, at_end = y0 <= TOL - 1, y1 >= geo.height - TOL + 1
if at_top and not at_end:
    bar_at_bottom = False
elif at_end and not at_top:
    bar_at_bottom = True
else:           # the full player with both panels fills the window: the seam below / above it tells
    bar_at_bottom = seam(geo.height - FULL_H) and not seam(FULL_H)
as_full, as_strip = match(FULL_H), match(bar)
if as_full != as_strip:
    full = as_full
else:           # ambiguous or nothing fits: the old pixel test
    full = inside(0, geo.height - bar if bar_at_bottom else bar)
if state_only:
    print("bar_at_bottom=%d full=%d" % (bar_at_bottom, full))
    sys.exit(0)
print("window %dx%d" % (geo.width, geo.height))
print("box x=%d y=%d w=%d h=%d  (right=%d bottom=%d)" % (x0, y0, x1 - x0, y1 - y0, x1, y1))
print("rects %d, bar_at_bottom %s, full_player_visible %s" % (len(rects), bar_at_bottom, full))
