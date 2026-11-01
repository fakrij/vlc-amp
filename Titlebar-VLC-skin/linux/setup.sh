#!/bin/sh
# linux/setup.sh - set VLC up for the Titlebar skin on Linux. Counterpart of
# taskbar/Setup.cmd (Windows). Works with VLC from the distro's package,
# Flatpak (org.videolan.VLC) or Snap, on any distro and desktop.
#
#   linux/setup.sh [options]          set up (close VLC first)
#   linux/setup.sh --uninstall        undo it
#
# Options:
#   --yes, -y             answer yes to every question (default player too)
#   --scale N             use Titlebar-N.vlt (100, 125, 150 or 200; any number
#                         picks the nearest; 1.5 means 150) instead of detecting
#                         the display scale
#   --default-player      make "VLC (Titlebar)" the default app for audio files
#   --no-default-player   do not touch the default app
#   --vlc native|flatpak|snap
#                         which VLC to set up when more than one is installed
#   --pin-autostart       start VLC pinned (always on top) at every login: runs
#                         linux/titlebar-pin.py --install-autostart (only if that
#                         file exists); --no-pin-autostart skips the question
#   --no-web              do not switch on VLC's local web interface
#   --ignore-running      do not refuse when a VLC process is running (VLC
#                         overwrites vlcrc when it exits: not recommended)
#   --uninstall           restore vlcrc from the backup, remove what was added
#   -h, --help            this text
#
# Needs only POSIX sh, awk, sed, grep, cp, mv, mkdir and tr. Optional: xdg-mime,
# update-desktop-database (default player), xrdb, gsettings, kreadconfig5/6
# (scale detection), flatpak, snap (detection). See README.md ("Linux").
#
# Test overrides: HOME, XDG_CONFIG_HOME, XDG_DATA_HOME, XDG_STATE_HOME and
# XDG_DATA_DIRS are honoured, so the script can run against a private home.

set -eu

APP_ID_FLATPAK="org.videolan.VLC"
DESKTOP_ID="vlc-titlebar.desktop"
MARKER="X-Titlebar-Skin=1"
HTTP_PORT=48080

ROOT=$(cd "$(dirname "$0")/.." && pwd -P)

say()  { printf '%s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }
usage() { sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'; }

# ------------------------------------------------------------------ options

UNINSTALL=0
YES=0
SCALE_ARG=""
DEFAULT_PLAYER=ask        # ask | yes | no
PIN_AUTOSTART=ask         # ask | yes | no
WANT_FLAVOR=""
WEB=1
IGNORE_RUNNING=0

while [ $# -gt 0 ]; do
    case "$1" in
        --uninstall)          UNINSTALL=1 ;;
        --yes|-y)             YES=1 ;;
        --scale)              [ $# -ge 2 ] || die "--scale needs a number"; SCALE_ARG="$2"; shift ;;
        --scale=*)            SCALE_ARG="${1#--scale=}" ;;
        --default-player)     DEFAULT_PLAYER=yes ;;
        --no-default-player)  DEFAULT_PLAYER=no ;;
        --pin-autostart)      PIN_AUTOSTART=yes ;;
        --no-pin-autostart)   PIN_AUTOSTART=no ;;
        --vlc)                [ $# -ge 2 ] || die "--vlc needs native, flatpak or snap"; WANT_FLAVOR="$2"; shift ;;
        --vlc=*)              WANT_FLAVOR="${1#--vlc=}" ;;
        --no-web)             WEB=0 ;;
        --ignore-running)     IGNORE_RUNNING=1 ;;
        -h|--help)            usage; exit 0 ;;
        *)                    usage >&2; die "unknown option: $1" ;;
    esac
    shift
done

case "$WANT_FLAVOR" in ""|native|flatpak|snap) ;; *) die "--vlc must be native, flatpak or snap" ;; esac
case "$SCALE_ARG" in *[!0-9.]*|"."*|*"."*"."*) die "--scale needs a number such as 150" ;; esac
[ -n "${HOME:-}" ] || die "HOME is not set"

# ----------------------------------------------------------- XDG directories

# A relative or empty XDG path is invalid per the spec: use the default instead.
xdg_dir() { # $1 value, $2 default
    case "$1" in /*) printf '%s' "$1" ;; *) printf '%s' "$2" ;; esac
}
CONFIG_HOME=$(xdg_dir "${XDG_CONFIG_HOME:-}" "$HOME/.config")
DATA_HOME=$(xdg_dir "${XDG_DATA_HOME:-}" "$HOME/.local/share")
STATE_HOME=$(xdg_dir "${XDG_STATE_HOME:-}" "$HOME/.local/state")
APPS_DIR="$DATA_HOME/applications"
DESKTOP_FILE="$APPS_DIR/$DESKTOP_ID"
STATE_FILE="$STATE_HOME/titlebar-vlc-skin/linux-setup.state"

# ------------------------------------------------------------------- state
# Plain "key=value" lines (lua= and mime= may repeat), so --uninstall knows
# exactly what was changed: flavor, rc, rc_created, desktop, lua, mime.
#   mime=<type> <desktop id that was the default before, or - for none>

ST_FLAVOR=""; ST_RC=""; ST_RC_CREATED=0; ST_DESK=""; ST_LUA=""; ST_MIME=""; ST_PIN=""
NL='
'

state_values() { sed -n "s/^$1=//p" "$STATE_FILE"; }

load_state() {
    [ -f "$STATE_FILE" ] || return 0
    ST_FLAVOR=$(state_values flavor | tail -n 1)
    ST_RC=$(state_values rc | tail -n 1)
    ST_RC_CREATED=$(state_values rc_created | tail -n 1)
    ST_DESK=$(state_values desktop | tail -n 1)
    ST_LUA=$(state_values lua)
    ST_MIME=$(state_values mime)
    ST_PIN=$(state_values pin | tail -n 1)
    [ -n "$ST_RC_CREATED" ] || ST_RC_CREATED=0
}

write_state() {
    mkdir -p "$(dirname "$STATE_FILE")"
    {
        echo "flavor=$ST_FLAVOR"
        echo "rc=$ST_RC"
        echo "rc_created=$ST_RC_CREATED"
        [ -z "$ST_PIN" ] || echo "pin=$ST_PIN"
        [ -z "$ST_DESK" ] || echo "desktop=$ST_DESK"
        if [ -n "$ST_LUA" ]; then printf '%s\n' "$ST_LUA" | sed 's/^/lua=/'; fi
        if [ -n "$ST_MIME" ]; then printf '%s\n' "$ST_MIME" | sed 's/^/mime=/'; fi
    } >"$STATE_FILE.new"
    mv "$STATE_FILE.new" "$STATE_FILE"
}

# ------------------------------------------------------------ small helpers

# ask_yes <question>: 0 = yes. --yes answers yes; with no terminal the answer is no.
ask_yes() {
    [ "$YES" = 1 ] && return 0
    [ -t 0 ] || return 1
    printf '%s [Y/n] ' "$1"
    ans=""
    read -r ans || ans=n
    case "$ans" in ""|y|Y|yes|YES|Yes) return 0 ;; esac
    return 1
}

# Is a VLC of this user running? (VLC rewrites vlcrc when it exits.)
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

refuse_if_running() {
    [ "$IGNORE_RUNNING" = 1 ] && return 0
    if vlc_running; then
        die "VLC is running. Close it first and run this again (VLC rewrites its settings file when it exits)."
    fi
}

# ------------------------------------------------------- VLC flavor + paths

FLAVOR=""; RC=""; LUA_DIR=""

# Fills FOUND with the installed flavors, in the order native flatpak snap.
detect_flavors() {
    FOUND=""
    snap_seen=0
    vp=$(command -v vlc 2>/dev/null || true)
    case "$vp" in
        "") ;;
        /snap/*|/var/lib/snapd/*) snap_seen=1 ;;     # snapd puts /snap/bin in PATH
        *) FOUND="native" ;;
    esac
    if command -v flatpak >/dev/null 2>&1 && flatpak info "$APP_ID_FLATPAK" >/dev/null 2>&1; then
        FOUND="${FOUND:+$FOUND }flatpak"
    fi
    if [ "$snap_seen" = 1 ] || { command -v snap >/dev/null 2>&1 && snap list vlc >/dev/null 2>&1; }; then
        FOUND="${FOUND:+$FOUND }snap"
    fi
}

# Sets RC and LUA_DIR for $FLAVOR.
set_flavor_paths() {
    case "$FLAVOR" in
        native)
            # VLC: config_GetUserDir(VLC_CONFIG_DIR) / VLC_DATA_DIR (XDG_*_HOME) + "/vlc"
            RC="$CONFIG_HOME/vlc/vlcrc"
            LUA_DIR="$DATA_HOME/vlc/lua/intf"
            ;;
        flatpak)
            # Flatpak sets XDG_CONFIG_HOME / XDG_DATA_HOME inside the sandbox to these
            RC="$HOME/.var/app/$APP_ID_FLATPAK/config/vlc/vlcrc"
            LUA_DIR="$HOME/.var/app/$APP_ID_FLATPAK/data/vlc/lua/intf"
            ;;
        snap)
            # VLC's snap wrapper runs `vlc --config=$SNAP_USER_COMMON/vlcrc` (extras/package/snap/
            # vlc-snap-wrapper.sh). Older snaps used .config/vlc below common/ or the revision folder.
            RC="$HOME/snap/vlc/common/vlcrc"
            for c in "$HOME/snap/vlc/common/vlcrc" "$HOME/snap/vlc/common/.config/vlc/vlcrc" \
                     "$HOME/snap/vlc/current/.config/vlc/vlcrc"; do
                if [ -f "$c" ]; then RC="$c"; break; fi
            done
            # UNVERIFIED: snapd's XDG_DATA_HOME for a snap is <SNAP_USER_DATA>/.local/share
            LUA_DIR="$HOME/snap/vlc/current/.local/share/vlc/lua/intf"
            ;;
    esac
}

choose_flavor() {
    if [ -n "$WANT_FLAVOR" ]; then
        FLAVOR="$WANT_FLAVOR"
        detect_flavors
        case " $FOUND " in *" $FLAVOR "*) ;; *) warn "$FLAVOR VLC was not detected; going on because of --vlc $FLAVOR" ;; esac
        return 0
    fi
    detect_flavors
    # shellcheck disable=SC2086
    set -- $FOUND
    case $# in
        0) die "VLC was not found (no vlc command, no Flatpak org.videolan.VLC, no Snap vlc). Install VLC, or use --vlc native|flatpak|snap to set up its settings anyway." ;;
        1) FLAVOR="$1" ;;
        *)
            FLAVOR="$1"
            if [ "$YES" != 1 ] && [ -t 0 ]; then
                say "More than one VLC is installed:"
                i=1; for f in "$@"; do say "  $i) $f"; i=$((i + 1)); done
                printf 'Which one? [1] '
                pick=""; read -r pick || pick=""
                case "$pick" in
                    ""|1) ;;
                    *[!0-9]*) die "not a number: $pick" ;;
                    *) [ "$pick" -ge 1 ] && [ "$pick" -le $# ] || die "no such choice: $pick"
                       eval "FLAVOR=\${$pick}" ;;
                esac
            else
                say "More than one VLC is installed ($FOUND); using $FLAVOR. Pick another with --vlc."
            fi
            ;;
    esac
}

# ----------------------------------------------------------- vlcrc editing
# vlcrc is "key=value" lines, optional "#key=value" commented defaults, and
# "[section]" headers that VLC ignores when reading. Same rules as the Windows
# setup (Set-VlcOption / Set-VlcModule in taskbar/vlc-taskbar.ps1): every line of
# the key (the commented default and any active one) is rewritten, else the key
# is added to its section. Everything works on a temporary copy ($WORK).

WORK=""
cleanup() { [ -z "$WORK" ] || rm -f "$WORK" "$WORK.new"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

# rc_edit <set|module> <section> <key> <value>: values go through the
# environment so that awk does not interpret backslashes in them.
rc_edit() {
    TB_MODE="$1" TB_SEC="$2" TB_KEY="$3" TB_VAL="$4" awk '
    function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t\r]+$/, "", s); return s }
    function key_at(s,   t) {      # 1 if the line is "key=..." or "#key=..."
        t = s
        sub(/^[ \t]+/, "", t)
        if (substr(t, 1, 1) == "#") { t = substr(t, 2); sub(/^[ \t]+/, "", t) }
        if (substr(t, 1, klen) == key "=") return 1
        return 0
    }
    BEGIN { mode = ENVIRON["TB_MODE"]; sec = ENVIRON["TB_SEC"]; key = ENVIRON["TB_KEY"]
            val = ENVIRON["TB_VAL"]; klen = length(key) + 1 }
    { line[NR] = $0 }
    END {
        n = NR
        if (mode == "module") {    # merge into the colon-separated list, keeping what is there
            cnt = 0
            for (i = 1; i <= n; i++) {
                t = line[i]; sub(/^[ \t]+/, "", t)
                if (substr(t, 1, klen) != key "=") continue      # active lines only
                m = split(substr(t, klen + 1), parts, ":")
                for (j = 1; j <= m; j++) {
                    p = trim(parts[j])
                    if (p != "" && !(p in seen)) { seen[p] = 1; order[++cnt] = p }
                }
            }
            if (!(val in seen)) order[++cnt] = val
            val = ""
            for (j = 1; j <= cnt; j++) val = val (j > 1 ? ":" : "") order[j]
        }
        found = 0
        for (i = 1; i <= n; i++) if (key_at(line[i])) { line[i] = key "=" val; found = 1 }
        if (!found) {
            head = 0
            for (i = 1; i <= n; i++)
                if (line[i] == "[" sec "]" || index(line[i], "[" sec "] ") == 1) { head = i; break }
            if (!head) {
                if (n > 0) line[++n] = ""
                line[++n] = "[" sec "]"
                line[++n] = key "=" val
            } else {
                e = head + 1
                while (e <= n && substr(line[e], 1, 1) != "[") e++
                while (e - 1 > head && line[e - 1] == "") e--      # stay above the blank line before the next section
                for (i = n; i >= e; i--) line[i + 1] = line[i]
                line[e] = key "=" val
                n++
            }
        }
        for (i = 1; i <= n; i++) print line[i]
    }' "$WORK" >"$WORK.new"
    mv "$WORK.new" "$WORK"
}

# rc_get <key>: value of the last active "key=" line (commented defaults do not count), may be empty
rc_get() {
    TB_KEY="$1" awk '
    BEGIN { key = ENVIRON["TB_KEY"]; klen = length(key) + 1 }
    { t = $0; sub(/^[ \t]+/, "", t); if (substr(t, 1, klen) == key "=") v = substr(t, klen + 1) }
    END { sub(/^[ \t]+/, "", v); sub(/[ \t\r]+$/, "", v); print v }' "$WORK"
}

# The skin's video window must be "shown" in the saved window state (skins2-config), or skins2
# never attaches a video to it: a state saved by an older skin has no entry for it, and VLC
# saves the shrunk title bar layout. $1 = display scaling in percent. Needs a saved state.
repair_video_window() {
    awk -v pct="$1" '
    /^skins2-config=./ {
        w = int(556 * pct / 100 + 0.5); h = int(386 * pct / 100 + 0.5)
        if (index($0, "[\"video\" ") == 0) $0 = $0 "[\"video\" \"video-l\" 600 300 " w " " h " 1]"
        while (match($0, /\["video" "video-min" -?[0-9]+ -?[0-9]+ [0-9]+ [0-9]+ [01]\]/)) {
            e = substr($0, RSTART, RLENGTH); split(e, f, " ")
            $0 = substr($0, 1, RSTART - 1) "[\"video\" \"video-l\" " f[3] " " f[4] " " w " " h " 1]" substr($0, RSTART + RLENGTH)
        }
        while (match($0, /\["video" "[^"]*" -?[0-9]+ -?[0-9]+ -?[0-9]+ -?[0-9]+ 0\]/)) {
            $0 = substr($0, 1, RSTART + RLENGTH - 3) "1]" substr($0, RSTART + RLENGTH)
        }
    }
    { print }' "$WORK" >"$WORK.new" && mv "$WORK.new" "$WORK"
}

# ---------------------------------------------------------- scale detection

NOTES=""
note() { NOTES="${NOTES}  $*$NL"; }

# pct_of <ratio>: "1.5" -> 150
pct_of() { awk -v r="$1" 'BEGIN { printf "%d", r * 100 + 0.5 }'; }

# nearest_scale <percent>: nearest of 100 125 150 200
nearest_scale() {
    awk -v p="$1" '
    function d(x) { return x > p ? x - p : p - x }
    BEGIN { n = split("100 125 150 200", a, " "); b = a[1]
            for (i = 2; i <= n; i++) if (d(a[i]) < d(b)) b = a[i]
            print b }'
}

is_number() { case "$1" in ""|*[!0-9.]*|"."*|*"."*"."*) return 1 ;; esac; [ "$1" != "." ]; }

# Collects every readable sign of the display scale into $NOTES and sets
# SCALE_PCT from the first one in this order: GDK_SCALE, QT_SCALE_FACTOR,
# Xft.dpi, KDE ScaleFactor, GNOME scaling-factor, GNOME text-scaling-factor.
detect_scale() {
    SCALE_PCT=""; SCALE_SRC=""
    consider() { # <label> <percent>
        note "$1 -> $2 %"
        if [ -z "$SCALE_PCT" ]; then SCALE_PCT="$2"; SCALE_SRC="$1"; fi
    }
    v="${GDK_SCALE:-}"
    if is_number "$v" && [ "$(pct_of "$v")" -gt 0 ]; then consider "GDK_SCALE=$v" "$(pct_of "$v")"; fi
    v="${QT_SCALE_FACTOR:-}"
    if is_number "$v" && [ "$(pct_of "$v")" -gt 0 ]; then consider "QT_SCALE_FACTOR=$v" "$(pct_of "$v")"; fi
    if [ -n "${DISPLAY:-}" ] && command -v xrdb >/dev/null 2>&1; then
        v=$(xrdb -query 2>/dev/null | sed -n 's/^Xft\.dpi:[[:space:]]*//p' | head -n 1 || true)
        if is_number "$v" && [ "$(pct_of "$v")" -gt 0 ]; then
            consider "Xft.dpi=$v" "$(awk -v d="$v" 'BEGIN { printf "%d", d * 100 / 96 + 0.5 }')"
        fi
    fi
    for k in kreadconfig6 kreadconfig5; do
        if command -v "$k" >/dev/null 2>&1; then
            v=$("$k" --group KScreen --key ScaleFactor 2>/dev/null || true)
            if is_number "$v" && [ "$(pct_of "$v")" -gt 0 ]; then consider "KDE ScaleFactor=$v" "$(pct_of "$v")"; fi
            break
        fi
    done
    if command -v gsettings >/dev/null 2>&1; then
        v=$(gsettings get org.gnome.desktop.interface scaling-factor 2>/dev/null | awk '{ print $NF }' || true)
        # 0 = automatic, 1 = none: only 2 and up says anything
        if is_number "$v" && [ "$(pct_of "$v")" -gt 100 ]; then consider "GNOME scaling-factor=$v" "$(pct_of "$v")"; fi
        v=$(gsettings get org.gnome.desktop.interface text-scaling-factor 2>/dev/null | awk '{ print $NF }' || true)
        if is_number "$v" && [ "$(pct_of "$v")" -gt 100 ]; then consider "GNOME text-scaling-factor=$v" "$(pct_of "$v")"; fi
    fi
}

# ------------------------------------------------------------ desktop file

# First existing <dir>/applications/<name> over the system data dirs (and the
# usual Flatpak / Snap export dirs, which are not always in XDG_DATA_DIRS).
find_system_desktop() { # <name>...
    dirs="${XDG_DATA_DIRS:-/usr/local/share:/usr/share}:/usr/local/share:/usr/share:/var/lib/flatpak/exports/share:$HOME/.local/share/flatpak/exports/share:/var/lib/snapd/desktop"
    oldifs=$IFS; IFS=:
    for d in $dirs; do
        [ -n "$d" ] || continue
        for n in "$@"; do
            if [ -f "$d/applications/$n" ]; then IFS=$oldifs; printf '%s' "$d/applications/$n"; return 0; fi
        done
    done
    IFS=$oldifs
    return 1
}

FALLBACK_MIMES="audio/mpeg;audio/x-mpeg;audio/mp4;audio/aac;audio/flac;audio/x-flac;audio/ogg;audio/x-vorbis+ogg;audio/x-opus+ogg;audio/x-wav;audio/wav;audio/x-ms-wma;audio/x-matroska;audio/webm;audio/x-musepack;audio/x-ape;audio/x-m4a;audio/mpegurl;audio/x-mpegurl;audio/x-scpls;"

# Copy of the system launcher named "VLC (Titlebar)" with --no-media-library in
# every Exec (the `vlc` program always adds --media-library before its own
# arguments, bin/vlc.c, which beats media-library=0 in vlcrc). Prints the MimeType
# list it based the copy on.
SYS_DESKTOP=""
make_desktop() {
    case "$FLAVOR" in
        native)  names="vlc.desktop" ;;
        flatpak) names="$APP_ID_FLATPAK.desktop" ;;
        snap)    names="vlc_vlc.desktop vlc.desktop" ;;
    esac
    SYS_DESKTOP=""
    # A follow-system-theme.sh --install wrap on the old file: remembered, re-applied below.
    old_wrap=""
    if [ -f "$DESKTOP_FILE" ]; then
        old_wrap=$(awk '/^Exec=/ && index($0, "follow-system-theme") > 0 && (p = index($0, " --exec ")) > 0 {
            print substr($0, 6, p - 6); exit }' "$DESKTOP_FILE")
    fi
    # shellcheck disable=SC2086
    SYS_DESKTOP=$(find_system_desktop $names) || SYS_DESKTOP=""
    mkdir -p "$APPS_DIR"
    if [ -n "$SYS_DESKTOP" ]; then
        awk '
        BEGIN { print "# Written by the Titlebar skin setup (linux/setup.sh --uninstall removes it)." }
        /^\[/ { grp = $0 }
        grp == "[Desktop Entry]" && /^Name\[[^]]*\]=/ { next }      # translated names would hide ours
        grp == "[Desktop Entry]" && /^Name=/ { print "Name=VLC (Titlebar)"; next }
        grp == "[Desktop Entry]" && /^DBusActivatable=/ { next }    # launchers would skip Exec
        /^Exec=/ {
            s = $0
            if (index(s, "--no-media-library") == 0) {
                best = 0
                m[1] = " --started-from-file"; m[2] = " @@u"; m[3] = " %U"; m[4] = " %u"; m[5] = " %F"; m[6] = " %f"
                for (k = 1; k <= 6; k++) { p = index(s, m[k]); if (p > 0 && (best == 0 || p < best)) best = p }
                if (best > 0) s = substr(s, 1, best - 1) " --no-media-library" substr(s, best)
                else s = s " --no-media-library"
            }
            print s; next
        }
        { print }
        $0 == "[Desktop Entry]" { print "'"$MARKER"'" }
        ' "$SYS_DESKTOP" >"$DESKTOP_FILE.new"
    else
        case "$FLAVOR" in
            native)
                vp=$(command -v vlc 2>/dev/null || echo vlc)
                case "$vp" in *" "*) vp=vlc ;; esac
                exec_line="$vp --no-media-library --started-from-file %U"; icon=vlc ;;
            flatpak) exec_line="flatpak run --file-forwarding $APP_ID_FLATPAK --no-media-library --started-from-file @@u %U @@"
                     icon="$APP_ID_FLATPAK" ;;
            snap)    exec_line="/snap/bin/vlc --no-media-library --started-from-file %U"; icon=vlc ;;
        esac
        warn "no vlc launcher (desktop file) found for $FLAVOR VLC; writing a basic one"
        cat >"$DESKTOP_FILE.new" <<EOF
# Written by the Titlebar skin setup (linux/setup.sh --uninstall removes it).
[Desktop Entry]
$MARKER
Version=1.0
Type=Application
Name=VLC (Titlebar)
GenericName=Media player
Comment=VLC with the Titlebar skin
Exec=$exec_line
Icon=$icon
Terminal=false
Categories=AudioVideo;Audio;Player;
MimeType=$FALLBACK_MIMES
EOF
    fi
    if [ -n "$old_wrap" ]; then
        awk -v pre="Exec=$old_wrap --exec " '
        /^Exec=/ && index($0, "follow-system-theme") == 0 { print pre substr($0, 6); next }
        { print }' "$DESKTOP_FILE.new" >"$DESKTOP_FILE.new2" && mv "$DESKTOP_FILE.new2" "$DESKTOP_FILE.new"
        say "  kept the follow-system-theme.sh wrap on the Exec lines"
    fi
    mv "$DESKTOP_FILE.new" "$DESKTOP_FILE"
    chmod 644 "$DESKTOP_FILE"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
    fi
}

# Audio MIME types the VLC launcher claims (our copy has the same MimeType line).
# inode/directory is left alone on purpose: as the default for folders it would
# open VLC every time a folder is opened in the file manager.
audio_mimes() {
    sed -n 's/^MimeType=//p' "$DESKTOP_FILE" | head -n 1 | tr ';' '\n' | grep '^audio/' || true
}

set_default_player() {
    command -v xdg-mime >/dev/null 2>&1 || { warn "xdg-mime not found: set the default app for audio files in your desktop's settings"; return 0; }
    mimes=$(audio_mimes)
    [ -n "$mimes" ] || { warn "the launcher lists no audio types; default app not changed"; return 0; }
    count=0
    for m in $mimes; do
        prev=$(xdg-mime query default "$m" 2>/dev/null || true)
        have=$(printf '%s\n' "$ST_MIME" | awk -v m="$m" '$1 == m { print "1" }')
        # Remember the previous default ("-" = none); on a second run, when the default is already
        # ours, keep the earlier record (and if there is none, --uninstall just removes our entry).
        if [ "$prev" != "$DESKTOP_ID" ] || [ -z "$have" ]; then
            ST_MIME=$(printf '%s\n' "$ST_MIME" | awk -v m="$m" '$1 != m && NF')
            if [ "$prev" = "$DESKTOP_ID" ]; then prev=""; fi
            ST_MIME="${ST_MIME:+$ST_MIME$NL}$m ${prev:--}"
        fi
        xdg-mime default "$DESKTOP_ID" "$m" 2>/dev/null || warn "xdg-mime could not set $m"
        count=$((count + 1))
    done
    say "  default app for $count audio types: VLC (Titlebar)"
}

# Remove "<mime>=vlc-titlebar.desktop[;]" lines (xdg-mime has no "unset").
drop_default() { # <mime>
    for f in "$CONFIG_HOME"/mimeapps.list "$CONFIG_HOME"/*-mimeapps.list; do
        [ -f "$f" ] || continue
        TB_LINE="$1=$DESKTOP_ID" awk '
        BEGIN { l = ENVIRON["TB_LINE"] }
        $0 == l || $0 == l ";" { next }
        { print }' "$f" >"$f.new" && cat "$f.new" >"$f"
        rm -f "$f.new"
    done
}

# ----------------------------------------------------------------- uninstall

do_uninstall() {
    load_state
    if [ -z "$ST_RC" ]; then
        # no record (setup never ran, or the state file was deleted): work it out again
        say "No record of a setup found; looking for the usual places."
        if [ -n "$WANT_FLAVOR" ]; then FLAVOR="$WANT_FLAVOR"; else detect_flavors; FLAVOR=${FOUND%% *}; fi
        [ -n "$FLAVOR" ] || FLAVOR=native
        set_flavor_paths
        ST_RC="$RC"; ST_FLAVOR="$FLAVOR"; ST_DESK="$DESKTOP_FILE"
    fi
    refuse_if_running

    backup="$ST_RC.before-titlebar"
    if [ -f "$backup" ]; then
        [ ! -f "$ST_RC" ] || cp -p "$ST_RC" "$ST_RC.titlebar-removed"
        cp -p "$backup" "$ST_RC"
        rm -f "$backup"
        say "  vlcrc restored from $backup"
        say "  (the version with your changes since setup: $ST_RC.titlebar-removed)"
    elif [ "$ST_RC_CREATED" = 1 ] && [ -f "$ST_RC" ]; then
        mv "$ST_RC" "$ST_RC.titlebar-removed"
        say "  vlcrc did not exist before setup: moved it to $ST_RC.titlebar-removed (VLC makes a new one)"
    else
        say "  no backup ($backup): vlcrc left as it is"
    fi

    # (first: xdg-mime only reports our launcher as the current default while its file exists)
    if [ -n "$ST_MIME" ] && command -v xdg-mime >/dev/null 2>&1; then
        restored=0
        printf '%s\n' "$ST_MIME" > "$STATE_FILE.mime.tmp"
        while read -r m prev; do
            [ -n "$m" ] || continue
            cur=$(xdg-mime query default "$m" 2>/dev/null || true)
            [ "$cur" = "$DESKTOP_ID" ] || continue          # the user changed it since: leave it
            if [ "$prev" != "-" ] && [ -n "$prev" ]; then
                xdg-mime default "$prev" "$m" 2>/dev/null || true
            else
                drop_default "$m"
            fi
            restored=$((restored + 1))
        done <"$STATE_FILE.mime.tmp"
        rm -f "$STATE_FILE.mime.tmp"
        say "  default app restored for $restored audio types"
    fi

    desk="${ST_DESK:-$DESKTOP_FILE}"
    if [ -f "$desk" ]; then
        if grep -qx "$MARKER" "$desk"; then
            rm -f "$desk"
            say "  removed $desk"
            if command -v update-desktop-database >/dev/null 2>&1; then
                update-desktop-database "$(dirname "$desk")" >/dev/null 2>&1 || true
            fi
        else
            say "  $desk was not written by this setup: left alone"
        fi
    fi

    if [ -n "$ST_LUA" ]; then
        printf '%s\n' "$ST_LUA" | while IFS= read -r f; do
            [ -n "$f" ] && [ -f "$f" ] || continue
            rm -f "$f"
            say "  removed $f"
        done
    fi

    # start-pinned autostart: use the script path recorded by setup, else the one in this repo
    pinner="${ST_PIN:-$ROOT/linux/titlebar-pin.py}"
    if [ -f "$pinner" ] && command -v python3 >/dev/null 2>&1; then
        if python3 "$pinner" --uninstall-autostart >/dev/null 2>&1; then
            [ -z "$ST_PIN" ] || say "  start-pinned autostart removed"
        else
            warn "$pinner --uninstall-autostart failed"
        fi
    fi

    rm -f "$STATE_FILE"
    rmdir "$(dirname "$STATE_FILE")" 2>/dev/null || true
    say "Done. VLC is back to how it was before the Titlebar setup."
    say "(The skin files are still in $ROOT.)"
}

# ---------------------------------------------------------------------- main

if [ "$UNINSTALL" = 1 ]; then
    do_uninstall
    exit 0
fi

# 1. which VLC
load_state
choose_flavor
set_flavor_paths
case "$FLAVOR" in native) vlc_desc="VLC (distro package)" ;; flatpak) vlc_desc="VLC (Flatpak)" ;; snap) vlc_desc="VLC (Snap)" ;; esac
say "Found: $vlc_desc"
say "  settings file: $RC"
# the state file records one VLC: setting up a second one would lose the first one's undo
if [ -n "$ST_RC" ] && [ "$ST_RC" != "$RC" ]; then
    die "already set up for ${ST_FLAVOR:-another} VLC ($ST_RC). Run $0 --uninstall first, then set up $FLAVOR VLC."
fi
refuse_if_running

# 2. which skin file
detect_scale
if [ -n "$SCALE_ARG" ]; then
    # "150" or "1.5" both mean 150 %
    SCALE_PCT=$(awk -v v="$SCALE_ARG" 'BEGIN { if (v < 10) v = v * 100; printf "%d", v + 0.5 }')
    SCALE_SRC="--scale $SCALE_ARG"
elif [ -z "$SCALE_PCT" ]; then
    SCALE_PCT=100; SCALE_SRC="nothing detected, assuming no scaling"
fi
SCALE=$(nearest_scale "$SCALE_PCT")
SKIN="$ROOT/Titlebar-$SCALE.vlt"
[ -f "$SKIN" ] || die "skin file not found: $SKIN"
if [ -n "$NOTES" ]; then say "Display scale detected:"; printf '%s' "$NOTES"; fi
say "  using $SCALE % ($SCALE_SRC): $SKIN"
case "${XDG_SESSION_TYPE:-}${WAYLAND_DISPLAY:+wayland}" in
    *wayland*) say "  note: on a Wayland session the skin runs through XWayland; if it looks too big or small or blurry, try --scale." ;;
esac
if [ "$FLAVOR" = snap ]; then
    case "$SKIN" in
        "$HOME"/*/.*|"$HOME"/.*) warn "the Snap can not read hidden folders: move this folder out of $SKIN's hidden parent." ;;
        "$HOME"/*) ;;
        *) warn "the Snap can only read files under your home folder; move this folder there." ;;
    esac
fi

# 3. vlcrc
WORK=$(mktemp "${TMPDIR:-/tmp}/titlebar-vlcrc.XXXXXX")
rc_existed=0
if [ -f "$RC" ]; then
    rc_existed=1
    cat "$RC" >"$WORK"
    # a vlcrc that an earlier run of this setup created is ours: no backup (--uninstall moves it away)
    if [ "$ST_RC_CREATED" != 1 ] || [ "$ST_RC" != "$RC" ]; then
        ST_RC_CREATED=0
        if [ ! -e "$RC.before-titlebar" ]; then
            cp -p "$RC" "$RC.before-titlebar"
            say "  backup: $RC.before-titlebar"
        fi
    fi
else
    ST_RC_CREATED=1
    say "  $RC does not exist yet: creating it with only our settings (VLC fills in the rest)"
fi

rc_edit set    core   intf "skins2"                                  # skin instead of the normal VLC window
rc_edit set    skins2 skins2-last "$SKIN"
repair_video_window "$SCALE"
rc_edit set    core   one-instance 1                                 # files opened from the file manager go to the
rc_edit set    core   one-instance-when-started-from-file 1          # running player (over D-Bus), no second window
rc_edit set    core   playlist-enqueue 0                             # ... and start playing
rc_edit set    core   media-library 0                                # (the launcher overrides this, see the desktop file below)
# skins2-taskbar (Windows setup) is a Windows-only option: VLC's Linux build does not have it.

if [ "$WEB" = 1 ]; then
    # VLC's local web interface: nothing needs it on Linux yet, it is for the later helpers
    # (as on Windows, where the taskbar helper reads the playing state through it).
    rc_edit module core   extraintf http
    rc_edit set    core   http-host 127.0.0.1                        # this computer only
    rc_edit set    core   http-port "$HTTP_PORT"                     # on an unusual port
    if [ -z "$(rc_get http-password)" ]; then
        pw=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24 || true)
        [ "${#pw}" -ge 16 ] || die "could not read random bytes for the web interface password"
        rc_edit set lua http-password "$pw"                          # (the key lives in vlcrc's [lua] section)
    fi
fi

LUA_SRC="$ROOT/lua/intf/titlebar.lua"
lua_done=0
lua_other=$(rc_get lua-intf)
case "$lua_other" in ""|dummy|titlebar) lua_other="" ;; esac
if [ -n "$lua_other" ]; then
    warn "vlcrc already runs the Lua interface '$lua_other' (lua-intf): the Titlebar Lua extras are not installed"
elif [ -f "$LUA_SRC" ]; then
    mkdir -p "$LUA_DIR"
    for f in "$ROOT"/lua/intf/*.lua; do
        cp "$f" "$LUA_DIR/$(basename "$f")"
        case "$NL$ST_LUA$NL" in *"$NL$LUA_DIR/$(basename "$f")$NL"*) ;; *) ST_LUA="${ST_LUA:+$ST_LUA$NL}$LUA_DIR/$(basename "$f")" ;; esac
    done
    rc_edit module core extraintf luaintf                            # run the script next to the skin
    rc_edit set    lua  lua-intf titlebar
    lua_done=1
fi

# lua/vlcrc-keys.txt: "<section> <key>=<value>" per line (blank lines and # comments
# are skipped); a key is only written when vlcrc has no active, non-empty value for it.
KEYS_FILE="$ROOT/lua/vlcrc-keys.txt"
keys_done=0
if [ "$lua_done" = 1 ] && [ -f "$KEYS_FILE" ]; then
    while IFS= read -r kl || [ -n "$kl" ]; do
        kl=$(printf '%s' "$kl" | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
        case "$kl" in ""|"#"*) continue ;; esac
        ksec=${kl%%[[:space:]]*}
        krest=$(printf '%s' "${kl#"$ksec"}" | sed 's/^[[:space:]]*//')
        case "$krest" in *=*) ;; *) warn "vlcrc-keys.txt: skipped '$kl' (expected: section key=value)"; continue ;; esac
        kkey=${krest%%=*}
        kval=${krest#*=}
        if [ -n "$(rc_get "$kkey")" ]; then continue; fi
        rc_edit set "$ksec" "$kkey" "$kval"
        keys_done=$((keys_done + 1))
    done <"$KEYS_FILE"
fi

mkdir -p "$(dirname "$RC")"
( umask 077; [ "$rc_existed" = 1 ] || : >"$RC" )
cat "$WORK" >"$RC"                                                   # (keeps the owner and mode of an existing file)
ST_FLAVOR="$FLAVOR"; ST_RC="$RC"
write_state
say "  vlcrc updated: skin, one instance, no media library$( [ "$WEB" = 1 ] && printf ', local web interface (127.0.0.1:%s)' "$HTTP_PORT")"
if [ "$lua_done" = 1 ]; then say "  Lua interface script installed in $LUA_DIR (and switched on)"; fi
if [ "$keys_done" -gt 0 ]; then say "  $keys_done extra setting(s) from lua/vlcrc-keys.txt written (only the ones that were unset)"; fi

# 4. launcher without the Media Library, and (optionally) the default player
make_desktop
ST_DESK="$DESKTOP_FILE"
write_state
say "  launcher: $DESKTOP_FILE  (\"VLC (Titlebar)\" in your applications menu)"
[ -z "$SYS_DESKTOP" ] || say "    based on $SYS_DESKTOP"

case "$DEFAULT_PLAYER" in
    yes) want_default=1 ;;
    no)  want_default=0 ;;
    *)
        want_default=0
        if [ "$YES" = 1 ] || [ -t 0 ]; then
            if ask_yes "Make \"VLC (Titlebar)\" the default app for audio files (double-click in the file manager)?"; then want_default=1; fi
        else
            say "  default app for audio files: not changed (no terminal to ask; use --default-player)"
        fi
        ;;
esac
if [ "$want_default" = 1 ]; then
    set_default_player
    write_state
elif [ "$DEFAULT_PLAYER" = no ] || [ -t 0 ]; then
    say "  default app for audio files: not changed. The normal VLC launcher still shows the Media Library"
    say "  entry; start \"VLC (Titlebar)\" instead, or run: vlc --no-media-library"
fi

# 5. start pinned (always on top): linux/titlebar-pin.py installs an autostart entry
PIN_SCRIPT="$ROOT/linux/titlebar-pin.py"
if [ -f "$PIN_SCRIPT" ]; then
    if ! command -v python3 >/dev/null 2>&1; then
        say "  start pinned: python3 not found, skipped"
    else
        case "$PIN_AUTOSTART" in
            yes) want_pin=1 ;;
            no)  want_pin=0 ;;
            *)
                want_pin=0
                if [ "$YES" = 1 ] || [ -t 0 ]; then
                    if ask_yes "Start VLC pinned (always on top) at every login?"; then want_pin=1; fi
                else
                    say "  start pinned: not changed (no terminal to ask; use --pin-autostart)"
                fi
                ;;
        esac
        if [ "$want_pin" = 1 ]; then
            if python3 "$PIN_SCRIPT" --install-autostart; then
                ST_PIN="$PIN_SCRIPT"
                write_state
                say "  start pinned: autostart installed (it points at $PIN_SCRIPT: run this setup again if you move this folder)"
            else
                warn "titlebar-pin.py --install-autostart failed; start pinned not set up"
            fi
        fi
    fi
fi

say ""
say "Done. Open a music file or folder with VLC (Titlebar) to start."
say "To undo: close VLC and run: $0 --uninstall"
