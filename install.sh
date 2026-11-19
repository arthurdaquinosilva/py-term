#!/bin/sh
# :py installer — https://github.com/arthurdaquinosilva/py-term
#
#   curl -fsSL https://raw.githubusercontent.com/arthurdaquinosilva/py-term/main/install.sh | sh
#
# Installs the `:py` command straight from GitHub into its own virtual
# environment, so it never interferes with your projects' packages. Uses pipx
# when available.
#
# Installs the latest release: its wheel is checked against the release's
# SHA256SUMS before anything is installed.
#
# Options (environment variables):
#   PY_TERM_VERSION=0.1.0   install a specific release (default: the latest)
#   PY_TERM_VERSION=main    install the development version from the main branch
#   PY_TERM_NO_PIPX=1       always use the built-in installer, never pipx
#   PY_TERM_INSTALL_DIR     where to put the `:py` command (default: ~/.local/bin)
#
# Uninstall:  curl -fsSL <url> | sh -s -- --uninstall

set -eu

MIN_PY_MINOR=10
PACKAGE="py-term"
REPO="arthurdaquinosilva/py-term"
# The venv sits next to :py's history; uninstalling removes only the venv.
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/py-term"
BIN_DIR="${PY_TERM_INSTALL_DIR:-$HOME/.local/bin}"
VENV="$DATA_DIR/venv"
COMMANDS=":py py-term"

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    accent=$(printf '\033[1;38;2;255;158;100m'); dim=$(printf '\033[2m'); bold=$(printf '\033[1m')
    green=$(printf '\033[38;2;158;206;106m'); red=$(printf '\033[38;2;247;118;142m'); reset=$(printf '\033[0m')
else
    accent=''; dim=''; bold=''; green=''; red=''; reset=''
fi

say()  { printf '%s\n' "$*"; }
step() { printf '%s▸%s %s\n' "$accent" "$reset" "$*"; }
note() { printf '%s  %s%s\n' "$dim" "$*" "$reset"; }
die()  { printf '%s✗ %s%s\n' "$red" "$*" "$reset" >&2; exit 1; }

banner() {
    printf '\n%s   ▄▄ █▀▀▀▄ █   █%s\n'   "$accent" "$reset"
    printf '%s   ▀▀ █▄▄▄▀  ▀▄▀%s\n'     "$accent" "$reset"
    printf '%s   ▄▄ █       █%s\n'      "$accent" "$reset"
    printf '%s   ▀▀ ▀       ▀%s\n\n'   "$accent" "$reset"
    note "a modern interactive Python shell"
    printf '\n'
}

# ── find a suitable python ─────────────────────────────────────────────────

python_ok() {
    [ -x "$(command -v "$1" 2>/dev/null)" ] || return 1
    "$1" -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, $MIN_PY_MINOR) else 1)" 2>/dev/null
}

find_python() {
    for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if python_ok "$candidate"; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

# ── install / uninstall ────────────────────────────────────────────────────

uninstall() {
    removed=0
    if command -v pipx >/dev/null 2>&1 && pipx list 2>/dev/null | grep -q "$PACKAGE"; then
        step "removing the pipx installation"
        pipx uninstall "$PACKAGE" >/dev/null 2>&1 && removed=1
    fi
    if [ -d "$VENV" ]; then
        step "removing $VENV"
        rm -rf "$VENV"
        removed=1
    fi
    for cmd in $COMMANDS; do
        if [ -L "$BIN_DIR/$cmd" ]; then
            rm -f "$BIN_DIR/$cmd"
            removed=1
        fi
    done
    if [ "$removed" -eq 1 ]; then
        printf '%s✓%s :py removed. Your settings and history are untouched:\n' "$green" "$reset"
        note "${XDG_CONFIG_HOME:-$HOME/.config}/py-term  ·  ${XDG_DATA_HOME:-$HOME/.local/share}/py-term"
    else
        say ":py was not installed by this script."
        note "installed into a project's environment? run: pip uninstall $PACKAGE"
    fi
}

# ── what to install ────────────────────────────────────────────────────────

fetch() {  # url dest
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 2 "$1" -o "$2"
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$1" -O "$2"
    else
        return 1
    fi
}

# GitHub redirects /releases/latest to /releases/tag/vX.Y.Z.
latest_version() {
    command -v curl >/dev/null 2>&1 || return 1
    url=$(curl -fsSLI -o /dev/null -w '%{url_effective}' "https://github.com/$REPO/releases/latest" 2>/dev/null) || return 1
    case "$url" in
        */tag/v*) printf '%s' "${url##*/tag/v}" ;;
        *) return 1 ;;
    esac
}

sha256() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d' ' -f1
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | cut -d' ' -f1
    else
        return 1
    fi
}

# Sets SPEC to what pip/pipx should install: a verified release wheel when the
# release publishes one, otherwise a GitHub source archive (no git or package
# index needed).
resolve_spec() {
    want="${PY_TERM_VERSION:-}"
    want="${want#v}"
    if [ -z "$want" ]; then
        want=$(latest_version) || {
            note "could not look up the latest release; installing the main branch"
            want=main
        }
    fi
    if [ "$want" = "main" ]; then
        note "version: main (development)"
        SPEC="$PACKAGE @ https://github.com/$REPO/archive/refs/heads/main.tar.gz"
        return 0
    fi
    note "version: $want"
    WORK_DIR=$(mktemp -d)
    base="https://github.com/$REPO/releases/download/v$want"
    wheel="py_term-$want-py3-none-any.whl"
    if fetch "$base/SHA256SUMS" "$WORK_DIR/SHA256SUMS" 2>/dev/null; then
        fetch "$base/$wheel" "$WORK_DIR/$wheel" || die "could not download $wheel from the v$want release"
        expected=$(awk -v f="$wheel" '$2 == f || $2 == "*" f { print $1 }' "$WORK_DIR/SHA256SUMS")
        [ -n "$expected" ] || die "SHA256SUMS of v$want does not list $wheel"
        actual=$(sha256 "$WORK_DIR/$wheel") || die "need sha256sum or shasum to verify the download"
        [ "$expected" = "$actual" ] || die "checksum mismatch for $wheel (expected $expected, got $actual)"
        note "checksum verified"
        SPEC="$WORK_DIR/$wheel"
    else
        note "v$want publishes no checksums; installing its source archive"
        SPEC="$PACKAGE @ https://github.com/$REPO/archive/refs/tags/v$want.tar.gz"
    fi
}

cleanup() { [ -n "${WORK_DIR:-}" ] && rm -rf "$WORK_DIR"; return 0; }

# The install_* functions set PY_TERM_BIN to the installed command.
install_with_pipx() {
    step "installing with pipx"
    pipx install --force "$SPEC" >/dev/null || die "pipx could not install $PACKAGE"
    PY_TERM_BIN=$(command -v :py 2>/dev/null || printf '%s/:py' "$HOME/.local/bin")
}

install_with_venv() {
    python=$1
    step "installing into $(printf '%s' "$VENV" | sed "s|$HOME|~|")"
    mkdir -p "$DATA_DIR" "$BIN_DIR"
    [ -d "$VENV" ] && rm -rf "$VENV"
    "$python" -m venv "$VENV" || die "could not create a virtual environment (is the python3-venv package installed?)"
    "$VENV/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
    "$VENV/bin/python" -m pip install --quiet "$SPEC" || die "pip could not install $PACKAGE from GitHub"
    for cmd in $COMMANDS; do
        ln -sf "$VENV/bin/$cmd" "$BIN_DIR/$cmd"
    done
    PY_TERM_BIN="$BIN_DIR/:py"
}

path_hint() {
    case ":$PATH:" in
        *":$BIN_DIR:"*) return 0 ;;
    esac
    # shellcheck disable=SC2088  # these are printed for the reader, not expanded
    case "${SHELL:-}" in
        */zsh)  rc="~/.zshrc" ;;
        */bash) rc="~/.bashrc" ;;
        */fish) rc="~/.config/fish/config.fish" ;;
        *)      rc="your shell's startup file" ;;
    esac
    printf '\n%s!%s %s is not on your PATH. Add this line to %s:\n' "$bold" "$reset" "$BIN_DIR" "$rc"
    if [ "${SHELL##*/}" = "fish" ]; then
        printf '\n    fish_add_path %s\n' "$BIN_DIR"
    else
        # shellcheck disable=SC2016  # $PATH must stay literal in the printed line
        printf '\n    export PATH="%s:$PATH"\n' "$BIN_DIR"
    fi
    printf '\nthen open a new terminal.\n'
}

main() {
    case "${1:-}" in
        --uninstall) uninstall; exit 0 ;;
        --help|-h)
            say "usage: install.sh [--uninstall]"
            note "PY_TERM_VERSION=x.y.z  install a specific release (default: the latest)"
            note "PY_TERM_VERSION=main   install the development version"
            note "PY_TERM_NO_PIPX=1      don't use pipx"
            note "PY_TERM_INSTALL_DIR    where to put the command (default: ~/.local/bin)"
            exit 0 ;;
        '') ;;
        *) die "unknown option: $1 (try --help)" ;;
    esac

    banner
    python=$(find_python) || die ":py needs Python 3.$MIN_PY_MINOR or newer — install it from https://python.org and run this again"
    version=$("$python" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')
    note "using $(printf '%s' "$python" | sed "s|$HOME|~|") (Python $version)"

    trap cleanup EXIT
    resolve_spec
    PY_TERM_BIN=''
    if command -v pipx >/dev/null 2>&1 && [ -z "${PY_TERM_NO_PIPX:-}" ]; then
        install_with_pipx
    else
        install_with_venv "$python"
    fi

    [ -x "$PY_TERM_BIN" ] || die "installation finished but $PY_TERM_BIN is missing"
    reported=$("$PY_TERM_BIN" --version 2>/dev/null) || die "$PY_TERM_BIN did not run"

    printf '\n%s✓%s installed %s%s%s\n' "$green" "$reset" "$bold" "$reported" "$reset"
    note "$(printf '%s' "$PY_TERM_BIN" | sed "s|$HOME|~|")"
    path_hint
    printf '\nstart it with %s:py%s — then %s%%help%s for everything it can do.\n' "$bold" "$reset" "$bold" "$reset"
}

main "$@"
