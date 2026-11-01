#!/bin/sh
# linux/follow-system-theme.sh - start VLC with the VLC Amp skin's light or
# dark theme matching the system's colour scheme (BACKLOG item 25, Linux part).
#
#   linux/follow-system-theme.sh [vlc arguments...]    set the theme, then exec vlc
#   linux/follow-system-theme.sh --exec CMD [args...]  same, but exec CMD (what
#                                                      --install puts in the .desktop file)
#   linux/follow-system-theme.sh --install             wrap the Exec lines of
#                                                      ~/.local/share/applications/vlc-amp.desktop
#   linux/follow-system-theme.sh --uninstall           unwrap them
#   linux/follow-system-theme.sh --check               print dark or light and exit
#
# Needs a skin built with two themes, for example
#   python3 source/build_skin.py --themes midnight,paper --out /tmp/skin
# th0 = first theme built, th1 = second. The default is th0 for dark and th1
# for light; change it with --dark-theme N / --light-theme N (or the variables
# TB_DARK_THEME / TB_LIGHT_THEME), for example when the order is paper,midnight.
#
# How: skins2 cannot read the system setting, but VLC saves the visibility of
# each theme's flag window (th0, th1, ...) in the skins2-config line of vlcrc and
# reads it at start. So, only while VLC is NOT running, this script rewrites those
# fields and then starts VLC. If VLC is already running (for example a file
# opened from the file manager is handed to the running player) nothing is
# edited and VLC is started as usual. VLC is never stopped. The theme is read
# once per start; it does not change while VLC runs (use the theme button).
# The very first start (no skins2-config in vlcrc yet) shows th0.
#
# System setting, first that answers: the XDG desktop portal
# (gdbus call ... org.freedesktop.appearance color-scheme), then
# gsettings org.gnome.desktop.interface color-scheme; no answer or "no
# preference" = dark. --scheme dark|light (or TB_SCHEME) forces it.
#
# Test and override variables: VLCRC (path of vlcrc), VLC (program, default vlc);
# HOME / XDG_CONFIG_HOME / XDG_DATA_HOME / XDG_STATE_HOME are honoured. Without
# VLCRC, the vlcrc that linux/setup.sh recorded is used, else the first one found.
# Needs only POSIX sh, awk, grep, sed, mktemp, cmp, mv.

set -eu

DESKTOP_ID="vlc-amp.desktop"
APP_ID_FLATPAK="org.videolan.VLC"
DARK_THEME="${TB_DARK_THEME:-0}"
LIGHT_THEME="${TB_LIGHT_THEME:-1}"
SCHEME="${TB_SCHEME:-}"

say()  { printf '%s\n' "$*"; }
note() { printf 'follow-system-theme: %s\n' "$*" >&2; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }
usage() { sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'; }

SELF=$(cd "$(dirname "$0")" && pwd -P)/$(basename "$0")

xdg_dir() { case "$1" in /*) printf '%s' "$1" ;; *) printf '%s' "$2" ;; esac; }
DATA_HOME=$(xdg_dir "${XDG_DATA_HOME:-}" "${HOME:-}/.local/share")
CONFIG_HOME=$(xdg_dir "${XDG_CONFIG_HOME:-}" "${HOME:-}/.config")
STATE_HOME=$(xdg_dir "${XDG_STATE_HOME:-}" "${HOME:-}/.local/state")
DESKTOP_FILE="$DATA_HOME/applications/$DESKTOP_ID"

# ---------------------------------------------------------------- scheme

# Prints dark or light.
system_scheme() {
    v=""
    if command -v gdbus >/dev/null 2>&1; then
        out=$(gdbus call --session --dest org.freedesktop.portal.Desktop \
              --object-path /org/freedesktop/portal/desktop \
              --method org.freedesktop.portal.Settings.Read \
              org.freedesktop.appearance color-scheme 2>/dev/null) || out=""
        # "(<<uint32 1>>,)": 1 = prefer dark, 2 = prefer light, 0 = no preference
        v=$(printf '%s' "$out" | sed -n 's/.*uint32 \([0-9]\).*/\1/p' | head -n 1)
    fi
    case "$v" in
        1) echo dark; return ;;
        2) echo light; return ;;
        0) echo dark; return ;;
    esac
    if command -v gsettings >/dev/null 2>&1; then
        out=$(gsettings get org.gnome.desktop.interface color-scheme 2>/dev/null) || out=""
        case "$out" in
            *prefer-dark*) echo dark; return ;;
            *prefer-light*) echo light; return ;;
        esac
    fi
    echo dark
}

# ------------------------------------------------------------- vlc state

vlc_running() {
    for p in /proc/[0-9]*; do
        [ -O "$p" ] || continue
        c=$(cat "$p/comm" 2>/dev/null) || continue
        case "$c" in vlc|vlc.bin) return 0 ;; esac
    done
    if command -v flatpak >/dev/null 2>&1 &&
       flatpak ps --columns=application 2>/dev/null | grep -qx "$APP_ID_FLATPAK"; then
        return 0
    fi
    return 1
}

find_vlcrc() {
    if [ -n "${VLCRC:-}" ]; then echo "$VLCRC"; return; fi
    # the vlcrc linux/setup.sh set up (more than one VLC flavor can have a vlcrc)
    c=$(sed -n 's/^rc=//p' "$STATE_HOME/vlc-amp/linux-setup.state" 2>/dev/null | tail -n 1)
    if [ -n "$c" ] && [ -f "$c" ]; then echo "$c"; return; fi
    for c in "$CONFIG_HOME/vlc/vlcrc" \
             "${HOME:-}/.var/app/$APP_ID_FLATPAK/config/vlc/vlcrc" \
             "${HOME:-}/snap/vlc/common/vlcrc" \
             "${HOME:-}/snap/vlc/common/.config/vlc/vlcrc"; do
        if [ -f "$c" ]; then echo "$c"; return; fi
    done
    echo ""
}

# Set the last field of every ["thN" "name" x y a b V] entry of the skins2-config
# line: 1 for theme $2, 0 for the others. Returns 1 when the line or the chosen
# theme's entry is missing (the file is then not touched).
set_theme_in_vlcrc() { # <vlcrc> <theme index>
    rc=$1; want=$2
    grep -q '^skins2-config=' "$rc" 2>/dev/null || return 1
    tmp=$(mktemp "$rc.XXXXXX") || return 1
    awk -v want="$want" '
    /^skins2-config=/ {
        line = $0; out = ""; found = 0
        while (match(line, /\["th[0-9]+" "[^"]*" -?[0-9]+ -?[0-9]+ -?[0-9]+ -?[0-9]+ [01]\]/)) {
            ent = substr(line, RSTART, RLENGTH)
            out = out substr(line, 1, RSTART - 1)
            idx = ent; sub(/^\["th/, "", idx); sub(/".*/, "", idx)
            if (idx == want) found = 1
            sub(/[01]\]$/, ((idx == want) ? "1" : "0") "]", ent)
            out = out ent
            line = substr(line, RSTART + RLENGTH)
        }
        if (!found) bad = 1
        print out line; next
    }
    { print }
    END { exit bad ? 3 : 0 }
    ' "$rc" >"$tmp" || { rm -f "$tmp"; return 1; }
    if cmp -s "$rc" "$tmp"; then rm -f "$tmp"; return 0; fi
    chmod --reference="$rc" "$tmp" 2>/dev/null || true
    mv "$tmp" "$rc"
}

# ------------------------------------------------------------ install

do_install() {
    [ -f "$DESKTOP_FILE" ] || die "$DESKTOP_FILE not found: run linux/setup.sh first"
    case "$SELF" in *\"*|*\\*|*%*|*'$'*|*'`'*) die "the script's path has characters that cannot go into an Exec line: $SELF" ;; esac
    tmp=$(mktemp "$DESKTOP_FILE.XXXXXX")
    awk -v pre="Exec=\"$SELF\" --exec " '
    /^Exec=/ && index($0, "follow-system-theme") == 0 { print pre substr($0, 6); next }
    { print }' "$DESKTOP_FILE" >"$tmp"
    chmod 644 "$tmp"; mv "$tmp" "$DESKTOP_FILE"
    refresh_desktop_db
    say "Wrapped the Exec lines of $DESKTOP_FILE with $SELF"
    grep '^Exec=' "$DESKTOP_FILE" | head -n 2
}

do_uninstall() {
    [ -f "$DESKTOP_FILE" ] || { say "$DESKTOP_FILE not found: nothing to do"; return 0; }
    tmp=$(mktemp "$DESKTOP_FILE.XXXXXX")
    awk '
    /^Exec=/ && index($0, "follow-system-theme") > 0 && (p = index($0, " --exec ")) > 0 {
        print "Exec=" substr($0, p + 8); next }
    { print }' "$DESKTOP_FILE" >"$tmp"
    chmod 644 "$tmp"; mv "$tmp" "$DESKTOP_FILE"
    refresh_desktop_db
    say "Unwrapped the Exec lines of $DESKTOP_FILE"
}

refresh_desktop_db() {
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$(dirname "$DESKTOP_FILE")" >/dev/null 2>&1 || true
    fi
}

# ------------------------------------------------------------- main

MODE=run
while [ $# -gt 0 ]; do
    case "$1" in
        --install)      MODE=install; shift ;;
        --uninstall)    MODE=uninstall; shift ;;
        --check)        MODE=check; shift ;;
        --scheme)       [ $# -ge 2 ] || die "--scheme needs dark or light"; SCHEME=$2; shift 2 ;;
        --scheme=*)     SCHEME=${1#--scheme=}; shift ;;
        --dark-theme)   [ $# -ge 2 ] || die "--dark-theme needs a number"; DARK_THEME=$2; shift 2 ;;
        --light-theme)  [ $# -ge 2 ] || die "--light-theme needs a number"; LIGHT_THEME=$2; shift 2 ;;
        -h|--help)      usage; exit 0 ;;
        *)              break ;;      # the rest belongs to VLC (or is --exec CMD...)
    esac
done

case "$SCHEME" in ""|dark|light) ;; *) die "--scheme must be dark or light" ;; esac
case "$DARK_THEME$LIGHT_THEME" in *[!0-9]*|"") die "theme numbers must be integers" ;; esac
[ -n "${HOME:-}" ] || die "HOME is not set"

case "$MODE" in
    install)   do_install; exit 0 ;;
    uninstall) do_uninstall; exit 0 ;;
    check)     if [ -n "$SCHEME" ]; then say "$SCHEME"; else system_scheme; fi; exit 0 ;;
esac

# What to start: "--exec CMD args" or "vlc args".
if [ "${1:-}" = "--exec" ]; then
    shift
    [ $# -ge 1 ] || die "--exec needs a command"
else
    set -- "${VLC:-vlc}" "$@"
fi

[ -n "$SCHEME" ] || SCHEME=$(system_scheme)
if [ "$SCHEME" = light ]; then theme=$LIGHT_THEME; else theme=$DARK_THEME; fi

if vlc_running; then
    note "VLC is running: theme not changed (VLC would overwrite vlcrc when it exits)"
else
    rc=$(find_vlcrc)
    if [ -z "$rc" ] || [ ! -f "$rc" ]; then
        note "no vlcrc yet: first start shows the first theme"
    elif set_theme_in_vlcrc "$rc" "$theme"; then
        note "system is $SCHEME: theme th$theme"
    else
        note "no skins2-config with th$theme in $rc (start VLC once with a two-theme skin and quit it): theme not changed"
    fi
fi

exec "$@"
