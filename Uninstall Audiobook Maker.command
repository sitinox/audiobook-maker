#!/bin/zsh
set -u

APP_NAME="Audiobook Maker"
DEFAULT_SUPPORT_DIR="$HOME/Library/Application Support/Audiobook Maker"
SUPPORT_DIR="${AUDIOBOOK_MAKER_SUPPORT_DIR:-$DEFAULT_SUPPORT_DIR}"
VENV_DIR="${AUDIOBOOK_MAKER_VENV_DIR:-$SUPPORT_DIR/venv}"
BIN_DIR="${AUDIOBOOK_MAKER_BIN_DIR:-$HOME/.local/bin}"
COMMAND_PATH="$BIN_DIR/audiobook"
PROFILE_PATH="${AUDIOBOOK_MAKER_PROFILE_PATH:-$HOME/.zprofile}"
PATH_MARKER_START="# >>> Audiobook Maker managed PATH >>>"
PATH_MARKER_END="# <<< Audiobook Maker managed PATH <<<"

say_line() {
    print -r -- "$1"
}

remove_managed_profile_block() {
    [[ -f "$PROFILE_PATH" ]] || return

    local temporary
    temporary="$(mktemp)" || return

    awk -v start="$PATH_MARKER_START" -v end="$PATH_MARKER_END" '
        $0 == start { skipping = 1; next }
        $0 == end { skipping = 0; next }
        !skipping { print }
    ' "$PROFILE_PATH" > "$temporary"

    mv "$temporary" "$PROFILE_PATH"
}

main() {
    say_line "$APP_NAME Uninstaller"
    say_line "========================"

    if [[ -L "$COMMAND_PATH" || -f "$COMMAND_PATH" ]]; then
        rm -f "$COMMAND_PATH"
        say_line "Removed command: $COMMAND_PATH"
    else
        say_line "The managed audiobook command was not present."
    fi

    if [[ -d "$VENV_DIR" ]]; then
        rm -rf "$VENV_DIR"
        say_line "Removed program environment: $VENV_DIR"
    else
        say_line "The managed program environment was not present."
    fi

    remove_managed_profile_block

    say_line ""
    say_line "UNINSTALL COMPLETE"
    say_line "Books, finished audiobooks, reports, and settings were left untouched."
    say_line "Application support folder preserved: $SUPPORT_DIR"
}

main "$@"
