#!/bin/sh
# Copy the generator and its DejaVu files next to the page (the page runs build_skin.py unchanged).
cd "$(dirname "$0")" || exit 1
cp ../source/build_skin.py build_skin.py
cp ../source/fonts/DejaVuSansMono.ttf ../source/fonts/DejaVuSans-Bold.ttf ../source/fonts/LICENSE-DejaVu.txt fonts/
