#!/bin/bash
# make-linux-package.sh - build the folder (and a .tar.gz of it) to copy to a Linux PC.
# Usage: tools/make-linux-package.sh [out dir]      (default: dist/)
# On Linux: run ./Install.sh in the copied folder (it runs linux/setup.sh).
# Takes the committed files (git HEAD), so uncommitted edits are never shipped.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${1:-dist}
NAME=VLC-Amp-linux
PKG="${OUT:?}/${NAME:?}"

paths=(README.md 'VLC-Amp-*.vlt' linux lua docs/img)
dirty=$(git status --porcelain -- "${paths[@]}")
[ -z "$dirty" ] || { echo "warning: uncommitted changes in packaged files (not included):"; echo "$dirty"; }

rm -rf "${PKG:?}" "${PKG:?}.tar.gz"
mkdir -p "$PKG"
git archive --format=tar HEAD -- "${paths[@]}" | tar -x -C "$PKG"
cat > "$PKG/Install.sh" <<'SH'
#!/bin/sh
# Sets VLC up for the VLC Amp skin. Close VLC first. Options: see linux/setup.sh --help
exec sh "$(dirname "$0")/linux/setup.sh" "$@"
SH
cat > "$PKG/Uninstall.sh" <<'SH'
#!/bin/sh
exec sh "$(dirname "$0")/linux/setup.sh" --uninstall "$@"
SH
cat > "$PKG/READ ME FIRST.txt" <<'TXT'
VLC Amp - a VLC skin

1. Close VLC.
2. In this folder run:   sh Install.sh      (add --yes for no questions)
   It detects native / Flatpak / Snap VLC and the display scale, writes VLC's
   settings (backup: vlcrc.before-vlc-amp) and adds a "VLC Amp" launcher.
3. Open a music file or folder with "VLC Amp".

Optional: linux/vlc-amp-pin.py (start pinned), linux/follow-system-theme.sh.
Undo: sh Uninstall.sh. Everything else: README.md.
TXT
chmod +x "$PKG/Install.sh" "$PKG/Uninstall.sh" "$PKG"/linux/*.sh "$PKG"/linux/*.py
tar -C "$OUT" -czf "$PKG.tar.gz" "$NAME"
echo "package: $PKG"
echo "tarball: $PKG.tar.gz ($(du -h "$PKG.tar.gz" | cut -f1))"
