#!/usr/bin/env bash
# VClicker installer for Linux.
#
#   ./install-linux.sh                install everything (asks for sudo once)
#   ./install-linux.sh --skip-system  only set up the Python side
#   ./install-linux.sh --uninstall    remove launcher, icons and the venv
#
# Installs the system libraries VClicker needs (XTest + Qt 6 platform plugin),
# creates a private virtualenv, and adds a launcher + desktop entry.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="VClicker"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
ICON_ROOT="${HOME}/.local/share/icons/hicolor"

BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'
RED=$'\033[31m'; BLUE=$'\033[34m'; RESET=$'\033[0m'

say()  { printf '%s\n' "$*"; }
step() { printf '\n%s==>%s %s\n' "$BLUE" "$RESET" "$*"; }
ok()   { printf '%s  ✓%s %s\n' "$GREEN" "$RESET" "$*"; }
warn() { printf '%s  !%s %s\n' "$YELLOW" "$RESET" "$*"; }
die()  { printf '%s  ✗%s %s\n' "$RED" "$RESET" "$*" >&2; exit 1; }

SKIP_SYSTEM=0
UNINSTALL=0
for arg in "$@"; do
    case "$arg" in
        --skip-system|--user) SKIP_SYSTEM=1 ;;
        --uninstall) UNINSTALL=1 ;;
        -h|--help)
            sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) warn "unknown option: $arg" ;;
    esac
done

VENV="${ROOT}/.venv"

if [[ $UNINSTALL -eq 1 ]]; then
    step "Removing VClicker launcher and desktop entry"
    rm -f "${BIN_DIR}/vclicker" "${APP_DIR}/vclicker.desktop"
    for size in 32 48 64 128 256; do
        rm -f "${ICON_ROOT}/${size}x${size}/apps/vclicker.png"
    done
    if [[ -d "$VENV" && "$VENV" == "$ROOT"* ]]; then
        rm -rf "$VENV"
        ok "removed $VENV"
    fi
    ok "VClicker removed (your macros in ~/.config/vclicker were kept)"
    exit 0
fi

# --------------------------------------------------------------------------- #
#  1. distribution
# --------------------------------------------------------------------------- #
FAMILY="linux"
PKG_INSTALL=""
if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    IDS=" ${ID:-} ${ID_LIKE:-} "
    case "$IDS" in
        *debian*|*ubuntu*|*mint*|*pop*) FAMILY="debian" ;;
        *arch*|*manjaro*|*steamos*)     FAMILY="arch" ;;
        *fedora*|*rhel*|*centos*|*rocky*) FAMILY="fedora" ;;
        *suse*|*opensuse*)              FAMILY="suse" ;;
        *alpine*)                       FAMILY="alpine" ;;
    esac
    say "${BOLD}VClicker installer${RESET}  ${DIM}${PRETTY_NAME:-Linux}${RESET}"
fi

if [[ -n "${XDG_SESSION_TYPE:-}" ]]; then
    say "${DIM}session: ${XDG_SESSION_TYPE}${RESET}"
elif [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    say "${DIM}session: wayland${RESET}"
elif [[ -n "${DISPLAY:-}" ]]; then
    say "${DIM}session: x11${RESET}"
fi

# --------------------------------------------------------------------------- #
#  2. system packages
# --------------------------------------------------------------------------- #
if [[ $SKIP_SYSTEM -eq 0 ]]; then
    step "Installing system libraries"
    case "$FAMILY" in
        debian) PKGS="libxtst6 libxcb-cursor0 libxkbcommon-x11-0 libgl1 libegl1 libfontconfig1 libdbus-1-3"
                PKG_INSTALL="sudo apt-get update -qq && sudo apt-get install -y $PKGS" ;;
        arch)   PKGS="libxtst xcb-util-cursor libxkbcommon libxkbcommon-x11 mesa fontconfig dbus"
                PKG_INSTALL="sudo pacman -S --needed --noconfirm $PKGS" ;;
        fedora) PKGS="libXtst xcb-util-cursor libxkbcommon-x11 mesa-libGL mesa-libEGL fontconfig dbus-libs"
                PKG_INSTALL="sudo dnf install -y $PKGS" ;;
        suse)   PKGS="libXtst6 libxcb-cursor0 libxkbcommon-x11-0 Mesa-libGL1 Mesa-libEGL1 fontconfig libdbus-1-3"
                PKG_INSTALL="sudo zypper --non-interactive install $PKGS" ;;
        alpine) PKGS="libxtst xcb-util-cursor libxkbcommon mesa-gl mesa-egl fontconfig dbus-libs"
                PKG_INSTALL="sudo apk add $PKGS" ;;
        *)      warn "unknown distribution — install libXtst + the Qt xcb libraries yourself" ;;
    esac
    if [[ -n "$PKG_INSTALL" ]]; then
        say "${DIM}$PKG_INSTALL${RESET}"
        if bash -c "$PKG_INSTALL"; then
            ok "system libraries installed"
        else
            warn "package install failed — run the command above manually, then re-run with --skip-system"
        fi
    fi
else
    step "Skipping system packages (--skip-system)"
fi

# --------------------------------------------------------------------------- #
#  3. python + venv
# --------------------------------------------------------------------------- #
step "Checking Python"
PYTHON_BIN="${PYTHON:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "python3 not found — install Python 3.10 or newer"
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    die "$("$PYTHON_BIN" -V) is too old — VClicker needs Python 3.10+"
fi
ok "$("$PYTHON_BIN" -V)"

step "Creating the virtualenv"
if [[ ! -d "$VENV" ]]; then
    "$PYTHON_BIN" -m venv "$VENV" || die "could not create $VENV (install python3-venv)"
fi
# shellcheck disable=SC1091
. "$VENV/bin/activate"
python -m pip install --quiet --upgrade pip wheel
ok "virtualenv ready at $VENV"

step "Installing VClicker's Python dependency (PySide6)"
python -m pip install --quiet -r "${ROOT}/requirements.txt"
ok "PySide6 $(python -c 'import PySide6; print(PySide6.__version__)')"

# --------------------------------------------------------------------------- #
#  4. launcher + desktop entry
# --------------------------------------------------------------------------- #
step "Adding launcher"
mkdir -p "$BIN_DIR" "$APP_DIR"
cat > "${BIN_DIR}/vclicker" <<EOF
#!/usr/bin/env bash
# VClicker launcher (generated by install-linux.sh)
exec "${VENV}/bin/python" "${ROOT}/run.py" "\$@"
EOF
chmod +x "${BIN_DIR}/vclicker"
ok "${BIN_DIR}/vclicker"

for size in 32 48 64 128 256; do
    src="${ROOT}/packaging/vclicker-${size}.png"
    if [[ -f "$src" ]]; then
        install -Dm644 "$src" "${ICON_ROOT}/${size}x${size}/apps/vclicker.png"
    fi
done
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -q -t -f "$ICON_ROOT" 2>/dev/null || true

cat > "${APP_DIR}/vclicker.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=VClicker
GenericName=Auto Clicker
Comment=Auto clicker, key holder, macro recorder and global hotkeys
Exec=${BIN_DIR}/vclicker
Icon=${ICON_ROOT}/256x256/apps/vclicker.png
Terminal=false
Categories=Utility;Accessibility;
Keywords=clicker;macro;hotkey;automation;
StartupWMClass=vclicker
EOF
chmod 644 "${APP_DIR}/vclicker.desktop"
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$APP_DIR" 2>/dev/null || true
ok "menu entry: ${APP_NAME} (in your applications list)"

# --------------------------------------------------------------------------- #
#  5. verify
# --------------------------------------------------------------------------- #
step "Checking the input layer"
"${VENV}/bin/python" "${ROOT}/run.py" --check || true

case ":$PATH:" in
    *":${BIN_DIR}:"*) ;;
    *) warn "${BIN_DIR} is not on your PATH — add it to run 'vclicker' from a terminal" ;;
esac

printf '\n%sDone.%s Start it from your applications menu, with %svclicker%s, or %spython run.py%s.\n' \
    "$GREEN" "$RESET" "$BOLD" "$RESET" "$BOLD" "$RESET"
if [[ "${XDG_SESSION_TYPE:-}" == "wayland" || -n "${WAYLAND_DISPLAY:-}" ]]; then
    warn "You are on Wayland: input only reaches X11/XWayland windows."
    warn "For games and native Wayland apps, log out and choose an “X11 / Xorg” session."
fi
