#!/bin/bash
# make-windows-package.sh - build the folder (and a zip of it) to copy to a Windows PC.
# Usage: tools/make-windows-package.sh [out dir]      (default: dist/)
# On Windows: double-click Install.cmd in the copied folder.
# Takes the committed files (git HEAD), so uncommitted edits are never shipped.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${1:-dist}
NAME=Titlebar-VLC-skin-windows
PKG="${OUT:?}/${NAME:?}"

paths=(Install.cmd Uninstall.cmd README.md 'Titlebar-*.vlt' taskbar lua docs/img)
dirty=$(git status --porcelain -- "${paths[@]}")
[ -z "$dirty" ] || { echo "warning: uncommitted changes in packaged files (not included):"; echo "$dirty"; }

rm -rf "${PKG:?}" "${PKG:?}.zip"
mkdir -p "$PKG"
git archive --format=tar HEAD -- "${paths[@]}" | tar -x -C "$PKG"
# Windows scripts need CRLF. Done here, not by .gitattributes: git archive ignores the
# attributes of a subfolder (this project is a subfolder of the git repository).
find "$PKG" -type f \( -name '*.ps1' -o -name '*.cs' -o -name '*.cmd' \) -exec sed -i 's/\r*$/\r/' {} +
sed 's/$/\r/' > "$PKG/READ ME FIRST.txt" <<'TXT'
Titlebar - a VLC skin

1. Close VLC.
2. Double-click Install.cmd. It
   - installs VLC 3 if it is missing (winget),
   - copies the skin to %LOCALAPPDATA%\Titlebar-VLC-skin,
   - asks a few questions (start the helper with Windows, dock in the
     taskbar, Windows media controls) and sets VLC up.
3. Open a music file or folder.

Undo: Start menu > Titlebar VLC skin > Uninstall Titlebar skin (or Uninstall.cmd).
Everything else: README.md.
TXT
(cd "$OUT" && python3 -m zipfile -c "$NAME.zip" "$NAME")
echo "package: $PKG"
echo "zip:     $PKG.zip ($(du -h "$PKG.zip" | cut -f1))"
