#!/usr/bin/env python3
"""Pick the accent colour of the VLC Amp skin's "Custom" theme.

usage: custom-colour.py [#rrggbb] [file.vlt ...]
       custom-colour.py --reset [file.vlt ...]

Without a colour, a colour picker opens (zenity, kdialog, yad, tkinter, or a
prompt in the terminal). Without files, every VLC-Amp-*.vlt in the folder above
this one is changed. Restart VLC afterwards and choose the Custom theme with the
theme button in the full player's title bar.

How it works: every .vlt keeps the Custom theme's images in a red reference
colour in custom-ref/ (pixel = grey + t * red). Recolouring turns that into
grey + t * accent, writes the result to img/ and the recoloured theme.xml, and
leaves every other file of the .vlt as it was. Python 3 standard library only
(Pillow is used for speed when it is installed; --no-pil turns that off).
"""
import argparse
import array
import io
import itertools
import os
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import time
import zlib

# Same as CUSTOM_DEFAULT in source/build_skin.py (the accent a fresh build uses).
CUSTOM_DEFAULT = "#b48cff"

REF = "custom-ref/"
HEX_RE = re.compile(r"#?([0-9A-Fa-f]{6})$")


class Fail(Exception):
    pass


# ---------------------------------------------------------------- colour maths
def parse_colour(s):
    m = HEX_RE.match(s.strip())
    if not m:
        raise Fail("not a colour like #b48cff: %r" % s)
    h = m.group(1)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hex_colour(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


def scale(t, c):
    """round(t * c / 255), t and c in 0..255 (never a tie, so this equals Python's round)."""
    return (t * c * 2 + 255) // 510


def recolour_pixel(r, g, ac):
    t = r - g
    if t < 0:
        t = 0
    return tuple(min(255, g + scale(t, c)) for c in ac)


def recolour_hex(c, ac):
    """#RRGGBB of the red reference -> #RRGGBB of the accent (as the generator does)."""
    r, g, _ = parse_colour(c)
    return "#%02X%02X%02X" % recolour_pixel(r, g, ac)


def recolour_xml(xml, ac, slot):
    """Recolour the colours of lines with visible="th<slot>.isVisible ..."."""
    mark = 'visible="th%d.isVisible' % slot
    rx = re.compile(r"#[0-9A-Fa-f]{6}")
    return "\n".join(rx.sub(lambda m: recolour_hex(m.group(0), ac), line) if mark in line else line
                     for line in xml.split("\n"))


# ---------------------------------------------------------------- PNG, pure Python
PNG_SIG = b"\x89PNG\r\n\x1a\n"
_and255 = (255).__and__
_masks = {}


def _lane_masks(n):
    m = _masks.get(n)
    if m is None:
        m = _masks[n] = (int.from_bytes(b"\x80" * n, "little"), int.from_bytes(b"\x7f" * n, "little"))
    return m


def _add_rows(a, b):
    """Bytewise (a + b) mod 256 of two equally long byte strings (SWAR on big ints)."""
    hi, lo = _lane_masks(len(a))
    x = int.from_bytes(a, "little")
    y = int.from_bytes(b, "little")
    return (((x & lo) + (y & lo)) ^ ((x ^ y) & hi)).to_bytes(len(a), "little")


def _sub_ints(x, y, hi, lo):
    """Bytewise (x - y) mod 256 of two ints holding byte lanes."""
    return ((x | hi) - (y & lo)) ^ ((x ^ ~y) & hi)


def decode_png(data, name="PNG"):
    """8-bit RGBA, non-interlaced PNG -> (width, height, bytes of all rows, 4 bytes per pixel)."""
    if data[:8] != PNG_SIG:
        raise Fail("%s: not a PNG file" % name)
    pos, idat, ihdr = 8, [], None
    while pos + 8 <= len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if len(body) != n:
            raise Fail("%s: truncated PNG" % name)
        if typ == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            break
        pos += 12 + n
    if ihdr is None or not idat:
        raise Fail("%s: broken PNG (no header or no image data)" % name)
    w, h, depth, ctype, comp, filt, interlace = ihdr
    if (depth, ctype, interlace) != (8, 6, 0) or comp != 0 or filt != 0:
        raise Fail("%s: unsupported PNG (need 8-bit RGBA, not interlaced; got bit depth %d, colour type %d, "
                   "interlace %d)" % (name, depth, ctype, interlace))
    try:
        z = zlib.decompress(b"".join(idat))
    except zlib.error as e:
        raise Fail("%s: damaged image data (%s)" % (name, e))
    stride = w * 4
    if len(z) != h * (stride + 1):
        raise Fail("%s: image data has the wrong length" % name)
    zero = bytes(stride)
    prev = zero
    rows = []
    for y in range(h):
        p = y * (stride + 1)
        ft = z[p]
        line = z[p + 1:p + 1 + stride]
        if ft == 0:
            cur = line
        elif ft == 1:                                   # Sub: running sum per channel
            cur = bytearray(stride)
            for c in range(4):
                cur[c::4] = bytes(map(_and255, itertools.accumulate(line[c::4])))
            cur = bytes(cur)
        elif ft == 2:                                   # Up
            cur = _add_rows(line, prev)
        elif ft == 3:                                   # Average
            cur = bytearray(line)
            for i in range(4):
                cur[i] = (line[i] + (prev[i] >> 1)) & 255
            for i in range(4, stride):
                cur[i] = (line[i] + ((cur[i - 4] + prev[i]) >> 1)) & 255
            cur = bytes(cur)
        elif ft == 4:                                   # Paeth
            if line == zero and prev == zero:
                cur = zero
            else:
                cur = bytearray(line)
                for i in range(4):
                    cur[i] = (line[i] + prev[i]) & 255
                for i in range(4, stride):
                    a, b, c = cur[i - 4], prev[i], prev[i - 4]
                    pa = b - c
                    if pa < 0:
                        pa = -pa
                    pb = a - c
                    if pb < 0:
                        pb = -pb
                    pc = a + b - c - c
                    if pc < 0:
                        pc = -pc
                    if pa <= pb and pa <= pc:
                        cur[i] = (line[i] + a) & 255
                    elif pb <= pc:
                        cur[i] = (line[i] + b) & 255
                    else:
                        cur[i] = (line[i] + c) & 255
                cur = bytes(cur)
        else:
            raise Fail("%s: unknown PNG filter type %d in row %d" % (name, ft, y))
        rows.append(cur)
        prev = cur
    return w, h, b"".join(rows)


_ABS = bytes(min(i, 256 - i) for i in range(256))


def encode_png(w, h, raw):
    """RGBA bytes -> PNG file. Per row: filter None, Sub or Up (whichever looks smallest), zlib 6."""
    stride = w * 4
    hi, lo = _lane_masks(stride)
    full = (1 << (8 * stride)) - 1
    out = []
    prev = bytes(stride)
    for y in range(h):
        row = raw[y * stride:(y + 1) * stride]
        best, bt, bs = row, 0, sum(row.translate(_ABS))
        if bs:
            x = int.from_bytes(row, "little")
            sub = _sub_ints(x, (x << 32) & full, hi, lo).to_bytes(stride, "little")
            s = sum(sub.translate(_ABS))
            if s < bs:
                best, bt, bs = sub, 1, s
            up = _sub_ints(x, int.from_bytes(prev, "little"), hi, lo).to_bytes(stride, "little")
            s = sum(up.translate(_ABS))
            if s < bs:
                best, bt, bs = up, 2, s
        out.append(bytes((bt,)))
        out.append(best)
        prev = row

    def chunk(typ, body):
        return struct.pack(">I", len(body)) + typ + body + struct.pack(">I", zlib.crc32(typ + body) & 0xffffffff)

    return b"".join([PNG_SIG, chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)),
                     chunk(b"IDAT", zlib.compress(b"".join(out), 6)), chunk(b"IEND", b"")])


class _PixelMap(dict):
    """32-bit pixel value (native byte order) -> recoloured pixel value, computed on first use."""

    def __init__(self, ac):
        dict.__init__(self)
        self.ac = ac

    def __missing__(self, key):
        r, g, _, a = key.to_bytes(4, sys.byteorder)
        v = int.from_bytes(bytes(recolour_pixel(r, g, self.ac) + (a,)), sys.byteorder)
        self[key] = v
        return v


def recolour_png_pure(data, ac, name="PNG"):
    w, h, raw = decode_png(data, name)
    px = array.array("I")
    if px.itemsize != 4:
        raise Fail("this Python has 8-byte unsigned ints in array('I'); install Pillow instead")
    px.frombytes(raw)
    px = array.array("I", map(_PixelMap(ac).__getitem__, px))
    return encode_png(w, h, px.tobytes())


# ---------------------------------------------------------------- PNG with Pillow (optional)
def load_pil():
    if os.environ.get("CUSTOM_COLOUR_NO_PIL"):
        return None
    try:
        from PIL import Image, ImageChops
        return Image, ImageChops
    except Exception:
        return None


def recolour_png_pil(pil, data, ac, name="PNG"):
    Image, ImageChops = pil
    im = Image.open(io.BytesIO(data))
    if im.mode != "RGBA" or im.info.get("interlace"):
        return None                                      # let the pure path explain what is wrong
    r, g, _, a = im.split()
    t = ImageChops.subtract(r, g)
    chans = [ImageChops.add(g, t.point([scale(v, c) for v in range(256)])) for c in ac]
    out = io.BytesIO()
    Image.merge("RGBA", chans + [a]).save(out, "PNG", compress_level=6)
    return out.getvalue()


# ---------------------------------------------------------------- .vlt
def read_vlt(path):
    try:
        with tarfile.open(path, "r:gz") as tf:
            items = []
            for m in tf.getmembers():
                f = tf.extractfile(m) if m.isfile() else None
                items.append((m, f.read() if f else None))
    except (tarfile.TarError, OSError, EOFError, zlib.error) as e:
        raise Fail("cannot read %s: %s" % (path, e))
    return items


def read_slot(items):
    for m, data in items:
        if m.name == REF + "slot.txt" and data is not None:
            kv = dict(line.split("=", 1) for line in data.decode("utf-8", "replace").split() if "=" in line)
            try:
                return int(kv["slot"]), parse_colour(kv["accent"])
            except (KeyError, ValueError, Fail):
                raise Fail("custom-ref/slot.txt is damaged")
    raise Fail("no custom-ref/ in it (built before the Custom theme existed; use a newer build)")


def current_accent(path):
    try:
        return read_slot(read_vlt(path))[1]
    except Fail:
        return None


def recolour_vlt(path, ac, pil):
    """Rewrite one .vlt with the Custom theme in colour ac. Returns the number of images changed."""
    items = read_vlt(path)
    slot, _ = read_slot(items)
    by_name = {m.name: i for i, (m, _) in enumerate(items)}
    changed = {}
    n_img = 0
    for m, data in list(items):
        if m.name.startswith(REF + "img/") and m.name.endswith(".png") and data is not None:
            target = m.name[len(REF):]
            new = None
            if pil:
                new = recolour_png_pil(pil, data, ac, m.name)
            if new is None:
                new = recolour_png_pure(data, ac, m.name)
            changed[target] = new
            n_img += 1
        elif m.name == REF + "theme.xml" and data is not None:
            changed["theme.xml"] = recolour_xml(data.decode("utf-8"), ac, slot).encode("utf-8")
        elif m.name == REF + "slot.txt":
            text = data.decode("utf-8")
            text = re.sub(r"(?m)^accent=.*$", "accent=" + hex_colour(ac), text)
            changed[m.name] = text.encode("utf-8")
    if "theme.xml" not in changed or not n_img:
        raise Fail("custom-ref/ is incomplete (no theme.xml or no images)")

    tmp = "%s.tmp%d" % (path, os.getpid())
    try:
        with tarfile.open(tmp, "w:gz", compresslevel=6, format=tarfile.PAX_FORMAT) as out:
            for m, data in items:
                if m.name in changed:
                    data = changed.pop(m.name)
                    m.size = len(data)
                if data is None:
                    out.addfile(m)
                else:
                    out.addfile(m, io.BytesIO(data))
            for name, data in changed.items():            # an image that img/ did not have yet
                ti = tarfile.TarInfo(name)
                ti.size, ti.mtime, ti.mode = len(data), int(time.time()), 0o644
                out.addfile(ti, io.BytesIO(data))
        try:
            shutil.copymode(path, tmp)
        except OSError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return n_img


# ---------------------------------------------------------------- colour picker
def _which(cmd):
    return shutil.which(cmd)


def _first_colour(text):
    """#rrggbb, rgb(r,g,b), rgba(r,g,b,a) or #rrrrggggbbbb -> (r, g, b), else None."""
    m = re.search(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", text)
    if m:
        return tuple(min(255, int(x)) for x in m.groups())
    m = re.search(r"#([0-9A-Fa-f]{12})\b", text)
    if m:
        h = m.group(1)
        return tuple(int(h[i:i + 2], 16) for i in (0, 4, 8))
    m = re.search(r"#([0-9A-Fa-f]{6})", text)
    if m:
        return parse_colour(m.group(1))
    return None


def pick_colour(initial):
    """Ask for a colour. Returns (r, g, b), or None when the user cancelled."""
    start = hex_colour(initial)
    title = "Accent colour of the Custom theme"
    have_display = sys.platform in ("win32", "darwin") or os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    tools = []
    if have_display:
        tools = [("zenity", ["zenity", "--color-selection", "--title=" + title, "--color=" + start]),
                 ("kdialog", ["kdialog", "--title", title, "--getcolor", "--default", start]),
                 ("yad", ["yad", "--color", "--title=" + title, "--init-color=" + start])]
    for name, cmd in tools:
        if not _which(name):
            continue
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        except OSError:
            continue
        col = _first_colour(r.stdout) if r.returncode == 0 else None
        if col:
            return col
        if r.returncode != 0 and not r.stderr.strip():
            return None                                  # closed or Cancel
    if have_display:
        try:
            import tkinter
            from tkinter import colorchooser
            root = tkinter.Tk()
            root.withdraw()
            try:
                root.attributes("-topmost", True)
            except Exception:
                pass
            try:
                rgb, _ = colorchooser.askcolor(color=start, title=title, parent=root)
            finally:
                root.destroy()
            return tuple(int(round(v)) for v in rgb) if rgb else None
        except Exception:
            pass                                         # no tkinter or no display: ask in the terminal
    if not sys.stdin or not sys.stdin.isatty():
        raise Fail("no colour picker available and no terminal: pass the colour, e.g. custom-colour.py #33ff99")
    while True:
        try:
            s = input("Accent colour as #rrggbb (now %s, empty = cancel): " % start).strip()
        except EOFError:
            return None
        if not s:
            return None
        try:
            return parse_colour(s)
        except Fail as e:
            print(e)


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description="Pick the accent colour of the VLC Amp skin's Custom theme.",
                                 usage="%(prog)s [#rrggbb] [file.vlt ...]")
    ap.add_argument("args", nargs="*", help="a colour like #b48cff, then .vlt files "
                    "(default: all VLC-Amp-*.vlt next to the custom-colour folder)")
    ap.add_argument("--reset", action="store_true", help="back to the default accent " + CUSTOM_DEFAULT)
    ap.add_argument("--no-pil", action="store_true", help="do not use Pillow even if it is installed")
    a = ap.parse_args(argv)
    if a.no_pil:
        os.environ["CUSTOM_COLOUR_NO_PIL"] = "1"

    colour, files = None, []
    for i, s in enumerate(a.args):
        if i == 0 and (HEX_RE.match(s) or s.startswith("#")) and not os.path.isfile(s):
            colour = parse_colour(s)
        else:
            files.append(s)
    if a.reset:
        if colour:
            ap.error("--reset and a colour together make no sense")
        colour = parse_colour(CUSTOM_DEFAULT)
    if not files:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        files = sorted(os.path.join(root, f) for f in os.listdir(root)
                       if re.fullmatch(r"VLC-Amp-.*\.vlt", f))
        if not files:
            raise Fail("no VLC-Amp-*.vlt in %s" % root)
    for f in files:
        if not os.path.isfile(f):
            raise Fail("no such file: %s" % f)

    if colour is None:
        start = next((c for c in map(current_accent, files) if c), parse_colour(CUSTOM_DEFAULT))
        colour = pick_colour(start)
        if colour is None:
            print("Cancelled, nothing changed.")
            return 0
    pil = load_pil()
    print("Accent %s (%s)" % (hex_colour(colour), "Pillow" if pil else "pure Python"))
    bad = 0
    for f in files:
        t0 = time.time()
        print("%s ..." % os.path.basename(f), end=" ")
        sys.stdout.flush()
        try:
            n = recolour_vlt(f, colour, pil)
        except Fail as e:
            print("skipped: %s" % e)
            bad += 1
            continue
        except OSError as e:
            print("failed: %s (is VLC running with this skin?)" % e)
            bad += 1
            continue
        print("%d images, %.1f s" % (n, time.time() - t0))
    if not bad:
        print("Done. Restart VLC, then choose the Custom theme with the theme button in the full player's title bar.")
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fail as e:
        print("error: %s" % e, file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
