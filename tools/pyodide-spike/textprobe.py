"""Render the same text natively and in Pyodide, print a hash: shows FreeType/layout differences."""
import hashlib
import sys

from PIL import Image, ImageDraw, ImageFont

font = sys.argv[1] if len(sys.argv) > 1 else "/work/source/fonts/DejaVuSansMono.ttf"
for size in (9, 11, 13, 20):
    im = Image.new("RGBA", (200, 40), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2, 2), "00:12:34 -1.5 dB 31k", font=ImageFont.truetype(font, size), fill=(255, 255, 255, 255))
    print("text size", size, hashlib.sha256(im.tobytes()).hexdigest()[:12])
im = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
ImageDraw.Draw(im).ellipse((10, 10, 300, 200), fill=(255, 0, 0, 255))
im = im.resize((100, 100), Image.LANCZOS)
print("shape+LANCZOS", hashlib.sha256(im.tobytes()).hexdigest()[:12])
