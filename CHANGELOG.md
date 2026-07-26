# Changelog

All notable changes to Audiobook Maker are documented in this file.

The project uses semantic versioning for public releases.

## [5.1.0] - 2026-07-25

### First public release

Version 5.1.0 builds on the functional and architectural work completed in 5.0.0. It prepares that system for public use through reliability hardening, packaging, maintainability improvements, testing, documentation, and licensing.

### Reliability and file safety

- Changed MP3 generation to stage each new file before replacing its final destination.
- Changed M4B generation to stage and verify the new audiobook before replacing an existing successful M4B.
- Prevented failed encoding, metadata tagging, or duration verification from publishing a partial final output.
- Preserved an existing successful audiobook when a replacement conversion fails.
- Improved temporary-file cleanup across successful and failed conversion paths.
- Strengthened protection of original source books so post-conversion handling only occurs after successful output creation.
- Made settings writes atomic.
- Preserved damaged or unreadable settings files rather than silently replacing them.
- Added speech-rate validation so invalid values fail clearly.
- Changed unreadable or invalid audio durations from a silent zero-duration result into an explicit conversion failure.
- Improved errors for missing external tools such as ffmpeg, ffprobe, `say`, and pdftotext.

### Maintainability

- Replaced wildcard imports with explicit imports throughout the package.
- Added an architectural regression check to prevent wildcard imports from returning.
- Consolidated repeated numbered-menu implementations into one reusable helper.
- Reduced duplicated settings control flow.
- Clarified module dependencies and internal boundaries.
- Added targeted type hints, validation, and error handling around the hardened paths.

### Packaging and command-line use

- Packaged Audiobook Maker as an installable Python project.
- Added project metadata and dependency declarations through `pyproject.toml`.
- Added the installed `audiobook` command-line entry point.
- Added development dependencies and a standard editable-install workflow.
- Added GPL-3.0-or-later package metadata.
- Prepared the repository structure for public distribution.

### Testing

- Introduced a regression suite covering the behaviour added in 5.0.0 and the safety changes in 5.1.0.
- Covered cover-art extraction and priority rules for TXT, DOCX, PDF, and EPUB sources.
- Covered MP3, M4B, and combined output structure.
- Covered M4B chapter markers, metadata, and duration.
- Covered successful and failed original-file handling.
- Covered settings validation, damaged-settings recovery, and atomic persistence.
- Covered atomic replacement of existing MP3 and M4B output.
- Covered packaging, version reporting, explicit imports, and shared menu architecture.
- The completed v5.1.0 release candidate passes 24 automated tests.

### Documentation and licensing

- Added a public README with installation, use, accessibility, output, testing, limitation, and safety information.
- Added this changelog.
- Added release notes for the first public release.
- Added the GNU General Public License version 3 with the option to use any later version.
- Documented 5.0.0 as the internal milestone on which 5.1.0 is based.

## [5.0.0] - Internal milestone

### Major functional and architectural release

- Reorganised the original script into a modular Python package.
- Added single-file M4B audiobook output.
- Added embedded M4B chapter markers and metadata.
- Added a choice of MP3, M4B, or both output formats.
- Expanded cover-art handling across supported source formats.
- Added conversion reporting and output-duration verification.
- Improved metadata, title, author, narrator, and front-matter handling.
- Improved original-file choices after successful conversion.
- Preserved the keyboard-led and VoiceOver-oriented interaction model.

Version 5.0.0 was used internally and was not published as a formal GitHub release.
