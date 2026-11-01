#!/bin/bash
# make-windows-package.sh - build the folder (and a zip of it) to copy to a Windows PC.
# Usage: tools/make-windows-package.sh [out dir]      (default: dist/)
# On Windows: double-click Install.cmd in the copied folder.
# Takes the committed files (git HEAD), so uncommitted edits are never shipped.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${1:-dist}
NAME=VLC-Amp-windows
PKG="${OUT:?}/${NAME:?}"

paths=(Install.cmd Uninstall.cmd README.md 'VLC-Amp-*.vlt' taskbar lua docs/img-thin)
dirty=$(git status --porcelain -- "${paths[@]}")
[ -z "$dirty" ] || { echo "warning: uncommitted changes in packaged files (not included):"; echo "$dirty"; }

rm -rf "${PKG:?}" "${PKG:?}.zip"
mkdir -p "$PKG"
git archive --format=tar HEAD -- "${paths[@]}" | tar -x -C "$PKG"
# The Windows helper follows Windows' light / dark setting (vlc-taskbar.ps1 $FollowSystemTheme), which
# needs both themes in the skin: rebuild the .vlt files as a Midnight + Paper pair (the committed
# ones, also used by the Linux package, have Midnight only). PAIR=0 keeps the committed files.
if [ "${PAIR:-1}" = 1 ]; then
    . tools/vlc-env.sh 2>/dev/null || true
    PY=python3; [ -x "${VENV:-}/bin/python" ] && PY="$VENV/bin/python"
    rm -f "$PKG"/VLC-Amp-*.vlt
    tmp=$(mktemp -d)
    # File names: VLC-Amp-[taskbar-]NNN.vlt (see taskbar/vlc-taskbar.ps1 Get-SkinInfo): 24 px strip;
    # taskbar- = 36 px strip when docked.
    for sc in 1:100 1.25:125 1.5:150 2:200; do
        for bar in 24 36; do
            "$PY" source/build_skin.py --scale "${sc%%:*}" --bar-height "$bar" --themes midnight,paper --out "$tmp" >/dev/null &
        done
    done
    wait
    cp "$tmp"/VLC-Amp-*.vlt "$PKG"/
    rm -rf "$tmp"
fi
# Windows scripts need CRLF. Done here, not by .gitattributes: git archive ignores the
# attributes of a subfolder (this project is a subfolder of the git repository).
find "$PKG" -type f \( -name '*.ps1' -o -name '*.cs' -o -name '*.cmd' -o -name '*.vbs' \) -exec sed -i 's/\r*$/\r/' {} +
sed 's/$/\r/' > "$PKG/READ ME FIRST.txt" <<'TXT'
VLC Amp - a VLC skin

1. Close VLC.
2. Double-click Install.cmd. It
   - installs VLC 3 if it is missing (winget),
   - copies the skin to %LOCALAPPDATA%\VLC-Amp,
   - asks a few questions (start the helper with Windows, dock in the
     taskbar, Windows media controls) and sets VLC up.
3. Open a music file or folder.

Undo: Start menu > VLC Amp > Uninstall VLC Amp (or Uninstall.cmd).
Everything else: README.md.
TXT
(cd "$OUT" && python3 -m zipfile -c "$NAME.zip" "$NAME")
echo "package: $PKG"
echo "zip:     $PKG.zip ($(du -h "$PKG.zip" | cut -f1))"
