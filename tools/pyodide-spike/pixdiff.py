"""Where do the decoded pixels of two .vlt PNG members differ? python3 pixdiff.py a.vlt b.vlt member.png"""
import io
import sys
import tarfile

from PIL import Image, ImageChops, features


def png(path, name):
    with tarfile.open(path) as t:
        return Image.open(io.BytesIO(t.extractfile(name).read())).convert("RGBA")


a, b = png(sys.argv[1], sys.argv[3]), png(sys.argv[2], sys.argv[3])
d = ImageChops.difference(a, b)
n = sum(1 for p in d.get_flattened_data() if p != (0, 0, 0, 0))
print(sys.argv[3], a.size, "differing pixels:", n, "max channel delta:", max(e[1] for e in d.getextrema()))
# differences that are invisible: both pixels fully transparent (only the hidden RGB differs)
inv = sum(1 for pa, pb in zip(a.get_flattened_data(), b.get_flattened_data())
          if pa != pb and pa[3] == 0 and pb[3] == 0)
print("of which both pixels alpha=0 (invisible):", inv, "| alpha channel differs:",
      ImageChops.difference(a.getchannel("A"), b.getchannel("A")).getbbox())
rows = [(max(abs(x - y) for x, y in zip(pa[:3], pb[:3])), pa[3])
        for pa, pb in zip(a.get_flattened_data(), b.get_flattened_data()) if pa != pb]
print("diff pixels with alpha>=128:", sum(1 for _, al in rows if al >= 128),
      "| max alpha among them:", max(al for _, al in rows), "| max RGB delta at alpha>=128:",
      max([dl for dl, al in rows if al >= 128] or [0]), "| max RGB delta at alpha<32:",
      max([dl for dl, al in rows if al < 32] or [0]))
w = a.width
ys = sorted({i // w for i, (pa, pb) in enumerate(zip(a.get_flattened_data(), b.get_flattened_data())) if pa != pb})
print("rows with differences:", ys[0], "-", ys[-1], "(%d rows)" % len(ys))
Image.merge("RGB", [ImageChops.difference(a, b).getchannel(c).point(lambda v: 255 if v else 0)
                    for c in "RGB"]).save("/tmp/claude-1000/-home-jirif-dev-vlc/86c0d79e-80a2-49a5-9cf6-3529d4d5c254/scratchpad/work/diff.png")
print("pillow freetype:", features.version("freetype2"), "zlib:", features.version("zlib"))
