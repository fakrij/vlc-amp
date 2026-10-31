"""Compare two .vlt files member by member: python3 compare.py a.vlt b.vlt
Differing PNGs are also compared by decoded pixels (needs Pillow)."""
import hashlib
import io
import sys
import tarfile


def members(path):
    with tarfile.open(path) as t:
        names = t.getnames()
        data = {m.name: t.extractfile(m).read() for m in t if m.isfile()}
        meta = {m.name: (m.mtime, m.uid, m.gid, m.uname, m.mode) for m in t}
    return names, data, meta


(na, da, ma), (nb, db, mb) = members(sys.argv[1]), members(sys.argv[2])
print("same member order:", na == nb, "| same member set:", set(na) == set(nb))
diff = sorted(k for k in da if da[k] != db.get(k))
print("files differing in content:", diff)
print("files with differing header metadata:", sum(ma[k] != mb.get(k) for k in ma), "of", len(ma))
try:
    from PIL import Image
    for k in diff:
        if k.endswith(".png"):
            a, b = Image.open(io.BytesIO(da[k])), Image.open(io.BytesIO(db[k]))
            print(" ", k, "pixels equal:", a.mode == b.mode and a.tobytes() == b.tobytes(),
                  "| bytes", len(da[k]), len(db[k]), "| info", a.info == b.info)
except ImportError:
    pass
