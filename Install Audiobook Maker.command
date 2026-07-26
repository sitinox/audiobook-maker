#!/bin/zsh
set -u

APP_NAME="Audiobook Maker"
VERSION="v1.0.0"
REPOSITORY="https://github.com/sitinox/audiobook-maker"
DEFAULT_SUPPORT_DIR="$HOME/Library/Application Support/Audiobook Maker"
SUPPORT_DIR="${AUDIOBOOK_MAKER_SUPPORT_DIR:-$DEFAULT_SUPPORT_DIR}"
VENV_DIR="${AUDIOBOOK_MAKER_VENV_DIR:-$SUPPORT_DIR/venv}"
BIN_DIR="${AUDIOBOOK_MAKER_BIN_DIR:-$HOME/.local/bin}"
COMMAND_PATH="$BIN_DIR/audiobook"
PROFILE_PATH="${AUDIOBOOK_MAKER_PROFILE_PATH:-$HOME/.zprofile}"
PATH_MARKER_START="# >>> Audiobook Maker managed PATH >>>"
PATH_MARKER_END="# <<< Audiobook Maker managed PATH <<<"
SCRIPT_DIR="${0:A:h}"
SOURCE_SPEC="${AUDIOBOOK_MAKER_SOURCE_SPEC:-}"

say_line() {
    print -r -- "$1"
}

fail() {
    say_line ""
    say_line "INSTALLATION FAILED"
    say_line "$1"
    exit 1
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

ensure_macos() {
    [[ "$(uname -s)" == "Darwin" ]] || fail "Audiobook Maker currently supports macOS only."
}

ensure_homebrew() {
    if command_exists brew; then
        return
    fi

    fail "Homebrew is required to install ffmpeg, Poppler, and Python. Install Homebrew from brew.sh, then run this installer again."
}

ensure_system_dependencies() {
    local missing=()

    command_exists python3 || missing+=("python")
    command_exists ffmpeg || missing+=("ffmpeg")
    command_exists ffprobe || missing+=("ffmpeg")
    command_exists pdftotext || missing+=("poppler")

    if (( ${#missing[@]} == 0 )); then
        return
    fi

    local unique=()
    local dependency
    for dependency in "${missing[@]}"; do
        if [[ " ${unique[*]} " != *" $dependency "* ]]; then
            unique+=("$dependency")
        fi
    done

    say_line "Installing required system tools with Homebrew: ${unique[*]}"
    brew install "${unique[@]}" || fail "Homebrew could not install the required system tools."
}

choose_source_spec() {
    if [[ -n "$SOURCE_SPEC" ]]; then
        print -r -- "$SOURCE_SPEC"
        return
    fi

    if [[ -f "$SCRIPT_DIR/pyproject.toml" && -d "$SCRIPT_DIR/audiobook_maker" ]]; then
        print -r -- "$SCRIPT_DIR"
        return
    fi

    print -r -- "https://github.com/sitinox/audiobook-maker/archive/refs/tags/$VERSION.zip"
}

ensure_profile_path() {
    mkdir -p "$BIN_DIR" || fail "Could not create command directory: $BIN_DIR"

    if [[ ":$PATH:" == *":$BIN_DIR:"* ]]; then
        return
    fi

    touch "$PROFILE_PATH" || fail "Could not update shell profile: $PROFILE_PATH"

    if grep -Fq "$PATH_MARKER_START" "$PROFILE_PATH"; then
        return
    fi

    {
        print -r -- ""
        print -r -- "$PATH_MARKER_START"
        print -r -- 'export PATH="$HOME/.local/bin:$PATH"'
        print -r -- "$PATH_MARKER_END"
    } >> "$PROFILE_PATH" || fail "Could not add Audiobook Maker to PATH."
}

install_package() {
    local source_spec
    source_spec="$(choose_source_spec)"

    mkdir -p "$SUPPORT_DIR" || fail "Could not create application support folder."

    if [[ -d "$VENV_DIR" ]]; then
        say_line "Refreshing the existing Audiobook Maker environment."
    else
        say_line "Creating the Audiobook Maker environment."
        python3 -m venv "$VENV_DIR" || fail "Could not create the Python environment."
    fi

    "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel >/dev/null \
        || fail "Could not prepare the Python environment."

    "$VENV_DIR/bin/python" -m pip install --upgrade "$source_spec" \
        || fail "Could not install Audiobook Maker."
}

install_command() {
    mkdir -p "$BIN_DIR" || fail "Could not create command directory."

    ln -sfn "$VENV_DIR/bin/audiobook" "$COMMAND_PATH" \
        || fail "Could not install the audiobook command."
}

verify_installation() {
    [[ -x "$VENV_DIR/bin/audiobook" ]] \
        || fail "The audiobook command was not created inside the environment."

    local installed_version
    installed_version="$("$VENV_DIR/bin/audiobook" --version 2>/dev/null | tail -n 1)"

    [[ "$installed_version" == "$VERSION" ]] \
        || fail "Version verification failed. Expected $VERSION but found ${installed_version:-nothing}."
}

main() {
    say_line "$APP_NAME Installer"
    say_line "======================"
    say_line "Installing $VERSION."

    ensure_macos

    if [[ "${AUDIOBOOK_MAKER_SKIP_BREW:-0}" != "1" ]]; then
        ensure_homebrew
        ensure_system_dependencies
    fi

    command_exists python3 || fail "Python 3 was not found."

    install_package
    install_command
    ensure_profile_path
    verify_installation

    say_line ""
    say_line "INSTALLATION COMPLETE"
    say_line "Command: audiobook"
    say_line "Version: $VERSION"
    say_line "Program files: $VENV_DIR"
    say_line ""
    say_line "Open a new Terminal window, then run:"
    say_line "audiobook"
}

main "$@"
