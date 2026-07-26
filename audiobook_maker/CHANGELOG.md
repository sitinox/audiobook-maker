# Changelog

All notable changes to Audiobook Maker are documented in this file.

The project uses semantic versioning for public releases.

## [1.0.0] - 2026-07-26

### Initial public release

Audiobook Maker 1.0.0 is the first stable public release. It consolidates the earlier private development milestones into one public version and establishes the supported installation, automation, safety, and testing baseline.

### Features

- Converts PDF, TXT, DOCX, and DRM-free EPUB books.
- Creates chapterised MP3 audiobooks, single-file M4B audiobooks, or both.
- Embeds chapters, title, author, narrator, cover art, and other metadata when available.
- Extracts EPUB artwork, PDF first-page artwork, suitable DOCX images, and companion cover files.
- Reviews front matter and suggests book metadata before conversion.
- Supports configurable macOS voices, speech rate, bitrate, output format, and original-file handling.
- Saves extracted text, chapter text, conversion reports, and completed audiobooks.
- Lets users choose the project storage folder rather than assuming iCloud Drive.
- Stores application settings in macOS Application Support.

### Non-interactive mode

- Adds `--non-interactive` with `--yes` as an alias.
- Supports one explicit source through `--source` or all project sources through `--all`.
- Supports command-line overrides for title, author, front matter, output format, original handling, project folder, voice, rate, bitrate, and forced replacement.
- Uses saved settings and detected metadata where appropriate.
- Fails clearly rather than falling back to prompts when required automation settings are missing.
- Includes end-to-end regression coverage proving that non-interactive runs do not call interactive functions.

### Reliability and safety

- Stages MP3 and M4B output before replacing an existing successful audiobook.
- Prevents failed encoding, tagging, or verification from publishing partial final output.
- Preserves existing output when a replacement conversion fails or is cancelled.
- Handles original source books only after conversion completes successfully.
- Uses atomic settings writes and preserves damaged settings files for inspection.
- Validates speech rate, output duration, required tools, source paths, supported extensions, and conversion results.
- Cleans temporary files after successful, failed, and cancelled operations.

### Accessibility and interaction

- Provides a keyboard-led command-line workflow designed around VoiceOver use.
- Uses spoken prompts, repeatable menus, clear completion messages, and macOS notifications.
- Keeps project locations and conversion choices explicit rather than hidden.
- Provides a fully prompt-free mode for scripts and repeatable workflows.

### Engineering and distribution

- Reorganised the original script into a modular Python package.
- Added the installed `audiobook` command.
- Added standard Python packaging through `pyproject.toml`.
- Added an executable macOS installer and matching uninstaller.
- Made installation safe to repeat for updates or repair.
- Preserves books, outputs, reports, and settings during uninstall.
- Added automated regression coverage for conversion behaviour, file safety, settings, metadata, cover art, output modes, architecture, non-interactive operation, and installation.
- Added GitHub Actions testing on macOS with Python 3.9 through 3.14.
- Added wheel and source-distribution build checks.
- Licensed the project under GPL-3.0-or-later.

Earlier 2.x through 5.x numbers were private development milestones and were never published as formal GitHub releases.
