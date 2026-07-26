# Contributing to Audiobook Maker

Thank you for considering a contribution.

## Development requirements

Audiobook Maker is developed and tested on macOS.

You need:

- Python 3.9 or newer

- ffmpeg and ffprobe

- Poppler, including `pdftotext`

- Git

Install the system dependencies with Homebrew:

    brew install python ffmpeg poppler

## Development setup

Clone the repository and enter it:

    git clone https://github.com/sitinox/audiobook-maker.git

    cd audiobook-maker

Create and activate a virtual environment:

    python3 -m venv .venv

    source .venv/bin/activate

Install the package and development dependencies:

    python -m pip install -e ".[dev]"

## Running tests

Run the complete regression suite with:

    python -m pytest

The GitHub Actions workflow also tests the project on macOS with Python 3.9 through 3.14 and verifies that wheel and source distributions build successfully.

## Building distributions

Install the build frontend:

    python -m pip install build

Build the wheel and source distribution:

    python -m build

The resulting files are written to `dist`.

## Project structure

- `audiobook_maker/` contains the application package.

- `tests/` contains the regression suite.

- `make_audiobooks.py` is the compatibility launcher.

- `CHANGELOG.md` contains public release history.

- `pyproject.toml` contains packaging and dependency metadata.

## Safety expectations

Changes must preserve the project's file-safety guarantees:

- failed or cancelled conversions must not replace existing successful output;

- original source books must only be handled after successful conversion;

- new MP3 and M4B output must be staged before publication;

- damaged settings files must be preserved for inspection;

- temporary files must be cleaned after successful, failed, and cancelled operations.

Please add or update regression tests whenever behaviour changes.

## Accessibility expectations

Audiobook Maker is designed for keyboard and VoiceOver use. New prompts and workflows should:

- work without mouse interaction;

- expose important information as Terminal text;

- remain understandable when spoken by a screen reader;

- provide a repeat option where users may need to hear choices again;

- avoid unnecessary visual-only status information.

## Pull requests

Keep pull requests focused and describe:

- what changed;

- why it changed;

- how it was tested;

- any effect on accessibility, file safety, or compatibility.

By contributing, you agree that your contribution may be distributed under the project's GPL-3.0-or-later licence.

## Release process

Public releases use semantic versioning.

Before creating a release:

1. Update `audiobook_maker.__version__`.
2. Update both `CHANGELOG.md` files.
3. Update installer version references and installer tests.
4. Confirm README installation and usage instructions match the released CLI.
5. Run Ruff, the formatting check, the complete test suite, shell syntax checks, and package builds.
6. Confirm CI passes on macOS with Python 3.9 through 3.14.
7. Create an annotated Git tag matching the package version, such as `v1.0.0`.
8. Create the GitHub release from that tag.
9. Attach `Install Audiobook Maker.command` and `Uninstall Audiobook Maker.command` as release assets.
10. Rehearse installation from the published release asset rather than from a local checkout.

A release should not be published if the installer verifies a different version from the tag or package metadata.
