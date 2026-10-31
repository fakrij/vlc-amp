#!/bin/bash
# Sets up a private test environment for running real VLC 3.0.x with the
# skin under Xvfb. No sudo: packages are downloaded with `apt-get download`
# and unpacked with `dpkg-deb -x`; nothing is installed system-wide.
#
# Cache layout (default ~/.cache/titlebar-test, override with TITLEBAR_TEST_CACHE):
#   debs/         downloaded .deb files     root/         extracted packages
#   venv/         Python with Pillow + python-xlib
#   audio/        generated test wavs
#   run-<name>/   per-session files (pid files, logs, VLC home); made by vlc-test.sh
#
# Safe to run again: every step is skipped when its result already exists.
# Set FORCE=1 to redo the extract and venv steps.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/vlc-env.sh"

# Top-level packages; their recursive dependencies are added below.
PACKAGES="vlc-bin vlc-plugin-base vlc-plugin-skins2 xvfb xdotool imagemagick x11-xkb-utils"

say() { echo "setup: $*"; }

for c in apt-get apt-cache dpkg-deb dpkg-query python3 unshare; do
    command -v "$c" >/dev/null 2>&1 || { echo "setup: missing required command: $c" >&2; exit 1; }
done

mkdir -p "$DEBS" "$ROOT" "$AUDIO"

# --- 1. download packages (and their dependencies) that are not installed ---
is_installed() {
    [ "$(dpkg-query -W -f='${db:Status-Status}' "$1" 2>/dev/null || true)" = "installed" ]
}

if [ -n "${FORCE:-}" ] || [ ! -f "$ROOT/.extracted-ok" ]; then
    say "resolving dependencies"
    todo=""
    # Lines starting with a letter or digit are real package names; virtual
    # packages are printed as <name> and skipped.
    for p in $(apt-cache depends --recurse --no-recommends --no-suggests --no-conflicts \
                   --no-breaks --no-replaces --no-enhances $PACKAGES | grep '^[a-z0-9]' | sort -u); do
        is_installed "$p" || todo="$todo $p"
    done
    say "$(echo $todo | wc -w) packages to fetch"

    # apt-get download writes into the current directory. Skip packages that
    # already have a .deb there.
    cd "$DEBS"
    for p in $todo; do
        ls "${p}_"*.deb >/dev/null 2>&1 && continue
        apt-get download "$p" >/dev/null 2>&1 || echo "setup: warning: could not download $p" >&2
    done
    say "$(ls "$DEBS"/*.deb | wc -l) .deb files in $DEBS"

    # --- 2. extract ---
    for f in "$DEBS"/*.deb; do
        dpkg-deb -x "$f" "$ROOT"
    done
    touch "$ROOT/.extracted-ok"
    say "extracted into $ROOT"
else
    say "packages already extracted (FORCE=1 to redo)"
fi

# --- 3. Python venv (system pip is locked by PEP 668) ---
if [ -n "${FORCE:-}" ] || ! "$VENV/bin/python" -c "import PIL, Xlib" 2>/dev/null; then
    say "creating venv"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet pillow python-xlib
else
    say "venv ok"
fi

# --- 4. test audio: three short songs + a 63 minute file (for h:mm:ss) ---
# 8 kHz mono 8-bit, so the 63 minute file is only about 30 MB.
if [ ! -f "$AUDIO/long.wav" ]; then
    say "generating test audio"
    "$VENV/bin/python" - "$AUDIO" <<'PY'
import math, sys, wave

out = sys.argv[1]
RATE = 8000

def write(name, seconds, freq):
    one_second = bytes(int(128 + 40 * math.sin(2 * math.pi * freq * i / RATE)) for i in range(RATE))
    with wave.open("%s/%s.wav" % (out, name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(RATE)
        for _ in range(seconds):
            w.writeframes(one_second)

write("song1", 190, 220)     # 3:10
write("song2", 252, 330)     # 4:12
write("song3", 125, 440)     # 2:05
write("long", 63 * 60, 261)  # 1:03:00 (written last: its existence marks this step done)
PY
fi

# --- 5. smoke test ---
use_test_env
"$ROOT/usr/bin/vlc" --version 2>/dev/null | head -1 || { echo "setup: vlc does not start" >&2; exit 1; }
say "done. Next: tools/vlc-test.sh start <skin.vlt>"
