#!/bin/bash
# Run real VLC with the skin under Xvfb, click it, take screenshots.
# Run tools/setup-test-env.sh once first. See tools/README.md.
#
# Only processes this script started are ever killed (PIDs are stored in
# $RUN); it never uses pkill/killall.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/vlc-env.sh"

usage() {
    cat <<'EOF'
usage: vlc-test.sh <command> [args]

  start <vlt> [files...]   start Xvfb (if needed) and VLC with the skin; fresh config.
                           Default files: song1 song2 song3 from the test audio.
  shot <name> [x,y,w,h]    screenshot to $SHOTS/<name>.png and print the path.
                           Crop is in screen pixels; default = the main window.
  click <x> <y>            left click at x,y relative to the main window's top-left
  drag <x> <y> <dx> <dy>   press at x,y (window-relative), move by dx,dy, release
  geometry                 main window position and size ("X Y W H")
  shape                    X11 shape (visible area) box of the main window
  quit                     expand the strip, click the full player's quit button
                           (VLC then writes skins2-config), wait for exit
  stop                     kill the VLC this script started (config is not saved)
  xvfb-stop                kill the Xvfb this script started
  build [scale] [bar]      build the skin with the test venv to $CACHE/skins;
                           prints the .vlt path (scale 1 = 100 %, default 1;
                           bar = strip height, default 24, 36 = taskbar build)

Environment: TITLEBAR_TEST_CACHE (cache dir), TB_DISPLAY_NUM (default 99),
TB_SCREEN (default 1280x1024x24), TB_KEEP_CONFIG=1 (keep VLC's config on start),
TB_INSTANCE (default "default"; separate pid files / config / shots per name),
TB_VLC_ARGS (extra VLC options for `start`, split on spaces, e.g. "--extraintf http").
Several agents at the same time: give each its own TB_INSTANCE and TB_DISPLAY_NUM.
EOF
}

die() { echo "vlc-test: $*" >&2; exit 1; }

[ -f "$ROOT/.extracted-ok" ] || die "test environment missing; run tools/setup-test-env.sh first"
mkdir -p "$RUN" "$SHOTS"
use_test_env

# ---------- process helpers ----------

# is_ours <pidfile> <program name>: the stored PID is alive and is that program
is_ours() {
    [ -f "$1" ] || return 1
    local pid
    pid="$(cat "$1")"
    [ -n "$pid" ] && [ "$(cat "/proc/$pid/comm" 2>/dev/null || true)" = "$2" ]
}

# stop_ours <pidfile> <program name>: SIGTERM, wait up to 10 s, then SIGKILL
stop_ours() {
    is_ours "$1" "$2" || { rm -f "$1"; return 0; }
    local pid i
    pid="$(cat "$1")"
    kill "$pid" 2>/dev/null || true
    for i in $(seq 1 50); do
        [ -d "/proc/$pid" ] || break
        sleep 0.2
    done
    [ -d "/proc/$pid" ] && kill -9 "$pid" 2>/dev/null || true
    rm -f "$1"
}

xvfb_start() {
    if is_ours "$RUN/xvfb.pid" Xvfb; then return 0; fi
    # Another X server (maybe another agent's) may own the display: never share it.
    if [ -e "/tmp/.X$DISPLAY_NUM-lock" ] || [ -e "/tmp/.X11-unix/X$DISPLAY_NUM" ]; then
        die "display :$DISPLAY_NUM is in use by another X server; pick another with TB_DISPLAY_NUM=<n>"
    fi
    # Xvfb runs xkbcomp from /usr/bin, which is not installed here: overlay
    # /usr/bin with a directory that has it (inside a user namespace, no root).
    # unshare and sh exec into Xvfb, so $! is Xvfb's own PID.
    # Each instance gets its own overlay directories.
    rm -rf "$RUN/overlay"
    mkdir -p "$RUN/overlay/up" "$RUN/overlay/work"
    cp "$ROOT/usr/bin/xkbcomp" "$RUN/overlay/up/xkbcomp"
    unshare -Urm sh -c "mount -t overlay overlay -o lowerdir=/usr/bin,upperdir=$RUN/overlay/up,workdir=$RUN/overlay/work /usr/bin && exec Xvfb :$DISPLAY_NUM -screen 0 $SCREEN -nolisten tcp" >"$RUN/xvfb.log" 2>&1 &
    echo $! >"$RUN/xvfb.pid"
    local i
    for i in $(seq 1 50); do
        # (the process name is still "unshare"/"sh" for a moment, so test liveness only)
        kill -0 "$(cat "$RUN/xvfb.pid")" 2>/dev/null || die "Xvfb exited at startup, see $RUN/xvfb.log"
        xdotool getdisplaygeometry >/dev/null 2>&1 && return 0
        sleep 0.2
    done
    die "Xvfb did not come up, see $RUN/xvfb.log"
}

vlc_pid() {
    is_ours "$RUN/vlc.pid" vlc || die "VLC is not running (start it first)"
    cat "$RUN/vlc.pid"
}

# main_window: X window id of the skin's main window.
# VLC creates one X window per skin window (main, plus hidden ones), so pick
# the visible one with the largest area.
main_window() {
    local pid w best="" area bestarea=0 X Y WIDTH HEIGHT
    pid="$(vlc_pid)"
    for w in $(xdotool search --onlyvisible --pid "$pid" 2>/dev/null); do
        eval "$(xdotool getwindowgeometry --shell "$w" 2>/dev/null)" || continue
        area=$((WIDTH * HEIGHT))
        if [ "$area" -gt "$bestarea" ]; then best="$w"; bestarea="$area"; fi
    done
    [ -n "$best" ] || die "no visible VLC window found"
    echo "$best"
}

# win_origin: sets WX WY WW WH for the main window
win_origin() {
    local w X Y WIDTH HEIGHT
    w="$(main_window)"
    eval "$(xdotool getwindowgeometry --shell "$w")"
    WX=$X; WY=$Y; WW=$WIDTH; WH=$HEIGHT
}

# ---------- commands ----------

cmd_start() {
    [ $# -ge 1 ] || die "usage: start <vlt> [files...]"
    local vlt="$1"; shift
    [ -f "$vlt" ] || die "no such skin file: $vlt"
    vlt="$(realpath "$vlt")"
    local files=("$@")
    if [ ${#files[@]} -eq 0 ]; then
        files=("$AUDIO/song1.wav" "$AUDIO/song2.wav" "$AUDIO/song3.wav")
    fi
    stop_ours "$RUN/vlc.pid" vlc
    xvfb_start
    [ -n "${TB_KEEP_CONFIG:-}" ] || rm -rf "$XDG_CONFIG_HOME/vlc"
    local extra=()
    [ -z "${TB_VLC_ARGS:-}" ] || read -ra extra <<<"$TB_VLC_ARGS"   # extra VLC options, split on spaces
    vlc --intf skins2 --skins2-last="$vlt" --aout dummy --no-video --no-media-library \
        --no-video-title-show -v ${extra[@]+"${extra[@]}"} "${files[@]}" >"$RUN/vlc.log" 2>&1 &
    echo $! >"$RUN/vlc.pid"
    local i
    for i in $(seq 1 75); do
        is_ours "$RUN/vlc.pid" vlc || die "VLC exited at startup, see $RUN/vlc.log"
        [ -n "$(xdotool search --onlyvisible --pid "$(cat "$RUN/vlc.pid")" 2>/dev/null)" ] && break
        sleep 0.2
    done
    sleep 1                      # let the skin finish drawing
    xdotool mousemove 5 5        # keep the pointer off the skin (no hover state)
    win_origin
    echo "vlc started: pid $(cat "$RUN/vlc.pid"), window at $WX,$WY size ${WW}x${WH}, log $RUN/vlc.log"
}

cmd_shot() {
    [ $# -ge 1 ] || die "usage: shot <name> [x,y,w,h]"
    local name="$1" crop="${2:-}"
    local ppm="$RUN/$name.ppm" png="$SHOTS/$name.png"
    if [ -z "$crop" ]; then
        if is_ours "$RUN/vlc.pid" vlc; then
            win_origin
            crop="$WX,$WY,$WW,$WH"
        fi
    fi
    import-im6.q16 -window root "ppm:$ppm"
    "$VENV/bin/python" - "$ppm" "$png" "$crop" <<'PY'
import sys
from PIL import Image
src, dst, crop = sys.argv[1:4]
im = Image.open(src)
if crop:
    x, y, w, h = [int(v) for v in crop.split(",")]
    im = im.crop((max(x, 0), max(y, 0), min(x + w, im.width), min(y + h, im.height)))
im.save(dst)
PY
    rm -f "$ppm"
    echo "$png"
}

cmd_click() {
    [ $# -eq 2 ] || die "usage: click <x> <y>"
    win_origin
    xdotool mousemove $((WX + $1)) $((WY + $2))
    sleep 0.15
    xdotool click 1
    sleep 0.5
}

cmd_drag() {
    [ $# -eq 4 ] || die "usage: drag <x> <y> <dx> <dy>"
    win_origin
    local x=$((WX + $1)) y=$((WY + $2)) i
    xdotool mousemove "$x" "$y"
    sleep 0.15
    xdotool mousedown 1
    for i in 1 2 3 4 5 6 7 8 9 10; do
        xdotool mousemove $((x + $3 * i / 10)) $((y + $4 * i / 10))
        sleep 0.05
    done
    xdotool mouseup 1
    sleep 0.5
}

cmd_geometry() {
    win_origin
    echo "$WX $WY $WW $WH"
}

# skin_scale: scale in percent of the running skin (from VLC-Amp-<n>.vlt,
# VLC-Amp-taskbar-<n>.vlt or VLC-Amp-bar<h>-<n>.vlt on VLC's command line),
# else TB_SCALE, else 100
skin_scale() {
    local n
    n="$(tr '\0' '\n' <"/proc/$(vlc_pid)/cmdline" | sed -n 's/.*VLC-Amp-\(taskbar-\|bar[0-9]*-\)\{0,1\}\([0-9]*\)\.vlt$/\2/p')"
    echo "${n:-${TB_SCALE:-100}}"
}

# skin_bar: strip height in logical px of the running skin: 24, 36 for
# VLC-Amp-taskbar-<n>.vlt, <h> for VLC-Amp-bar<h>-<n>.vlt (as in the generator)
skin_bar() {
    local f
    f="$(tr '\0' '\n' <"/proc/$(vlc_pid)/cmdline" | sed -n 's/.*\/\(VLC-Amp-[^/]*\.vlt\)$/\1/p')"
    case "$f" in
        VLC-Amp-taskbar-*) echo 36 ;;
        VLC-Amp-bar[0-9]*-*) f="${f#VLC-Amp-bar}"; echo "${f%%-*}" ;;
        *) echo 24 ;;
    esac
}

cmd_shape() {
    "$VENV/bin/python" "$HERE/xshape.py" "$DISPLAY" "$(main_window)" $(($(skin_bar) * $(skin_scale) / 100)) "$@"
}

# quit: VLC only writes skins2-config on a clean exit, so use the skin's own
# quit button. It is in the full player (top right); expand the strip first.
# Button positions are the generator's 100 % values times the scale.
cmd_quit() {
    local pct bar bar_at_bottom full pid i
    pct="$(skin_scale)"
    bar="$(skin_bar)"
    pid="$(vlc_pid)"
    p() { echo $(($1 * pct / 100)); }     # scale a 100 % pixel value
    win_origin
    eval "$(cmd_shape --state)"            # sets bar_at_bottom and full
    if [ "$full" = 0 ]; then
        # expand button of the strip
        if [ "$bar_at_bottom" = 1 ]; then cmd_click "$(p 27)" $((WH - $(p "$bar") + $(p "$bar") / 2))
        else cmd_click "$(p 27)" $(($(p "$bar") / 2)); fi
        eval "$(cmd_shape --state)"
        [ "$full" = 1 ] || die "could not expand the strip to the full player"
    fi
    # quit button of the full player (122 px tall)
    if [ "$bar_at_bottom" = 1 ]; then cmd_click $((WW - $(p 13))) $((WH - $(p 122) + $(p 11)))
    else cmd_click $((WW - $(p 13))) "$(p 11)"; fi
    for i in $(seq 1 50); do
        [ -d "/proc/$pid" ] || break
        sleep 0.2
    done
    if [ -d "/proc/$pid" ]; then die "VLC did not exit after clicking quit (pid $pid still running; use stop)"; fi
    rm -f "$RUN/vlc.pid"
    # skins2 stores its window state as the option skins2-config in vlcrc
    echo "vlc exited; saved state in $XDG_CONFIG_HOME/vlc/vlcrc:"
    grep '^skins2-config' "$XDG_CONFIG_HOME/vlc/vlcrc" || echo "  (no skins2-config line: VLC did not save)"
}

cmd_build() {
    local scale="${1:-1}" bar="${2:-24}" out="$CACHE/skins" pct kind=""
    mkdir -p "$out"
    "$VENV/bin/python" "$HERE/../source/build_skin.py" --scale "$scale" --bar-height "$bar" --out "$out" >&2
    pct="$(awk "BEGIN{printf \"%d\", $scale * 100 + 0.5}")"
    if [ "$bar" = 36 ]; then kind=taskbar-; elif [ "$bar" != 24 ]; then kind="bar$bar-"; fi
    echo "$out/VLC-Amp-$kind$pct.vlt"
}

[ $# -ge 1 ] || { usage; exit 1; }
cmd="$1"; shift
case "$cmd" in
    start)      cmd_start "$@" ;;
    shot)       cmd_shot "$@" ;;
    click)      cmd_click "$@" ;;
    drag)       cmd_drag "$@" ;;
    park)       xdotool mousemove 0 0 ;;   # pointer off the skin: no hover state, tooltips go away
    geometry)   cmd_geometry ;;
    shape)      cmd_shape "$@" ;;
    quit)       cmd_quit ;;
    stop)       stop_ours "$RUN/vlc.pid" vlc ;;
    xvfb-stop)  stop_ours "$RUN/xvfb.pid" Xvfb ;;
    build)      cmd_build "$@" ;;
    -h|--help|help) usage ;;
    *)          usage; exit 1 ;;
esac
