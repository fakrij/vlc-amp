# Shared settings for setup-test-env.sh and vlc-test.sh. Source this, do not run it.

CACHE="${TITLEBAR_TEST_CACHE:-$HOME/.cache/titlebar-test}"
DEBS="$CACHE/debs"
ROOT="$CACHE/root"
VENV="$CACHE/venv"
AUDIO="$CACHE/audio"

# Everything that belongs to one running test session lives under one
# instance name, so several agents can work at once: give each its own
# TB_INSTANCE and TB_DISPLAY_NUM (the downloaded packages are shared).
INSTANCE="${TB_INSTANCE:-default}"
RUN="$CACHE/run-$INSTANCE"          # pid files, logs
SHOTS="$RUN/shots"
TEST_HOME="$RUN/home"               # VLC's HOME: config starts clean on every `start`

DISPLAY_NUM="${TB_DISPLAY_NUM:-99}"
SCREEN="${TB_SCREEN:-1280x1024x24}"

LIB="$ROOT/usr/lib/x86_64-linux-gnu"

# Call this before running the extracted programs (vlc, xdotool, ImageMagick,
# Qt). It is a function so that sourcing this file changes nothing; setup
# needs the real HOME for apt and pip.
use_test_env() {
    mkdir -p "$TEST_HOME"
    export DISPLAY=":$DISPLAY_NUM"
    export HOME="$TEST_HOME"
    export XDG_CONFIG_HOME="$TEST_HOME/.config"
    export LD_LIBRARY_PATH="$LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export VLC_PLUGIN_PATH="$LIB/vlc/plugins"
    export VLC_DATA_PATH="$ROOT/usr/share/vlc"
    export VLC_LIB_PATH="$LIB/vlc"
    export PATH="$ROOT/usr/bin:$PATH"
    export QT_PLUGIN_PATH="$LIB/qt5/plugins"
    export QT_QPA_PLATFORM_PLUGIN_PATH="$LIB/qt5/plugins/platforms"
    export MAGICK_CONFIGURE_PATH="$ROOT/etc/ImageMagick-6:$ROOT/usr/share/ImageMagick-6"
    export MAGICK_CODER_MODULE_PATH="$LIB/ImageMagick-6.9.12/modules-Q16/coders"
    export MAGICK_FILTER_MODULE_PATH="$LIB/ImageMagick-6.9.12/modules-Q16/filters"
}
