# Audiobook Maker v5.0.0 release notes

Audiobook Maker can now create complete single-file M4B audiobooks as well as chapterised MP3 folders.

## Highlights

- Choose MP3, M4B, or both.
- M4B files include embedded chapters, title, author, cover art, and duration verification.
- The original single-file script has been reorganised into a modular Python package.
- Cover art now works across EPUB, PDF, TXT, and DOCX sources.
- Companion artwork can be used for any supported source and overrides automatically detected artwork.
- PDFs can use first-page artwork.
- DOCX files can use a suitable early embedded image.
- EPUB structure, table-of-contents handling, chapter parsing, and spoken headings have been improved.
- Audiobook Maker can notify the user when a run finishes and can keep, archive, or move successfully converted originals to the Bin.
- Regression tests confirm all supported non-EPUB cover-art routes.
- Existing MP3 behaviour remains available.
