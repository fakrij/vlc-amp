#!/bin/sh
# Copy the generator and its DejaVu files next to the page (the page runs build_skin.py unchanged).
# Dependency-free twin of ../tools/sync-configurator.py (which does the same copy and then VERIFIES that the
# CLI and the copy build identical skins; it needs Pillow). Run one of them after EVERY change to
# ../source/build_skin.py and commit configurator/ too (the Pages workflow checks the copy with cmp).
cd "$(dirname "$0")" || exit 1
cp ../source/build_skin.py build_skin.py
cp ../source/fonts/DejaVuSansMono.ttf ../source/fonts/DejaVuSans-Bold.ttf ../source/fonts/LICENSE-DejaVu.txt fonts/
cmp ../source/build_skin.py build_skin.py && echo "configurator/build_skin.py is identical to source/build_skin.py"
