#!/bin/bash
# doc-shots.sh - regenerate the screenshots in docs/img from real VLC (needs tools/setup-test-env.sh).
# Usage: tools/doc-shots.sh            (uses TB_DISPLAY_NUM, default 98, and TB_INSTANCE=docs)
set -euo pipefail
cd "$(dirname "$0")/.."
export TB_DISPLAY_NUM=${TB_DISPLAY_NUM:-98} TB_INSTANCE=${TB_INSTANCE:-docs}
CACHE=${TITLEBAR_TEST_CACHE:-$HOME/.cache/titlebar-test}
PY=$CACHE/venv/bin/python
T=tools/vlc-test.sh
OUT=docs/img
mkdir -p "$OUT"

# test music with readable names (silent 8 kHz WAVs)
MUSIC=$CACHE/doc-music
mkdir -p "$MUSIC"
"$PY" - "$MUSIC" <<'EOF'
import os, sys, wave
for name, secs in (("Nightline Orchestra - Slow Burn Across the River", 252), ("Harbour Lights", 201),
                   ("Paper Satellites", 187), ("Static Bloom", 233), ("Glass Elevator", 176),
                   ("Northbound", 214), ("Late Train to Brno", 268)):
    p = os.path.join(sys.argv[1], name + ".wav")
    if not os.path.exists(p):
        w = wave.open(p, "wb"); w.setnchannels(1); w.setsampwidth(1); w.setframerate(8000)
        w.writeframes(bytes([128]) * 8000 * secs); w.close()
EOF

SKIN=$($T build 1 | tail -1)
$T start "$SKIN" "$MUSIC"/*.wav >/dev/null
sleep 3
read -r WX WY WW WH < <($T geometry)
W=556; H=436
shot() {  # shot <name> <x> <y> <w> <h>   (window-relative)
    local f; f=$($T shot "$1" "$((WX + $2)),$((WY + $3)),$4,$5" | tail -1)
    cp "$f" "$OUT/$1.png"
}
click() { $T click "$1" "$2" >/dev/null; sleep 0.6; }
park() { $T park; sleep 1; }   # pointer off the skin, so no hover look and no tooltip

# positions at 100 % (window 556 x 436), from build_skin.py:
#   strip (bar at top):  expand 27,12  title 125..321  mode switch 382,12  PL 479,12  EQ 507,12
#   EQ header flip: 497, EQ top + 10    full player: theme 434,11  collapse 503,11
click 243 12                           # seek to ~60 % in the title window
park; shot strip 0 0 $W 24
click 382 12                           # time: countdown
park; shot strip-countdown 0 0 $W 24
click 382 12                           # back to elapsed
click 479 12; click 507 12             # PL, EQ (open below)
park; shot panels-below 0 0 $W 338
click 497 34                           # flip: panels above, bar at the bottom (y 412)
park; shot panels-above 0 98 $W 338
click 27 424                           # expand: full player at the bottom (y 314)
park; shot full-above 0 0 $W $H
click 503 325                          # collapse
click 497 306                          # flip back: panels below
click 507 12; click 479 12             # EQ, PL off
click 27 12                            # expand
park; shot full 0 0 $W 122

$T quit >/dev/null

# the taller strip of the taskbar build (Titlebar-taskbar-NNN.vlt, 36 px at 100 %): title seek at ~60 %
SKIN=$($T build 1 36 | tail -1)
$T start "$SKIN" "$MUSIC"/*.wav >/dev/null
sleep 3
read -r WX WY WW WH < <($T geometry)
click 243 18
park; shot strip-taskbar 0 0 $W 36
$T quit >/dev/null
$T xvfb-stop >/dev/null

echo "screenshots in $OUT"
