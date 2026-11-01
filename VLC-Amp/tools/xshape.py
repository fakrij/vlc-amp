"""Print the X11 shape (visible area) of a window.

usage: xshape.py <display> <window id> [bar_height] [--state]

The skin's window is invisible and click-through wherever nothing is drawn;
the shape's bounding box is the visible part. The last line applies the same
rule as VlcDock.ReadShape in taskbar/VlcDock.cs: the bar is at the bottom when
the box reaches the window's bottom edge, and the full player is showing when
a point one bar height from the bar's outer edge is inside the shape.
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


bar_at_bottom = y1 >= geo.height - 1
full = inside(0, geo.height - bar if bar_at_bottom else bar)
if state_only:
    print("bar_at_bottom=%d full=%d" % (bar_at_bottom, full))
    sys.exit(0)
print("window %dx%d" % (geo.width, geo.height))
print("box x=%d y=%d w=%d h=%d  (right=%d bottom=%d)" % (x0, y0, x1 - x0, y1 - y0, x1, y1))
print("rects %d, bar_at_bottom %s, full_player_visible %s" % (len(rects), bar_at_bottom, full))
