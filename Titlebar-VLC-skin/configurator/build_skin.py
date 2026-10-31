#!/usr/bin/env python3
"""
Titlebar - a VLC skin (skins2 format) whose main window collapses into a
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
                   Titlebar-taskbar-NNN.vlt (36 px) or Titlebar-bar<N>-NNN.vlt, which the
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
    BG_TOP="#2e3135", BG_BOT="#1b1c1e", OUTLINE="#08090a", HILITE="#4c5055", PL_FLAT="#26282b",
    BTN={"up": ("#3d4045", "#28292c"), "over": ("#484b50", "#303236"), "down": ("#1f2023", "#2c2e32")},
    BTN_BORDER="#0b0c0d", BTN_HILITE="#565a60", ICON_UP="#c8cbcf", ICON_OVER="#ffffff",
    LCD_EDGE="#3d4045", GRIP="#6c7075", LABEL="#9fa3a8",
    THUMB_UP=("#e5e7e9", "#8f9399"), THUMB_OVER=("#ffffff", "#a9adb2"), TRACK="#0c0d0e",
    PT_PLAY="#ffffff", HEAD_OVER="#ffffff", SHADOW=200, SHADOW2=120)
LIGHT = dict(
    BG_TOP="#f0f1f2", BG_BOT="#d6d9dc", OUTLINE="#83878b", HILITE="#ffffff", PL_FLAT="#e5e7e9",
    BTN={"up": ("#fbfcfc", "#e0e2e5"), "over": ("#ffffff", "#ebedee"), "down": ("#cdd0d3", "#dcdfe1")},
    BTN_BORDER="#8f9397", BTN_HILITE="#ffffff", ICON_UP="#3d4043", ICON_OVER="#000000",
    LCD_EDGE="#ffffff", GRIP="#8f9397", LABEL="#5e6266",
    THUMB_UP=("#ffffff", "#bdc1c5"), THUMB_OVER=("#ffffff", "#d8dbde"), TRACK="#bec2c6",
    PT_PLAY="#000000", HEAD_OVER="#000000", SHADOW=60, SHADOW2=30)


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
    (playlist selection / odd rows); AMBER / AMBER_OFF from the LED colour.
    Only mixes with neutral colours: the custom theme's recolouring relies on it."""
    k, w, g = "#000000", "#ffffff", "#808080"
    if mode == "dark":
        return dict(CYAN=A, CYAN_TXT=mix(A, w, 0.05), CYAN2=mix(A, k, 0.18), CYAN_DIM=mix(A, k, 0.52),
                    LCD_BG=mix(A, k, 0.93), TITLE_FILL=mix(A, k, 0.78), LCD_HI=mix(A, w, 0.85),
                    DIVIDER=mix(A, k, 0.78), EQ_TRACK=mix(A, "#141414", 0.88), SCROLL_TRACK=mix(A, k, 0.89),
                    PT_SEL=mix(A, k, 0.78), PT_BG2=mix(A, k, 0.9), AMBER=led, AMBER_OFF=mix(led, k, 0.7))
    return dict(CYAN=A, CYAN_TXT=mix(A, k, 0.25), CYAN2=mix(A, g, 0.3), CYAN_DIM=mix(A, w, 0.6),
                LCD_BG=mix(A, w, 0.9), TITLE_FILL=mix(A, w, 0.74), LCD_HI=mix(A, k, 0.6),
                DIVIDER=mix(A, w, 0.72), EQ_TRACK=mix(A, w, 0.78), SCROLL_TRACK=mix(A, w, 0.82),
                PT_SEL=mix(A, w, 0.74), PT_BG2=mix(A, w, 0.86), AMBER=led, AMBER_OFF=mix(led, w, 0.62))


# The custom theme is rendered with a pure red accent and a neutral grey base, so every
# pixel is grey + t * red; recolour() turns it into grey + t * any colour (exact, since the
# palette only mixes the accent with neutral colours). The .vlt keeps the red originals in
# custom-ref/ for the colour picker tools.
CUSTOM_REF = "#ff0000"
CUSTOM_DEFAULT = "#b48cff"

# (mode, name, base hue, base saturation, accent, LED); the button in the full player's
# title bar steps through them in this order. Index 0 = default.
THEME_SEEDS = [
    ("dark",  "Midnight", 210, 0.12, "#5fd3e8", "#f2a93b"),
    ("dark",  "Ember",     28, 0.12, "#ffb547", "#ff7b4a"),
    ("dark",  "Forest",   150, 0.09, "#78e0a0", "#e8d36a"),
    ("dark",  "Nord",     220, 0.17, "#88c0d0", "#ebcb8b"),
    ("dark",  "Dusk",     268, 0.15, "#ff79c6", "#f1fa8c"),
    ("dark",  "Carbon",     0, 0.00, "#ff5a4f", "#ffd166"),
    ("light", "Paper",    210, 0.12, "#1f7fc4", "#e8901a"),
    ("light", "Sand",      44, 0.45, "#1f9a92", "#d0561c"),
    ("light", "Sage",     120, 0.10, "#2e8b45", "#d08a1a"),
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


FLAT = True     # flat style (default): solid fills, no gradients / bevel lines / glow; --classic turns it off


def flatten(pal):
    """Flat style: every gradient pair collapses to its mean, button borders vanish into the fill."""
    mid = lambda p: mix(p[0], p[1], 0.5)
    pal["BG_TOP"] = pal["BG_BOT"] = mid((pal["BG_TOP"], pal["BG_BOT"]))
    pal["PL_FLAT"] = pal["BG_TOP"]
    pal["BTN"] = {k: (mid(v),) * 2 for k, v in pal["BTN"].items()}
    pal["THUMB_UP"] = (pal["THUMB_UP"][0],) * 2
    pal["THUMB_OVER"] = (pal["THUMB_OVER"][0],) * 2
    pal["BTN_BORDER"] = pal["BTN"]["up"][0]
    pal["HILITE"] = pal["BG_TOP"]
    pal["BTN_HILITE"] = pal["BTN"]["up"][0]
    pal["LCD_EDGE"] = pal["LCD_BG"]
    pal["SHADOW"] = pal["SHADOW2"] = 0
    return pal


def apply_theme(i):
    pal = dict(THEMES[i][2])
    if FLAT:
        pal = flatten(pal)
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

    def X(self, v):
        return v * self.kx

    def Y(self, v):
        return v * self.ky

    def _layer(self):
        layer = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        return layer, ImageDraw.Draw(layer)

    def _box(self, x, y, w, h):
        return [round(self.X(x)), round(self.Y(y)),
                round(self.X(x + w)) - 1, round(self.Y(y + h)) - 1]

    def rrect(self, x, y, w, h, r, color):
        layer, d = self._layer()
        b = self._box(x, y, w, h)
        if b[2] < b[0] or b[3] < b[1]:
            return
        if r > 0:
            d.rounded_rectangle(b, radius=r * self.kx, fill=H(color) if isinstance(color, str) else color)
        else:
            d.rectangle(b, fill=H(color) if isinstance(color, str) else color)
        self.im.alpha_composite(layer)

    def grad(self, x, y, w, h, r, top, bot):
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
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, gw - 1, gh - 1], radius=max(0, r * self.kx), fill=255)
        layer = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        layer.paste(g, (b[0], b[1]), mask)
        self.im.alpha_composite(layer)

    def poly(self, pts, color):
        layer, d = self._layer()
        d.polygon([(self.X(x), self.Y(y)) for x, y in pts], fill=H(color))
        self.im.alpha_composite(layer)

    def lines(self, pts, color, width):
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
        d.arc([self.X(cx - r), self.Y(cy - r), self.X(cx + r), self.Y(cy + r)],
              start, end, fill=H(color), width=max(1, round(width * self.kx)))
        self.im.alpha_composite(layer)

    def circle(self, cx, cy, r, color):
        layer, d = self._layer()
        d.ellipse([self.X(cx - r), self.Y(cy - r), self.X(cx + r), self.Y(cy + r)],
                  fill=H(color) if isinstance(color, str) else color)
        self.im.alpha_composite(layer)

    def text(self, x, y, s, size, color, font="bold", anchor="la"):
        self.texts.append((x, y, s, size, color, font, anchor))

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
    """Flat style: give a bitmap that sits on a plain panel colour no partly transparent pixels.
    skins2 premultiplies every bitmap when it loads it, draws buttons, thumbs and similar into
    a blank graphic without blending (the corner pixels come out darker than the panel) and
    copies that over the window. Windows (Win32Graphics::drawBitmap) alpha-blends it onto a
    blank bitmap whose start content nobody guarantees. Compositing the bitmap over the colour
    it will sit on (BG_TOP: every flat panel has it) gives the same pixels everywhere and keeps
    the smooth corners. Classic style has gradient panels, so it is left alone."""
    if not FLAT:
        return im
    return Image.alpha_composite(Image.new("RGBA", im.size, H(bg or BG_TOP)), im.convert("RGBA"))


def resize_handle(c, x, y, h):
    """Grip for the right edge (the resizeE zone): a 9 px wide tab in the button colour with three
    light ribs, so it reads as something to grab. x = its left edge in logical px (W - 10)."""
    pad = BTN["up"][0]
    c.rrect(x, y, 9, h, 2, pad)
    for rx in (x + 2, x + 4, x + 6):
        c.rrect(rx, y + 3, 1, h - 6, 0, mix(pad, ICON["up"], 0.6))


# ---------------------------------------------------------------- primitives
def panel_bg(c, x, y, w, h, r, flat=False):
    c.rrect(x, y, w, h, r, OUTLINE)
    if FLAT:
        r = min(r, 2)
    if flat:
        c.rrect(x + 1, y + 1, w - 2, h - 2, max(0, r - 1), PL_FLAT)
    else:
        c.grad(x + 1, y + 1, w - 2, h - 2, max(0, r - 1), BG_TOP, BG_BOT)
    c.rrect(x + r, y + 1, w - 2 * r, 1, 0, HILITE)


def lcd(c, x, y, w, h, r=2):
    c.rrect(x, y, w, h, r, LCD_EDGE)               # light bottom edge
    c.rrect(x, y, w, h - 1, r, LCD_BG)
    c.rrect(x + 1, y, w - 2, 1, 0, (0, 0, 0, SHADOW))  # inner top shadow
    c.rrect(x, y + 1, 1, h - 3, 0, (0, 0, 0, SHADOW2))
    c.rrect(x + w - 1, y + 1, 1, h - 3, 0, (0, 0, 0, SHADOW2))


def grip_dots(c, x, y, rows=3):
    for cx in (x + 2, x + 6):
        for i in range(rows):
            c.circle(cx, y + 3 + 4 * i, 1, GRIP)


def button_face(c, w, h, state):
    top, bot = BTN[state]
    c.rrect(0, 0, w, h, 3, BTN_BORDER)
    c.grad(1, 1, w - 2, h - 2, 2, top, bot)
    if state == "down":
        if not FLAT:
            c.rrect(2, 1, w - 4, 1, 0, (0, 0, 0, 150))
    elif not FLAT:
        c.rrect(2, 1, w - 4, 1, 0, BTN_HILITE)


def led(c, cx, cy, on):
    if on:
        if not FLAT:
            c.circle(cx, cy, 3.2, H(AMBER, 70))
        c.circle(cx, cy, 2, AMBER)
    else:
        c.circle(cx, cy, 2, AMBER_OFF)


def icon(c, name, ox, oy, size, color):
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
    elif name == "close":
        c.lines(T([(2.5, 2.5), (9.5, 9.5)]), color, 1.6 * f)
        c.lines(T([(9.5, 2.5), (2.5, 9.5)]), color, 1.6 * f)
    elif name == "menu":
        for yy in (3, 6, 9):
            c.lines(T([(2.5, yy), (9.5, yy)]), color, 1.4 * f)
    elif name in ("arrow_up", "arrow_down"):  # flip: open panels above / below
        if name == "arrow_up":
            c.poly(T([(6, 2), (10.5, 8), (1.5, 8)]), color)
        else:
            c.poly(T([(1.5, 4), (10.5, 4), (6, 10)]), color)
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


def label_on(skin, bid, bg, x, y, w, h, text):
    """Label baked onto a crop of the window background so it is fully opaque."""
    im = bg.crop((P(x), P(y), P(x) + P(w), P(y) + P(h))).copy()
    d = ImageDraw.Draw(im)
    d.text((0, im.height / 2), text, font=_truetype(FONT_BOLD, P(8)), fill=H(LABEL), anchor="lm")
    skin.add(bid, im)
    return bid


def hslice(skin, lay, name, im, x, y, capl, capr, action="move", action2="none", right_action=None):
    """Cut a horizontally stretchable element into left cap / mosaic middle / right cap."""
    w, h = im.size
    l, r = P(capl), P(capr)
    skin.add(name + "_l", im.crop((0, 0, l, h)))
    skin.add(name + "_m", im.crop((l, 0, w - r, h)))
    skin.add(name + "_r", im.crop((w - r, 0, w, h)))
    lay.image(name + "_l", x, y, action=action, action2=action2)
    lay.image(name + "_m", x + l, y, rb="righttop", action=action, action2=action2)
    lay.image(name + "_r", x + w - r, y, lt="righttop", rb="righttop", action=right_action or action)


def nslice(skin, lay, name, im, x, y, cap, actions=None):
    """Nine-slice for elements stretching in both directions."""
    w, h = im.size
    c = P(cap)
    xs = [(0, c, "l"), (c, w - c, "m"), (w - c, w, "r")]
    ys = [(0, c, "t"), (c, h - c, "m"), (h - c, h, "b")]
    anchor_x = {"l": ("lefttop", "lefttop"), "m": ("lefttop", "righttop"), "r": ("righttop", "righttop")}
    actions = actions or {}
    for y0, y1, vy in ys:
        for x0, x1, vx in xs:
            bid = skin.add("%s_%s%s" % (name, vy, vx), im.crop((x0, y0, x1, y1)))
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
def make_button(skin, base, w, h, icon_name=None, icon_size=12, label=None, led_on=None):
    for st in ("up", "over", "down"):
        c = Canvas(w, h)
        button_face(c, w, h, st)
        if icon_name:
            icon(c, icon_name, (w - icon_size) / 2, (h - icon_size) / 2, icon_size, ICON[st])
        if label:
            c.text(w / 2, h / 2 + 0.5, label, 8, ICON[st], anchor="mm")
        skin.add("%s_%s" % (base, st), solid(c.done()))
    return base


def make_toggle(skin, base, w, h, icon_off=None, icon_on=None, label=None, use_led=False,
                on_color=None, icon_size=12, label_size=8):
    """Checkbox bitmaps: <base>_off_* (state false) and <base>_on_* (state true)."""
    for on in (False, True):
        for st in ("up", "over", "down"):
            c = Canvas(w, h)
            button_face(c, w, h, st)
            col = ICON[st]
            if on and on_color and st != "down":
                col = on_color
            name = icon_on if on else icon_off
            if name:
                icon(c, name, (w - icon_size) / 2, (h - icon_size) / 2, icon_size, col)
            if label:
                if use_led:
                    led(c, 6, h / 2, on)
                    c.text(w / 2 + 3, h / 2 + 0.5, label, label_size, ICON[st], anchor="mm")
                else:
                    c.text(w / 2, h / 2 + 0.5, label, label_size, col, anchor="mm")
            skin.add("%s_%s_%s" % (base, "on" if on else "off", st), solid(c.done()))
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
    """Left part of the strip's time box: "+" = elapsed time, "-" = time left; click switches."""
    for on in (False, True):
        for st in ("up", "over", "down"):
            c = Canvas(w, h)
            c.rrect(0, 0, w, h, 2, LCD_BG)
            c.rrect(w - 3, 0, 3, h, 0, LCD_BG)           # square right side
            c.rrect(w - 1, 2, 1, h - 4, 0, DIVIDER)
            col = CYAN_TXT if st == "over" else CYAN_DIM
            cx, cy = (w - 1) / 2, h / 2
            c.rrect(cx - 2.5, cy - 0.5, 5, 1, 0, col)
            if not on:
                c.rrect(cx - 0.5, cy - 2.5, 1, 5, 0, col)
            skin.add("%s_%s_%s" % (base, "on" if on else "off", st), solid(c.done()))
    return base


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
    for st, (t, b) in (("up", THUMB_UP), ("over", THUMB_OVER)):
        c = Canvas(w, h)
        c.rrect(0, 0, w, h, 2, BTN_BORDER)
        c.grad(1, 1, w - 2, h - 2, 1, t, b)
        skin.add("%s_%s" % (bid, st), solid(c.done(), bg))
    return bid


def make_eq_thumb(skin, bid, w, h):
    """EQ slider knob: a flat accent-coloured pill (on the LCD)."""
    for st, col in (("up", CYAN), ("over", LCD_HI)):
        c = Canvas(w, h)
        c.rrect(0, 0, w, h, h / 2, col)
        skin.add("%s_%s" % (bid, st), solid(c.done(), LCD_BG))
    return bid


def make_fill_frames(skin, bid, w, h, track_y, track_h, n):
    """Slider background: n frames stacked vertically, frame i filled to i/(n-1)."""
    sheet = Image.new("RGBA", (P(w), P(h) * n), (0, 0, 0, 0))
    for i in range(n):
        frac = i / (n - 1)
        c = Canvas(w, h)
        c.rrect(0, track_y, w, track_h, track_h / 2, TRACK)
        c.rrect(0, track_y, w, 1, 0, (0, 0, 0, 160))
        if frac > 0:
            c.rrect(0, track_y, max(track_h, w * frac), track_h, track_h / 2, CYAN)
        sheet.paste(c.done(), (0, P(h) * i))
    skin.add(bid, solid(sheet))
    return bid


# ---------------------------------------------------------------- windows
MIN_W = 420   # narrowest strip: EQ band block (400 px) plus a 10 px margin each side; title window 62 px
TIME_ZONE = 16   # width of the elapsed / countdown switch at the left of the strip's time box
BAR_DEFAULT = 24   # strip height (logical px) of the normal skin
BAR_TASKBAR = 36   # --bar-height of the taskbar build (Titlebar-taskbar-NNN.vlt); the helper assumes the same


def bar_metrics(bh):
    """Sizes of the strip's parts for a bar of bh logical px. At 24 these are the original
    values (the normal skin must not change). Widths do not grow with the height, except the
    time box, which has to fit "-1:23:45" in the bigger strip font; MIN_W grows with it."""
    fs = 12 + (bh - 24) // 6                       # strip font (title, time), px
    tw = TIME_ZONE + 12 + math.ceil(8 * 0.602 * fs)  # time box: mode zone + 4 px + text + 8 px margin; DejaVu Sans Mono advance = 0.602 em
    return dict(bh=bh, btn=bh - 6, icon=12 + (bh - 24) // 4, label=8 + (bh - 24) // 12, font=fs, tw=tw,
                min_w=MIN_W, grip_rows=3 + (bh - 24) // 8, grip_h=10 + (bh - 24) // 2)


def skin_name(bh, pct):
    """File stem of a build: Titlebar-150, Titlebar-taskbar-150 (36 px bar), Titlebar-bar40-150."""
    kind = "" if bh == BAR_DEFAULT else "taskbar-" if bh == BAR_TASKBAR else "bar%d-" % bh
    return "Titlebar-%s%d" % (kind, pct)
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
    FH, EH, LH = 122, 116, 198
    HT = FH + EH + LH                 # window height: full player + EQ + playlist (the same for every bar height)
    M = bar_metrics(BH)
    TW = M["tw"]                      # strip time box: fits "-1:23:45" (hours) in the strip font
    BT = M["btn"]                     # strip button height (3 px margin above and below)
    skin.strip_font = ("lcd12" if M["font"] == 12 else "lcdbar", M["font"])
    PW = P(W)
    tr = dict(lt="righttop", rb="righttop")
    sw = W - 20                       # seek bar width (full player; ends 12 px from the edge)

    def make_bitmaps():
        """All bitmaps of the current theme (skin.prefix namespaces them)."""
        isz, lsz = M["icon"], M["label"]
        make_button(skin, "b_expand", 22, BT, "expand", icon_size=isz)
        make_button(skin, "b_prev", 22, BT, "prev", icon_size=isz)
        make_toggle(skin, "t_play", 26, BT, icon_off="play", icon_on="pause", on_color=CYAN, icon_size=isz)
        make_button(skin, "b_next", 22, BT, "next", icon_size=isz)
        make_toggle(skin, "t_pl", 26, BT, label="PL", use_led=True, label_size=lsz)
        make_toggle(skin, "t_eq", 26, BT, label="EQ", use_led=True, label_size=lsz)
        make_toggle(skin, "t_top", 22, BT, icon_off="pin", icon_on="pin", on_color=AMBER, icon_size=isz)
        make_thumb(skin, "thumb_v", 7, 13)
        for st, col in (("up", mix(CYAN, TITLE_FILL, 0.2)), ("over", CYAN)):   # play head in the title window
            skin.add("thumb_title_" + st, Image.new("RGBA", (max(1, P(1)), P(BT - 6)), H(col)))
        for st in ("up", "over"):   # volume bar in the strip's time box: the fill is the indicator, no knob
            skin.add("thumb_none_" + st, Image.new("RGBA", (1, 1), (0, 0, 0, 0)))
        make_button(skin, "b_menu", 18, 12, "menu", icon_size=8)
        make_toggle(skin, "t_top_s", 18, 12, icon_off="pin", icon_on="pin", on_color=AMBER, icon_size=9)
        make_button(skin, "b_collapse", 18, 12, "collapse", icon_size=8)
        make_button(skin, "b_min", 18, 12, "minimize", icon_size=8)
        make_button(skin, "b_close", 18, 12, "close", icon_size=8)
        make_toggle(skin, "vb_max", 26, 18, icon_off="maximize", icon_on="unmaximize", icon_size=11)   # video window: fill the screen, keep the title bar
        make_button(skin, "vb_full", 26, 18, "expand", icon_size=11)      # video window: full screen
        make_button(skin, "vb_min", 26, 18, "minimize", icon_size=11)     # video window: shrink to its title bar
        make_button(skin, "vb_restore", 26, 18, "restore", icon_size=11)  # ... and back
        make_button(skin, "fb_fs", 28, 22, "expand")                      # fullscreen controller: leave full screen
        make_button(skin, "b_flip_up", 18, 12, "arrow_up", icon_size=8)
        make_button(skin, "b_flip_dn", 18, 12, "arrow_down", icon_size=8)
        make_button(skin, "fb_prev", 28, 22, "prev")
        make_button(skin, "fb_slower", 28, 22, "slower")
        make_toggle(skin, "ft_play", 34, 22, icon_off="play", icon_on="pause", on_color=CYAN)
        make_button(skin, "fb_faster", 28, 22, "faster")
        make_button(skin, "fb_next", 28, 22, "next")
        make_toggle(skin, "ft_pl", 30, 22, label="PL", use_led=True)
        make_toggle(skin, "ft_eq", 30, 22, label="EQ", use_led=True)
        make_thumb(skin, "thumb_s", 8, 12)
        make_toggle(skin, "t_eqon", 34, 12, label="ON", use_led=True)
        make_eq_thumb(skin, "thumb_eq", 12, 6)
        make_thumb(skin, "thumb_pl", 6, 22, SCROLL_TRACK)
        make_lcd_toggle(skin, "l_shuf", 30, 12, "SHUF")
        make_lcd_toggle(skin, "l_loop", 30, 12, "LOOP")
        make_lcd_toggle(skin, "l_rep", 30, 12, "REP1")
        make_fill_frames(skin, "vol90", 90, 8, 2, 4, P(90))
        make_fill_frames(skin, "seek", sw, 6, 1, 4, FILL_FRAMES)
        c = Canvas(12, 12)
        icon(c, "speaker", 0, 0, 12, LABEL)
        skin.add("ic_speaker", solid(c.done()))
        # time readout backgrounds, used as checkboxes (an Image only reacts to double-clicks)
        c = Canvas(TW, BT)
        lcd(c, 0, 0, TW, BT)
        skin.add("c_time_s", solid(c.done()))
        make_mode_toggle(skin, "c_mode", TIME_ZONE, BT)
        make_progress_frames(skin, "vol_fill", TW - TIME_ZONE - 1, BT - 2, FILL_FRAMES, TITLE_FILL)
        c = Canvas(142, 44)
        c.rrect(0, 0, 142, 44, 0, LCD_BG)
        plain_toggle(skin, "c_time_f", c.done())
        for lbl in ("add", "rem", "sort", "load", "save"):
            make_button(skin, "b_pl_" + lbl, 32, 14, label=lbl.upper())
        for lbl in ("shuf", "loop", "rep1"):
            make_toggle(skin, "t_pl_" + lbl, 38, 14, label=lbl.upper(), use_led=True)
        # theme button (full player title bar): a dot in the theme's accent colour
        for st in ("up", "over", "down"):
            c = Canvas(18, 12)
            button_face(c, 18, 12, st)
            c.circle(9, 6, 4.4, ICON[st])
            c.circle(9, 6, 3.3, BG_BOT)
            c.circle(9, 6, 2.5 if st != "down" else 2.0, CYAN)
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

    # ================= strip bar
    def add_strip(lay, d):
        c = Canvas(W, BH)
        panel_bg(c, 0, 0, W, BH, 4)
        rows = M["grip_rows"]
        grip_dots(c, 4, BH / 2 - 3 - 2 * (rows - 1), rows)
        resize_handle(c, W - 10, 3, BH - 6)   # same 10 px as the right cap; the pin ends 12 px from the edge
        hslice(skin, lay, "strip_bg", c.done(hard_edges=True), 0, 0, 14, 10, right_action="resizeE")
        lay.button("b_expand", P(16), P(3), "main.setLayout(full-%s)" % d, "Expand to full player")
        lay.button("b_prev", P(44), P(3), "playlist.previous()", "Previous")
        lay.checkbox("t_play", P(68), P(3), "vlc.isPlaying", "vlc.play()", "vlc.pause()", "Play", "Pause")
        lay.button("b_next", P(96), P(3), "playlist.next()", "Next")
        dx, dw = 124, W - (TW + 100) - 124   # slower / faster live in the full player only
        c = Canvas(dw, BT)
        lcd(c, 0, 0, dw, BT)
        hslice(skin, lay, "strip_lcd", solid(c.done()), P(dx), P(3), 4, 4)
        # the title window is also a seek bar: progress fills it from the left, a click jumps
        # there (and drags), the mouse wheel steps 5 %. The title text ignores the mouse.
        fw, fh = dw - 2, BT - 2
        make_progress_frames(skin, "title_fill", fw, fh, FILL_FRAMES, TITLE_FILL)
        lay.slider("s_title_" + lay.id, P(dx + 1), P(4), "(0,%d),(%d,%d)" % (P(fh) // 2, P(fw) - 1, P(fh) // 2),
                   "thumb_title", "time", "$T / $D  (click to jump, wheel = 5 %)", bg="title_fill", nbvert=FILL_FRAMES,
                   rb="righttop")
        ty = round(BH / 2 - 0.582 * M["font"])   # text top: the line (1.164 em) is centred in the bar
        lay.text(P(dx + 5), P(ty), P(dw - 10), skin.strip_font[0], "$N", CYAN_TXT, rb="righttop", focus=False,
                 sample="Nightline Orchestra - Slow Burn Across the River (Extended Mix)")
        R = lambda v: PW - P(v)
        tx = R(TW + 96)
        # time box: left = switch elapsed <-> time left (remembered by VLC), right = volume bar
        # filled from the left like the title's seek fill; click / drag / wheel sets the volume
        lay.image("c_time_s", tx, P(3), action="move", **tr)
        lay.checkbox("c_mode", tx, P(3), COUNTDOWN, "tflag.show()", "tflag.hide()",
                     "Elapsed time (click: time left)", "Time left (click: elapsed time)", **tr)
        vw, vfh = TW - TIME_ZONE - 1, BT - 2
        lay.slider("s_vol_" + lay.id, tx + P(TIME_ZONE), P(4), "(0,%d),(%d,%d)" % (P(vfh) // 2, P(vw) - 1, P(vfh) // 2),
                   "thumb_none", "volume", "Volume $V%  (click to set, wheel to change)", bg="vol_fill",
                   nbvert=FILL_FRAMES, **tr)
        for text, vis, sample in (("$t", "not " + COUNTDOWN, "1:02"), ("-$l", COUNTDOWN, "-3:10")):
            lay.text(tx + P(TIME_ZONE), P(ty), P(TW - TIME_ZONE), skin.strip_font[0], text, CYAN_TXT,
                     lt="righttop", rb="righttop", align="center", scrolling="none", sample=sample,
                     focus=False).vis = vis_and(lay.theme_vis, vis)
        panel_toggles(lay, "t_pl", "t_eq", R(90), R(62), P(3))
        lay.checkbox("t_top", R(34), P(3), "vlc.isOnTop", "vlc.onTop()", "vlc.onTop()",
                     "Always on top: off (click to pin)", "Always on top: on (click to unpin)", **tr)

    # ================= full player bar
    def add_full(lay, d):
        F = lambda v: PW - P(v)
        c = Canvas(W, FH)
        panel_bg(c, 0, 0, W, FH, 6)
        grip_dots(c, 4, 4)
        resize_handle(c, W - 10, 33, 56)   # right edge column (10 px): LCD, seek bar and the bottom row stay clear of it
        bg = c.done(hard_edges=True)
        hslice(skin, lay, "full_bg", bg, 0, 0, 14, 10, right_action="resizeE")
        # theme button, left of the menu button: steps to the next theme (none with one theme)
        nxt = (cur["theme"] + 1) % len(THEMES)
        if nxt != cur["theme"]:
            lay.button("b_theme", F(122), P(5), select_theme(nxt),
                       "Theme: %s (click: %s)" % (THEMES[cur["theme"]][1], THEMES[nxt][1]), **tr)
        lay.button("b_menu", F(102), P(5), "dialogs.popup()", "VLC menu (open files, skins, settings)", **tr)
        lay.checkbox("t_top_s", F(82), P(5), "vlc.isOnTop", "vlc.onTop()", "vlc.onTop()",
                     "Always on top: off (click to pin)", "Always on top: on (click to unpin)", **tr)
        lay.button("b_collapse", F(62), P(5), "main.setLayout(strip-%s)" % d, "Collapse to title-bar strip", **tr)
        lay.button("b_min", F(42), P(5), "vlc.minimize()", "Minimize", **tr)
        lay.button("b_close", F(22), P(5), "vlc.quit()", "Quit VLC", **tr)
        # LCD: left column = time (wide enough for -1:23:45), right column = title, info, toggles
        c = Canvas(W - 16, 54)
        lcd(c, 0, 0, W - 16, 54, 3)
        c.rrect(150, 4, 1, 46, 0, DIVIDER)         # divider (inside left cap)
        hslice(skin, lay, "full_lcd", solid(c.done()), P(4), P(20), 154, 6)
        time_toggle(lay, "c_time_f", P(8), P(22))
        # big = elapsed or time left (click switches), small = total only: VLC truncates time and
        # length to seconds separately, so "time left" next to "elapsed" would tick at a different
        # moment and can disagree by a second (skins2 vars/time.cpp)
        for big, small, vis, s1, s2 in (("$t", "of $d", "not " + COUNTDOWN, "1:02", "of 4:12"),
                                        ("-$l", "of $d", COUNTDOWN, "-3:10", "of 4:12")):
            lay.text(P(18), P(24), P(130), "lcd26", big, CYAN_TXT, scrolling="none", sample=s1,
                     focus=False).vis = vis_and(lay.theme_vis, vis)
            lay.text(P(18), P(56), P(128), "lcd10", small, CYAN2, scrolling="none", sample=s2,
                     focus=False).vis = vis_and(lay.theme_vis, vis)
        lay.text(P(162), P(24), P(W - 180), "lcd14", "$N", CYAN_TXT, rb="righttop",
                 sample="Nightline Orchestra - Slow Burn Across the River (Extended Mix)")
        lay.text(P(162), P(43), P(W - 180), "lcd10", "$B kbps  $S kHz", CYAN2, rb="righttop",
                 scrolling="none", sample="320 kbps  44.1 kHz")
        lay.checkbox("l_shuf", P(162), P(58), "playlist.isRandom", "playlist.setRandom(true)",
                     "playlist.setRandom(false)", "Shuffle: off", "Shuffle: on")
        lay.checkbox("l_loop", P(198), P(58), "playlist.isLoop", "playlist.setLoop(true)",
                     "playlist.setLoop(false)", "Loop playlist: off", "Loop playlist: on")
        lay.checkbox("l_rep", P(234), P(58), "playlist.isRepeat", "playlist.setRepeat(true)",
                     "playlist.setRepeat(false)", "Repeat one: off", "Repeat one: on")
        lay.text(F(90), P(58), P(72), "lcd10", "SPEED $Rx", CYAN2, align="right", scrolling="none",
                 sample="SPEED 1x", **tr)
        # seek bar (stretches; the fill frames scale with it)
        lay.slider("s_seek_" + lay.id, P(8), P(78), "(0,%d),(%d,%d)" % (P(3), P(sw) - 1, P(3)), "thumb_s",
                   "time", "$T / $D", bg="seek", nbvert=FILL_FRAMES, rb="righttop")
        # transport row
        ty = 96
        lay.button("fb_prev", P(8), P(ty), "playlist.previous()", "Previous")
        lay.button("fb_slower", P(38), P(ty), "vlc.slower()", "Slower")
        lay.checkbox("ft_play", P(68), P(ty), "vlc.isPlaying", "vlc.play()", "vlc.pause()", "Play", "Pause")
        lay.button("fb_faster", P(104), P(ty), "vlc.faster()", "Faster")
        lay.button("fb_next", P(134), P(ty), "playlist.next()", "Next")
        lay.image("ic_speaker", F(186), P(ty + 5), lt="righttop", rb="righttop", action="move")
        lay.slider("s_vol_" + lay.id, F(170), P(ty + 7), "(0,%d),(%d,%d)" % (P(4), P(90) - 1, P(4)), "thumb_v",
                   "volume", "Volume $V%", bg="vol90", nbvert=P(90), **tr)
        panel_toggles(lay, "ft_pl", "ft_eq", F(72), F(40), P(ty))   # 6 px left of the old place: the edge column is free

    def flip_button(lay, mode, d, x, y):
        other = "up" if d == "dn" else "dn"
        lay.button("b_flip_" + other, x, y, "main.setLayout(%s-%s)" % (mode, other),
                   "Open playlist / EQ %s the player" % ("above" if other == "up" else "below"), **tr)

    # ================= equalizer section (y offset is applied by the layout)
    def add_eq(lay, mode, d, sfx):
        c = Canvas(W, EH)
        panel_bg(c, 0, 0, W, EH, 4)
        resize_handle(c, W - 10, 44, 56)   # right edge column (10 px), below the header buttons
        bg = c.done(hard_edges=True)
        hslice(skin, lay, "eq_bg", bg, 0, 0, 10, 10, right_action="resizeE")
        label_on(skin, "lbl_eq", bg, 8, 4, 70, 12, "EQUALIZER")
        lay.image("lbl_eq", P(8), P(4), action="move")
        flip_button(lay, mode, d, PW - P(68), P(4))
        lay.checkbox("t_eqon", PW - P(46), P(4), "equalizer.isEnabled", "equalizer.enable()",
                     "equalizer.disable()", "Equalizer is off", "Equalizer is on", **tr)
        c = Canvas(W - 18, 90)
        lcd(c, 0, 0, W - 18, 90, 3)
        hslice(skin, lay, "eq_lcd", solid(c.done()), P(6), P(19), 6, 6)
        # band block: fixed 400 px, kept centered when the window is resized
        BW = 400
        names = ["PRE", "60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"]
        cxs = [43 + i * 33 + (8 if i else 0) for i in range(11)]
        c = Canvas(BW, 90)
        c.rrect(0, 2, BW, 85, 0, LCD_BG)  # same as the LCD interior, keeps small text crisp
        for lbl, yy in (("+20", 11), ("0", 40), ("-20", 69)):
            c.text(22, yy, lbl, 8, CYAN2, font="mono", anchor="rm")
        for i, cx in enumerate(cxs):
            c.rrect(cx - 1, 10, 2, 60, 1, EQ_TRACK)
            c.rrect(cx - 5, 39.5, 3, 1, 0, CYAN_DIM)          # 0 dB ticks either side of the track
            c.rrect(cx + 2, 39.5, 3, 1, 0, CYAN_DIM)
            c.text(cx, 81, names[i], 8, AMBER if i == 0 else CYAN2, font="mono", anchor="mm")
        c.rrect((cxs[0] + cxs[1]) / 2, 8, 1, 78, 0, DIVIDER)
        skin.add("eq_bands", c.done())
        lay.panel_begin("eq_panel" + sfx, P((W - BW) // 2), P(19), P(BW), P(90))
        lay.image("eq_bands", 0, 0)
        tips = ["Preamp"] + [n.replace("K", " kHz") if "K" in n else n + " Hz" for n in names[1:]]
        for i, cx in enumerate(cxs):
            value = "equalizer.preamp" if i == 0 else "equalizer.band(%d)" % (i - 1)
            lay.slider("s_eq%d%s" % (i, sfx), P(cx - 6), P(8),
                       "(%d,%d),(%d,%d)" % (P(6), P(61), P(6), P(3)), "thumb_eq", value, tips[i],
                       thickness=P(8))
        lay.panel_end()

    # ================= playlist section (fixed height: the window height is shared by all layouts)
    def add_pl(lay, mode, d, sfx):
        c = Canvas(W, LH)
        panel_bg(c, 0, 0, W, LH, 4, flat=True)
        resize_handle(c, W - 10, 71, 56)   # right edge column (10 px)
        bg = c.done(hard_edges=True)
        nslice(skin, lay, "pl_bg", bg, 0, 0, 12, actions={"mr": "resizeE"})
        label_on(skin, "lbl_pl", bg, 8, 4, 60, 12, "PLAYLIST")
        lay.image("lbl_pl", P(8), P(4), action="move")
        flip_button(lay, mode, d, PW - P(26), P(4))
        c = Canvas(W - 18, 154)
        lcd(c, 0, 0, W - 18, 154, 3)
        c.rrect(W - 18 - 16, 3, 8, 148, 3, SCROLL_TRACK)  # scroll track (inside right edge)
        nslice(skin, lay, "pl_lcd", solid(c.done()), P(6), P(19), 18, actions={k: "none" for k in
               ("tl", "tm", "tr", "ml", "mm", "mr", "bl", "bm", "br")})
        lay.playtree(P(10), P(23), P(W - 42), P(146), "lcd11",
                     dict(x=PW - P(28), y=P(23), points="(%d,%d),(%d,%d)" % (P(4), P(135), P(4), P(11)),
                          thumb="thumb_pl"), pid="playtree" + sfx, sid="pl_scroll" + sfx)
        for i, (lbl, act, tip) in enumerate((("add", "playlist.add()", "Add files"),
                                             ("rem", "playlist.del()", "Remove selected"),
                                             ("sort", "playlist.sort()", "Sort by name"),
                                             ("load", "playlist.load()", "Load playlist"),
                                             ("save", "playlist.save()", "Save playlist"))):
            lay.button("b_pl_" + lbl, P(8 + i * 34), P(178), act, tip)
        for i, (lbl, state, name, tip) in enumerate((("shuf", "playlist.isRandom", "Random", "Shuffle"),
                                                     ("loop", "playlist.isLoop", "Loop", "Loop playlist"),
                                                     ("rep1", "playlist.isRepeat", "Repeat", "Repeat one"))):
            lay.checkbox("t_pl_" + lbl, PW - P(132 - i * 40), P(178), state, "playlist.set%s(true)" % name,
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
    # frame width, title bar height, docked control panel height (logical px); the video starts 16:9
    # and the layout is as wide as the full player, so the seek bar bitmap fits like there
    VB, VT, PH = 6, 24, 50
    VW = W
    VIDH = 306
    PBASE = VT + VIDH                                      # top of the docked control panel
    VH = PBASE + PH + VB
    vlay = Layout(skin, "video-l", P(VW), P(VH), minw=P(420), maxw=P(3840),
                  minh=P(VT + VB + PH + 90), maxh=P(2160))
    MW = 140                                               # minimized: the title bar alone
    mlay = Layout(skin, "video-min", P(MW), P(VT))
    # Full screen: skins2 shows the window "fullscreenController" over the video when the mouse
    # moves, and fades it out (VLC's own fullscreen controller option, on by default).
    FSH = 56
    flay = Layout(skin, "fsc-l", P(W), P(FSH))
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
        mlay.theme_vis, mlay.vis = vlay.theme_vis, vlay.vis
        c = Canvas(VW, VH)
        panel_bg(c, 0, 0, VW, VH, 6)
        grip_dots(c, 4, 4, rows=2)                        # title bar grip, left
        grip_dots(c, VW - 11, VH - 14)                    # resize grip, bottom right
        nslice(skin, vlay, "video_bg", c.done(hard_edges=True), 0, 0, VT,
               actions={"mr": "resizeE", "br": "resizeSE"})
        rt = dict(lt="righttop", rb="righttop")
        vlay.checkbox("vb_max", P(VW - 94), P(3), "video.isMaximized", "video.maximize()", "video.unmaximize()",
                      "Fill the screen (title bar and control panel stay)", "Back to the window size", **rt)
        vlay.button("vb_full", P(VW - 64), P(3), "vlc.fullscreen()", "Full screen (no frame, control panel on mouse move)", **rt)
        vlay.button("vb_min", P(VW - 34), P(3), "video.setLayout(video-min)", "Shrink to the title bar", **rt)
        # docked control panel under the video: seek bar, transport, time, volume (kept at the bottom
        # and stretched with the window)
        bl = dict(lt="leftbottom", rb="leftbottom")
        vlay.slider("s_seek_vid", P(8), P(PBASE + 4), "(0,%d),(%d,%d)" % (P(3), P(sw) - 1, P(3)), "thumb_s",
                    "time", "$T / $D", bg="seek", nbvert=FILL_FRAMES, lt="leftbottom", rb="rightbottom")
        vlay.button("fb_prev", P(8), P(PBASE + 22), "playlist.previous()", "Previous", **bl)
        vlay.checkbox("ft_play", P(38), P(PBASE + 22), "vlc.isPlaying", "vlc.play()", "vlc.pause()", "Play", "Pause", **bl)
        vlay.button("fb_next", P(78), P(PBASE + 22), "playlist.next()", "Next", **bl)
        vlay.text(P(124), P(PBASE + 25), P(190), "lcd14", "$T / $D", CYAN_TXT, scrolling="none",
                  sample="1:02 / 4:12", focus=False, **bl)
        vlay.image("ic_speaker", P(VW - 118), P(PBASE + 27), lt="rightbottom", rb="rightbottom", action="none")
        vlay.slider("s_vol_vid", P(VW - 102), P(PBASE + 29), "(0,%d),(%d,%d)" % (P(4), P(90) - 1, P(4)), "thumb_v",
                    "volume", "Volume $V%", bg="vol90", nbvert=P(90), lt="rightbottom", rb="rightbottom")
        vlay.video(P(VB), P(VT), P(VW - 2 * VB), P(VIDH))
        c = Canvas(MW, VT)
        panel_bg(c, 0, 0, MW, VT, 6)
        grip_dots(c, 4, 4, rows=2)
        skin.add("video_min_bg", c.done(hard_edges=True))
        mlay.image("video_min_bg", 0, 0, action="move")
        mlay.button("vb_restore", P(MW - 34), P(3), "video.setLayout(video-l)", "Show the video")
        flay.theme_vis = vlay.theme_vis
        c = Canvas(W, FSH)
        panel_bg(c, 0, 0, W, FSH, 6)
        hslice(skin, flay, "fsc_bg", c.done(hard_edges=True), 0, 0, 14, 14, action="none")
        flay.slider("s_seek_fsc", P(8), P(8), "(0,%d),(%d,%d)" % (P(3), P(sw) - 1, P(3)), "thumb_s",
                    "time", "$T / $D", bg="seek", nbvert=FILL_FRAMES)
        flay.button("fb_prev", P(8), P(28), "playlist.previous()", "Previous")
        flay.checkbox("ft_play", P(38), P(28), "vlc.isPlaying", "vlc.play()", "vlc.pause()", "Play", "Pause")
        flay.button("fb_next", P(78), P(28), "playlist.next()", "Next")
        flay.text(P(124), P(31), P(190), "lcd14", "$T / $D", CYAN_TXT, scrolling="none", sample="1:02 / 4:12",
                  focus=False)
        flay.image("ic_speaker", P(W - 150), P(33), action="none")
        flay.slider("s_vol_fsc", P(W - 134), P(35), "(0,%d),(%d,%d)" % (P(4), P(90) - 1, P(4)), "thumb_v",
                    "volume", "Volume $V%", bg="vol90", nbvert=P(90))
        flay.button("fb_fs", P(W - 36), P(28), "vlc.fullscreen()", "Leave full screen")
        vlay.vis, vlay.theme_vis, mlay.vis, mlay.theme_vis = None, None, None, None
        flay.theme_vis = None
    apply_theme(0)
    skin.prefix = ""

    skin.add("flag_px", Image.new("RGBA", (1, 1), (0, 0, 0, 0)))
    flags = []
    for fid in ["eqflag", "plflag", "tflag"] + ["th%d" % i for i in range(len(THEMES))]:
        fl = Layout(skin, fid + "-l", 1, 1)
        fl.image("flag_px", 0, 0)
        flags.append(dict(id=fid, visible="true" if fid == "th0" else "false", position="Center",
                          yoffset=0, layouts=[fl], dragdrop=False))
    skin.windows = [dict(id="main", visible="true", position="Center", yoffset=0, layouts=layouts),
                    dict(id="video", visible="true", position="Center", yoffset=0, layouts=[mlay, vlay],                  # last = default
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
        if im.width * im.height > 16384:
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
         '  <ThemeInfo name=%s author="Jiri" webpage=""/>' % q("Titlebar " + label)]
    fonts = [("lcd10", 10), ("lcd11", 11), ("lcd12", 12), ("lcd14", 14), ("lcd26", 26)]
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
        on = set(flags) | {"th%d" % theme}
        return eval(re.sub(r"(\w+)\.isVisible", lambda m: str(m.group(1) in on), e))
    out = Image.new("RGBA", (AW, AH), (0, 0, 0, 0))
    font_px = {"lcd10": P(10), "lcd11": P(11), "lcd12": P(12), "lcd14": P(14), "lcd26": P(26),
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
         if i]
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
    ap.add_argument("--width", type=int, default=556)
    ap.add_argument("--bar-height", type=int, default=BAR_DEFAULT,
                    help="strip height in logical px (default %%(default)s; %d for the Windows 11 taskbar, "
                    "sensible 32-40): a taller strip is written as Titlebar-taskbar-NNN.vlt" % BAR_TASKBAR)
    ap.add_argument("--out", default=os.path.join(HERE, "dist"))
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--classic", action="store_true", help="old bevelled / gradient style instead of the flat one")
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
    global FLAT
    FLAT = not a.classic
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
    name = skin_name(a.bar_height, pct)[len("Titlebar-"):]    # "150", "taskbar-150", "bar40-150"
    skin = Skin()
    build(skin, a.width, a.bar_height)
    # VLC unpacks the .vlt to disk: on Windows (case-insensitive) b_x.png and B_x.png would collide
    lower = {}
    for bid in skin.bitmaps:
        assert bid.lower() not in lower, "bitmap ids differ only by case: %s / %s" % (bid, lower[bid.lower()])
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
            assert ImageChops.difference(g, b).getextrema()[1] <= 1 and \
                ImageChops.subtract(g, r).getextrema()[1] <= 1, "custom theme bitmap not grey + red: " + bid
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
    assert all(ids), "element without id: %r" % [t for t, i in zip(tags, ids) if not i][:3]
    dup = [k for k, v in Counter(i.group(1) for i in ids).items() if v > 1]
    assert not dup, "duplicate ids: %r" % sorted(dup)[:5]
    if CUSTOM is not None:
        with open(os.path.join(stage, "custom-ref", "theme.xml"), "w", encoding="utf-8") as fh:
            fh.write(xml)
    if CUSTOM is not None:
        with open(os.path.join(stage, "custom-ref", "slot.txt"), "w", encoding="utf-8") as fh:
            fh.write("slot=%d\naccent=%s\n" % (CUSTOM, a.custom.lower()))
        xml = recolour_xml(xml, a.custom)
    with open(os.path.join(stage, "theme.xml"), "w", encoding="utf-8") as fh:
        fh.write(xml)

    vlt = os.path.join(a.out, "Titlebar-%s.vlt" % name)
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
