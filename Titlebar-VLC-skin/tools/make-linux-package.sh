#!/bin/bash
# make-linux-package.sh - build the folder (and a .tar.gz of it) to copy to a Linux PC.
# Usage: tools/make-linux-package.sh [out dir]      (default: dist/)
# On Linux: run ./Install.sh in the copied folder (it runs linux/setup.sh).
# Takes the committed files (git HEAD), so uncommitted edits are never shipped.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${1:-dist}
NAME=Titlebar-VLC-skin-linux
PKG="${OUT:?}/${NAME:?}"

paths=(README.md 'Titlebar-*.vlt' linux lua docs/img-thin)
dirty=$(git status --porcelain -- "${paths[@]}")
[ -z "$dirty" ] || { echo "warning: uncommitted changes in packaged files (not included):"; echo "$dirty"; }

rm -rf "${PKG:?}" "${PKG:?}.tar.gz"
mkdir -p "$PKG"
git archive --format=tar HEAD -- "${paths[@]}" | tar -x -C "$PKG"
# The committed Titlebar-*.vlt in git can lag behind the generator, so rebuild them: 24 px strip only
# (titlebar-pin.py assumes it), Midnight only.
# REBUILD=0 ships the committed files as they are.
if [ "${REBUILD:-1}" = 1 ]; then
    . tools/vlc-env.sh 2>/dev/null || true
    PY=python3; [ -x "${VENV:-}/bin/python" ] && PY="$VENV/bin/python"
    rm -f "$PKG"/Titlebar-*.vlt
    tmp=$(mktemp -d)
    for sc in 1:100 1.25:125 1.5:150 2:200; do
        "$PY" source/build_skin.py --scale "${sc%%:*}" --out "$tmp" >/dev/null &
    done
    wait
    cp "$tmp"/Titlebar-*.vlt "$PKG"/
    rm -rf "$tmp"
fi
cat > "$PKG/Install.sh" <<'SH'
#!/bin/sh
# Sets VLC up for the Titlebar skin. Close VLC first. Options: see linux/setup.sh --help
exec sh "$(dirname "$0")/linux/setup.sh" "$@"
SH
cat > "$PKG/Uninstall.sh" <<'SH'
#!/bin/sh
exec sh "$(dirname "$0")/linux/setup.sh" --uninstall "$@"
SH
cat > "$PKG/READ ME FIRST.txt" <<'TXT'
Titlebar - a VLC skin

1. Close VLC.
2. In this folder run:   sh Install.sh      (add --yes for no questions)
   It detects native / Flatpak / Snap VLC and the display scale, writes VLC's
   settings (backup: vlcrc.before-titlebar) and adds a "VLC (Titlebar)" launcher.
3. Open a music file or folder with "VLC (Titlebar)".

Optional: linux/titlebar-pin.py (start pinned), linux/follow-system-theme.sh.
Undo: sh Uninstall.sh. Everything else: README.md.
TXT
chmod +x "$PKG/Install.sh" "$PKG/Uninstall.sh" "$PKG"/linux/*.sh "$PKG"/linux/*.py
tar -C "$OUT" -czf "$PKG.tar.gz" "$NAME"
echo "package: $PKG"
echo "tarball: $PKG.tar.gz ($(du -h "$PKG.tar.gz" | cut -f1))"
