#!/bin/bash
# doc-shots.sh - regenerate docs/img-thin/{strip,strip-panels,full-eq}.png from a build,
# with real VLC under Xvfb (needs tools/setup-test-env.sh once).
#
# Usage: tools/doc-shots.sh
#        BAR=40 tools/doc-shots.sh          the 40 px strip of the concept instead of the 24 px title-bar strip
#        TB_DISPLAY_NUM=102 TB_INSTANCE=hifi-ts tools/doc-shots.sh   (parallel agents: own values)
#
# Window 620 px wide (TB_WIDTH), scale 100 %. The click positions are measured on the
# build of that width (BAR 24 and BAR 40); change them if the layout changes.
# The crops come from the window's X11 shape, so the panels' visible height is exact.
set -euo pipefail
cd "$(dirname "$0")/.."
export TB_DISPLAY_NUM=${TB_DISPLAY_NUM:-98} TB_INSTANCE=${TB_INSTANCE:-docs}
BAR=${BAR:-24}
W=620
export TB_WIDTH=$W
OUT=${OUT:-docs/img-thin}
CACHE=${TITLEBAR_TEST_CACHE:-$HOME/.cache/titlebar-test}
PY=$CACHE/venv/bin/python
T=tools/vlc-test.sh

# strip click positions (window-relative, 100 %): y = centre of the strip, PL / EQ x
case "$BAR" in
    40) SY=20; PL_X=504; EQ_X=554 ;;
    24) SY=12; PL_X=514; EQ_X=560 ;;
    *) echo "doc-shots: BAR must be 24 or 40 (the positions are measured for these)" >&2; exit 1 ;;
esac
# full player (same at every bar height): expand from the strip at x 27; PL / EQ at the transport row
EXPAND_X=27
FULL_PL="534 209"
FULL_EQ="586 209"
SEEK="280 $SY"     # title window (about 60 % of its width), jumps the seek bar there

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

SKIN=$($T build 1 "$BAR" | tail -1)
$T start "$SKIN" "$MUSIC"/*.wav >/dev/null
trap '$T stop >/dev/null 2>&1; $T xvfb-stop >/dev/null 2>&1' EXIT   # on failure: stop what this run started
sleep 3
read -r WX WY WW WH < <($T geometry)
echo "window ${WW}x${WH} at $WX,$WY, bar $BAR"

shot() {  # shot <name> <x> <y> <w> <h>   (window-relative)
    local f; f=$($T shot "$1" "$((WX + $2)),$((WY + $3)),$4,$5" | tail -1)
    cp "$f" "$OUT/$1.png"
}
shot_shape() {  # shot <name>: the window's visible box (X11 shape), window-relative
    local x y w h
    read -r x y w h < <($T shape | sed -n 's/^box x=\([0-9]*\) y=\([0-9]*\) w=\([0-9]*\) h=\([0-9]*\).*/\1 \2 \3 \4/p')
    shot "$1" "$x" "$y" "$w" "$h"
}
click() { $T click "$1" "$2" >/dev/null; sleep 0.6; }
park() { $T park; sleep 1; }   # pointer off the skin, so no hover look and no tooltip

# 1. strip, panels closed (seek the title to about 60 %, so the fill shows)
click $SEEK
park; shot strip 0 0 "$W" "$BAR"
# 2. strip with PL and EQ open (below the bar)
click "$PL_X" "$SY"; click "$EQ_X" "$SY"
park; shot_shape strip-panels
# 3. close both, expand to the full player, open its PL and EQ
click "$PL_X" "$SY"; click "$EQ_X" "$SY"
click "$EXPAND_X" "$SY"
click $FULL_PL; click $FULL_EQ
park; shot_shape full-eq

# quit only with the panels closed: with them open the shape reaches the window's bottom edge,
# and the harness takes that as "bar at the bottom" and misses the quit button
click $FULL_PL; click $FULL_EQ
$T quit >/dev/null
trap - EXIT
$T xvfb-stop >/dev/null

echo "screenshots in $OUT: strip.png strip-panels.png full-eq.png"
