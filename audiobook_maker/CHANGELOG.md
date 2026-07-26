# Changelog

All notable changes to Audiobook Maker are documented in this file.

The project uses semantic versioning for public releases.

## [1.0.0] - 2026-07-26

### Initial public release

Audiobook Maker 1.0.0 is the first stable public release. It brings together the private development work that produced the original script, multi-format support, the modular application, M4B output, safety hardening, configurable storage, automated testing, and continuous integration.

### Features

- Converts PDF, TXT, DOCX, and DRM-free EPUB books.

- Creates chapterised MP3 audiobooks, single-file M4B audiobooks, or both.

- Embeds chapters, title, author, narrator, cover art, and other metadata when available.

- Extracts EPUB artwork, PDF first-page artwork, suitable DOCX images, and companion cover files.

- Reviews front matter and suggests book metadata before conversion.

- Supports configurable macOS voices, speech rate, bitrate, and original-file handling.

- Saves extracted text, chapter text, conversion reports, and completed audiobooks.

- Lets users choose the project storage folder rather than assuming iCloud Drive.

- Stores application settings in macOS Application Support.

### Reliability and safety

- Stages MP3 and M4B output before replacing an existing successful audiobook.

- Prevents failed encoding, tagging, or verification from publishing partial final output.

- Preserves existing output when a replacement conversion fails or is cancelled.

- Handles original source books only after conversion completes successfully.

- Uses atomic settings writes and preserves damaged settings files for inspection.

- Validates speech rate, output duration, required tools, and conversion results.

- Cleans temporary files after successful, failed, and cancelled operations.
### Accessibility and interaction

- Provides a keyboard-led command-line workflow designed around VoiceOver use.

- Uses spoken prompts, repeatable menus, clear completion messages, and macOS notifications.

- Keeps project locations and conversion choices explicit rather than hidden.

### Engineering and distribution

- Reorganised the original script into a modular Python package.

- Added the installed `audiobook` command.

- Added standard Python packaging through `pyproject.toml`.

- Added automated regression coverage for conversion behaviour, file safety, settings, metadata, cover art, output modes, and architecture.

- Added GitHub Actions testing on macOS with Python 3.9 through 3.14.

- Added wheel and source-distribution build checks.

- Licensed the project under GPL-3.0-or-later.

Earlier 2.x through 5.x numbers were private development milestones and were never published as formal GitHub releases.
