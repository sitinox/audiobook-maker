# Audiobook Maker

[![CI](https://github.com/sitinox/audiobook-maker/actions/workflows/ci.yml/badge.svg)](https://github.com/sitinox/audiobook-maker/actions/workflows/ci.yml)

Audiobook Maker is an accessible macOS command-line tool that converts DRM-free PDF, TXT, DOCX, and EPUB books into chapterised MP3 audiobooks, single-file M4B audiobooks, or both.

It is designed for keyboard and VoiceOver use.

## Features

- Converts PDF, TXT, DOCX, and EPUB sources.
- Creates separately tagged MP3 chapters, one chapterised M4B, or both.
- Embeds chapters, title, author, narrator, cover art, and other metadata.
- Reviews front matter before conversion.
- Suggests titles and authors from filenames, extracted text, and EPUB metadata.
- Cleans duplicated spoken EPUB headings.
- Estimates audiobook duration and verifies completed audio.
- Produces a conversion report for each book.
- Provides spoken and macOS desktop completion notifications.
- Can keep, archive, uniquely rename, or move successfully converted originals to the Bin.
- Protects original source files unless conversion succeeds.
- Stages MP3 and M4B output before publication so failed replacements do not overwrite an existing successful audiobook.
- Saves settings atomically and preserves unreadable settings files for investigation.

## Cover art

Audiobook Maker can use:

- cover art stored inside an EPUB;
- a companion image with the same filename as the source book;
- suitable artwork from the first page of a PDF;
- a suitable early embedded image from a DOCX file.

Companion artwork takes priority over automatically detected artwork.

Books without usable artwork can still be converted.

## Requirements

Audiobook Maker currently supports macOS.

It requires:

- Python 3.9 or newer;
- ffmpeg and ffprobe;
- pdftotext from Poppler;
- the Python packages listed in `pyproject.toml`.

Speech and desktop notifications use the built-in macOS `say` and `osascript` commands.

## Installation for development

Install the required system tools with Homebrew:

    brew install python ffmpeg poppler

Create and activate a virtual environment:

    python3 -m venv .venv
    source .venv/bin/activate

Install Audiobook Maker:

    python -m pip install .

Run it with:

    audiobook

For development and testing:

    python -m pip install -e ".[dev]"
    python -m pytest

## Basic use

1. Put a DRM-free PDF, TXT, DOCX, or EPUB file in the configured `Books to Convert` folder.
2. Open Terminal.
3. Run `audiobook`.
4. Follow the spoken and written prompts.

Audiobook Maker guides you through output format, voice, speech rate, bitrate, title, author, front matter, and original-file handling.

## Useful commands

    audiobook --help
    audiobook --settings
    audiobook --changelog
    audiobook --version

## Output formats

### MP3

Creates a folder containing separately tagged chapter MP3 files.

### M4B

Creates one M4B audiobook containing embedded chapter markers and metadata.

### Both

Creates the M4B in the book folder and places the MP3 chapters in an `MP3` subfolder.

## Accessibility

Audiobook Maker was developed for keyboard and VoiceOver use.

Prompts are written to Terminal and spoken aloud. Choices can be repeated by typing `r`, and completion is announced with speech and a macOS notification.

The interface avoids requiring mouse interaction and keeps important progress and error information available as text in Terminal.

## Reliability and file safety

Audiobook Maker is designed not to treat incomplete work as a successful conversion.

- Original source files are only handled after conversion succeeds.
- New MP3 and M4B output is staged before replacing an existing successful output.
- Failed encoding, tagging, or duration verification does not publish a partial final file.
- Temporary conversion files are cleaned up after successful and failed operations.
- Invalid speech-rate values are rejected.
- Settings are written atomically.
- Damaged settings files are preserved rather than silently overwritten.
- Missing external tools are reported with specific installation guidance.

These safeguards reduce the risk of losing an original book or replacing a working audiobook with a failed conversion.

## Tests

The regression suite exercises the behaviour behind the public features and safety guarantees, including:

- command-line version behaviour and packaging metadata;
- TXT, DOCX, PDF, and EPUB cover-art handling;
- companion-artwork priority;
- M4B creation, chapter markers, metadata, and duration;
- MP3, M4B, and combined output rules;
- keeping, archiving, uniquely renaming, and binning originals;
- protection of original files after failed conversion;
- settings validation, damaged-settings recovery, and atomic writes;
- staged MP3 and M4B replacement;
- failure during encoding, tagging, and duration verification;
- architectural checks that prevent wildcard imports and duplicated menu implementations from returning.

Run the suite with:

    python -m pytest

The 1.0.0 release passes 34 automated tests.

## Limitations

- Audiobook Maker is currently macOS-only.
- It does not remove or bypass DRM.
- PDF chapter detection depends on the structure and quality of extracted text.
- Scanned image-only PDFs require OCR before conversion.
- Unusually structured books may need manual chapter or front-matter decisions.
- Speech generation currently depends on the voices supplied by macOS.

## Project status

Version 1.0.0 is the first stable public release.

Earlier version numbers were used only during private development. The full development history remains available through the repository commits, pull requests, and closed issues.

## Version history

See `CHANGELOG.md` and the GitHub Releases page.

## Licence

Audiobook Maker is free software licensed under the GNU General Public License version 3 or any later version. See `LICENSE` for the full licence text.
