"""LEGACY - kept for reference only. It models the old (pre hi-fi) bitmaps; the check that
replaces it is tools/bitmap-audit.py (scans every bitmap for semi-transparent pixels).

Simulate how skins2 draws our semi-transparent bitmaps.

skins2 (3.0.x) pipeline for buttons / checkboxes / images:
  1. FileBitmap: PNG -> RGBA, colour premultiplied  c' = c*a/255 (truncated), alpha kept.
  2. a control's own OSGraphics (blank) <- drawBitmap(bitmap), blend=false.
       X11  : putPixel(r', g', b') (alpha ignored), mask = pixels with a > 0
       Win32: AlphaBlend(AC_SRC_ALPHA, premultiplied) over the blank DDB (blend flag ignored),
              mask = pixels with a > 0
  3. window buffer <- drawGraphics(control graphics): masked copy, no blending (XCopyArea / BitBlt SRCCOPY)
So an edge pixel with 0 < a < 255 ends up opaque with colour c*a/255 (+ (255-a)/255 * blank content on Win32).

Usage (needs Pillow; use the harness venv):
    ~/.cache/titlebar-test/venv/bin/python tools/windows-sim.py [out dir [scale]]
Writes buttons-{before,after}-{midnight,paper}-<scale>.png: columns = skins2 on X11, Windows with
a black / white blank bitmap, ideal blend (4x). "before" = generator without solid().
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "source"))
from PIL import Image, ImageDraw
import build_skin as B

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "docs", "img", "windows-sim")
scale = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
os.makedirs(out, exist_ok=True)


def premul(im):
    return [(r * a // 255, g * a // 255, bl * a // 255, a) for r, g, bl, a in im.convert("RGBA").getdata()]


def _img(size, px):
    o = Image.new("RGB", size)
    o.putdata(px)
    return o


def skins2_x11(im, bg):
    bgp = list(bg.convert("RGB").getdata())
    out = [(r, g, b) if a > 0 else bgp[i] for i, (r, g, b, a) in enumerate(premul(im))]
    return _img(im.size, out)


def win32(im, bg, blank):
    bgp = list(bg.convert("RGB").getdata())
    out = []
    for i, (r, g, b, a) in enumerate(premul(im)):
        if a > 0:
            out.append((r + blank * (255 - a) // 255, g + blank * (255 - a) // 255, b + blank * (255 - a) // 255))
        else:
            out.append(bgp[i])
    return _img(im.size, out)


def ideal(im, bg):
    return Image.alpha_composite(bg.convert("RGBA"), im.convert("RGBA")).convert("RGB")


def up(img, k=4):
    return img.resize((img.width * k, img.height * k), Image.NEAREST)


B.S = scale
ZOOM = 4


def run(tag, patched):
    orig = B.solid
    if patched:                       # before: no solid() (the generator as it was)
        B.solid = lambda im, bg=None: im
    res = {}
    for tname in ("midnight", "paper"):
        B.set_themes([tname])
        B.apply_theme(0)
        skin = B.Skin()
        B.build(skin, 556, 24)
        names = ["t0_b_prev_up", "t0_t_play_off_up", "t0_t_pl_on_up", "t0_t_top_off_up", "t0_b_close_up",
                 "t0_fb_prev_up", "t0_ft_eq_off_up", "t0_b_pl_add_up", "t0_b_theme_up",
                 "t0_thumb_v_up", "t0_thumb_s_up", "t0_thumb_eq_up", "t0_thumb_pl_up", "t0_ic_speaker"]
        bgs = {"t0_thumb_eq_up": B.LCD_BG, "t0_thumb_pl_up": B.SCROLL_TRACK}
        rows = []
        for n in names:
            im = skin.bitmaps[n]
            pad = 3 * max(1, round(scale))
            W, Hh = im.width + 2 * pad, im.height + 2 * pad
            bgc = B.H(bgs.get(n, B.BG_TOP))
            bg = Image.new("RGBA", (W, Hh), bgc)
            big = Image.new("RGBA", (W, Hh), (0, 0, 0, 0))
            big.paste(im, (pad, pad))
            cols = [skins2_x11(big, bg), win32(big, bg, 0), win32(big, bg, 255), ideal(big, bg)]
            rows.append([up(c, ZOOM) for c in cols])
            a = [q[3] for q in im.getdata()]
            print(tag, tname, n, im.size, "partial-alpha px:", sum(1 for v in a if 0 < v < 255))
        res[tname] = rows
    B.solid = orig
    return res


labels = ["skins2 X11 (Linux)", "Windows, blank bmp black", "Windows, blank bmp white", "ideal blend"]
for tag, patched in (("before", True), ("after", False)):
    res = run(tag, patched)
    for tname, rows in res.items():
        cw = max(r[0].width for r in rows) + 8
        rh = max(r[0].height for r in rows) + 8
        sheet = Image.new("RGB", (cw * 4 + 8, rh * len(rows) + 28), (96, 96, 96))
        d = ImageDraw.Draw(sheet)
        d.text((8, 6), tag.upper() + " - " + tname + " - " + "   |   ".join(labels), fill=(255, 255, 255))
        for i, r in enumerate(rows):
            for j, c in enumerate(r):
                sheet.paste(c, (8 + j * cw, 28 + i * rh))
        p = os.path.join(out, "buttons-%s-%s-%d.png" % (tag, tname, round(scale * 100)))
        sheet.save(p)
        print(p)
