#!/usr/bin/env python3
"""Start VLC pinned "always on top" with the Titlebar skin, like the Windows helper.

VLC never saves "always on top", so every VLC start would begin unpinned. This
script waits for VLC's skin window, works out where the skin's own pin button is
and clicks it once, so VLC's state and the lit pin agree.

    titlebar-pin.py                       wait for VLC's window, pin it, exit
    titlebar-pin.py --watch               run in the background, pin every new VLC once
    titlebar-pin.py --install-autostart   start --watch at every login (XDG autostart)
    titlebar-pin.py --uninstall-autostart

Needs only Python 3 and libX11 / libXext (which VLC's skins2 on X11 needs too);
no xdotool, no python-xlib. Works on X11 and on Wayland through XWayland.

How the click works (checked against skins2 in VLC 3.0.x): skins2's X11 loop does
not look at XEvent.send_event, and it takes the position of a click from the
event itself, so a synthetic ButtonPress / ButtonRelease sent with XSendEvent
is a real click on the skin's checkbox, and the user's pointer never moves.
(A MotionNotify would not help: skins2 ignores its coordinates and asks the X
server where the real pointer is.) A synthetic LeaveNotify afterwards puts the
pin back from its hover look.

Exit status: 0 pinned (or already pinned), 1 no VLC window found, 2 the click
did not take effect, 3 cannot open the X display.
"""
import argparse
import ctypes
import ctypes.util
import fcntl
import hashlib
import os
import re
import sys
import time

# ---------------------------------------------------------------- layout (100 % values)
# Must follow source/build_skin.py (add_strip / add_full); every value is multiplied by
# the skin's scale. The window is 556 x 436 at 100 %.
BASE_H = 436            # window height at 100 %
BAR = 24                # strip height
FULL = 122              # full player height
STRIP_PIN = (34, 11, 12)    # distance of the pin's left edge from the window's right edge, x offset to its centre, y
FULL_PIN = (82, 9, 11)
SCALES = (100, 125, 150, 200)   # the shipped Titlebar-NNN.vlt files

POLL_VLC = 2.0          # --watch: seconds between looks at /proc
SETTLE = 1.0            # seconds the skin gets to finish drawing after its window shows
WINDOW_WAIT = 60.0      # --watch: how long to wait for a started VLC's window

VLC_NAMES = ("vlc", "cvlc", "qvlc", "svlc")   # /proc/<pid>/comm of VLC
VERBOSE = False


def log(*a):
    if VERBOSE:
        print("titlebar-pin:", *a, file=sys.stderr, flush=True)


def say(*a):
    print("titlebar-pin:", *a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- Xlib through ctypes
class XClassHint(ctypes.Structure):
    _fields_ = [("res_name", ctypes.c_void_p), ("res_class", ctypes.c_void_p)]


class XWindowAttributes(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int), ("width", ctypes.c_int), ("height", ctypes.c_int),
                ("border_width", ctypes.c_int), ("depth", ctypes.c_int), ("visual", ctypes.c_void_p),
                ("root", ctypes.c_ulong), ("class_", ctypes.c_int), ("bit_gravity", ctypes.c_int),
                ("win_gravity", ctypes.c_int), ("backing_store", ctypes.c_int),
                ("backing_planes", ctypes.c_ulong), ("backing_pixel", ctypes.c_ulong),
                ("save_under", ctypes.c_int), ("colormap", ctypes.c_ulong), ("map_installed", ctypes.c_int),
                ("map_state", ctypes.c_int), ("all_event_masks", ctypes.c_long),
                ("your_event_mask", ctypes.c_long), ("do_not_propagate_mask", ctypes.c_long),
                ("override_redirect", ctypes.c_int), ("screen", ctypes.c_void_p)]


class XButtonEvent(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                ("display", ctypes.c_void_p), ("window", ctypes.c_ulong), ("root", ctypes.c_ulong),
                ("subwindow", ctypes.c_ulong), ("time", ctypes.c_ulong), ("x", ctypes.c_int),
                ("y", ctypes.c_int), ("x_root", ctypes.c_int), ("y_root", ctypes.c_int),
                ("state", ctypes.c_uint), ("button", ctypes.c_uint), ("same_screen", ctypes.c_int)]


class XCrossingEvent(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                ("display", ctypes.c_void_p), ("window", ctypes.c_ulong), ("root", ctypes.c_ulong),
                ("subwindow", ctypes.c_ulong), ("time", ctypes.c_ulong), ("x", ctypes.c_int),
                ("y", ctypes.c_int), ("x_root", ctypes.c_int), ("y_root", ctypes.c_int),
                ("mode", ctypes.c_int), ("detail", ctypes.c_int), ("same_screen", ctypes.c_int),
                ("focus", ctypes.c_int), ("state", ctypes.c_uint)]


class XEvent(ctypes.Union):
    _fields_ = [("type", ctypes.c_int), ("xbutton", XButtonEvent), ("xcrossing", XCrossingEvent),
                ("pad", ctypes.c_long * 24)]


class XRectangle(ctypes.Structure):
    _fields_ = [("x", ctypes.c_short), ("y", ctypes.c_short), ("width", ctypes.c_ushort),
                ("height", ctypes.c_ushort)]


class XImage(ctypes.Structure):
    _fields_ = [("width", ctypes.c_int), ("height", ctypes.c_int), ("xoffset", ctypes.c_int),
                ("format", ctypes.c_int), ("data", ctypes.c_void_p), ("byte_order", ctypes.c_int),
                ("bitmap_unit", ctypes.c_int), ("bitmap_bit_order", ctypes.c_int),
                ("bitmap_pad", ctypes.c_int), ("depth", ctypes.c_int), ("bytes_per_line", ctypes.c_int),
                ("bits_per_pixel", ctypes.c_int)]


ButtonPress, ButtonRelease, LeaveNotify = 4, 5, 8
NotifyNormal, NotifyAncestor = 0, 0
Button1, Button1Mask = 1, 1 << 8
IsViewable = 2
XA_ATOM, XA_CARDINAL = 4, 6
ShapeBounding = 0
ZPixmap = 2

_keep = []   # error handler must stay referenced


class XError(Exception):
    pass


class X:
    """The few Xlib calls we need."""

    def __init__(self, name=None):
        lx = ctypes.util.find_library("X11") or "libX11.so.6"
        try:
            self.x = ctypes.CDLL(lx)
        except OSError:
            raise XError("libX11 not found")
        le = ctypes.util.find_library("Xext") or "libXext.so.6"
        try:
            self.ext = ctypes.CDLL(le)
        except OSError:
            self.ext = None
        x = self.x
        V, UL, I, UI, L = ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_uint, ctypes.c_long
        x.XOpenDisplay.restype = V
        x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x.XCloseDisplay.argtypes = [V]
        x.XDefaultRootWindow.restype = UL
        x.XDefaultRootWindow.argtypes = [V]
        x.XInternAtom.restype = UL
        x.XInternAtom.argtypes = [V, ctypes.c_char_p, I]
        x.XQueryTree.argtypes = [V, UL, ctypes.POINTER(UL), ctypes.POINTER(UL),
                                 ctypes.POINTER(ctypes.POINTER(UL)), ctypes.POINTER(UI)]
        x.XFree.argtypes = [V]
        x.XGetClassHint.argtypes = [V, UL, ctypes.POINTER(XClassHint)]
        x.XFetchName.argtypes = [V, UL, ctypes.POINTER(V)]
        x.XGetWindowAttributes.argtypes = [V, UL, ctypes.POINTER(XWindowAttributes)]
        x.XGetWindowProperty.argtypes = [V, UL, UL, L, L, I, UL, ctypes.POINTER(UL), ctypes.POINTER(I),
                                         ctypes.POINTER(UL), ctypes.POINTER(UL),
                                         ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
        x.XSendEvent.argtypes = [V, UL, I, L, ctypes.POINTER(XEvent)]
        x.XSync.argtypes = [V, I]
        x.XFlush.argtypes = [V]
        x.XTranslateCoordinates.argtypes = [V, UL, UL, I, I, ctypes.POINTER(I), ctypes.POINTER(I),
                                            ctypes.POINTER(UL)]
        x.XGetImage.restype = V
        x.XGetImage.argtypes = [V, UL, I, I, UI, UI, UL, I]
        x.XDestroyImage.argtypes = [V]
        if self.ext is not None:
            self.ext.XShapeGetRectangles.restype = ctypes.POINTER(XRectangle)
            self.ext.XShapeGetRectangles.argtypes = [V, UL, I, ctypes.POINTER(I), ctypes.POINTER(I)]
        # Errors (a window that vanished, BadMatch, ...) must not kill us: remember and go on.
        self.last_error = 0
        handler_t = ctypes.CFUNCTYPE(I, V, V)

        def on_error(dpy, ev):
            self.last_error = 1
            return 0
        self._handler = handler_t(on_error)
        _keep.append(self._handler)
        x.XSetErrorHandler.argtypes = [handler_t]
        x.XSetErrorHandler(self._handler)

        self.dpy = x.XOpenDisplay(name.encode() if name else None)
        if not self.dpy:
            raise XError("cannot open X display %r" % (name or os.environ.get("DISPLAY")))
        self.root = x.XDefaultRootWindow(self.dpy)
        self._atoms = {}

    def close(self):
        if self.dpy:
            self.x.XCloseDisplay(self.dpy)
            self.dpy = None

    def atom(self, name):
        if name not in self._atoms:
            self._atoms[name] = self.x.XInternAtom(self.dpy, name.encode(), 0)
        return self._atoms[name]

    def children(self, win):
        root, parent = ctypes.c_ulong(), ctypes.c_ulong()
        kids = ctypes.POINTER(ctypes.c_ulong)()
        n = ctypes.c_uint()
        if not self.x.XQueryTree(self.dpy, win, ctypes.byref(root), ctypes.byref(parent),
                                 ctypes.byref(kids), ctypes.byref(n)):
            return []
        out = [kids[i] for i in range(n.value)]
        if kids:
            self.x.XFree(ctypes.cast(kids, ctypes.c_void_p))
        return out

    def wm_class(self, win):
        h = XClassHint()
        if not self.x.XGetClassHint(self.dpy, win, ctypes.byref(h)):
            return None
        res = []
        for p in (h.res_name, h.res_class):
            res.append(ctypes.string_at(p).decode("latin-1") if p else "")
            if p:
                self.x.XFree(p)
        return tuple(res)

    def name(self, win):
        p = ctypes.c_void_p()
        if not self.x.XFetchName(self.dpy, win, ctypes.byref(p)) or not p.value:
            return ""
        s = ctypes.string_at(p.value).decode("latin-1")
        self.x.XFree(p)
        return s

    def attrs(self, win):
        a = XWindowAttributes()
        self.last_error = 0
        if not self.x.XGetWindowAttributes(self.dpy, win, ctypes.byref(a)) or self.last_error:
            return None
        return a

    def prop(self, win, name, typ):
        """A property of format 32 as a list of ints ([] when absent)."""
        at = ctypes.c_ulong()
        fmt = ctypes.c_int()
        n, left = ctypes.c_ulong(), ctypes.c_ulong()
        data = ctypes.POINTER(ctypes.c_ubyte)()
        self.last_error = 0
        r = self.x.XGetWindowProperty(self.dpy, win, self.atom(name), 0, 64, 0, typ, ctypes.byref(at),
                                      ctypes.byref(fmt), ctypes.byref(n), ctypes.byref(left),
                                      ctypes.byref(data))
        out = []
        if r == 0 and not self.last_error and data and fmt.value == 32:
            arr = ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))
            out = [arr[i] for i in range(n.value)]
        if data:
            self.x.XFree(ctypes.cast(data, ctypes.c_void_p))
        return out

    def shape_rects(self, win):
        """Bounding shape rectangles of the window as (x, y, w, h); [] if unshaped / unavailable."""
        if self.ext is None:
            return []
        n, order = ctypes.c_int(), ctypes.c_int()
        self.last_error = 0
        rp = self.ext.XShapeGetRectangles(self.dpy, win, ShapeBounding, ctypes.byref(n), ctypes.byref(order))
        out = []
        if rp and not self.last_error:
            out = [(rp[i].x, rp[i].y, rp[i].width, rp[i].height) for i in range(n.value)]
        if rp:
            self.x.XFree(ctypes.cast(rp, ctypes.c_void_p))
        return out

    def above(self, win):
        """Is _NET_WM_STATE_ABOVE / _STAYS_ON_TOP set on the window?"""
        st = self.prop(win, "_NET_WM_STATE", XA_ATOM)
        return bool({self.atom("_NET_WM_STATE_ABOVE"), self.atom("_NET_WM_STATE_STAYS_ON_TOP")} & set(st))

    def wm_supports_above(self):
        sup = self.prop(self.root, "_NET_SUPPORTED", XA_ATOM)
        return bool({self.atom("_NET_WM_STATE_ABOVE"), self.atom("_NET_WM_STATE_STAYS_ON_TOP")} & set(sup))

    def snapshot(self, win, x, y, w, h):
        """Hash of the window's pixels in a box (None when the server will not say)."""
        self.last_error = 0
        img = self.x.XGetImage(self.dpy, win, x, y, w, h, ctypes.c_ulong(~0 & 0xFFFFFFFFFFFFFFFF), ZPixmap)
        if not img or self.last_error:
            return None
        im = ctypes.cast(img, ctypes.POINTER(XImage)).contents
        raw = ctypes.string_at(im.data, im.bytes_per_line * im.height)
        self.x.XDestroyImage(img)
        return hashlib.md5(raw).hexdigest()

    def send(self, win, ev):
        self.x.XSendEvent(self.dpy, win, 0, 0, ctypes.byref(ev))  # mask 0: to the client that owns the window

    def root_xy(self, win, x, y):
        rx, ry, child = ctypes.c_int(), ctypes.c_int(), ctypes.c_ulong()
        self.x.XTranslateCoordinates(self.dpy, win, self.root, x, y, ctypes.byref(rx), ctypes.byref(ry),
                                     ctypes.byref(child))
        return rx.value, ry.value

    def sync(self):
        self.x.XSync(self.dpy, 0)


# ---------------------------------------------------------------- VLC's window
def walk(xd, win, depth):
    """Yield windows below win; a window manager puts clients into frames, so look a few levels down."""
    for c in xd.children(win):
        yield c
        if depth > 0:
            yield from walk(xd, c, depth - 1)


def find_main_windows(xd, pid=None):
    """VLC's main skin window(s): class vlc / Vlc, mapped, big (not the 1 x 1 flag windows or the
    10 x 10 parked ones), the largest first. With pid, only that process's (via _NET_WM_PID)."""
    found = []
    for w in walk(xd, xd.root, 3):
        cls = xd.wm_class(w)
        if not cls or cls[1] != "Vlc":
            continue
        a = xd.attrs(w)
        if a is None or a.map_state != IsViewable or a.width < 200 or a.height < 100:
            continue
        if not xd.name(w).startswith("VLC (TopWindow)"):
            continue    # skins2 names its windows so; this skips the video / fullscreen / Qt windows
        if pid is not None:
            pids = xd.prop(w, "_NET_WM_PID", XA_CARDINAL)
            if pids and pids[0] != pid and proc_comm(pids[0]) in VLC_NAMES:
                continue    # another VLC's window (a sandbox's own pid, as in Flatpak, is not in /proc: accept)
        found.append((a.width * a.height, w, a.width, a.height))
    found.sort(reverse=True)
    return [(w, ww, hh) for _, w, ww, hh in found]


def pid_scale(pid):
    """Skin scale in percent from the .vlt name on VLC's command line or in vlcrc (skins2-last)."""
    names = []
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            names += f.read().decode("utf-8", "replace").split("\0")
    except OSError:
        pass
    home = os.path.expanduser("~")
    cfg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    for rc in (os.path.join(cfg, "vlc", "vlcrc"), os.path.join(home, ".config/vlc/vlcrc"),
               os.path.join(home, ".var/app/org.videolan.VLC/config/vlc/vlcrc"),
               os.path.join(home, "snap/vlc/common/vlcrc"),
               os.path.join(home, "snap/vlc/common/.config/vlc/vlcrc")):
        try:
            with open(rc, errors="replace") as f:
                names += [l for l in f if l.startswith("skins2-last")]
        except OSError:
            pass
    for n in names:     # the command line wins over vlcrc (it is first in the list)
        m = re.search(r"Titlebar-(\d+)\.vlt", n)
        if m:
            return int(m.group(1))
    return None


def guess_scale(win_h, hint):
    """Scale in percent. The window height is 436 px at 100 %; trust that when it matches a shipped
    scale, else the name's scale, else the nearest shipped scale to the height."""
    for s in SCALES:
        if abs(win_h - BASE_H * s / 100.0) <= 1:
            return s
    if hint:
        return hint
    return min(SCALES, key=lambda s: abs(win_h - BASE_H * s / 100.0))


def pin_position(rects, win_w, win_h, scale):
    """(x, y, full, bar_at_bottom) of the pin: the rule of ReadShape in taskbar/VlcDock.cs."""
    def p(v):
        return int(round(v * scale / 100.0))

    def inside(px, py):
        return any(r[0] <= px < r[0] + r[2] and r[1] <= py < r[1] + r[3] for r in rects)
    if rects:
        bottom = max(r[1] + r[3] for r in rects)
        bar_at_bottom = bottom >= win_h - 1
        full = inside(0, win_h - p(BAR) if bar_at_bottom else p(BAR))
    else:       # no shape information: assume the default layout, the strip at the top
        bar_at_bottom, full = False, False
    if full:
        d, cx, cy = FULL_PIN
        top = win_h - p(FULL) if bar_at_bottom else 0
    else:
        d, cx, cy = STRIP_PIN
        top = win_h - p(BAR) if bar_at_bottom else 0
    return win_w - p(d) + p(cx), top + p(cy), full, bar_at_bottom


# ---------------------------------------------------------------- the click
def click(xd, win, x, y):
    """Synthetic left click at x, y of the window, then a leave event (hover look off)."""
    rx, ry = xd.root_xy(win, x, y)
    ev = XEvent()
    b = ev.xbutton
    b.type, b.send_event, b.display = ButtonPress, 1, xd.dpy
    b.window, b.root, b.subwindow, b.time = win, xd.root, 0, 0
    b.x, b.y, b.x_root, b.y_root = x, y, rx, ry
    b.state, b.button, b.same_screen = 0, Button1, 1
    xd.send(win, ev)
    xd.sync()
    time.sleep(0.08)
    b.type, b.state = ButtonRelease, Button1Mask
    xd.send(win, ev)
    xd.sync()
    time.sleep(0.15)
    ev = XEvent()
    c = ev.xcrossing
    c.type, c.send_event, c.display = LeaveNotify, 1, xd.dpy
    c.window, c.root, c.subwindow, c.time = win, xd.root, 0, 0
    c.x, c.y, c.x_root, c.y_root = x, y, rx, ry
    c.mode, c.detail, c.same_screen, c.focus, c.state = NotifyNormal, NotifyAncestor, 1, 0, 0
    xd.send(win, ev)
    xd.sync()


def wait_stable(xd, pid, deadline):
    """The main window, once its size and shape stay the same for SETTLE seconds. None on timeout."""
    last, since = None, 0.0
    while time.time() < deadline:
        if pid is not None and not os.path.isdir("/proc/%d" % pid):
            return None
        wins = find_main_windows(xd, pid)
        if wins:
            w, ww, hh = wins[0]
            rects = xd.shape_rects(w)
            key = (w, ww, hh, tuple(rects))
            if (rects or xd.ext is None) and key == last:
                if time.time() - since >= SETTLE:
                    return w, ww, hh, rects
            else:
                last, since = key, time.time()
        time.sleep(0.25)
    return None


def pin_window(xd, win, ww, wh, rects, hint_scale, dry=False):
    """Click the pin of the main window and check it. Returns 0 ok, 2 not verified."""
    scale = guess_scale(wh, hint_scale)
    x, y, full, bottom = pin_position(rects, ww, wh, scale)
    log("window 0x%x %dx%d scale %d%% %s player, bar at %s: pin at %d,%d" % (
        win, ww, wh, scale, "full" if full else "strip", "bottom" if bottom else "top", x, y))
    if xd.above(win):
        log("already on top (_NET_WM_STATE_ABOVE): nothing to do")
        return 0
    if dry:
        print("pin at %d,%d (window 0x%x, %d%%, %s, bar at %s)" % (
            x, y, win, scale, "full" if full else "strip", "bottom" if bottom else "top"))
        return 0
    box = (max(x - 8, 0), max(y - 6, 0), 16, 12)
    for attempt in (1, 2):
        before = xd.snapshot(win, *box)
        click(xd, win, x, y)
        # the window manager answers a moment later; give it up to 1.5 s before judging
        for _ in range(8):
            time.sleep(0.2)
            if xd.above(win):
                log("clicked (attempt %d): _NET_WM_STATE_ABOVE is set" % attempt)
                return 0
        after = xd.snapshot(win, *box)
        if before is not None and after is not None and before != after:
            # the pin is lit and VLC asked for "on top"; a window manager that is missing or
            # ignores it leaves _NET_WM_STATE alone. Do not click again: that would unpin.
            if xd.wm_supports_above():
                say("pin is lit, but the window manager did not set _NET_WM_STATE_ABOVE "
                    "(it may ignore the request for this window)")
            else:
                log("clicked (attempt %d): pin changed look; no window manager with _NET_WM_STATE_ABOVE" % attempt)
            return 0
        if before is None or after is None:
            log("cannot read the window's pixels; click not verifiable")
            return 0 if not xd.wm_supports_above() else 2
        log("attempt %d: nothing changed" % attempt)
    return 2


# ---------------------------------------------------------------- VLC processes
def proc_comm(pid):
    try:
        with open("/proc/%d/comm" % pid) as f:
            return f.read().strip()
    except OSError:
        return ""


def vlc_pids():
    """PIDs of VLC processes (of this user, as far as /proc shows them)."""
    out = []
    for d in os.listdir("/proc"):
        if d.isdigit() and proc_comm(int(d)) in VLC_NAMES:
            out.append(int(d))
    return out


def proc_env(pid, key):
    try:
        with open("/proc/%d/environ" % pid, "rb") as f:
            for e in f.read().split(b"\0"):
                if e.startswith(key.encode() + b"="):
                    return e.split(b"=", 1)[1].decode("utf-8", "replace")
    except OSError:
        pass
    return None


def connect(pid, display):
    """Open the X display. Order: --display; with a VLC pid (watch mode) that process's own DISPLAY, then
    ours; without one, ours, then any VLC's, then :0. XAUTHORITY is taken from the VLC process when
    we have none."""
    own = os.environ.get("DISPLAY")
    vlc = [pid] if pid else ([] if own else vlc_pids())
    theirs = []
    for p in vlc:
        d = proc_env(p, "DISPLAY")
        if d:
            theirs.append((d, p))
    names = [display] if display else []
    for n in ([d for d, _ in theirs] + [own]) if pid else ([own] + [d for d, _ in theirs]):
        if n and n not in names:
            names.append(n)
    if ":0" not in names:
        names.append(":0")
    if not os.environ.get("XAUTHORITY"):
        for _, p in theirs:
            xa = proc_env(p, "XAUTHORITY")
            if xa and os.path.exists(xa):
                os.environ["XAUTHORITY"] = xa
                break
    err = XError("no X display")
    for n in names:
        try:
            return X(n)
        except XError as e:
            err = e
    raise err


def pin_one(pid, args, timeout):
    """Wait for the main window of VLC (pid, or any VLC when None) and pin it. Returns an exit status."""
    deadline = time.time() + timeout
    xd = None
    while xd is None:
        try:
            xd = connect(pid, args.display)
        except XError as e:
            if time.time() >= deadline:
                say(e)
                return 3
            time.sleep(1.0)
    try:
        got = wait_stable(xd, pid, deadline)
        if not got:
            say("no VLC skin window found" + (" (pid %d)" % pid if pid else ""))
            return 1
        win, ww, wh, rects = got
        hint = args.scale
        if not hint:
            wp = xd.prop(win, "_NET_WM_PID", XA_CARDINAL)
            hint = pid_scale(pid or (wp[0] if wp else 0))
        return pin_window(xd, win, ww, wh, rects, hint, args.dry_run)
    finally:
        xd.close()


# ---------------------------------------------------------------- watch mode
def lock_single():
    """One watcher per user: an flock on a file in the runtime dir."""
    d = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    path = os.path.join(d, "titlebar-pin-%d.lock" % os.getuid())
    f = open(path, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    return f


def pin_in_child(pid, args, timeout):
    """Pin in a forked child (an X connection that breaks exits only the child; several VLCs do not
    wait for each other). Returns the child's pid."""
    c = os.fork()
    if c == 0:
        try:
            code = pin_one(pid, args, timeout)
        except BaseException as e:     # noqa
            say("error:", e)
            code = 4
        os._exit(code)
    return c


def reap(children):
    """Collect finished children; {child pid: VLC pid}."""
    for c in list(children):
        try:
            done, status = os.waitpid(c, os.WNOHANG)
        except ChildProcessError:
            del children[c]
            continue
        if done:
            log("VLC pid %d: exit status %d" % (children.pop(c), os.waitstatus_to_exitcode(status)
                if hasattr(os, "waitstatus_to_exitcode") else status >> 8))


def watch(args):
    lock = lock_single()
    if lock is None:
        say("another --watch is already running")
        return 0
    log("watching for VLC (every %.0f s)" % POLL_VLC)
    seen = {}       # pid -> start time (from /proc/<pid>/stat) of the VLCs we have handled once
    children = {}
    while True:
        for pid in vlc_pids():
            try:
                with open("/proc/%d/stat" % pid) as f:
                    start = f.read().rsplit(")", 1)[1].split()[19]
            except (OSError, IndexError):
                continue
            if seen.get(pid) != start:
                seen[pid] = start
                theirs = proc_env(pid, "DISPLAY")
                if args.display and theirs and theirs != args.display:
                    continue    # --display limits the watcher to the VLCs on that display
                log("new VLC, pid %d" % pid)
                children[pin_in_child(pid, args, WINDOW_WAIT)] = pid
        for pid in list(seen):
            if not os.path.isdir("/proc/%d" % pid):
                del seen[pid]
        reap(children)
        time.sleep(POLL_VLC)


# ---------------------------------------------------------------- autostart
def autostart_path():
    cfg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(cfg, "autostart", "titlebar-pin.desktop")


def exec_quote(s):
    """One argument of an Exec line (Desktop Entry spec: quote, escape " ` $ \\ and double the backslash)."""
    if re.fullmatch(r"[A-Za-z0-9_./+:@%-]+", s):
        return s
    s = s.replace("\\", "\\\\")
    for ch in '"`$':
        s = s.replace(ch, "\\" + ch)
    return '"' + s + '"'


def install_autostart():
    script = os.path.realpath(__file__)
    exec_line = "python3 %s --watch" % exec_quote(script)
    # Desktop Entry values escape a backslash once more
    exec_line = exec_line.replace("\\", "\\\\")
    path = autostart_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Titlebar skin: pin VLC on top\n"
                "Comment=Pins every new VLC window on top when it starts (Titlebar VLC skin)\n"
                "Exec=%s\n"
                "Terminal=false\n"
                "NoDisplay=true\n"
                "X-GNOME-Autostart-enabled=true\n" % exec_line)
    print("wrote %s" % path)
    print("it starts at your next login; to start it now run:  %s --watch &" % script)
    return 0


def uninstall_autostart():
    path = autostart_path()
    try:
        os.remove(path)
        print("removed %s" % path)
    except FileNotFoundError:
        print("nothing to remove (%s does not exist)" % path)
    print("a watcher that is already running keeps running until you log out")
    return 0


def main():
    global VERBOSE
    ap = argparse.ArgumentParser(description="Pin VLC (Titlebar skin) on top once its window appears.")
    ap.add_argument("--watch", action="store_true", help="stay in the background, pin every new VLC once")
    ap.add_argument("--install-autostart", action="store_true", help="start --watch at login (XDG autostart)")
    ap.add_argument("--uninstall-autostart", action="store_true", help="remove that autostart entry")
    ap.add_argument("--timeout", type=float, default=30.0, help="seconds to wait for VLC's window (default 30)")
    ap.add_argument("--scale", type=int, help="skin scale in percent (default: from the window size / .vlt name)")
    ap.add_argument("--display", help="X display (default: $DISPLAY, then VLC's own, then :0); with --watch, only VLCs on this display")
    ap.add_argument("--dry-run", action="store_true", help="only print where the pin is, do not click")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    VERBOSE = args.verbose
    if args.install_autostart:
        return install_autostart()
    if args.uninstall_autostart:
        return uninstall_autostart()
    if args.watch:
        try:
            return watch(args)
        except KeyboardInterrupt:
            return 0
    return pin_one(None, args, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
