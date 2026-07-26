# Audiobook Maker 5.1.0

## First public release

Audiobook Maker 5.1.0 is the first public release of the project.

It builds directly on the 5.0.0 internal milestone, which introduced the modular package, M4B creation, expanded cover-art support, and the choice of MP3, M4B, or both. Version 5.1.0 does not pretend those features were newly invented here. Instead, it turns that functional milestone into a safer, maintainable, installable, and documented public project.

## What changed after 5.0.0

### Failed conversions no longer publish replacement output prematurely

MP3 and M4B files are now created through staged output paths. A new file only replaces its final destination after encoding, metadata work, and verification have succeeded.

This means a failed replacement conversion should not destroy an older successful audiobook or leave a partial file under the expected final filename.

### Settings handling is safer

Settings are now written atomically. Invalid speech rates are rejected, and damaged settings files are preserved rather than silently overwritten.

### Errors are more specific

Failures involving required tools and invalid duration data now produce explicit errors. Audiobook Maker no longer treats unreadable duration information as a valid zero-length result.

### The codebase is easier to maintain

Wildcard imports were removed, module dependencies were made explicit, and repeated interactive menu implementations were consolidated into a reusable helper.

Regression checks now protect those architectural improvements.

### The project is installable

Audiobook Maker now has standard Python packaging metadata, declared dependencies, a development installation workflow, and an installed `audiobook` command.

### The important behaviour is tested

The automated suite covers the conversion and safety behaviour behind the project, rather than merely counting superficial tests. It includes output selection, M4B chapters and metadata, cover-art rules, original-file handling, settings recovery, and atomic replacement when conversion fails.

The release candidate passes 24 automated tests.

### The repository is documented and licensed

The project now includes a public README, changelog, versioned release notes, and the GNU General Public License version 3 or any later version.

## Supported input

- EPUB
- PDF
- DOCX
- TXT

Audiobook Maker only works with DRM-free input.

## Supported output

- Tagged chapter MP3 files
- One chapterised M4B file
- Both formats in one conversion

## Accessibility

Audiobook Maker remains designed around keyboard and VoiceOver use on macOS. Prompts are both printed and spoken, choices can be repeated, and completion or failure is announced without requiring mouse interaction.

## System requirements

- macOS
- Python 3.9 or newer
- ffmpeg and ffprobe
- Poppler/pdftotext
- Python dependencies declared in `pyproject.toml`

## Upgrade note

This is the first public release, so there is no public-package upgrade path from an earlier GitHub version.

Existing internal users should back up their current installation and settings before replacing it with the packaged v5.1.0 release candidate.

## Licence

Audiobook Maker is licensed under GPL-3.0-or-later.
