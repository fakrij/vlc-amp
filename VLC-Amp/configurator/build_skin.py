#!/usr/bin/env python3
"""
VLC Amp - a VLC skin (skins2 format) whose main window collapses into a
24 px strip that fits into a Windows title bar or the taskbar.

Build:
    python3 build_skin.py                       # 100 %, strip 556 px wide
    python3 build_skin.py --scale 1.5           # for 150 % Windows display scaling
    python3 build_skin.py --width 480 --preview

Options
    --scale        1.0 / 1.25 / 1.5 / 2.0 ... multiplies every pixel size
    --width        default width (logical px, before scaling) of the strip, the
                   full player and the panels (all share one width). Can also be
                   resized in VLC by dragging the right edge.
    --bar-height   height of the strip in logical px (default 24; 32-40 for the Windows 11
                   taskbar, which is 48 px tall). Buttons, LCDs, strip fonts, the volume slider
                   and the grips grow with it; widths and right-edge offsets do not. The full
                   player, EQ and playlist stay as they are. A taller build is named
                   VLC-Amp-taskbar-NNN.vlt (36 px) or VLC-Amp-bar<N>-NNN.vlt, which the
                   Windows helper reads the bar height from.
    --out          output folder (default: dist)
    --preview      also write a PNG preview of all windows

Needs: Python 3.8+, Pillow. Fonts are read from ./fonts next to this script.
"""
import argparse
import math
from collections import Counter
import re
import os
import shutil
import gzip
import tarfile
from xml.sax.saxutils import quoteattr

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_MONO = os.path.join(HERE, "fonts", "DejaVuSansMono.ttf")


def _truetype(path, size):
    """BASIC layout on every platform: native Pillow wheels ship libraqm, Pyodide's does not, and
    the two lay glyphs out differently; BASIC makes all environments render identically."""
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.BASIC)


FONT_FILE = ["fonts/DejaVuSansMono.ttf"]   # path of the LCD font inside the .vlt (--font changes it)
FONT_BOLD = os.path.join(HERE, "fonts", "DejaVuSans-Bold.ttf")
SS = 4          # supersampling factor for shapes
S = 1.0         # global scale, set in main()


def P(v):
    return int(round(v * S))


def H(c, a=255):
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), a)


# ---------------------------------------------------------------- palettes
# The skin is rendered once per theme. apply_theme() sets the module-level colour names
# below; CYAN* are the accent colours (cyan in the default theme), AMBER the LED colour.
# A theme is a few seed colours: base (dark / light template, tinted with a hue), accent
# and LED. Everything else is derived from them by mixing with grey, black or white.
DARK = dict(
    BG_TOP="#292f3a", BG_BOT="#1e232d", PL_FLAT="#232831",
    BTN={"up": ("#3b4353", "#252b37"), "over": ("#465064", "#2e3544"), "down": ("#191d26", "#282e3a")},
    ICON_UP="#c8cbcf", ICON_OVER="#ffffff",
    LCD_EDGE="#333b49", GRIP="#6c7075", LABEL="#9fa3a8",
    THUMB_UP=("#e2e6ec", "#59606b"), THUMB_OVER=("#ffffff", "#7a828e"), TRACK="#080a0e",
    PT_PLAY="#ffffff", SHADOW=200, SHADOW2=120)
LIGHT = dict(
    BG_TOP="#f0f1f2", BG_BOT="#d6d9dc", PL_FLAT="#e5e7e9",
    BTN={"up": ("#fbfcfc", "#e0e2e5"), "over": ("#ffffff", "#ebedee"), "down": ("#cdd0d3", "#dcdfe1")},
    ICON_UP="#3d4043", ICON_OVER="#000000",
    LCD_EDGE="#ffffff", GRIP="#8f9397", LABEL="#50545a",
    THUMB_UP=("#ffffff", "#bdc1c5"), THUMB_OVER=("#ffffff", "#d8dbde"), TRACK="#bec2c6",
    PT_PLAY="#000000", SHADOW=60, SHADOW2=30)


def _rgb(c):
    return tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    """Colour a mixed with colour b; t = share of b."""
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(_rgb(a), _rgb(b)))


def tint(c, hue, sat):
    """Same lightness as c, with the given hue (degrees) and HLS saturation."""
    import colorsys
    _, l, _ = colorsys.rgb_to_hls(*(v / 255 for v in _rgb(c)))
    return "#%02x%02x%02x" % tuple(round(v * 255) for v in colorsys.hls_to_rgb(hue / 360, l, sat))


def base_palette(mode, hue, sat):
    """The dark or light template, every colour tinted with hue / sat."""
    def t(v):
        if isinstance(v, str):
            return tint(v, hue, sat)
        if isinstance(v, tuple):
            return tuple(t(x) for x in v)
        if isinstance(v, dict):
            return {k: t(x) for k, x in v.items()}
        return v
    return t(DARK if mode == "dark" else LIGHT)


def accent_palette(mode, A, led):
    """Accent colours from one colour A: CYAN (fills, active icons), CYAN_TXT / CYAN2 /
    CYAN_DIM (LCD text: main / secondary / off), LCD_BG, TITLE_FILL (played part of the strip
    title), LCD_HI (LCD toggle hover), DIVIDER, EQ_TRACK, SCROLL_TRACK, PT_SEL / PT_BG2
    (playlist selection / odd rows); AMBER from the LED colour.
    Only mixes with neutral colours: the custom theme's recolouring relies on it."""
    k, w, g = "#000000", "#ffffff", "#808080"
    if mode == "dark":
        return dict(CYAN=A, CYAN_TXT=mix(A, w, 0.05), CYAN2=mix(A, k, 0.18), CYAN_DIM=mix(A, k, 0.40),
                    LCD_BG=mix(A, k, 0.93), TITLE_FILL=mix(A, k, 0.68), LCD_HI=mix(A, w, 0.85),
                    DIVIDER=mix(A, k, 0.78), EQ_TRACK=mix(A, "#141414", 0.88), SCROLL_TRACK=mix(A, k, 0.89),
                    PT_SEL=mix(A, k, 0.78), PT_BG2=mix(A, k, 0.85), AMBER=led)
    return dict(CYAN=A, CYAN_TXT=mix(A, k, 0.25), CYAN2=mix(A, k, 0.12), CYAN_DIM=mix(A, w, 0.08),
                LCD_BG=mix(A, w, 0.9), TITLE_FILL=mix(A, w, 0.74), LCD_HI=mix(A, k, 0.6),
                DIVIDER=mix(A, w, 0.72), EQ_TRACK=mix(A, w, 0.78), SCROLL_TRACK=mix(A, w, 0.82),
                PT_SEL=mix(A, w, 0.74), PT_BG2=mix(A, w, 0.80), AMBER=led)


# The custom theme is rendered with a pure red accent and a neutral grey base, so every
# pixel is grey + t * red; recolour() turns it into grey + t * any colour (exact, since the
# palette only mixes the accent with neutral colours). The .vlt keeps the red originals in
# custom-ref/ for the colour picker tools.
CUSTOM_REF = "#ff0000"
CUSTOM_DEFAULT = "#b48cff"

# (mode, name, base hue, base saturation, accent, LED); the button in the full player's
# title bar steps through them in this order. Index 0 = default.
THEME_SEEDS = [
    ("dark",  "Midnight", 214, 0.20, "#5fd3e8", "#f2a93b"),
    ("dark",  "Ember",     28, 0.12, "#ffb547", "#ff7b4a"),
    ("dark",  "Forest",   150, 0.09, "#78e0a0", "#e8d36a"),
    ("dark",  "Nord",     220, 0.17, "#88c0d0", "#ebcb8b"),
    ("dark",  "Dusk",     268, 0.15, "#ff79c6", "#f1fa8c"),
    ("dark",  "Carbon",     0, 0.00, "#ff7064", "#ffd166"),
    ("light", "Paper",    210, 0.12, "#1f7fc4", "#e8901a"),
    ("light", "Sand",      44, 0.45, "#12726a", "#d0561c"),
    ("light", "Sage",     120, 0.10, "#217239", "#d08a1a"),
    ("light", "Rose",     345, 0.22, "#c2185b", "#e8901a"),
    ("dark",  "Custom",     0, 0.00, CUSTOM_REF, None),
]


def _theme(mode, hue, sat, accent, led):
    if led is None:     # custom: LED from the accent, so it follows the chosen colour
        led = mix(accent, "#ffffff", 0.25)
    return dict(base_palette(mode, hue, sat), **accent_palette(mode, accent, led))


THEMES, CUSTOM = [], None      # CUSTOM = index of the Custom theme, None when it is not built
# The release skins carry only these: every theme costs ~10 MB of VLC memory at 100 % scaling
# (~20 MB at 150 %) and start-up time. --themes all builds every theme.
DEFAULT_THEMES = ["midnight"]


def set_themes(names=None):
    """Build all themes (names=None), or only the named ones, in THEME_SEEDS order."""
    global CUSTOM
    seeds = [t for t in THEME_SEEDS if names is None or t[1].lower() in names]
    THEMES[:] = [(mode, name, _theme(mode, hue, sat, acc, led)) for mode, name, hue, sat, acc, led in seeds]
    CUSTOM = next((i for i, t in enumerate(THEMES) if t[1] == "Custom"), None)


def _seed_hue_sat(accent):
    """Base tint of a single / pair theme: the accent's hue at Midnight's saturation (none for a grey accent)."""
    import colorsys
    r, g, b = (v / 255 for v in _rgb(accent))
    h, _, sat = colorsys.rgb_to_hls(r, g, b)
    return round(h * 360), (0.12 if sat > 0.05 else 0.0)


def set_single_theme(mode, accent, led=None):
    """One theme from seeds. The base tint takes the accent's hue (Midnight's saturation, none for
    a grey accent); the LED defaults to a lightened accent, like the Custom theme."""
    global CUSTOM
    hue, sat = _seed_hue_sat(accent)
    THEMES[:] = [(mode, "Theme", _theme(mode, hue, sat, accent.lower(), led.lower() if led else None))]
    CUSTOM = None


def _luminance(c):
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in _rgb(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """WCAG contrast ratio of two colours (1 .. 21)."""
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _fit_colour(c, towards, ok):
    """c, mixed step by step with `towards` (black or white) until ok(colour) holds."""
    for i in range(34):
        m = mix(c, towards, i * 0.03)
        if ok(m):
            return m
    return mix(c, towards, 1.0)


def fit_for_mode(mode, accent, led, hue, sat):
    """The same accent / LED seeds, moved in lightness (hue kept) until they read on this mode's
    surfaces: LCD text 4.5:1 on the LCD, accent and LED 3:1 on the button face. A seed that already
    reads is unchanged, so a dark pair half equals the single dark theme."""
    base = base_palette(mode, hue, sat)
    face = base["BTN"]["up"][0]
    towards = "#ffffff" if mode == "dark" else "#000000"
    if led is None:
        led = mix(accent, "#ffffff", 0.25)
    accent = _fit_colour(accent, towards, lambda c: contrast(c, face) >= 3 and contrast(
        accent_palette(mode, c, led)["CYAN_TXT"], accent_palette(mode, c, led)["LCD_BG"]) >= 4.5)
    led = _fit_colour(led, towards, lambda c: contrast(c, face) >= 3)
    return accent, led


def set_pair(first_mode, accent, led=None):
    """The same design twice: first_mode (shown at start) and the other base, same hue, accent and LED
    seeds fitted for contrast on each base; the theme button toggles them."""
    global CUSTOM
    hue, sat = _seed_hue_sat(accent)
    modes = [first_mode, "light" if first_mode == "dark" else "dark"]
    THEMES[:] = []
    for mode in modes:
        acc, lc = fit_for_mode(mode, accent.lower(), led.lower() if led else None, hue, sat)
        THEMES.append((mode, mode.capitalize(), _theme(mode, hue, sat, acc, lc)))
    CUSTOM = None


set_themes(DEFAULT_THEMES)


def apply_theme(i):
    pal = dict(THEMES[i][2])
    dark = _luminance(pal["BG_TOP"]) < 0.5
    pal["EDGE"] = mix(pal["BG_BOT"], "#ffffff" if dark else "#000000", 0.14 if dark else 0.17)
    pal["LED_OFF"] = mix(pal["BTN"]["up"][1], "#ffffff" if dark else "#000000", 0.42)   # light 1 px outline of buttons, displays, panels (hi-fi)
    pal["ICON"] = {"up": pal.pop("ICON_UP"), "over": pal.pop("ICON_OVER"), "down": pal["CYAN"]}
    globals().update(pal)


def recolour(im, accent):
    """Custom theme: a pixel grey n + t * red becomes n + t * accent (alpha unchanged)."""
    from PIL import ImageChops
    r, g, _, a = im.split()
    t = ImageChops.subtract(r, g)                     # t * 255; g is the grey part n
    return Image.merge("RGBA", [ImageChops.add(g, t.point(lambda v, c=c: round(v * c / 255)))
                                for c in _rgb(accent)] + [a])


def recolour_hex(c, accent):
    r, g, _ = _rgb(c)
    return "#%02X%02X%02X" % tuple(min(255, g + round((r - g) * x / 255)) for x in _rgb(accent))


def recolour_xml(xml, accent, slot=None):
    """Recolour the colours of the custom theme's controls (visible="th<slot>.isVisible ...")."""
    mark = 'visible="th%d.isVisible' % (CUSTOM if slot is None else slot)
    return "\n".join(re.sub(r"#[0-9A-Fa-f]{6}", lambda m: recolour_hex(m.group(0), accent), l) if mark in l else l
                     for l in xml.split("\n"))


apply_theme(0)


# ---------------------------------------------------------------- canvas
class Canvas:
    """Draw in logical units, rendered supersampled, then downsampled."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.pw, self.ph = P(w), P(h)
        self.kx = self.pw * SS / w
        self.ky = self.ph * SS / h
        self.im = Image.new("RGBA", (self.pw * SS, self.ph * SS), (0, 0, 0, 0))
        self.texts = []
        self.ox = self.oy = 0       # drawing offset (logical px): lets a face be drawn inset in a well
        self.crisp = False          # icon mode: shapes sampled at pixel centres (see _ss), set by icon()

    def X(self, v):
        return (v + self.ox) * self.kx

    def Y(self, v):
        return (v + self.oy) * self.ky

    def _layer(self):
        layer = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        return layer, ImageDraw.Draw(layer)

    def _box(self, x, y, w, h):
        return [round(self.X(x)), round(self.Y(y)),
                round(self.X(x + w)) - 1, round(self.Y(y + h)) - 1]

    def rrect(self, x, y, w, h, r, color, corners=None):
        """corners = (top left, top right, bottom right, bottom left) rounded?; default all."""
        layer, d = self._layer()
        b = self._box(x, y, w, h)
        if b[2] < b[0] or b[3] < b[1]:
            return
        if r > 0:
            d.rounded_rectangle(b, radius=r * self.kx, fill=H(color) if isinstance(color, str) else color,
                                corners=corners)
        else:
            d.rectangle(b, fill=H(color) if isinstance(color, str) else color)
        self.im.alpha_composite(layer)

    def grad(self, x, y, w, h, r, top, bot, corners=None):
        b = self._box(x, y, w, h)
        gw, gh = b[2] - b[0] + 1, b[3] - b[1] + 1
        if gw <= 0 or gh <= 0:
            return
        col = Image.new("RGBA", (1, gh))
        t0, t1 = H(top), H(bot)
        for yy in range(gh):
            t = yy / max(1, gh - 1)
            col.putpixel((0, yy), tuple(int(t0[i] + (t1[i] - t0[i]) * t) for i in range(3)) + (255,))
        g = col.resize((gw, gh))
        mask = Image.new("L", (gw, gh), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, gw - 1, gh - 1], radius=max(0, r * self.kx), fill=255,
                                               corners=corners)
        layer = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        layer.paste(g, (b[0], b[1]), mask)
        self.im.alpha_composite(layer)

    def _ss(self, x, y):
        """Logical -> supersampled pixel position (crisp / icon shapes, see _fill)."""
        return (self.X(x), self.Y(y))

    # Pillow's polygon / ellipse / wide-line fill is not centred: it covers every pixel the shape touches
    # (plus the end pixel), sampled at the top of each scanline, so shapes grow by up to one supersampled
    # pixel (1/4 device pixel at SS = 4), unequally on the left / right and top / bottom. That is the
    # asymmetric halo of H22. Crisp shapes are filled here instead: a pixel is set exactly when its centre
    # is inside the polygon (even-odd rule), so a mirror-symmetric shape on a symmetric lattice stays symmetric.
    @staticmethod
    def _fill(d, pts, fill):
        # an edge exactly through a pixel centre counts as inside on every side (two scanlines per row,
        # both ends inclusive), so a tie cannot favour left / top over right / bottom
        n = len(pts)
        ys = [p[1] for p in pts]
        eps = 1e-6
        for j in range(max(0, int(math.floor(min(ys)))), int(math.ceil(max(ys))) + 1):
            spans = []
            for yc in (j + 0.5 - eps, j + 0.5 + eps):
                xs = []
                for i in range(n):
                    (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
                    if (y0 <= yc < y1) or (y1 <= yc < y0):
                        xs.append(x0 + (yc - y0) / (y1 - y0) * (x1 - x0))
                xs.sort()
                spans += [(xs[k], xs[k + 1]) for k in range(0, len(xs) - 1, 2)]
            for xl, xr in spans:
                xa, xb = int(math.ceil(xl - 0.5 - eps)), int(math.floor(xr - 0.5 + eps))
                if xb >= xa:
                    d.line([(xa, j), (xb, j)], fill=fill)

    @staticmethod
    def _ellipse_pts(cx, cy, rx, ry, a0=0, a1=360, n=None):
        n = n or max(48, int(max(rx, ry) * 4))
        return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                 cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]

    def _lines_crisp(self, pts, color, width):
        layer, d = self._layer()
        pp = [self._ss(x, y) for x, y in pts]
        hx, hy = width * self.kx / 2, width * self.ky / 2
        fill = H(color)
        for (x0, y0), (x1, y1) in zip(pp, pp[1:]):
            dx, dy = x1 - x0, y1 - y0
            n = math.hypot(dx, dy)
            if n == 0:
                continue
            nx, ny = -dy / n * hx, dx / n * hy
            self._fill(d, [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], fill)
        for x, y in pp:  # round caps and joins
            self._fill(d, self._ellipse_pts(x, y, hx, hy), fill)
        self.im.alpha_composite(layer)

    def poly(self, pts, color):
        layer, d = self._layer()
        if self.crisp:
            self._fill(d, [self._ss(x, y) for x, y in pts], H(color))
        else:
            d.polygon([(self.X(x), self.Y(y)) for x, y in pts], fill=H(color))
        self.im.alpha_composite(layer)

    def lines(self, pts, color, width):
        if self.crisp:
            return self._lines_crisp(pts, color, width)
        layer, d = self._layer()
        pp = [(self.X(x), self.Y(y)) for x, y in pts]
        wpx = width * self.kx
        d.line(pp, fill=H(color), width=max(1, round(wpx)), joint="curve")
        r = wpx / 2
        for x, y in pp:  # round caps
            d.ellipse([x - r, y - r, x + r, y + r], fill=H(color))
        self.im.alpha_composite(layer)

    def arc(self, cx, cy, r, start, end, color, width):
        layer, d = self._layer()
        if self.crisp:  # ring between r - width (inside) and r, like Pillow's arc, as a polygon
            x, y = self._ss(cx, cy)
            n = max(24, int(r * self.kx))
            outer = self._ellipse_pts(x, y, r * self.kx, r * self.ky, start, end, n)
            inner = self._ellipse_pts(x, y, r * self.kx - width * self.kx, r * self.ky - width * self.ky, start, end, n)
            self._fill(d, outer + inner[::-1], H(color))
            self.im.alpha_composite(layer)
            return
        d.arc([self.X(cx - r), self.Y(cy - r), self.X(cx + r), self.Y(cy + r)],
              start, end, fill=H(color), width=max(1, round(width * self.kx)))
        self.im.alpha_composite(layer)

    def circle(self, cx, cy, r, color):
        layer, d = self._layer()
        if self.crisp:
            x, y = self._ss(cx, cy)
            self._fill(d, self._ellipse_pts(x, y, r * self.kx, r * self.ky),
                       H(color) if isinstance(color, str) else color)
            self.im.alpha_composite(layer)
            return
        d.ellipse([self.X(cx - r), self.Y(cy - r), self.X(cx + r), self.Y(cy + r)],
                  fill=H(color) if isinstance(color, str) else color)
        self.im.alpha_composite(layer)

    def text(self, x, y, s, size, color, font="bold", anchor="la"):
        self.texts.append((x + self.ox, y + self.oy, s, size, color, font, anchor))

    def done(self, hard_edges=False):
        out = self.im.resize((self.pw, self.ph), Image.BOX)
        if hard_edges:  # window silhouette: VLC cuts windows on alpha, keep it binary
            a = out.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
            out.putalpha(a)
        d = ImageDraw.Draw(out)
        for x, y, s, size, color, font, anchor in self.texts:
            f = _truetype(FONT_MONO if font == "mono" else FONT_BOLD, max(6, P(size)))
            d.text((x * self.pw / self.w, y * self.ph / self.h), s, font=f, fill=H(color), anchor=anchor)
        return out


def solid(im, bg=None):
    """Give a bitmap that sits on a plain panel colour no partly transparent pixels.
    skins2 premultiplies every bitmap when it loads it, draws buttons, thumbs and similar into
    a blank graphic without blending (the corner pixels come out darker than the panel) and
    copies that over the window. Windows (Win32Graphics::drawBitmap) alpha-blends it onto a
    blank bitmap whose start content nobody guarantees. Compositing the bitmap over the colour
    it will sit on (the panel fill) gives the same pixels everywhere and keeps the smooth corners."""
    return Image.alpha_composite(Image.new("RGBA", im.size, H(bg or mix(BG_TOP, BG_BOT, 0.5))),
                                 im.convert("RGBA"))


PL_GUTTER = 6                       # playlist list box: row stripes (left) and scroll track (right) sit 6 px from the box edge
GRIP_W = 9                          # resize tab width
GRIP_H = 70                         # tab height in the EQ, playlist and full player (the strip: bar height - 6)


def grip_x(w):
    """Left edge of the resize tab: 9 px centred in the 12 px right margin (W - 12 .. W - 1)."""
    return w - 12 + (12 - GRIP_W) // 2


def grip_y(box_y, box_h, h=GRIP_H):
    """Top edge of a tab of height h centred on a section's main box (display card, EQ / list box)."""
    return box_y + (box_h - h) // 2


def grip_tab(skin, lay, bg, x, y, h):
    """The resize zone: the drawn tab as its own control (resizeE), so the hit area is exactly the tab.
    The section backgrounds only move the window. bg = a section bitmap (opaque at the tab), x / y / h logical px."""
    x0, x1 = int(math.floor(x * S)), int(math.ceil((x + GRIP_W) * S))
    y0, y1 = int(math.floor(y * S)), int(math.ceil((y + h) * S))
    im = bg.crop((x0, y0, x1, y1))
    if im.getchannel("A").getextrema()[0] != 255:
        raise SystemExit("error: resize tab must be opaque")
    lay.image(add_shared(skin, "grip_%d_%d" % (x1 - x0, y1 - y0), im), x0, y0, lt="righttop", rb="righttop",
              action="resizeE")


def resize_handle(c, x, y, h):
    """Grip for the right edge: a 9 px wide tab in the button colour with three light ribs, so it reads
    as something to grab. x = its left edge in logical px (grip_x(W)). The hit zone is made by grip_tab."""
    pad = BTN["up"][0]
    c.rrect(x, y, 9, h, 2, pad)
    for rx in (x + 2, x + 4, x + 6):
        c.rrect(rx, y + 3, 1, h - 6, 0, mix(pad, ICON["up"], 0.6))


# ---------------------------------------------------------------- primitives
def panel_bg(c, x, y, w, h, r, flat=False, rt=True, rb=True):
    """Window section background. rt / rb: round the top / bottom corners (a corner that touches
    another section is square, so stacked sections form one rounded block)."""
    cn = (rt, rt, rb, rb)
    c.rrect(x, y, w, h, r, EDGE, corners=cn)
    fh = h - 2 + (0 if rb else 1)    # a square bottom touches the next section: its top outline is the only line there
    # the fill covers the side outline (top / bottom lines stay)
    c.rrect(x, y + 1, w, fh, max(0, r - 1), PL_FLAT if flat else mix(BG_TOP, BG_BOT, 0.5), corners=cn)


def box_edge(a):
    """Outline colour of a display box: a light line on dark themes, a dark line on light ones."""
    if _luminance(LCD_BG) < 0.5:
        return mix(LCD_BG, "#ffffff", a)
    return mix(LCD_BG, "#000000", 2 * a)      # light themes: twice as strong, the dark line on a light box is faint


def lcd(c, x, y, w, h, r=2, outline=True):
    if not outline:    # a plain dark box, no light outline
        c.rrect(x, y, w, h, r, LCD_BG)
        return
    c.rrect(x, y, w, h, r, box_edge(0.13))     # outline all round; no inner shadow (it left a dark sliver beside the fill at fractional scales)
    c.rrect(x + 1, y + 1, w - 2, h - 2, max(0, r - 1), LCD_BG)


def grip_dots(c, x, y, rows=3):
    for cx in (x + 2, x + 6):
        for i in range(rows):
            c.circle(cx, y + 3 + 4 * i, 1, GRIP)


def button_face(c, w, h, state, ring=None):
    """Hairline outline, nearly flat gradient face; ring = accent outline (lit toggles)."""
    top, bot = BTN[state]
    r = 4 if h >= 18 else 3
    c.rrect(0, 0, w, h, r, ring or EDGE)
    top, bot = mix(top, bot, 0.3), mix(top, bot, 0.8)
    c.grad(1, 1, w - 2, h - 2, r - 1, top, bot)


def ring_colour(col):
    return mix(col, BG_BOT, 0.45)


def led(c, cx, cy, on):
    if on:
        c.circle(cx, cy, 3.2, H(AMBER, 70))
        c.circle(cx, cy, 2, AMBER)
    else:
        c.circle(cx, cy, 2, LED_OFF)


def icon(c, name, ox, oy, size, color):
    """Draw a glyph in crisp mode with its centre snapped to the device pixel grid (H22): the centre
    (ox + size / 2, oy + size / 2) moves to the nearest half device pixel (at most 1/4 px), so the
    4x supersampled box filter sees a mirror-symmetric lattice and symmetric glyphs stay symmetric."""
    cx = c.X(ox + size / 2)
    cy = c.Y(oy + size / 2)
    unit = SS / 2.0                                              # half a device pixel in supersampled px
    ox += (round(cx / unit) * unit - cx) / c.kx
    oy += (round(cy / unit) * unit - cy) / c.ky
    c.crisp = True
    try:
        _icon(c, name, ox, oy, size, color)
    finally:
        c.crisp = False


def _icon(c, name, ox, oy, size, color):
    f = size / 12.0

    def T(pts):
        return [(ox + x * f, oy + y * f) for x, y in pts]

    lw = 1.5 * f
    if name == "expand":
        for seg in ([(1.5, 4.5), (1.5, 1.5), (4.5, 1.5)], [(7.5, 1.5), (10.5, 1.5), (10.5, 4.5)],
                    [(10.5, 7.5), (10.5, 10.5), (7.5, 10.5)], [(4.5, 10.5), (1.5, 10.5), (1.5, 7.5)]):
            c.lines(T(seg), color, lw)
    elif name == "collapse":  # a thin bar = "back to the strip"
        c.lines(T([(1.5, 4.5), (10.5, 4.5), (10.5, 7.5), (1.5, 7.5), (1.5, 4.5)]), color, 1.5 * f)
    elif name == "prev":
        c.poly(T([(2, 2), (3.6, 2), (3.6, 10), (2, 10)]), color)
        c.poly(T([(10, 2), (4.4, 6), (10, 10)]), color)
    elif name == "stop":   # hollow square
        c.lines(T([(2.5, 2.5), (9.5, 2.5), (9.5, 9.5), (2.5, 9.5), (2.5, 2.5)]), color, 1.4 * f)
    elif name == "next":
        c.poly(T([(2, 2), (7.6, 6), (2, 10)]), color)
        c.poly(T([(8.4, 2), (10, 2), (10, 10), (8.4, 10)]), color)
    elif name == "play":
        c.poly(T([(3.4, 1.8), (10.2, 6), (3.4, 10.2)]), color)
    elif name == "pause":
        c.poly(T([(2.6, 2), (5, 2), (5, 10), (2.6, 10)]), color)
        c.poly(T([(7, 2), (9.4, 2), (9.4, 10), (7, 10)]), color)
    elif name in ("slower", "faster"):
        # small speedometer: half dial + needle pointing low (slower) or high (faster)
        c.arc(ox + 6 * f, oy + 8 * f, 5 * f, 180, 360, color, 1.4 * f)
        tip = (3.2, 5.1) if name == "slower" else (8.8, 5.1)
        c.lines(T([(6, 8), tip]), color, 1.5 * f)
        c.circle(ox + 6 * f, oy + 8 * f, 1.3 * f, color)
    elif name == "pin":
        w = 1.4 * f
        c.lines(T([(4.2, 1.5), (7.8, 1.5)]), color, w)
        c.lines(T([(4.8, 1.5), (4.8, 4.9), (3, 6.8), (9, 6.8), (7.2, 4.9), (7.2, 1.5)]), color, w)
        c.lines(T([(6, 6.8), (6, 10.5)]), color, w)
    elif name == "minimize":
        c.lines(T([(2.5, 9), (9.5, 9)]), color, 1.6 * f)
    elif name == "maximize":  # one big square
        c.lines(T([(2, 2), (10, 2), (10, 10), (2, 10), (2, 2)]), color, 1.5 * f)
    elif name == "unmaximize":  # two overlapping squares: "back to the window size"
        c.lines(T([(4, 4), (10, 4), (10, 10), (4, 10), (4, 4)]), color, 1.4 * f)
        c.lines(T([(2, 8), (2, 2), (8, 2)]), color, 1.4 * f)
    elif name == "restore":  # a window outline: "open the video window again"
        c.lines(T([(2, 2.5), (10, 2.5), (10, 9.5), (2, 9.5), (2, 2.5)]), color, 1.4 * f)
        c.lines(T([(2, 4.5), (10, 4.5)]), color, 1.4 * f)
    elif name == "speaker_off":  # muted: the speaker with a cross
        c.poly(T([(1.2, 4.5), (3.3, 4.5), (6.3, 2), (6.3, 10), (3.3, 7.5), (1.2, 7.5)]), color)
        c.lines(T([(7.6, 4.2), (11, 7.8)]), color, 1.4 * f)
        c.lines(T([(11, 4.2), (7.6, 7.8)]), color, 1.4 * f)
    elif name == "close":
        c.lines(T([(2.5, 2.5), (9.5, 9.5)]), color, 1.6 * f)
        c.lines(T([(9.5, 2.5), (2.5, 9.5)]), color, 1.6 * f)
    elif name == "menu":
        for yy in (3, 6, 9):
            c.lines(T([(2.5, yy), (9.5, yy)]), color, 1.4 * f)
    elif name in ("arrow_up", "arrow_down"):  # flip: open panels above / below
        if name == "arrow_up":
            c.poly(T([(6, 3), (10.5, 9), (1.5, 9)]), color)
        else:
            c.poly(T([(1.5, 3), (10.5, 3), (6, 9)]), color)
    elif name == "sun":
        c.circle(ox + 6 * f, oy + 6 * f, 2.4 * f, color)
        for a in range(0, 360, 45):
            r1, r2 = 3.8, 5.6
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            c.lines(T([(6 + r1 * ca, 6 + r1 * sa), (6 + r2 * ca, 6 + r2 * sa)]), color, 1.1 * f)
    elif name == "moon":  # crescent: outer circle minus an offset circle
        pts = []
        for a in range(40, 321, 10):
            pts.append((6 + 5 * math.cos(math.radians(a)), 6 + 5 * math.sin(math.radians(a))))
        for a in range(320, 39, -10):
            pts.append((8.6 + 4 * math.cos(math.radians(a)), 6 + 4 * math.sin(math.radians(a))))
        c.poly(T(pts), color)
    elif name == "speaker":
        c.poly(T([(1.5, 4.5), (3.6, 4.5), (6.6, 2), (6.6, 10), (3.6, 7.5), (1.5, 7.5)]), color)
        c.arc(ox + 7 * f, oy + 6 * f, 2.6 * f, -50, 50, color, 1.3 * f)
        c.arc(ox + 7 * f, oy + 6 * f, 4.6 * f, -50, 50, color, 1.3 * f)


# ---------------------------------------------------------------- skin model
class Skin:
    def __init__(self):
        self.bitmaps = {}   # id -> PIL image
        self.windows = []
        self.prefix = ""    # theme namespace ("t3_"): added to every bitmap id

    def add(self, bid, im):
        self.bitmaps[self.prefix + bid] = im
        return bid


class Node:
    def __init__(self, kind, **kw):
        self.kind = kind
        self.__dict__.update(kw)
        self.children = []


class Layout:
    def __init__(self, skin, lid, w, h, minw=None, maxw=None, minh=None, maxh=None):
        self.skin, self.id = skin, lid
        self.w, self.h = w, h            # pixels
        self.minw = minw if minw else w
        self.maxw = maxw if maxw else w
        self.minh = minh if minh else h
        self.maxh = maxh if maxh else h
        self.nodes = []
        self._stack = [self.nodes]
        self.oy = 0                      # vertical offset of the section being added (px)
        self.vis = None                  # visible="..." expression for the section being added
        self.theme_vis = None            # visible="..." expression of the theme being added

    def _add(self, n):
        if len(self._stack) == 1:        # top level only: panel children are panel-relative
            n.y += self.oy
        n.vis = vis_and(self.theme_vis, self.vis)
        self._stack[-1].append(n)
        return n

    def size(self, bid):
        return self.skin.bitmaps[bid].size

    def image(self, bid, x, y, lt="lefttop", rb="lefttop", action="none", action2="none"):
        bid = self.skin.prefix + bid
        w, h = self.size(bid)
        return self._add(Node("Image", bid=bid, x=x, y=y, w=w, h=h, lt=lt, rb=rb,
                              action=action, action2=action2))

    def button(self, base, x, y, action, tip, lt="lefttop", rb="lefttop"):
        base = self.skin.prefix + base
        w, h = self.size(base + "_up")
        return self._add(Node("Button", base=base, x=x, y=y, w=w, h=h, lt=lt, rb=rb,
                              action=action, tip=tip))

    def checkbox(self, base, x, y, state, a1, a2, tip1, tip2, lt="lefttop", rb="lefttop"):
        base = self.skin.prefix + base
        w, h = self.size(base + "_off_up")
        return self._add(Node("Checkbox", base=base, x=x, y=y, w=w, h=h, lt=lt, rb=rb,
                              state=state, a1=a1, a2=a2, tip1=tip1, tip2=tip2))

    def text(self, x, y, w, font, text, color, lt="lefttop", rb="lefttop", align="left",
             scrolling="auto", sample="", focus=True):
        """focus=False: the text ignores the mouse, so a click reaches the image under it."""
        return self._add(Node("Text", x=x, y=y, w=w, h=0, font=font, text=text, color=color,
                              lt=lt, rb=rb, align=align, scrolling=scrolling, sample=sample, focus=focus))

    def slider(self, sid, x, y, points, thumb, value, tip, bg=None, nbvert=1,
               lt="lefttop", rb="lefttop", thickness=None):
        p = self.skin.prefix
        sid, thumb, bg = p + sid, p + thumb, (p + bg) if bg else None
        return self._add(Node("Slider", sid=sid, x=x, y=y, points=points, thumb=thumb, value=value,
                              tip=tip, bg=bg, nbvert=nbvert, lt=lt, rb=rb, thickness=thickness))

    def video(self, x, y, w, h):
        """skins2 shows video only inside a Video control; it grows with the layout."""
        return self._add(Node("Video", x=x, y=y, w=w, h=h, lt="lefttop", rb="rightbottom"))

    def anchor(self, x, y, priority, points="(0,0)"):
        return self._add(Node("Anchor", x=x, y=y, priority=priority, points=points))

    def playtree(self, x, y, w, h, font, slider_kw, lt="lefttop", rb="rightbottom", pid="playtree",
                 sid="pl_scroll"):
        p = self.skin.prefix
        pid, sid = p + pid, p + sid
        slider_kw = dict(slider_kw, y=slider_kw["y"] + self.oy, thumb=p + slider_kw["thumb"])
        colors = dict(fg=CYAN_TXT, play=PT_PLAY, sel=PT_SEL, bg1=LCD_BG, bg2=PT_BG2)
        return self._add(Node("Playtree", x=x, y=y, w=w, h=h, font=font, slider=slider_kw, lt=lt, rb=rb,
                              pid=pid, sid=sid, colors=colors))

    def panel_begin(self, pid, x, y, w, h):
        n = self._add(Node("Panel", pid=self.skin.prefix + pid, x=x, y=y, w=w, h=h))
        self._stack.append(n.children)
        return n

    def panel_end(self):
        self._stack.pop()


def vis_and(*exprs):
    """Join visible="..." expressions with "and" (skins2 has no parentheses; "not" binds tightest)."""
    return " and ".join(e for e in exprs if e) or None


def label_on(skin, bid, bg, x, y, w, h, text, size=8):
    """Label baked onto a crop of the window background so it is fully opaque."""
    im = bg.crop((P(x), P(y), P(x) + P(w), P(y) + P(h))).copy()
    d = ImageDraw.Draw(im)
    d.text((0, im.height / 2), text, font=_truetype(FONT_BOLD, P(size)), fill=H(LABEL), anchor="lm")
    skin.add(bid, im)
    return bid


def add_shared(skin, name, im):
    """Add a piece that corner variants share (slice middles). Variants whose pixels differ (the bottom
    outline of a strip that has a panel below it) get their own id (name, name2, ...); equal ones reuse it."""
    n = 1
    while True:
        bid = name if n == 1 else "%s%d" % (name, n)
        old = skin.bitmaps.get(skin.prefix + bid)
        if old is None or (old.size == im.size and old.tobytes() == im.tobytes()):
            return skin.add(bid, im)
        n += 1


def hslice(skin, lay, name, im, x, y, capl, capr, action="move", action2="none", right_action=None, tag=""):
    """Cut a horizontally stretchable element into left cap / mosaic middle / right cap.
    tag names the caps only (corner variants share the middle piece)."""
    w, h = im.size
    l, r = P(capl), P(capr)
    skin.add(name + tag + "_l", im.crop((0, 0, l, h)))
    mid = add_shared(skin, name + "_m", im.crop((l, 0, w - r, h)))
    skin.add(name + tag + "_r", im.crop((w - r, 0, w, h)))
    lay.image(name + tag + "_l", x, y, action=action, action2=action2)
    lay.image(mid, x + l, y, rb="righttop", action=action, action2=action2)
    lay.image(name + tag + "_r", x + w - r, y, lt="righttop", rb="righttop", action=right_action or action)


def nslice(skin, lay, name, im, x, y, cap, actions=None, tag=""):
    """Nine-slice for elements stretching in both directions."""
    w, h = im.size
    c = P(cap)
    xs = [(0, c, "l"), (c, w - c, "m"), (w - c, w, "r")]
    ys = [(0, c, "t"), (c, h - c, "m"), (h - c, h, "b")]
    anchor_x = {"l": ("lefttop", "lefttop"), "m": ("lefttop", "righttop"), "r": ("righttop", "righttop")}
    actions = actions or {}
    for y0, y1, vy in ys:
        for x0, x1, vx in xs:
            corner = vy in "tb" and vx in "lr"
            piece, bid = im.crop((x0, y0, x1, y1)), "%s%s_%s%s" % (name, tag if corner else "", vy, vx)
            bid = skin.add(bid, piece) if corner else add_shared(skin, bid, piece)
            lt_x, rb_x = anchor_x[vx]
            if vy == "t":
                lt, rb = lt_x, rb_x
            elif vy == "m":
                lt = lt_x
                rb = rb_x.replace("top", "bottom")
            else:
                lt, rb = lt_x.replace("top", "bottom"), rb_x.replace("top", "bottom")
            lay.image(bid, x + x0, y + y0, lt=lt, rb=rb, action=actions.get(vy + vx, "move"))


# ---------------------------------------------------------------- bitmap factories
def make_button(skin, base, w, h, icon_name=None, icon_size=12, label=None, led_on=None, label_size=8):
    for st in ("up", "over", "down"):
        c = Canvas(w, h)
        button_face(c, w, h, st)
        if icon_name:
            icon(c, icon_name, (w - icon_size) / 2, (h - icon_size) / 2, icon_size, ICON[st])
        if label:
            c.text(w / 2, h / 2 + 0.5, label, label_size, ICON[st], anchor="mm")
        skin.add("%s_%s" % (base, st), solid(c.done()))
    return base


def make_toggle(skin, base, w, h, icon_off=None, icon_on=None, label=None, use_led=False,
                on_color=None, icon_size=12, label_size=8, well=None):
    """Checkbox bitmaps: <base>_off_* (state false) and <base>_on_* (state true).
    well = (outer width, outer height): the button sits in a recessed box (w x h is the button)."""
    for on in (False, True):
        for st in ("up", "over", "down"):
            c = Canvas(*(well or (w, h)))
            if well:
                c.rrect(0, 0, well[0], well[1], 3, LCD_EDGE)
                c.rrect(1, 1, well[0] - 2, well[1] - 2, 3, LCD_BG)
                c.ox, c.oy = (well[0] - w) / 2, (well[1] - h) / 2
            col = ICON[st]
            if on and on_color and st != "down":
                col = on_color
            ring = None
            if on and on_color:
                ring = ring_colour(on_color)
            elif on and (use_led or label):
                ring = ring_colour(CYAN)
                col = CYAN if st != "down" else col
            elif icon_on == "pause":
                ring = ring_colour(CYAN)
            button_face(c, w, h, st, ring)
            name = icon_on if on else icon_off
            if name:
                icon(c, name, (w - icon_size) / 2, (h - icon_size) / 2, icon_size, col)
            if label:
                if use_led:      # dot + gap + text, centred as one group
                    tw_ = _truetype(FONT_BOLD, P(label_size)).getlength(label) / S
                    x0 = (w - (4 + 5 + tw_)) / 2
                    led(c, x0 + 2, h / 2, on)
                    c.text(x0 + 9, h / 2 + 0.5, label, label_size, col, anchor="lm")
                else:
                    c.text(w / 2, h / 2 + 0.5, label, label_size, col, anchor="mm")
            skin.add("%s_%s_%s" % (base, "on" if on else "off", st), solid(c.done()))
    return base


def make_strip_button(skin, base, w, h):
    """Labelled "STRIP" button (icon + text, accent ring) that collapses the full player."""
    for st in ("up", "over", "down"):
        c = Canvas(w, h)
        button_face(c, w, h, st, ring_colour(CYAN))
        col = CYAN if st != "down" else ICON[st]
        icon(c, "collapse", 7, (h - 10) / 2, 10, col)
        c.text(23, h / 2 + 0.5, "STRIP", 9, col, anchor="lm")
        skin.add("%s_%s" % (base, st), solid(c.done()))
    return base


EQ_FRAMES, EQ_FW, EQ_FH = 41, 30, 104
EQ_KNOB_H = 14        # EQ knob height (thumb_eq)
EQ_G0, EQ_G1 = 16, 96   # EQ groove: top row, row after the bottom


def eq_travel():
    """Device y of the EQ knob centre at +20 dB and at -20 dB: the knob (height P(14), drawn from centre - h // 2)
    stays inside the groove at both ends at every scale (rounding the logical 23 / 89 overshot by 1 px at 150 %)."""
    kh = P(EQ_KNOB_H)
    return P(EQ_G0) + kh // 2, P(EQ_G1) - (kh - kh // 2)


# A fader is drawn as one 30 x 104 design, but only three parts of it are stored (each frame sheet is
# copied by VLC into 44 sliders per theme, so every pixel counts):
#   - the dB label (a slider of its own on top of the fader, thumb_none), columns EQ_LBL_X, rows 0 .. EQ_LBL_H
#   - the groove with the lit fill, columns EQ_FILL_X, rows EQ_LBL_H .. EQ_CROP_H (the knob stays on this slider)
#   - the two 0 dB ticks never change: they are pasted into the static eq_bands image (EQ_TICKS)
# Everything else is the plain LCD background, which eq_bands already has. (x0, width), logical px:
EQ_LBL_X = {False: (6, 18), True: (1, 28)}   # band fader / preamp (its label has a "dB")
EQ_LBL_H = 14
EQ_FILL_X = (11, 8)
EQ_CROP_H = 98
EQ_TICK_BOX = (8, 54, 22, 58)   # 1 px of slack each side: ticks are anti-aliased at fractional scales
EQ_FILL_STEP = 2   # the groove sheet has every 2nd dB: the knob (14 px high, centred on the fill's top edge) hides the gap
EQ_TICKS = {}


def eq_boxes(pre):
    """Device-px crop boxes (left, top, right, bottom) in the 30 x 104 design: label, fill, ticks."""
    lx, lw = EQ_LBL_X[pre]
    fx, fw = EQ_FILL_X
    return ((P(lx), 0, P(lx + lw), P(EQ_LBL_H)), (P(fx), P(EQ_LBL_H), P(fx + fw), P(EQ_CROP_H)),
            tuple(P(v) for v in EQ_TICK_BOX))


def make_eq_frames(skin, bid, lbl_bid, col, pre=False):
    """EQ fader frames, frame i (i = dB + 20), 1 dB per frame, opaque (LCD_BG): `bid` has the groove
    and the lit fill from the bottom up to the knob, `lbl_bid` the dB value above the groove."""
    lb, fb, tb = eq_boxes(pre)
    lw, lh, fw, fh = lb[2] - lb[0], lb[3] - lb[1], fb[2] - fb[0], fb[3] - fb[1]
    lsheet = Image.new("RGBA", (lw, lh * EQ_FRAMES), (0, 0, 0, 0))
    nf = len(range(0, EQ_FRAMES, EQ_FILL_STEP))
    fsheet = Image.new("RGBA", (fw, fh * nf), (0, 0, 0, 0))
    for i in range(EQ_FRAMES):
        db = i - 20
        c = Canvas(EQ_FW, EQ_FH)
        c.rrect(0, 0, EQ_FW, EQ_FH, 0, LCD_BG)
        c.rrect(14, EQ_G0, 2, EQ_G1 - EQ_G0, 1, EQ_TRACK)
        c.rrect(9, 55.5, 4, 1, 0, CYAN_DIM)       # 0 dB ticks either side of the groove
        c.rrect(17, 55.5, 4, 1, 0, CYAN_DIM)
        ct, cb = eq_travel()
        cy = (cb - (cb - ct) * i / 40.0) / S  # knob centre
        c.rrect(13.5, cy, 3, 96 - cy, 0, col)
        label = ("%+d" % db if db else "0") + ("dB" if pre and db else "")
        c.text(15, 6, label, 9, col if db else CYAN2, font="mono", anchor="mm")
        full = c.done()
        lsheet.paste(full.crop(lb), (0, lh * i))
        if i % EQ_FILL_STEP == 0:
            fsheet.paste(full.crop(fb), (0, fh * (i // EQ_FILL_STEP)))
        if i == 0:
            EQ_TICKS[pre] = full.crop(tb)
    skin.add(bid, solid(fsheet, LCD_BG))
    skin.add(lbl_bid, solid(lsheet, LCD_BG))
    return bid


def make_chip_toggle(skin, base, w, h, label):
    """Bordered mode chip inside an LCD (SHUF / LOOP / REP1): dot + text, accent border when on."""
    for on in (False, True):
        for st in ("up", "over", "down"):
            c = Canvas(w, h)
            # same rules as the buttons: the outline (lit ring) is the same in every state, hover lightens
            # the face, pressed darkens it and turns the text accent-coloured
            edge = ring_colour(CYAN) if on else box_edge(0.16)
            face = mix(LCD_BG, CYAN, 0.14 if on else 0.0)
            if st == "over":
                face = mix(face, CYAN, 0.10)
            elif st == "down":
                face = mix(face, "#000000", 0.35)
            c.rrect(0, 0, w, h, 3, edge)
            c.rrect(1, 1, w - 2, h - 2, 2, face)
            tw_ = _truetype(FONT_MONO, P(9)).getlength(label) / S
            x0 = (w - (4 + 5 + tw_)) / 2
            c.circle(x0 + 2, h / 2, 2, CYAN if on else mix(LCD_BG, CYAN, 0.45))
            c.text(x0 + 9, h / 2 + 0.5, label, 9, CYAN_TXT if (on or st == "down") else CYAN2, font="mono", anchor="lm")
            skin.add("%s_%s_%s" % (base, "on" if on else "off", st), solid(c.done(), LCD_BG))
    return base


def make_lcd_toggle(skin, base, w, h, label):
    """Text-only toggle shown inside an LCD: dim when off, lit when on."""
    for on in (False, True):
        for st in ("up", "over", "down"):
            c = Canvas(w, h)
            c.rrect(0, 0, w, h, 0, LCD_BG)  # opaque: thin text on transparency renders badly on X11
            if on:
                col = LCD_HI if st == "over" else CYAN_TXT
            else:
                col = CYAN2 if st == "over" else CYAN_DIM
            c.text(0, h / 2, label, 10, col, font="mono", anchor="lm")
            skin.add("%s_%s_%s" % (base, "on" if on else "off", st), c.done())
    return base


def plain_toggle(skin, base, im):
    """Checkbox bitmaps that look the same in every state (a clickable background)."""
    for on in ("off", "on"):
        for st in ("up", "over", "down"):
            skin.add("%s_%s_%s" % (base, on, st), im)
    return base


def make_mode_toggle(skin, base, w, h):
    """Small button left of the strip's time box: "+" = elapsed time, "-" (lit) = time left; click switches."""
    for on in (False, True):
        for st in ("up", "over", "down"):
            c = Canvas(w, h)
            button_face(c, w, h, st, ring_colour(CYAN) if on else None)
            col = CYAN if on and st != "down" else ICON[st]
            cx, cy = w / 2, h / 2
            c.rrect(cx - 3, cy - 0.75, 6, 1.5, 0, col)         # "-" = time left
            if not on:
                c.rrect(cx - 0.75, cy - 3, 1.5, 6, 0, col)     # "+" = elapsed
            skin.add("%s_%s_%s" % (base, "on" if on else "off", st), solid(c.done()))
    return base


def make_title_thumb(skin, bid, h):
    """Thumb of a title box: left half = fill colour, right half = box colour, accent line at the
    centre (the thumb's centre sits on the playing position). It covers the gap between the fill
    frame (4 % steps, rounded down) and the exact position, so progress moves pixel by pixel."""
    for st, col in (("up", mix(CYAN, TITLE_FILL, 0.5)), ("over", CYAN)):
        im = Image.new("RGBA", (P(2 * TITLE_S), P(h)), H(LCD_BG))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, P(TITLE_S) - 1, P(h) - 1], fill=H(TITLE_FILL))
        d.rectangle([P(TITLE_S) - 0, 0, P(TITLE_S) + max(1, P(1)) - 1, P(h) - 1], fill=H(col))
        skin.add("%s_%s" % (bid, st), im)


def make_title_frames(skin, bid, w, h, n, color):
    """Title box fill frames. The play position runs from TITLE_S to w - TITLE_S (the thumb is
    2 x TITLE_S wide and must stay inside the box); frame i is filled up to that position."""
    pw, ph, ps = P(w), P(h), P(TITLE_S)
    sheet = Image.new("RGBA", (pw, ph * n), (0, 0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for i in range(n):      # frame 0 too: it is shown while the position is inside the first step (about 0-2 %),
        # and without its lit lead-in the box stays dark from its left edge up to the thumb's left half
        end = ps + round((pw - 2 * ps) * i / (n - 1))
        d.rectangle([0, ph * i, end - 1, ph * i + ph - 1], fill=H(color))
    skin.add(bid, sheet)
    return bid


def make_title_under(skin, bid, w, h, n):
    """H14 'underline' mode: line thumb (full height, accent) + the underline's own thumb (h = underline
    height) + underline frames (w x ul_h x n) + a 1-frame opaque box background (the click area)."""
    lw = max(1, P(1))
    for st, col in (("up", mix(CYAN, TITLE_FILL, 0.5)), ("over", CYAN)):
        skin.add("%s_line_%s" % (bid, st), Image.new("RGBA", (lw, P(h)), H(col)))
        skin.add("%s_ulthumb_%s" % (bid, st), Image.new("RGBA", (lw, P(TITLE_UL_H)), H(col)))
    skin.add(bid + "_box", Image.new("RGBA", (P(w), P(h)), (0, 0, 0, 0)))
    pw, uh = P(w), P(TITLE_UL_H)
    sheet = Image.new("RGBA", (pw, uh * n), (0, 0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for i in range(1, n):
        d.rectangle([0, uh * i, round(pw * i / (n - 1)) - 1, uh * i + uh - 1], fill=H(CYAN))
    skin.add(bid + "_ul", sheet)


def inset():
    """Device px between a display box's edge and its fill controls: exactly the outline (int(S) px), so no
    unfilled sliver is left at fractional scales (one logical px = 1.5 device px at 150 %; P(x + 1) rounded up)."""
    return max(1, int(S))


def title_slider(lay, skin, sid, bid, x, y, fw, fh, frames, thumb):
    """The progress slider(s) of one title box at (x, y) (device px), inner size fw x fh (design px)."""
    tip = "$T / $D  (click to jump, wheel = 5 %)"
    if TITLE_MODE == "underline":
        make_title_under(skin, bid, fw, fh, TITLE_UL_FRAMES)
        lay.slider(sid, x, y, "(0,%d),(%d,%d)" % (P(fh) // 2, P(fw) - 1, P(fh) // 2), bid + "_line", "time", tip,
                   bg=bid + "_box", nbvert=1, rb="righttop")
        lay.slider(sid + "_ul", x, y + P(fh) - P(TITLE_UL_H), "(0,%d),(%d,%d)" % (P(TITLE_UL_H) // 2, P(fw) - 1, P(TITLE_UL_H) // 2),
                   bid + "_ulthumb", "time", tip, bg=bid + "_ul", nbvert=TITLE_UL_FRAMES, rb="righttop")
        return
    make_title_frames(skin, bid + "_fill", fw, fh, TITLE_FRAMES, TITLE_FILL)
    lay.slider(sid, x, y, "(%d,%d),(%d,%d)" % (P(TITLE_S), P(fh) // 2, P(fw) - P(TITLE_S) - 1, P(fh) // 2),
               thumb, "time", tip, bg=bid + "_fill", nbvert=TITLE_FRAMES, rb="righttop")


def make_progress_frames(skin, bid, w, h, n, color):
    """Slider background drawn inside an LCD: frame i is filled to i/(n-1) from the left,
    the rest is fully transparent (the LCD shows through). Hard edges: X11 skins2 draws
    without alpha blending."""
    pw, ph = P(w), P(h)
    sheet = Image.new("RGBA", (pw, ph * n), (0, 0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for i in range(1, n):
        fw = round(pw * i / (n - 1))
        d.rectangle([0, ph * i, fw - 1, ph * i + ph - 1], fill=H(color))
    skin.add(bid, sheet)
    return bid


def make_thumb(skin, bid, w, h, bg=None):
    """Metallic slider knob (bright top half, darker lower half) with an accent notch."""
    for st, (t, b) in (("up", THUMB_UP), ("over", THUMB_OVER)):
        c = Canvas(w, h)
        c.rrect(0, 0, w, h, 2, mix(b, "#ffffff", 0.5))
        mid = h // 2
        c.grad(1, 1, w - 2, mid - 1, 1, t, mix(t, b, 0.55))
        c.grad(1, mid, w - 2, h - 1 - mid, 1, mix(t, b, 0.8), b)
        c.rrect(1, 1, w - 2, 1, 0, (255, 255, 255, 120))
        c.rrect((w - 1) / 2, 3, 1, h - 6, 0, CYAN)
        skin.add("%s_%s" % (bid, st), solid(c.done(), bg))
    return bid


def make_eq_thumb(skin, bid, w, h):
    """EQ slider knob on the LCD: a metallic block with an accent notch."""
    for st, col in (("up", CYAN), ("over", LCD_HI)):
        c = Canvas(w, h)
        t, b = THUMB_UP if st == "up" else THUMB_OVER
        c.rrect(0, 0, w, h, 2, mix(b, "#ffffff", 0.5))
        c.grad(1, 1, w - 2, h // 2 - 1, 1, t, mix(t, b, 0.55))
        c.grad(1, h // 2, w - 2, h - 1 - h // 2, 1, mix(t, b, 0.8), b)
        c.rrect(1, 1, w - 2, 1, 0, (255, 255, 255, 120))
        c.rrect(2, (h - 1) / 2 - 0.5, w - 4, 2, 0, col)   # accent notch across the knob
        skin.add("%s_%s" % (bid, st), solid(c.done(), LCD_BG))
    return bid


def make_fill_frames(skin, bid, w, h, track_y, track_h, n, knob=None, lead=0.0):
    """Slider background: n frames stacked vertically, frame i filled to i/(n-1). The groove
    has a light 1 px outline and a dark inside; the fill is the accent colour.
    knob = (lo, hi): the knob's centre runs from lo to hi device px (a knob kept inside the groove);
    the fill then ends under the knob centre instead of at i/(n-1) of the groove.
    lead = fraction of a frame step the fill runs ahead: skins2 shows frame floor(value * (n-1)), so the fill
    lags the knob by up to one step; with lead 0.5 the error is +-half a step and the knob (which covers
    +-6 px) hides it up to about 1200 px of seek bar width."""
    sheet = Image.new("RGBA", (P(w), P(h) * n), (0, 0, 0, 0))
    r = 3 if track_h >= 8 else track_h / 2
    for i in range(n):
        frac = i / (n - 1) if i in (0, n - 1) else min(1.0, (i + lead) / (n - 1))
        c = Canvas(w, h)
        c.rrect(0, track_y, w, track_h, r, mix(TRACK, "#ffffff", 0.22))
        c.rrect(1, track_y + 1, w - 2, track_h - 2, max(0, r - 1), TRACK)
        if frac > 0:
            fw = (w - 4) * frac if knob is None else (knob[0] + (knob[1] - knob[0]) * frac + 0.5) / S - 2
            c.rrect(2, track_y + 2, max(track_h - 4, fw), track_h - 4, max(0, r - 2), CYAN)
        sheet.paste(c.done(), (0, P(h) * i))
    skin.add(bid, solid(sheet))
    return bid


# ---------------------------------------------------------------- windows
MIN_W = 490   # narrowest strip: stop / prev / slower / play / faster / next + time box + PL / EQ / pin leave a 94 px title window
TIME_ZONE = 1    # inset of the volume fill in the strip's time box (the box border)
BAR_DEFAULT = 24   # strip height (logical px) of the normal skin
BAR_TASKBAR = 36   # --bar-height of the taskbar build (VLC-Amp-taskbar-NNN.vlt); the helper assumes the same


def bar_metrics(bh):
    """Sizes of the strip's parts for a bar of bh logical px. At 24 these are the original
    values (the normal skin must not change). Widths do not grow with the height, except the
    time box, which has to fit "-1:23:45" in the bigger strip font; MIN_W grows with it."""
    fs = 12 + (bh - 24) // 6                       # strip font (title, time), px
    tw = TIME_ZONE + 12 + math.ceil(8 * 0.602 * fs)  # time box: mode zone + 4 px + text + 8 px margin; DejaVu Sans Mono advance = 0.602 em
    big = bh >= 30
    return dict(bh=bh, btn=min(bh - 6, 24), y=(bh - min(bh - 6, 24)) // 2, bw=24 if big else 22, gap=6 if big else 2,
                icon=13 if big else 12, label=9 if big else 8, font=fs, tw=tw,
                min_w=MIN_W, grip_rows=3 + (bh - 24) // 8, grip_h=10 + (bh - 24) // 2)


def skin_name(bh, pct):
    """File stem of a build: VLC-Amp-150, VLC-Amp-taskbar-150 (36 px bar), VLC-Amp-bar40-150."""
    kind = "" if bh == BAR_DEFAULT else "taskbar-" if bh == BAR_TASKBAR else "bar%d-" % bh
    return "VLC-Amp-%s%d" % (kind, pct)
SEEK_LEAD = float(os.environ.get("TB_SEEK_LEAD", "0.5"))   # fill runs this many frame steps ahead of the frame index (see make_fill_frames)
SEEK_FRAMES = 101   # full-player seek bar: 1 % steps (the sheet is only 10 px high)
# H14 prototype (docs/architecture.md "Progress bar options"): "thumb" = fill frames + 2 x TITLE_S thumb (current);
# "underline" = exact 1 px line over a 1-frame box + a TITLE_UL_H px accent underline sheet (TITLE_UL_FRAMES frames)
TITLE_MODE = os.environ.get("TB_TITLE_MODE", "thumb")
TITLE_UL_H, TITLE_UL_FRAMES = 2, int(os.environ.get("TB_UL_FRAMES", "101"))
TITLE_FRAMES, TITLE_S = 51, 10   # title boxes: 2 % steps; the thumb (2 x TITLE_S wide) carries the fill in between
FILL_FRAMES = 51   # frames of the seek / title progress fills (2 % steps); each frame costs memory in every theme

# State that must survive layout switches and restarts lives in tiny invisible "flag"
# windows: VLC saves every window's visibility, and controls can test it with
# visible="<id>.isVisible". Shown = on.
EQ_ON, PL_ON, COUNTDOWN = "eqflag.isVisible", "plflag.isVisible", "tflag.isVisible"


def select_theme(i):
    """Action: show theme flag i, hide the others (show first, so something is always drawn)."""
    return ";".join(["th%d.show()" % i] + ["th%d.hide()" % j for j in range(len(THEMES)) if j != i])


def build(skin, W, BH=BAR_DEFAULT):
    """One main window, four layouts: strip / full x panels below ("dn") / above ("up").
    All four have the same size, so VLC carries a dragged width from one to the other
    (it only does that between layouts of identical original size). Areas without
    pixels are cut out of the window, so the unused space is invisible and click-through.
    EQ and playlist are shown / hidden inside the layout, not separate layouts."""
    FH, EH, LH = 232, 164, 280
    HT = FH + EH + LH                 # window height: full player + EQ + playlist (the same for every bar height)
    M = bar_metrics(BH)
    TW = M["tw"]                      # strip time box: fits "-1:23:45" (hours) in the strip font
    BT = M["btn"]                     # strip button height
    BW_, G_, BY = M["bw"], M["gap"], M["y"]
    PLW = 44                          # PL / EQ toggle width (strip and full player)
    MB = min(16, BT - 4)              # mode button (elapsed / time left) next to the strip's time box
    skin.strip_font = ("lcd12" if M["font"] == 12 else "lcdbar", M["font"])
    PW = P(W)
    tr = dict(lt="righttop", rb="righttop")
    sw = W - 24                       # seek bar width (full player)
    EQ_BW = 446                       # EQ band block width (fixed, centred): the faders span 3 .. 443
    VK = P(10)                        # full-player volume knob width (thumb_v); the knob is drawn from centre - VK // 2
    V_LO, V_HI = VK // 2, P(100) - 1 - (VK - 1 - VK // 2)    # its centre range: the knob stays inside the 100 px groove (it never scales: fixed-width control)

    def make_bitmaps():
        """All bitmaps of the current theme (skin.prefix namespaces them)."""
        isz, lsz = M["icon"], M["label"]
        for nm, ic in (("b_expand", "expand"), ("b_prev", "prev"), ("b_next", "next")):
            make_button(skin, nm, BW_, BT, ic, icon_size=isz)
        make_toggle(skin, "t_play", BW_ + 4, BT, icon_off="play", icon_on="pause", on_color=CYAN, icon_size=isz)
        make_toggle(skin, "t_pl", PLW, BT, label="PL", use_led=True, label_size=lsz)   # same look as the full player's
        make_toggle(skin, "t_eq", PLW, BT, label="EQ", use_led=True, label_size=lsz)
        make_toggle(skin, "t_top", BW_, BT, icon_off="pin", icon_on="pin", on_color=AMBER, icon_size=isz)
        make_thumb(skin, "thumb_v", 10, 18)
        make_title_thumb(skin, "thumb_title", BT - 2)
        make_title_thumb(skin, "thumb_ftitle", 26)
        for st in ("up", "over"):   # volume bar in the strip's time box: the fill is the indicator, no knob
            skin.add("thumb_none_" + st, Image.new("RGBA", (1, 1), (0, 0, 0, 0)))
        make_strip_button(skin, "b_strip", 68, 22)
        make_eq_frames(skin, "eqfill", "eqlbl", CYAN)
        make_eq_frames(skin, "eqfill_pre", "eqlbl_pre", AMBER, pre=True)
        make_button(skin, "b_menu", 24, 22, "menu", icon_size=11)
        make_toggle(skin, "t_top_s", 24, 22, icon_off="pin", icon_on="pin", on_color=AMBER, icon_size=11)
        make_button(skin, "b_min", 24, 22, "minimize", icon_size=11)
        make_button(skin, "b_close", 24, 22, "close", icon_size=11)
        make_button(skin, "b_flip_up", 24, 22, "arrow_up", icon_size=10)
        make_button(skin, "b_flip_dn", 24, 22, "arrow_down", icon_size=10)
        for nm, ic in (("fb_stop", "stop"), ("fb_prev", "prev"), ("fb_slower", "slower"), ("fb_faster", "faster"),
                       ("fb_next", "next")):
            make_button(skin, nm, 30, 28, ic, icon_size=13)
        make_toggle(skin, "ft_play", 40, 28, icon_off="play", icon_on="pause", on_color=CYAN, icon_size=14)
        make_toggle(skin, "ft_pl", 44, 28, label="PL", use_led=True, label_size=9)
        make_toggle(skin, "ft_eq", 44, 28, label="EQ", use_led=True, label_size=9)
        # video window (title bar, control panel, extra row) and fullscreen controller
        for nm, ic in (("vb_full", "expand"), ("vb_min", "minimize"), ("vb_restore", "restore"), ("vb_close", "close")):
            make_button(skin, nm, 24, 22, ic, icon_size=11)
        make_toggle(skin, "vb_max", 24, 22, icon_off="maximize", icon_on="unmaximize", icon_size=11)
        make_toggle(skin, "ft_mute", 30, 28, icon_off="speaker", icon_on="speaker_off", on_color=AMBER, icon_size=13)
        make_button(skin, "fb_fs", 30, 28, "expand", icon_size=13)            # fullscreen controller: leave full screen
        make_button(skin, "fb_more", 30, 28, "arrow_down", icon_size=12)      # show the extra row (it opens below)
        make_button(skin, "fb_less", 30, 28, "arrow_up", icon_size=12)        # hide it
        make_toggle(skin, "ft_more", 30, 28, icon_off="arrow_down", icon_on="arrow_up", icon_size=12)
        make_toggle(skin, "xt_ab", 44, 22, label="A-B", label_size=9)         # same look in both states (a button)
        make_button(skin, "xb_chprev", 44, 22, label="CH-", label_size=9)
        make_button(skin, "xb_chnext", 44, 22, label="CH+", label_size=9)
        make_button(skin, "xb_snap", 48, 22, label="SNAP", label_size=9)
        make_button(skin, "xb_slower", 30, 22, "slower", icon_size=12)
        make_button(skin, "xb_faster", 30, 22, "faster", icon_size=12)
        c = Canvas(60, 22)                                                    # speed readout box (between slower / faster)
        lcd(c, 0, 0, 60, 22, 3)
        skin.add("x_speed_bg", solid(c.done()))
        make_thumb(skin, "thumb_s", 12, 20)
        make_toggle(skin, "t_eqon", 44, 22, label="ON", use_led=True, label_size=9)
        make_eq_thumb(skin, "thumb_eq", 18, 14)
        make_thumb(skin, "thumb_pl", 8, 24, SCROLL_TRACK)
        for nm, lbl in (("l_shuf", "SHUF"), ("l_loop", "LOOP"), ("l_rep", "REP1")):
            make_chip_toggle(skin, nm, 46, 16, lbl)
        make_fill_frames(skin, "vol100", 100, 10, 0, 10, P(100), knob=(V_LO, V_HI))
        make_fill_frames(skin, "seek", sw, 10, 0, 10, SEEK_FRAMES, lead=SEEK_LEAD)
        c = Canvas(12, 12)
        icon(c, "speaker", 0, 0, 12, LABEL)
        skin.add("ic_speaker", solid(c.done()))
        # time readout backgrounds, used as checkboxes (an Image only reacts to double-clicks)
        c = Canvas(TW, BT)
        lcd(c, 0, 0, TW, BT, 3)
        skin.add("c_time_s", solid(c.done()))
        make_mode_toggle(skin, "c_mode", MB, MB)
        make_progress_frames(skin, "vol_fill", TW - TIME_ZONE - 1, BT - 2, FILL_FRAMES, TITLE_FILL)
        c = Canvas(190, 96)
        c.rrect(0, 0, 190, 96, 0, LCD_BG)
        plain_toggle(skin, "c_time_f", c.done())
        for lbl in ("add", "rem", "sort", "load", "save"):
            make_button(skin, "b_pl_" + lbl, 44, 22, label=lbl.upper(), label_size=9)
        for lbl in ("shuf", "loop", "rep1"):
            make_toggle(skin, "t_pl_" + lbl, 52, 22, label=lbl.upper(), use_led=True, label_size=9)
        c = Canvas(62, 16)
        c.rrect(0, 0, 62, 16, 3, mix(LCD_BG, CYAN, 0.28))
        c.rrect(1, 1, 60, 14, 2, mix(LCD_BG, CYAN, 0.08))
        skin.add("chip", solid(c.done(), LCD_BG))
        c = Canvas(41, 16)
        c.rrect(0, 0, 41, 16, 3, mix(LCD_BG, CYAN, 0.28))
        c.rrect(1, 1, 39, 14, 2, mix(LCD_BG, CYAN, 0.08))
        skin.add("chip_fmt", solid(c.done(), LCD_BG))
        # theme button (full player title bar): a dot in the theme's accent colour
        for st in ("up", "over", "down"):
            c = Canvas(24, 22)
            button_face(c, 24, 22, st)
            c.circle(12, 11, 5.2, ICON[st])
            c.circle(12, 11, 4.1, BG_BOT)
            c.circle(12, 11, 3.2 if st != "down" else 2.6, CYAN)
            skin.add("b_theme_" + st, solid(c.done()))

    def panel_toggles(lay, pl_base, eq_base, x_pl, x_eq, y):
        lay.checkbox(pl_base, x_pl, y, PL_ON, "plflag.show()", "plflag.hide()",
                     "Show playlist", "Hide playlist", **tr)
        lay.checkbox(eq_base, x_eq, y, EQ_ON, "eqflag.show()", "eqflag.hide()",
                     "Show equalizer", "Hide equalizer", **tr)

    def time_toggle(lay, base, x, y, **kw):
        """Background of a time readout; clicking it switches elapsed <-> countdown
        (remembered by VLC). The texts on top of it use focus=False."""
        lay.checkbox(base, x, y, COUNTDOWN, "tflag.show()", "tflag.hide()",
                     "Elapsed time (click: time left)", "Time left (click: elapsed time)", **kw)

    # Corners: only the outer corners of the whole stack are round. The bar's side towards the
    # panels is round only while no panel is open; the EQ's side towards the playlist only while
    # the playlist is closed. (skins2 expressions have no "or": a square variant is placed twice.)
    ANY_OFF = "not %s and not %s" % (EQ_ON, PL_ON)

    def bar_corners(d):
        """[(rounded top, rounded bottom, visibility)] of the bar's background in direction d."""
        return [(True, flag, v) if d == "dn" else (flag, True, v)
                for flag, v in ((True, ANY_OFF), (False, EQ_ON), (False, PL_ON + " and not " + EQ_ON))]

    def eq_corners(d):
        return [(False, flag, v) if d == "dn" else (flag, False, v)
                for flag, v in ((True, "not " + PL_ON), (False, PL_ON))]

    def cap_tag(rt, rb):
        return "_%d%d" % (rt, rb)

    # ================= strip bar
    def add_strip(lay, d):
        base_vis = lay.vis
        for rt, rb, v in bar_corners(d):
            c = Canvas(W, BH)
            panel_bg(c, 0, 0, W, BH, 6, rt=rt, rb=rb)
            rows = M["grip_rows"]
            grip_dots(c, 4, BH / 2 - 3 - 2 * (rows - 1), rows)
            resize_handle(c, grip_x(W), 3, BH - 6)
            lay.vis = vis_and(base_vis, v)
            bg = c.done(hard_edges=True)
            hslice(skin, lay, "strip_bg", bg, 0, 0, 14, 10, tag=cap_tag(rt, rb))
        lay.vis = base_vis
        grip_tab(skin, lay, bg, grip_x(W), 3, BH - 6)
        x = 16
        lay.button("b_expand", P(x), P(BY), "main.setLayout(full-%s)" % d, "Expand to full player")
        x += BW_ + G_
        lay.button("b_prev", P(x), P(BY), "playlist.previous()", "Previous")
        x += BW_ + G_
        lay.checkbox("t_play", P(x), P(BY), "vlc.isPlaying", "vlc.play()", "vlc.pause()", "Play", "Pause")
        x += BW_ + 4 + G_
        lay.button("b_next", P(x), P(BY), "playlist.next()", "Next")
        dx = x + BW_ + G_
        RP = 14 + BW_ + 2 * (G_ + PLW)           # distance of the PL button's left edge from the right edge
        MG = 3                                       # tight gap around the mode button
        dw = W - (RP + G_ + TW + 2 * MG + MB) - dx
        c = Canvas(dw, BT)
        lcd(c, 0, 0, dw, BT, 3)
        hslice(skin, lay, "strip_lcd", solid(c.done()), P(dx), P(BY), 4, 4)
        # the title window is also a seek bar: progress fills it from the left, a click jumps
        # there (and drags), the mouse wheel steps 5 %. The title text ignores the mouse.
        fw, fh = dw - 2, BT - 2
        title_slider(lay, skin, "s_title_" + lay.id, "title", P(dx) + inset(), P(BY) + inset(), fw, fh, TITLE_FRAMES, "thumb_title")
        ty = round(BH / 2 - 0.582 * M["font"])   # text top: the line (1.164 em) is centred in the bar
        lay.text(P(dx + 8), P(ty), P(dw - 16), skin.strip_font[0], "$N", CYAN_TXT, rb="righttop", focus=False,
                 sample="Nightline Orchestra - Slow Burn Across the River (Extended Mix)")
        R = lambda v: PW - P(v)
        tx = R(RP + G_ + TW)
        # time box = volume bar filled from the left like the title's seek fill; click / drag / wheel sets
        # the volume. The small button on its left switches elapsed <-> time left (remembered by VLC)
        lay.image("c_time_s", tx, P(BY), action="move", **tr)
        lay.checkbox("c_mode", R(RP + G_ + TW + MG + MB), P(BY + (BT - MB) // 2), COUNTDOWN, "tflag.show()", "tflag.hide()",
                     "Elapsed time (click: time left)", "Time left (click: elapsed time)", **tr)
        vw, vfh = TW - TIME_ZONE - 1, BT - 2
        lay.slider("s_vol_" + lay.id, tx + inset(), P(BY) + inset(), "(0,%d),(%d,%d)" % (P(vfh) // 2, P(vw) - 1, P(vfh) // 2),
                   "thumb_none", "volume", "Volume $V%  (click to set, wheel to change)", bg="vol_fill",
                   nbvert=FILL_FRAMES, **tr)
        for text, vis, sample in (("$t", "not " + COUNTDOWN, "1:02"), ("-$l", COUNTDOWN, "-3:10")):
            lay.text(tx + P(TIME_ZONE), P(ty), P(TW - TIME_ZONE), skin.strip_font[0], text, CYAN_TXT,
                     lt="righttop", rb="righttop", align="center", scrolling="none", sample=sample,
                     focus=False).vis = vis_and(lay.theme_vis, vis)
        panel_toggles(lay, "t_pl", "t_eq", R(RP), R(14 + BW_ + G_ + PLW), P(BY))
        lay.checkbox("t_top", R(14 + BW_), P(BY), "vlc.isOnTop", "vlc.onTop()", "vlc.onTop()",
                     "Always on top: off (click to pin)", "Always on top: on (click to unpin)", **tr)

    # ================= full player bar
    def add_full(lay, d):
        F = lambda v: PW - P(v)
        base_vis = lay.vis
        for rt, rb, v in bar_corners(d):
            c = Canvas(W, FH)
            panel_bg(c, 0, 0, W, FH, 6, rt=rt, rb=rb)
            grip_dots(c, 4, 12)
            resize_handle(c, grip_x(W), grip_y(44, 108), GRIP_H)     # centred on the display card (y 44..152)
            lay.vis = vis_and(base_vis, v)
            bg = c.done(hard_edges=True)
            hslice(skin, lay, "full_bg", bg, 0, 0, 14, 10, tag=cap_tag(rt, rb))
        lay.vis = base_vis
        grip_tab(skin, lay, bg, grip_x(W), grip_y(44, 108), GRIP_H)
        nxt = (cur["theme"] + 1) % len(THEMES)
        if nxt != cur["theme"]:
            lay.button("b_theme", F(148), P(9), select_theme(nxt),
                       "Theme: %s (click: %s)" % (THEMES[cur["theme"]][1], THEMES[nxt][1]), **tr)
        lay.button("b_menu", F(120), P(9), "dialogs.popup()", "VLC menu (open files, skins, settings)", **tr)
        lay.checkbox("t_top_s", F(92), P(9), "vlc.isOnTop", "vlc.onTop()", "vlc.onTop()",
                     "Always on top: off (click to pin)", "Always on top: on (click to unpin)", **tr)
        lay.button("b_min", F(64), P(9), "vlc.minimize()", "Minimize", **tr)
        lay.button("b_close", F(36), P(9), "vlc.quit()", "Quit VLC", **tr)
        lay.button("b_strip", P(16), P(9), "main.setLayout(strip-%s)" % d, "Collapse to title-bar strip")
        # display: left card = time, right = title (seek box), spec chips, mode toggles
        c = Canvas(W - 24, 108)
        lcd(c, 0, 0, W - 24, 108, 4, outline=False)
        c.rrect(200, 8, 1, 92, 0, DIVIDER)
        hslice(skin, lay, "full_lcd", solid(c.done()), P(12), P(44), 206, 8)
        time_toggle(lay, "c_time_f", P(18), P(48))
        for big, small, lbl, vis, s1, s2 in (("$t", "of $d", "ELAPSED", "not " + COUNTDOWN, "1:02", "of 4:12"),
                                             ("-$l", "of $d", "REMAINING", COUNTDOWN, "-3:10", "of 4:12")):
            v = vis_and(lay.theme_vis, vis)
            lay.text(P(26), P(54), P(150), "lcd10", lbl, CYAN_DIM, scrolling="none", sample=lbl,
                     focus=False).vis = v
            lay.text(P(18), P(70), P(190), "lcd30", big, CYAN_TXT, scrolling="none", align="center", sample=s1,
                     focus=False).vis = v
            lay.text(P(26), P(128), P(150), "lcd10", small, CYAN2, scrolling="none", sample=s2,
                     focus=False).vis = v
        # title box = seek bar (like the strip's): progress fills it from the left, a click jumps there
        tx0, ty0, tw0, th0 = 222, 52, W - 242, 28
        c = Canvas(tw0, th0)
        lcd(c, 0, 0, tw0, th0, 3)
        hslice(skin, lay, "full_title", solid(c.done(), LCD_BG), P(tx0), P(ty0), 4, 4)
        fw0, fh0 = tw0 - 2, th0 - 2
        title_slider(lay, skin, "s_ftitle_" + lay.id, "ftitle", P(tx0) + inset(), P(ty0) + inset(), fw0, fh0, TITLE_FRAMES, "thumb_ftitle")
        lay.text(P(tx0 + 8), P(ty0 + 6), P(tw0 - 16), "lcd14", "$N", CYAN_TXT, rb="righttop", focus=False,
                 sample="Nightline Orchestra - Slow Burn Across the River (Extended Mix)")
        lay.image("chip", P(222), P(90), action="move")
        lay.image("chip", P(290), P(90), action="move")
        lay.text(P(222), P(92), P(62), "lcd10", "$B kbps", CYAN_TXT, scrolling="none", align="center",
                 sample="320 kbps", focus=False)
        lay.text(P(290), P(92), P(62), "lcd10", "$S kHz", CYAN_TXT, scrolling="none", align="center",
                 sample="44.1 kHz", focus=False)
        # file format from the file name: "$F" is the path; a right-aligned box too narrow for it shows
        # only the end, i.e. the extension (4 characters: ".wav", ".mp3", "flac", "opus")
        lay.image("chip_fmt", P(358), P(90), action="move")
        lay.text(P(367), P(92), P(24), "lcd10", "$F", CYAN_TXT, scrolling="none", align="right",
                 sample=".wav", focus=False)
        lay.checkbox("l_shuf", P(222), P(122), "playlist.isRandom", "playlist.setRandom(true)",
                     "playlist.setRandom(false)", "Shuffle: off", "Shuffle: on")
        lay.checkbox("l_loop", P(274), P(122), "playlist.isLoop", "playlist.setLoop(true)",
                     "playlist.setLoop(false)", "Loop playlist: off", "Loop playlist: on")
        lay.checkbox("l_rep", P(326), P(122), "playlist.isRepeat", "playlist.setRepeat(true)",
                     "playlist.setRepeat(false)", "Repeat one: off", "Repeat one: on")
        lay.text(F(120), P(124), P(100), "lcd10", "SPEED $Rx", CYAN2, align="right", scrolling="none",
                 sample="SPEED 1x", **tr)
        # seek bar (stretches; the fill frames scale with it)
        lay.slider("s_seek_" + lay.id, P(12), P(164), "(0,%d),(%d,%d)" % (P(5), P(sw) - 1, P(5)), "thumb_s",
                   "time", "$T / $D", bg="seek", nbvert=SEEK_FRAMES, rb="righttop")
        # transport row
        ty = 195
        for nm, x, act, tip in (("fb_stop", 12, "vlc.stop()", "Stop"), ("fb_prev", 46, "playlist.previous()", "Previous"),
                                ("fb_slower", 80, "vlc.slower()", "Slower")):
            lay.button(nm, P(x), P(ty), act, tip)
        lay.checkbox("ft_play", P(114), P(ty), "vlc.isPlaying", "vlc.play()", "vlc.pause()", "Play", "Pause")
        lay.button("fb_faster", P(158), P(ty), "vlc.faster()", "Faster")
        lay.button("fb_next", P(192), P(ty), "playlist.next()", "Next")
        lay.image("ic_speaker", F(276), P(ty + 8), lt="righttop", rb="righttop", action="move")
        lay.slider("s_vol_" + lay.id, F(256), P(ty + 9), "(%d,%d),(%d,%d)" % (V_LO, P(5), V_HI, P(5)), "thumb_v",
                   "volume", "Volume $V%", bg="vol100", nbvert=P(100), **tr)
        lay.text(F(148), P(ty + 8), P(36), "lcd10", "$V%", CYAN2, align="left", scrolling="none", sample="78%",
                 focus=False, **tr)
        panel_toggles(lay, "ft_pl", "ft_eq", F(108), F(56), P(ty))

    def flip_button(lay, mode, d, x, y):
        other = "up" if d == "dn" else "dn"
        lay.button("b_flip_" + other, x, y, "main.setLayout(%s-%s)" % (mode, other),
                   "Open playlist / EQ %s the player" % ("above" if other == "up" else "below"), **tr)

    # ================= equalizer section (y offset is applied by the layout)
    def add_eq(lay, mode, d, sfx):
        base_vis = lay.vis
        for rt, rb, v in eq_corners(d):
            c = Canvas(W, EH)
            panel_bg(c, 0, 0, W, EH, 6, rt=rt, rb=rb)
            grip_dots(c, 4, 12, 2)
            resize_handle(c, grip_x(W), grip_y(33, 122), GRIP_H)     # centred on the band box (y 33..155)
            bg = c.done(hard_edges=True)
            lay.vis = vis_and(base_vis, v)
            hslice(skin, lay, "eq_bg", bg, 0, 0, 10, 10, tag=cap_tag(rt, rb))
        lay.vis = base_vis
        grip_tab(skin, lay, bg, grip_x(W), grip_y(33, 122), GRIP_H)
        label_on(skin, "lbl_eq", bg, 18, 9, 110, 14, "EQUALIZER", 10)
        lay.image("lbl_eq", P(18), P(9), action="move")
        flip_button(lay, mode, d, PW - P(86), P(6))
        lay.checkbox("t_eqon", PW - P(56), P(6), "equalizer.isEnabled", "equalizer.enable()",
                     "equalizer.disable()", "Equalizer is off", "Equalizer is on", **tr)
        c = Canvas(W - 24, 122)
        lcd(c, 0, 0, W - 24, 122, 4, outline=False)
        hslice(skin, lay, "eq_lcd", solid(c.done()), P(12), P(33), 8, 8)
        # band block: fixed width, kept centred when the window is resized
        names = ["PRE", "60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"]
        cxs = [36 + i * 38 + (12 if i else 0) for i in range(11)]
        c = Canvas(EQ_BW, 120)
        c.rrect(0, 0, EQ_BW, 120, 0, LCD_BG)  # opaque, same as the LCD interior, keeps small text crisp
        for lbl, yy in (("+20", 24), ("0", 60), ("-20", 96)):
            c.text(18, yy, lbl, 8, CYAN2, font="mono", anchor="rm")
        for i, cx in enumerate(cxs):
            c.text(cx, 111, names[i], 9, AMBER if i == 0 else CYAN2, font="mono", anchor="mm")
        c.rrect((cxs[0] + cxs[1]) / 2, 8, 1, 100, 0, DIVIDER)
        bands = c.done()
        for i, cx in enumerate(cxs):     # the 0 dB ticks of every fader (not part of the frame sheets)
            lb, fb, tb = eq_boxes(i == 0)
            bands.paste(EQ_TICKS[i == 0], (P(cx - EQ_FW // 2) + tb[0], P(4) + tb[1]))
        skin.add("eq_bands", bands)
        fbx = eq_boxes(False)[1]      # click-zone sheet: fully transparent (not drawn, but it takes clicks), fader column wide
        skin.add("eqclick", Image.new("RGBA", (P(EQ_FW), fbx[3] - fbx[1]), (0, 0, 0, 0)))
        lay.panel_begin("eq_panel" + sfx, P((W - EQ_BW) // 2), P(34), P(EQ_BW), P(120))
        lay.image("eq_bands", 0, 0)
        tips = ["Preamp"] + [n.replace("K", " kHz") if "K" in n else n + " Hz" for n in names[1:]]
        for i, cx in enumerate(cxs):
            value = "equalizer.preamp" if i == 0 else "equalizer.band(%d)" % (i - 1)
            lb, fb, tb = eq_boxes(i == 0)    # the sheets are crops of the 30 x 104 design: offsets lb / fb
            x0 = P(cx - EQ_FW // 2)
            pre = "_pre" if i == 0 else ""
            # click zone: an invisible slider as wide as the fader column, under the others (skins2 hit-tests the
            # topmost control first, so the knob and groove keep working; a click beside the groove lands here)
            lay.slider("s_eqc%d%s" % (i, sfx), x0, P(4) + fb[1],
                       "(%d,%d),(%d,%d)" % (P(15), eq_travel()[1] - fb[1], P(15), eq_travel()[0] - fb[1]), "thumb_none", value, tips[i],
                       bg="eqclick", nbvert=1, thickness=P(8))
            # dB label: its own slider on the same value (no knob), above the groove
            lay.slider("s_eql%d%s" % (i, sfx), x0 + lb[0], P(4),
                       "(%d,%d),(%d,%d)" % (P(15) - lb[0], P(10), P(15) - lb[0], P(2)), "thumb_none", value, tips[i],
                       bg="eqlbl" + pre, nbvert=EQ_FRAMES, thickness=P(8))
            lay.slider("s_eq%d%s" % (i, sfx), x0 + fb[0], P(4) + fb[1],
                       "(%d,%d),(%d,%d)" % (P(15) - fb[0], eq_travel()[1] - fb[1], P(15) - fb[0], eq_travel()[0] - fb[1]), "thumb_eq", value, tips[i],
                       bg="eqfill" + pre, nbvert=len(range(0, EQ_FRAMES, EQ_FILL_STEP)), thickness=P(8))
        lay.panel_end()

    # ================= playlist section (fixed height: the window height is shared by all layouts)
    def add_pl(lay, mode, d, sfx):
        c = Canvas(W, LH)
        rt, rb = (False, True) if d == "dn" else (True, False)     # always the last section of the stack
        panel_bg(c, 0, 0, W, LH, 6, flat=True, rt=rt, rb=rb)
        grip_dots(c, 4, 12, 2)
        resize_handle(c, grip_x(W), grip_y(33, 204), GRIP_H)     # centred on the list box (y 33..237)
        bg = c.done(hard_edges=True)
        nslice(skin, lay, "pl_bg", bg, 0, 0, 12, tag=cap_tag(rt, rb))
        grip_tab(skin, lay, bg, grip_x(W), grip_y(33, 204), GRIP_H)
        label_on(skin, "lbl_pl", bg, 18, 9, 110, 14, "PLAYLIST", 10)
        lay.image("lbl_pl", P(18), P(9), action="move")
        flip_button(lay, mode, d, PW - P(36), P(6))
        c = Canvas(W - 24, 204)
        lcd(c, 0, 0, W - 24, 204, 4, outline=False)
        c.rrect(W - 24 - PL_GUTTER - 8, 5, 8, 194, 3, SCROLL_TRACK)  # scroll track: PL_GUTTER from the box's right edge, like the row stripes on the left
        nslice(skin, lay, "pl_lcd", solid(c.done()), P(12), P(33), 18, actions={k: "none" for k in
               ("tl", "tm", "tr", "ml", "mm", "mr", "bl", "bm", "br")})
        lay.playtree(P(18), P(38), P(W - 60), P(194), "lcd12",
                     dict(x=PW - P(12 + PL_GUTTER + 8), y=P(38), points="(%d,%d),(%d,%d)" % (P(4), P(182), P(4), P(12)),
                          thumb="thumb_pl"), pid="playtree" + sfx, sid="pl_scroll" + sfx)
        for i, (lbl, act, tip) in enumerate((("add", "playlist.add()", "Add files"),
                                             ("rem", "playlist.del()", "Remove selected"),
                                             ("sort", "playlist.sort()", "Sort by name"),
                                             ("load", "playlist.load()", "Load playlist"),
                                             ("save", "playlist.save()", "Save playlist"))):
            lay.button("b_pl_" + lbl, P(12 + i * 48), P(247), act, tip)
        for i, (lbl, state, name, tip) in enumerate((("shuf", "playlist.isRandom", "Random", "Shuffle"),
                                                     ("loop", "playlist.isLoop", "Loop", "Loop playlist"),
                                                     ("rep1", "playlist.isRepeat", "Repeat", "Repeat one"))):
            lay.checkbox("t_pl_" + lbl, PW - P(176 - i * 56), P(247), state, "playlist.set%s(true)" % name,
                         "playlist.set%s(false)" % name, tip + ": off", tip + ": on", **tr)

    # ================= main window
    # "dn": bar at the top of the window, EQ then playlist below it (title-bar use).
    # "up": bar at the bottom, EQ then playlist above it (taskbar use).
    # The playlist sits next to the bar when the EQ is closed, otherwise beyond the EQ,
    # so it is placed twice with complementary visibility.
    # Every theme adds its own copy of all controls, visible only while its flag window
    # (th0, th1, ...) is shown; the layouts themselves are shared, so the width stays shared.
    layouts = [Layout(skin, "%s-%s" % (mode, d), PW, P(HT), minw=P(M["min_w"]), maxw=P(4000))
               for mode in ("full", "strip") for d in ("up", "dn")]   # last = default: strip-dn
    # Video window: skins2 draws video only inside a Video control. The window is "shown" all the
    # time, but every control in it needs vlc.hasVout, so with no video it has no pixels and no
    # window shape (invisible, like the flag windows). It grows to the video (autoresize).
    # Title bar (name of what plays, maximize / full screen / shrink / close), the video, then a
    # control panel docked under it. As wide as the player, so the seek bar bitmap (sw) fits as in
    # the full player; the 12 px frame is the margin rule and holds the corner resize tab.
    VB, VT, PH = 12, 36, 68                                # frame, title bar, control panel (logical px)
    VW = W
    VIDH = (VW - 2 * VB) * 9 // 16                         # starts 16:9
    PBASE = VT + VIDH                                      # top of the control panel
    VH = PBASE + PH
    VMIN = 580                                             # the panel's controls need this width
    vlay = Layout(skin, "video-l", P(VW), P(VH), minw=P(VMIN), maxw=P(3840),
                  minh=P(VT + PH + 90), maxh=P(2160))
    # The same window with an extra row of controls below the panel (the arrow button switches):
    # the same original size, so skins2 carries the current (maximized) size between the two; the
    # row takes its height from the video, as a Video control cannot change size inside a layout.
    RH = 30
    xlay = Layout(skin, "video-x", P(VW), P(VH), minw=P(VMIN), maxw=P(3840),
                  minh=P(VT + PH + RH + 90), maxh=P(2160))
    MW = 160                                               # shrunk: the title bar alone
    mlay = Layout(skin, "video-min", P(MW), P(VT))
    # Full screen: skins2 shows the window "fullscreenController" over the video when the mouse
    # moves, and fades it out (VLC's own fullscreen controller option, on by default). The extra
    # row is shown by the flag window fxflag below the controls; the layout always has its height
    # (skins2 places the window once, at the bottom; a taller layout would grow off the screen),
    # and without the row that part has no pixels, so it is transparent and click-through.
    FSH = 70
    flay = Layout(skin, "fsc-l", P(W), P(FSH + RH))

    def extra_row(lay, y, lt, rb):
        """The extra controls: A-B loop, chapters, snapshot, shuffle / loop / repeat, slower / speed / faster.
        A-B: a skin button can run only skins2's own actions, so it toggles the flag window abflag
        (2 x 1 px, the only flag of that size) and the Windows helper, which sees the window change,
        sends VLC's A-B hotkey action through the web interface (lua/intf/vlcamp.lua does the loop)."""
        k = dict(lt=lt, rb=rb)
        tip = "A-B loop: 1st click sets A, 2nd sets B, 3rd clears (Windows, with the helper)"
        lay.checkbox("xt_ab", P(12), y, "abflag.isVisible", "abflag.show()", "abflag.hide()", tip, tip, **k)
        lay.button("xb_chprev", P(60), y, "dvd.previousChapter()", "Previous chapter", **k)
        lay.button("xb_chnext", P(108), y, "dvd.nextChapter()", "Next chapter", **k)
        lay.button("xb_snap", P(156), y, "vlc.snapshot()", "Snapshot (saved to your Pictures folder)", **k)
        for i, (lbl, name, state, tp) in enumerate((("shuf", "Random", "playlist.isRandom", "Shuffle"),
                                                    ("loop", "Loop", "playlist.isLoop", "Loop playlist"),
                                                    ("rep1", "Repeat", "playlist.isRepeat", "Repeat one"))):
            lay.checkbox("t_pl_" + lbl, P(214 + i * 56), y, state, "playlist.set%s(true)" % name,
                         "playlist.set%s(false)" % name, tp + ": off", tp + ": on", **k)
        lay.button("xb_slower", P(390), y, "vlc.slower()", "Slower", **k)
        lay.image("x_speed_bg", P(424), y, action="none", **k)
        lay.text(P(426), y + P(4), P(56), "lcd12", "$Rx", CYAN_TXT, align="center", scrolling="none",
                 sample="1.25x", focus=False, **k)
        lay.button("xb_faster", P(488), y, "vlc.faster()", "Faster", **k)

    def video_layout(lay, extra):
        pb = PBASE - (RH if extra else 0)                 # top of the control panel (the row is below it)
        c = Canvas(VW, VH)
        # free-standing window: 1 px EDGE outline on all four sides
        c.rrect(0, 0, VW, VH, 6, EDGE)
        c.rrect(1, 1, VW - 2, VH - 2, 5, mix(BG_TOP, BG_BOT, 0.5))
        grip_dots(c, 4, 12)                               # title bar grip, left
        resize_handle(c, grip_x(VW), VH - 13, 12)         # resize grip: the tab in the bottom-right corner slice
        nslice(skin, lay, "video_bg", c.done(hard_edges=True), 0, 0, VB + 2,
               actions={"mr": "resizeE", "bm": "resizeS", "br": "resizeSE"})
        rt = dict(lt="righttop", rb="righttop")
        # the name of what plays, across the title bar (clicks go through to the bar: it moves the window)
        lay.text(P(24), P(11), P(VW - 24 - 132), "lcd12", "$N", CYAN_TXT, rb="righttop", scrolling="none",
                 sample="Video title", focus=False)
        lay.checkbox("vb_max", P(VW - 120), P(7), "video.isMaximized", "video.maximize()", "video.unmaximize()",
                     "Fill the screen (title bar and control panel stay)", "Back to the window size", **rt)
        lay.button("vb_full", P(VW - 92), P(7), "vlc.fullscreen()", "Full screen (no frame, control panel on mouse move)", **rt)
        lay.button("vb_min", P(VW - 64), P(7), "video.setLayout(video-min)", "Shrink to the title bar", **rt)
        lay.button("vb_close", P(VW - 36), P(7), "vlc.stop()", "Close the video (stops playback)", **rt)
        # docked control panel under the video: seek bar (12 px below the video, so the knob keeps a
        # margin), transport, time, volume (kept at the bottom and stretched with the window)
        bl = dict(lt="leftbottom", rb="leftbottom")
        rbk = dict(lt="rightbottom", rb="rightbottom")
        lay.slider("s_seek_vid" + ("_x" if extra else ""), P(12), P(pb + 12), "(0,%d),(%d,%d)" % (P(5), P(sw) - 1, P(5)),
                   "thumb_s", "time", "$T / $D", bg="seek", nbvert=SEEK_FRAMES, lt="leftbottom", rb="rightbottom")
        ty = pb + 30
        lay.button("fb_prev", P(12), P(ty), "playlist.previous()", "Previous", **bl)
        if extra:                                         # slower / faster are in the row, around the speed
            lay.checkbox("ft_play", P(46), P(ty), "vlc.isPlaying", "vlc.play()", "vlc.pause()", "Play", "Pause", **bl)
            lay.button("fb_next", P(90), P(ty), "playlist.next()", "Next", **bl)
            tx = 132
        else:
            lay.button("fb_slower", P(46), P(ty), "vlc.slower()", "Slower", **bl)
            lay.checkbox("ft_play", P(80), P(ty), "vlc.isPlaying", "vlc.play()", "vlc.pause()", "Play", "Pause", **bl)
            lay.button("fb_faster", P(124), P(ty), "vlc.faster()", "Faster", **bl)
            lay.button("fb_next", P(158), P(ty), "playlist.next()", "Next", **bl)
            tx = 200
        lay.text(P(tx), P(ty + 5), P(150), "lcd14", "$T / $D", CYAN_TXT, scrolling="none",
                 sample="1:02 / 4:12", focus=False, **bl)
        if extra:
            lay.button("fb_less", P(VW - 222), P(ty), "video.setLayout(video-l)", "Fewer controls", **rbk)
        else:
            lay.button("fb_more", P(VW - 222), P(ty), "video.setLayout(video-x)",
                       "More controls (A-B loop, chapters, snapshot, shuffle / loop / repeat, speed)", **rbk)
        lay.checkbox("ft_mute", P(VW - 188), P(ty), "vlc.isMute", "vlc.mute()", "vlc.mute()", "Mute", "Unmute", **rbk)
        lay.slider("s_vol_vid" + ("_x" if extra else ""), P(VW - 152), P(ty + 9),
                   "(%d,%d),(%d,%d)" % (V_LO, P(5), V_HI, P(5)), "thumb_v", "volume", "Volume $V%",
                   bg="vol100", nbvert=P(100), **rbk)
        lay.text(P(VW - 48), P(ty + 8), P(36), "lcd10", "$V%", CYAN2, align="left", scrolling="none",
                 sample="78%", focus=False, **rbk)
        if extra:
            extra_row(lay, P(pb + PH - 6), "leftbottom", "leftbottom")
        lay.video(P(VB), P(VT), P(VW - 2 * VB), P(VIDH - (RH if extra else 0)))

    cur = {}
    for ti, (tmode, tname, _) in enumerate(THEMES):
        apply_theme(ti)
        skin.prefix = "t%d_" % ti
        cur.update(theme=ti)
        make_bitmaps()
        for lay in layouts:
            mode, d = lay.id.split("-")
            # theme 0 is also the fallback: a saved state with no theme flag shown must not
            # leave the window empty (nothing drawn = no shape = invisible, cannot be moved)
            lay.theme_vis = ("th%d.isVisible" % ti if ti else
                             " and ".join("not th%d.isVisible" % j for j in range(1, len(THEMES))))
            sfx = "_%s_%s" % (mode, d)
            bh = BH if mode == "strip" else FH
            top = 0 if d == "dn" else HT - bh                     # bar position
            if d == "dn":
                eq_y, pl_near, pl_far = top + bh, top + bh, top + bh + EH
            else:
                eq_y, pl_near, pl_far = top - EH, top - LH, top - EH - LH
            lay.oy = P(top)
            (add_strip if mode == "strip" else add_full)(lay, d)
            lay.oy, lay.vis = P(eq_y), EQ_ON
            add_eq(lay, mode, d, sfx)
            lay.oy, lay.vis = P(pl_near), PL_ON + " and not " + EQ_ON
            add_pl(lay, mode, d, sfx + "_n")
            lay.oy, lay.vis = P(pl_far), PL_ON + " and " + EQ_ON
            add_pl(lay, mode, d, sfx + "_f")
            lay.oy, lay.vis, lay.theme_vis = 0, None, None
        vlay.theme_vis = ("th%d.isVisible" % ti if ti else
                          " and ".join("not th%d.isVisible" % j for j in range(1, len(THEMES))))
        vlay.vis = "vlc.hasVout"
        for lay in (xlay, mlay, flay):
            lay.theme_vis = vlay.theme_vis
        xlay.vis = mlay.vis = vlay.vis
        video_layout(vlay, False)
        video_layout(xlay, True)
        c = Canvas(MW, VT)
        c.rrect(0, 0, MW, VT, 6, EDGE)
        c.rrect(1, 1, MW - 2, VT - 2, 5, mix(BG_TOP, BG_BOT, 0.5))
        grip_dots(c, 4, 12)
        skin.add("video_min_bg", c.done(hard_edges=True))
        mlay.image("video_min_bg", 0, 0, action="move")
        mlay.button("vb_restore", P(MW - 64), P(7), "video.setLayout(video-l)", "Show the video")
        mlay.button("vb_close", P(MW - 36), P(7), "vlc.stop()", "Close the video (stops playback)")
        # fullscreen controller: seek bar, transport, time, more, volume, leave full screen; the row below
        c = Canvas(W, FSH)
        panel_bg(c, 0, 0, W, FSH, 6)
        hslice(skin, flay, "fsc_bg", c.done(hard_edges=True), 0, 0, 14, 14, action="none")
        flay.slider("s_seek_fsc", P(12), P(12), "(0,%d),(%d,%d)" % (P(5), P(sw) - 1, P(5)), "thumb_s",
                    "time", "$T / $D", bg="seek", nbvert=SEEK_FRAMES)
        flay.button("fb_prev", P(12), P(32), "playlist.previous()", "Previous")
        flay.checkbox("ft_play", P(46), P(32), "vlc.isPlaying", "vlc.play()", "vlc.pause()", "Play", "Pause")
        flay.button("fb_next", P(90), P(32), "playlist.next()", "Next")
        flay.text(P(132), P(37), P(170), "lcd14", "$T / $D", CYAN_TXT, scrolling="none", sample="1:02 / 4:12",
                  focus=False)
        flay.checkbox("ft_more", P(W - 222), P(32), "fxflag.isVisible", "fxflag.show()", "fxflag.hide()",
                      "More controls", "Fewer controls")
        flay.image("ic_speaker", P(W - 186), P(40), action="none")
        flay.slider("s_vol_fsc", P(W - 168), P(41), "(%d,%d),(%d,%d)" % (V_LO, P(5), V_HI, P(5)), "thumb_v",
                    "volume", "Volume $V%", bg="vol100", nbvert=P(100))
        flay.button("fb_fs", P(W - 42), P(32), "vlc.fullscreen()", "Leave full screen")
        c = Canvas(W, RH - 2)                              # the extra row: its own panel below the controls
        panel_bg(c, 0, 0, W, RH - 2, 6)
        flay.vis, flay.oy = "fxflag.isVisible", P(FSH + 2)
        hslice(skin, flay, "fsc_xbg", c.done(hard_edges=True), 0, 0, 14, 14, action="none")
        extra_row(flay, P(3), "lefttop", "lefttop")
        flay.vis, flay.oy = None, 0
        for lay in (vlay, xlay, mlay, flay):
            lay.vis, lay.theme_vis = None, None
    apply_theme(0)
    skin.prefix = ""

    skin.add("flag_px", Image.new("RGBA", (1, 1), (0, 0, 0, 0)))
    flags = []
    for fid in ["eqflag", "plflag", "tflag", "fxflag", "abflag"] + ["th%d" % i for i in range(len(THEMES))]:
        fl = Layout(skin, fid + "-l", 2 if fid == "abflag" else 1, 1)   # abflag: the helper finds it by its size
        fl.image("flag_px", 0, 0)
        flags.append(dict(id=fid, visible="true" if fid == "th0" else "false", position="Center",
                          yoffset=0, layouts=[fl], dragdrop=False))
    skin.windows = [dict(id="main", visible="true", position="Center", yoffset=0, layouts=layouts),
                    dict(id="video", visible="true", position="Center", yoffset=0, layouts=[mlay, xlay, vlay],      # last = default
                         dragdrop=False),
                    dict(id="fullscreenController", visible="false", position="South", yoffset=0,
                         layouts=[flay], dragdrop=False)] + flags


# ---------------------------------------------------------------- XML
def q(v):
    return quoteattr(str(v))


_ids = [0]


def next_id(kind):
    """Explicit id for every control. VLC 3.0's generated ids ("_ReservedId_N") keep only
    3 digits (SkinParser::generateId), so with more than 999 unnamed controls they repeat,
    and a repeated id frees the earlier control: VLC crashes when it draws the layout."""
    _ids[0] += 1
    return "%s%d" % (kind[0].lower(), _ids[0])


def node_xml(n, ind):
    sp = "  " * ind
    if n.kind in ("Image", "Button", "Checkbox", "Text", "Video"):
        n.xid = next_id(n.kind)
    common = 'x=%s y=%s lefttop=%s rightbottom=%s' % (q(n.x), q(n.y), q(getattr(n, "lt", "lefttop")),
                                                      q(getattr(n, "rb", "lefttop")))
    if getattr(n, "vis", None):
        common += ' visible=%s' % q(n.vis)
    if n.kind == "Video":
        return [sp + '<Video id=%s %s width=%s height=%s autoresize="true"/>' % (q(n.xid), common, q(n.w), q(n.h))]
    if n.kind == "Image":
        return [sp + '<Image id=%s image=%s %s action=%s action2=%s resize="mosaic"/>' % (
            q(n.xid), q(n.bid), common, q(n.action), q(n.action2))]
    if n.kind == "Button":
        b = n.base
        return [sp + '<Button id=%s up=%s over=%s down=%s %s action=%s tooltiptext=%s/>' % (
            q(n.xid), q(b + "_up"), q(b + "_over"), q(b + "_down"), common, q(n.action), q(n.tip))]
    if n.kind == "Checkbox":
        b = n.base
        return [sp + ('<Checkbox id=%s state=%s up1=%s over1=%s down1=%s up2=%s over2=%s down2=%s %s '
                      'action1=%s action2=%s tooltiptext1=%s tooltiptext2=%s/>') % (
            q(n.xid), q(n.state), q(b + "_off_up"), q(b + "_off_over"), q(b + "_off_down"),
            q(b + "_on_up"), q(b + "_on_over"), q(b + "_on_down"), common,
            q(n.a1), q(n.a2), q(n.tip1), q(n.tip2))]
    if n.kind == "Text":
        return [sp + '<Text id=%s text=%s font=%s color=%s %s width=%s alignment=%s scrolling=%s%s/>' % (
            q(n.xid), q(n.text), q(n.font), q(n.color.upper()), common, q(n.w), q(n.align), q(n.scrolling),
            '' if n.focus else ' focus="false"')]
    if n.kind == "Slider":
        extra = ' thickness=%s' % q(n.thickness) if n.thickness else ""
        head = sp + '<Slider id=%s up=%s over=%s down=%s %s points=%s value=%s tooltiptext=%s%s' % (
            q(n.sid), q(n.thumb + "_up"), q(n.thumb + "_over"), q(n.thumb + "_over"), common,
            q(n.points), q(n.value), q(n.tip), extra)
        if n.bg:
            return [head + ">", sp + '  <SliderBackground id=%s image=%s nbvert=%s/>' % (
                        q(n.sid + "_bg"), q(n.bg), q(n.nbvert)),
                    sp + "</Slider>"]
        return [head + "/>"]
    if n.kind == "Anchor":
        return [sp + '<Anchor x=%s y=%s priority=%s points=%s range="12"/>' % (
            q(n.x), q(n.y), q(n.priority), q(n.points))]
    if n.kind == "Playtree":
        s = n.slider
        k = {c: q(v.upper()) for c, v in n.colors.items()}
        return [sp + ('<Playtree id=%s %s width=%s height=%s font=%s flat="true" '
                      'fgcolor=%s playcolor=%s selcolor=%s bgcolor1=%s bgcolor2=%s>') % (
                    q(n.pid), common, q(n.w), q(n.h), q(n.font), k["fg"], k["play"], k["sel"], k["bg1"], k["bg2"]),
                sp + ('  <Slider id=%s up=%s over=%s down=%s x=%s y=%s points=%s '
                      'lefttop="righttop" rightbottom="rightbottom"%s/>') % (
                    q(n.sid), q(s["thumb"] + "_up"), q(s["thumb"] + "_over"), q(s["thumb"] + "_over"),
                    q(s["x"]), q(s["y"]), q(s["points"]), ' visible=%s' % q(n.vis) if n.vis else ""),
                sp + "</Playtree>"]
    if n.kind == "Panel":
        out = [sp + ('<Panel id=%s x=%s y=%s width=%s height=%s lefttop="lefttop" rightbottom="lefttop" '
                     'xkeepratio="true">') % (q(n.pid), q(n.x), q(n.y), q(n.w), q(n.h))]
        for ch in n.children:
            out += node_xml(ch, ind + 1)
        return out + [sp + "</Panel>"]
    raise ValueError(n.kind)


def pack_atlases(skin):
    """Pack the small bitmaps into one atlas image per theme (shelf packing). VLC starts an
    image decoder per <Bitmap>, which made loading ~1400 separate PNGs take 10+ s;
    <SubBitmap> cuts the pieces out of the atlas instead. VLC keeps the atlas in memory
    next to the pieces, so large bitmaps (fill frame sheets, wide stretch pieces) stay
    separate files. Returns ([(atlas id, PIL image, [(bid, x, y)])], [separate bids])."""
    groups, singles = {}, []
    for bid, im in skin.bitmaps.items():
        # tall frame sheets stay separate too: in a shelf row they would make the whole atlas that high
        if im.width * im.height > 16384 or im.height > P(400):
            singles.append(bid)
            continue
        m = re.match(r"(t\d+)_", bid)
        groups.setdefault(m.group(1) if m else "common", []).append(bid)
    atlases = []
    for g, bids in sorted(groups.items()):
        bids.sort(key=lambda b: (-skin.bitmaps[b].height, b))
        aw = max(P(1024), max(skin.bitmaps[b].width for b in bids))
        x = y = row_h = 0
        places = []
        for b in bids:
            w, h = skin.bitmaps[b].size
            if x + w > aw:
                x, y, row_h = 0, y + row_h, 0
            places.append((b, x, y))
            x += w
            row_h = max(row_h, h)
        atlas = Image.new("RGBA", (aw, y + row_h), (0, 0, 0, 0))
        for b, bx, by in places:
            atlas.paste(skin.bitmaps[b], (bx, by))
        atlases.append(("atlas_" + g, atlas, places))
    return atlases, sorted(singles)


def theme_xml(skin, label, atlases, singles):
    L = ['<?xml version="1.0" encoding="utf-8" standalone="no"?>',
         '<!DOCTYPE Theme PUBLIC "-//VideoLAN//DTD VLC Skins V2.0//EN" "skin.dtd">',
         '<Theme version="2.0" magnet="0" alpha="255" movealpha="255">',
         '  <ThemeInfo name=%s author="Jiri" webpage=""/>' % q("VLC Amp " + label)]
    fonts = [("lcd10", 10), ("lcd11", 11), ("lcd12", 12), ("lcd14", 14), ("lcd26", 26), ("lcd30", 30)]
    if skin.strip_font[0] == "lcdbar":      # taller strip: its own, bigger font for title and time
        fonts.append(skin.strip_font)
    for fid, size in fonts:
        L.append('  <Font id=%s file=%s size=%s/>' % (q(fid), q(FONT_FILE[0]), q(P(size))))
    for aid, atlas, places in atlases:
        L.append('  <Bitmap id=%s file=%s alphacolor="#FF00FF">' % (q(aid), q("img/%s.png" % aid)))
        for bid, x, y in sorted(places):
            w, h = skin.bitmaps[bid].size
            L.append('    <SubBitmap id=%s x="%d" y="%d" width="%d" height="%d"/>' % (q(bid), x, y, w, h))
        L.append('  </Bitmap>')
    for bid in singles:
        L.append('  <Bitmap id=%s file=%s alphacolor="#FF00FF"/>' % (q(bid), q("img/%s.png" % bid)))
    for w in skin.windows:
        L.append('  <Window id=%s visible=%s position=%s yoffset=%s dragdrop=%s playondrop="true">' % (
            q(w["id"]), q(w["visible"]), q(w["position"]), q(w["yoffset"]),
            q("true" if w.get("dragdrop", True) else "false")))
        for lay in w["layouts"]:
            L.append('    <Layout id=%s width=%s height=%s minwidth=%s maxwidth=%s minheight=%s maxheight=%s>' % (
                q(lay.id), q(lay.w), q(lay.h), q(lay.minw), q(lay.maxw), q(lay.minh), q(lay.maxh)))
            for n in lay.nodes:
                L += node_xml(n, 3)
            L.append("    </Layout>")
        L.append("  </Window>")
    L.append("</Theme>")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- preview (emulates VLC anchoring)
def preview_layout(skin, lay, AW=None, AH=None, flags=(), theme=0):
    """Render a layout like VLC would; flags = ids of the flag windows that are shown.
    The result is cropped to the visible pixels."""
    AW, AH = AW or lay.w, AH or lay.h

    def shown(n):
        e = getattr(n, "vis", None)
        if not e:
            return True
        e = e.replace("vlc.hasVout", "True")    # preview shows the video window as if a video played
        on = set(flags) | {"th%d" % theme}
        return eval(re.sub(r"(\w+)\.isVisible", lambda m: str(m.group(1) in on), e))
    out = Image.new("RGBA", (AW, AH), (0, 0, 0, 0))
    font_px = {"lcd10": P(10), "lcd11": P(11), "lcd12": P(12), "lcd14": P(14), "lcd26": P(26), "lcd30": P(30),
               skin.strip_font[0]: P(skin.strip_font[1])}

    def pos(n, bw, bh, aw, ah, w, h):
        lt, rb = getattr(n, "lt", "lefttop"), getattr(n, "rb", "lefttop")
        l = n.x - bw + aw if lt.startswith("right") else n.x
        t = n.y - bh + ah if lt.endswith("bottom") else n.y
        r = n.x + w - bw + aw if rb.startswith("right") else n.x + w
        b = n.y + h - bh + ah if rb.endswith("bottom") else n.y + h
        return l, t, r, b

    def tile(im, w, h):
        t = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
        for yy in range(0, h, im.height):
            for xx in range(0, w, im.width):
                t.paste(im, (xx, yy))
        return t

    def draw(nodes, ox, oy, bw, bh, aw, ah):
        for n in nodes:
            if not shown(n):
                continue
            if n.kind == "Image":
                l, t, r, b = pos(n, bw, bh, aw, ah, n.w, n.h)
                out.alpha_composite(tile(skin.bitmaps[n.bid], r - l, b - t), (ox + l, oy + t))
            elif n.kind in ("Button", "Checkbox"):
                l, t, r, b = pos(n, bw, bh, aw, ah, n.w, n.h)
                if n.kind == "Button":
                    on = None
                elif n.state.endswith(".isVisible"):
                    on = n.state.split(".")[0] in flags
                else:
                    on = re.sub(r"^t\d+_", "", n.base) in ("t_play", "ft_play", "t_top", "t_top_s", "t_eqon",
                                                             "l_loop", "t_pl_loop")
                key = n.base + ("_up" if on is None else "_on_up" if on else "_off_up")
                out.alpha_composite(skin.bitmaps[key], (ox + l, oy + t))
            elif n.kind == "Slider":
                pts = [tuple(map(int, p.strip("()").split(","))) for p in n.points.split("),(")]
                cw = max(p[0] for p in pts) + 1
                ch = max(p[1] for p in pts) + 1
                l, t, r, b = pos(n, bw, bh, aw, ah, cw, ch)
                fx = (r - l) / cw
                v = 0.6
                if n.bg:
                    sheet = skin.bitmaps[n.bg]
                    fh = sheet.height // n.nbvert
                    fr = sheet.crop((0, fh * int(v * (n.nbvert - 1)), sheet.width, fh * int(v * (n.nbvert - 1)) + fh))
                    fr = fr.resize((max(1, int(sheet.width * fx)), fh))
                    out.alpha_composite(fr, (ox + l, oy + t))
                x = pts[0][0] + (pts[1][0] - pts[0][0]) * v
                y = pts[0][1] + (pts[1][1] - pts[0][1]) * v
                th = skin.bitmaps[n.thumb + "_up"]
                out.alpha_composite(th, (int(ox + l + x * fx - th.width / 2), int(oy + t + y - th.height / 2)))
            elif n.kind == "Text":
                l, t, r, b = pos(n, bw, bh, aw, ah, n.w, 0)
                f = _truetype(FONT_MONO, font_px[n.font])
                txt = Image.new("RGBA", (max(1, r - l), font_px[n.font] * 2), (0, 0, 0, 0))
                dd = ImageDraw.Draw(txt)
                tw = dd.textlength(n.sample, font=f)
                tx = (r - l - tw) / (2 if n.align == "center" else 1) if n.align != "left" and tw < r - l else 0
                dd.text((tx, 0), n.sample, font=f, fill=H(n.color), anchor="la")
                out.alpha_composite(txt, (ox + l, oy + t))
            elif n.kind == "Video":
                l, t, r, b = pos(n, bw, bh, aw, ah, n.w, n.h)
                dd = ImageDraw.Draw(out)
                dd.rectangle([ox + l, oy + t, ox + r - 1, oy + b - 1], fill=(0, 0, 0, 255))
                dd.text((ox + (l + r) // 2, oy + (t + b) // 2), "video placeholder", font=_truetype(FONT_MONO, P(10)),
                        fill=(110, 110, 110, 255), anchor="mm")
            elif n.kind == "Playtree":
                l, t, r, b = pos(n, bw, bh, aw, ah, n.w, n.h)
                f = _truetype(FONT_MONO, font_px[n.font])
                dd = ImageDraw.Draw(out)
                lh = int(font_px[n.font] * 1.35)
                songs = ["Harbour Lights", "Paper Satellites", "Slow Burn Across the River (Extended Mix)",
                         "Static Bloom", "Glass Elevator", "Northbound", "Low Tide Radio", "Afterimage",
                         "Late Train to Brno", "Copper Wire", "Quiet Hours", "Field Recording No. 3"]
                for i, s in enumerate(songs):
                    yy = oy + t + i * lh
                    if yy + lh > oy + b:
                        break
                    if i == 2:
                        dd.rectangle([ox + l, yy, ox + r - 1, yy + lh - 1], fill=H(n.colors["sel"]))
                    dd.text((ox + l + 2, yy + 1), s, font=f, fill=H(n.colors["play" if i == 2 else "fg"]))
                sl = n.slider
                th = skin.bitmaps[sl["thumb"] + "_up"]
                sx = sl["x"] - bw + aw
                out.alpha_composite(th, (ox + sx + P(4) - th.width // 2, oy + sl["y"] + P(11) - th.height // 2))
            elif n.kind == "Panel":
                if aw != bw:
                    ratio = n.x / (bw - n.w)
                    l = int(ratio * (aw - n.w))
                else:
                    l = n.x
                draw(n.children, ox + l, oy + n.y, n.w, n.h, n.w, n.h)

    draw(lay.nodes, 0, 0, lay.w, lay.h, AW, AH)
    return out.crop(out.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())


def preview(skin, path):
    lays = {l.id: l for w in skin.windows for l in w["layouts"]}
    sd, su, fd, fu = lays["strip-dn"], lays["strip-up"], lays["full-dn"], lays["full-up"]
    EQ, PL, T = ("eqflag",), ("plflag",), ("tflag",)
    shots = [
        ("strip (elapsed time)", preview_layout(skin, sd)),
        ("strip, countdown (click the time to switch)", preview_layout(skin, sd, flags=T)),
        ("strip, resized +200 px", preview_layout(skin, sd, sd.w + P(200))),
        ("strip, minimum width", preview_layout(skin, sd, sd.minw)),
        ("strip + EQ + playlist, opening below (arrow on the panel header flips)",
         preview_layout(skin, sd, flags=EQ + PL)),
        ("strip + playlist, opening above (taskbar)", preview_layout(skin, su, flags=PL)),
        ("expanded player", preview_layout(skin, fd)),
        ("expanded player + EQ, opening above, countdown", preview_layout(skin, fu, flags=EQ + T)),
    ] + [("theme %d: %s" % (i, n), preview_layout(skin, fd, theme=i)) for i, (m, n, _) in enumerate(THEMES)
         if i] + [("video window, theme %d: %s" % (i, n), preview_layout(skin, lays["video-l"], theme=i))
                  for i, (m, n, _) in enumerate(THEMES)] + [
        ("video window, resized +120 x +60", preview_layout(skin, lays["video-l"], lays["video-l"].w + P(120),
                                                              lays["video-l"].h + P(60)))]
    pad = P(24)
    lab = _truetype(FONT_BOLD, P(12))
    Wc = max(im.width for _, im in shots) + 2 * pad
    Hc = sum(im.height + P(26) for _, im in shots) + pad * (len(shots) + 1)
    canvas = Image.new("RGBA", (Wc, Hc), H("#e6e8eb"))
    d = ImageDraw.Draw(canvas)
    y = pad
    for name, im in shots:
        d.text((pad, y), name, font=lab, fill=H("#3d444c"))
        y += P(22)
        canvas.alpha_composite(im, (pad, y))
        y += im.height + pad + P(4)
    canvas.convert("RGB").save(path)


# ---------------------------------------------------------------- main
def main():
    global S
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--width", type=int, default=620)
    ap.add_argument("--bar-height", type=int, default=BAR_DEFAULT,
                    help="strip height in logical px (default %%(default)s; %d for the Windows 11 taskbar, "
                    "sensible 32-40): a taller strip is written as VLC-Amp-taskbar-NNN.vlt" % BAR_TASKBAR)
    ap.add_argument("--out", default=os.path.join(HERE, "dist"))
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--custom", default=CUSTOM_DEFAULT, help="accent of the Custom theme, #RRGGBB")
    ap.add_argument("--mode", choices=["dark", "light"],
                    help="build ONE single theme from --mode / --accent / --led / --font instead of the named themes")
    ap.add_argument("--pair", action="store_true",
                    help="with --mode / --accent / --led: build the design twice, --mode base first and the other base "
                    "second, accent / LED adjusted for contrast; the theme button in the full player toggles them "
                    "(about twice the VLC memory of one theme)")
    ap.add_argument("--accent", help="single theme: primary colour #RRGGBB (LCD text, progress, active buttons)")
    ap.add_argument("--led", help="single theme: secondary colour #RRGGBB (indicator LEDs); default: from the accent")
    ap.add_argument("--font", help="TTF / OTF used for every LCD text (shipped in the .vlt); default: DejaVu Sans Mono")
    ap.add_argument("--themes", default=",".join(DEFAULT_THEMES),
                    help="comma-separated theme names to build, or 'all' (default: %(default)s): " +
                    ", ".join(t[1] for t in THEME_SEEDS))
    a = ap.parse_args()
    single = a.mode or a.accent or a.led or a.pair
    for opt in ("accent", "led"):
        if getattr(a, opt) and not re.fullmatch(r"#[0-9A-Fa-f]{6}", getattr(a, opt)):
            ap.error("--%s must look like #ff8800" % opt)
    if a.font and not os.path.isfile(a.font):
        ap.error("--font: no such file: " + a.font)
    if single:
        (set_pair if a.pair else set_single_theme)(a.mode or "dark", a.accent or "#5fd3e8", a.led)
    elif a.themes.lower() == "all":
        set_themes()
    else:
        names = [n.strip().lower() for n in a.themes.split(",")]
        unknown = set(names) - {t[1].lower() for t in THEME_SEEDS}
        if unknown:
            ap.error("unknown theme(s): " + ", ".join(sorted(unknown)))
        set_themes(names)
    apply_theme(0)
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", a.custom):
        ap.error("--custom must look like #b48cff")
    S = a.scale
    global FONT_MONO
    font_file = "DejaVuSansMono.ttf"
    if a.font:
        FONT_MONO = a.font
        font_file = "lcd" + os.path.splitext(a.font)[1].lower()
        FONT_FILE[0] = "fonts/" + font_file
    if not BAR_DEFAULT <= a.bar_height <= 60:
        ap.error("--bar-height must be between %d and 60" % BAR_DEFAULT)
    min_w = bar_metrics(a.bar_height)["min_w"]
    if a.width < min_w:
        ap.error("--width must be at least %d (with --bar-height %d)" % (min_w, a.bar_height))

    pct = round(S * 100)
    label = "%d%%" % pct + ("" if a.bar_height == BAR_DEFAULT else " bar %d" % a.bar_height)
    name = skin_name(a.bar_height, pct)[len("VLC-Amp-"):]    # "150", "taskbar-150", "bar40-150"
    skin = Skin()
    build(skin, a.width, a.bar_height)
    # VLC unpacks the .vlt to disk: on Windows (case-insensitive) b_x.png and B_x.png would collide
    lower = {}
    for bid in skin.bitmaps:
        if bid.lower() in lower:
            raise SystemExit("error: bitmap ids differ only by case: %s / %s" % (bid, lower[bid.lower()]))
        lower[bid.lower()] = bid

    stage = os.path.join(a.out, "stage-" + name)
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(os.path.join(stage, "img"))
    os.makedirs(os.path.join(stage, "fonts"))
    # the Custom theme must be pure grey + red, or recolouring it would be wrong
    from PIL import ImageChops
    cpre = "t%d_" % CUSTOM if CUSTOM is not None else "-"
    for bid, im in skin.bitmaps.items():
        if bid.startswith(cpre):
            r, g, b, _ = im.split()
            if ImageChops.difference(g, b).getextrema()[1] > 1 or \
                    ImageChops.subtract(g, r).getextrema()[1] > 1:
                raise SystemExit("error: custom theme bitmap not grey + red: " + bid)
    atlases, singles = pack_atlases(skin)
    # img/ gets the Custom theme in its colour; custom-ref/ keeps the red originals (and the
    # unrecoloured theme.xml) for the colour picker tools (custom-colour/)
    if CUSTOM is not None:
        os.makedirs(os.path.join(stage, "custom-ref", "img"))
    for fid, im in [(aid, atlas) for aid, atlas, _ in atlases] + [(bid, skin.bitmaps[bid]) for bid in singles]:
        if fid.startswith(cpre) or fid == "atlas_" + cpre[:-1]:
            im.save(os.path.join(stage, "custom-ref", "img", fid + ".png"), optimize=True)
            im = recolour(im, a.custom)
        im.save(os.path.join(stage, "img", fid + ".png"), optimize=True)
    shutil.copy(FONT_MONO, os.path.join(stage, "fonts", font_file))
    lic = os.path.join(HERE, "fonts", "LICENSE-DejaVu.txt")
    if os.path.exists(lic) and not a.font:
        shutil.copy(lic, os.path.join(stage, "fonts"))
    xml = theme_xml(skin, label, atlases, singles)
    # every element needs its own id: VLC's generated ids repeat after 999 (see next_id)
    tags = re.findall(r"<(Window|Layout|Panel|Image|Button|Checkbox|Slider|SliderBackground|Text|Playtree)\b([^>]*)>", xml)
    ids = [re.search(r'\bid="([^"]*)"', attrs) for _, attrs in tags]
    if not all(ids):
        raise SystemExit("error: element without id: %r" % [t for t, i in zip(tags, ids) if not i][:3])
    dup = [k for k, v in Counter(i.group(1) for i in ids).items() if v > 1]
    if dup:
        raise SystemExit("error: duplicate ids: %r" % sorted(dup)[:5])
    if CUSTOM is not None:
        with open(os.path.join(stage, "custom-ref", "theme.xml"), "w", encoding="utf-8") as fh:
            fh.write(xml)
    if CUSTOM is not None:
        with open(os.path.join(stage, "custom-ref", "slot.txt"), "w", encoding="utf-8") as fh:
            fh.write("slot=%d\naccent=%s\n" % (CUSTOM, a.custom.lower()))
        xml = recolour_xml(xml, a.custom)
    with open(os.path.join(stage, "theme.xml"), "w", encoding="utf-8") as fh:
        fh.write(xml)

    vlt = os.path.join(a.out, "VLC-Amp-%s.vlt" % name)
    def clean(ti):      # reproducible .vlt: no mtime / owner / platform-dependent mode in the tar
        ti.mtime = 0
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = ""
        ti.mode = 0o644
        return ti
    with open(vlt, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz, \
            tarfile.open(fileobj=gz, mode="w") as tar:
        for root, dirs, files in os.walk(stage):
            dirs.sort()
            for fn in sorted(files):
                full_path = os.path.join(root, fn)
                tar.add(full_path, arcname=os.path.relpath(full_path, stage), filter=clean)
    print("wrote", vlt, "(%d bitmaps: %d in %d atlases, %d separate)" % (
        len(skin.bitmaps), len(skin.bitmaps) - len(singles), len(atlases), len(singles)))
    if a.preview:
        for bid in skin.bitmaps:                      # show the Custom theme in its colour
            if bid.startswith(cpre):
                skin.bitmaps[bid] = recolour(skin.bitmaps[bid], a.custom)

        def walk(nodes):
            for n in nodes:
                if CUSTOM is not None and (getattr(n, "vis", None) or "").startswith("th%d.isVisible" % CUSTOM):
                    if getattr(n, "color", None):
                        n.color = recolour_hex(n.color, a.custom)
                    if getattr(n, "colors", None):
                        n.colors = {k: recolour_hex(v, a.custom) for k, v in n.colors.items()}
                walk(getattr(n, "children", []))
        for w in skin.windows:
            for lay in w["layouts"]:
                walk(lay.nodes)
        pv = os.path.join(a.out, "preview-%s.png" % name)
        preview(skin, pv)
        print("wrote", pv)


if __name__ == "__main__":
    main()
