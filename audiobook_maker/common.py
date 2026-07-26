#!/usr/bin/env python3

from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Optional, Any

try:
    from mutagen.id3 import ID3, TIT2, TALB, TPE1, TPE2, TRCK, TCON, COMM, TDRC, APIC
    from mutagen.mp3 import MP3
except ImportError:
    ID3 = None
    MP3 = None

try:
    import docx
except ImportError:
    docx = None

try:
    from ebooklib import epub as ebook_epub, ITEM_DOCUMENT, ITEM_IMAGE
except ImportError:
    ebook_epub = None
    ITEM_DOCUMENT = None
    ITEM_IMAGE = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

VERSION = "v5.1.0"
DEFAULT_VOICE = "Daniel (Enhanced)"
DEFAULT_RATE = 325
MIN_SPEECH_RATE = 80
MAX_SPEECH_RATE = 500
DEFAULT_BITRATE = 192
SAMPLE_RATE = 44100
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx", ".epub"}

PROJECT_DIR = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Audiobook Maker"
SOURCE_DIR = PROJECT_DIR / "Books to Convert"
FINISHED_DIR = PROJECT_DIR / "Finished MP3 Audiobooks"
CHAPTER_TEXT_DIR = PROJECT_DIR / "Chapter Text Files"
EXTRACTED_TEXT_DIR = PROJECT_DIR / "Extracted Full Text"
REPORTS_DIR = PROJECT_DIR / "Reports"
SCRIPTS_DIR = PROJECT_DIR / "Scripts"
BACKUPS_DIR = SCRIPTS_DIR / "Backups"
CONVERTED_ORIGINALS_DIR = PROJECT_DIR / "Converted Originals"
SETTINGS_PATH = PROJECT_DIR / "settings.json"

CHANGELOG_TEXT = """Audiobook Maker changelog

Current stable version: v5.1.0
Stable checkpoint: per-run and per-book original-file handling with accessible completion notifications.

v5.0.0 - M4B output and modular architecture

- Added complete M4B audiobook output with embedded chapters, title, author, cover art, and duration verification.

- Added output choices for MP3, M4B, or both.

- Modularised Audiobook Maker into dedicated modules for the command-line interface, settings, extraction, chapter handling, audio, M4B creation, files, notifications, and conversion orchestration.

- Added universal cover-art handling across EPUB, PDF, TXT, and DOCX sources.

- Added companion cover-art support and overrides.

- Added PDF first-page artwork and DOCX early embedded-image detection.

- Improved structured EPUB extraction, table-of-contents handling, and chapter parsing.

- Added completion notifications and flexible handling of successfully converted original files.

- Confirmed TXT, DOCX, and PDF cover-art behaviour with disposable automated regression tests.


v4.2.1 - Per-run and per-book original handling
- Added a choice at the start of each run to keep, archive, or bin all successful originals, or ask after each successful book.
- Per-book prompts can apply the selected action to all remaining successful books in the same run.
- Added r to repeat all new original-file choice menus.

v4.2.0 - Original-file handling and completion notifications
- Added a remembered choice to keep successful source books, move them to Converted Originals, or move them to the Bin.
- Source files are only handled after conversion, tagging, and report creation complete successfully.
- Added a spoken completion message and a macOS notification with a sound.
- Added a distinct failure notification when one or more books fail.
- Added the Converted Originals folder to automatic folder creation.
- Renamed the temporary working-folder prefix to Audiobook Maker.

Stable checkpoint: renamed project from PDF Audiobook Maker to Audiobook Maker; EPUB support is working on A Christmas Carol, including correct stave splitting, no duplicate spoken stave headings, and clearer heading pauses before the chapter body.

v4.1.0 - Project rename and folder cleanup
- Renamed the project from PDF Audiobook Maker to Audiobook Maker because the tool now supports PDF, TXT, DOCX, and EPUB sources.
- Renamed the source folder from 'PDFs to Convert' to 'Books to Convert'.
- Updated help, settings, built-in changelog, and startup text to use the new project name.
- Kept the stable v4.0.6 EPUB behaviour unchanged.

v4.0.6 - Stable EPUB spoken-heading polish
- Fixed spoken EPUB chapter openings so duplicate heading labels are not read twice.
- Added punctuation and a blank line between a heading/subtitle and the chapter body, so macOS say gives the opening more breathing room.
- Kept useful subtitles such as 'Marley's Ghost' while removing repeated labels such as repeated 'Stave I'.
- Confirmed expected structure for A Christmas Carol: 5 main staves plus the generated intro track.

v4.0.5 - Spoken duplicate heading cleanup
- Cleaned repeated heading labels at the start of generated chapter text.
- Fixed cases where the MP3 title was correct but the audio itself still repeated the section label.

v4.0.4 - Stronger title cleanup
- Stripped generic duplicate title endings such as 'Stave I - Stave', 'Chapter One - Chapter', and similar patterns.
- Kept meaningful subtitles when they add useful information.

v4.0.3 - Cosmetic EPUB title cleanup
- Improved EPUB track title cleaning for generic heading/subheading combinations.

v4.0.2 - Tiny heading-track merge
- Merged one-second heading-only EPUB sections into the following real section.
- Fixed A Christmas Carol style output where each stave was being split into a tiny heading track and a body track.

v4.0.1 - EPUB heading polish
- Added Stave as a recognised main heading type.
- Improved EPUB heading selection so weak headings like I or One are not trusted when better nearby headings exist.

v4.0 - EPUB support
- Added EPUB support using structured spine extraction.
- Added EPUB metadata title and author suggestions.
- Added EPUB cover-art detection and embedding when cover art is available.
- Added settings display with --settings.
- Kept existing PDF, TXT, and DOCX support.

v3.x - Multi-format and quality improvements
- Added TXT and DOCX support.
- Added configurable MP3 bitrate: 128, 192, 256, or 320 kbps.
- Standardised output to 44.1 kHz MP3.
- Improved reports, duration estimates, actual duration checks, and ID3 tagging.
- Standardised repeat prompts to r.

v2.x - Front matter and tagging improvements
- Added front-matter-only review.
- Added title/author intro track when needed.
- Added ID3 tagging through mutagen.
- Improved command-line help and reports.
"""

DIVIDER_PATTERN = re.compile(r"(?m)^\s*(?:[*~_\-=]\s*){3,}\s*$")
PAGE_NUMBER_PATTERN = re.compile(r"(?m)^\s*\d+\s*$")
URL_PATTERN = re.compile(r"https?://\S+", re.I)

MAIN_HEADING_PATTERN = re.compile(
    r"""(?imx)
    ^\s*(
        Chapter\s+(?:\d+|[IVXLCDM]+|[A-Za-z]+(?:[-\s][A-Za-z]+)*)(?:\s*[:\-–—]\s*.+)?
        |
        Prologue(?:\s*[:\-–—]\s*.+)?
        |
        Epilogue(?:\s*[:\-–—]\s*.+)?
        |
        Interlude(?:\s*[:\-–—]\s*.+)?
        |
        Part\s+(?:\d+|[IVXLCDM]+|[A-Za-z]+(?:[-\s][A-Za-z]+)*)(?:\s*[:\-–—]\s*.+)?
        |
        Book\s+(?:\d+|[IVXLCDM]+|[A-Za-z]+(?:[-\s][A-Za-z]+)*)(?:\s*[:\-–—]\s*.+)?
        |
        Stave\s+(?:\d+|[IVXLCDM]+|[A-Za-z]+(?:[-\s][A-Za-z]+)*)(?:\s*[:\-–—]\s*.+)?
        |
        Letter\s+(?:\d+|[IVXLCDM]+|[A-Za-z]+(?:[-\s][A-Za-z]+)*)(?:\s*[:\-–—]\s*.+)?
        |
        Short\s+Story(?:\s*[:\-–—]\s*.+)?
        |
        Author'?s\s+Note(?:\s*[:\-–—]\s*.+)?
        |
        Foreword(?:\s*[:\-–—]\s*.+)?
        |
        Afterword(?:\s*[:\-–—]\s*.+)?
        |
        Acknowledgements?(?:\s*[:\-–—]\s*.+)?
        |
        Appendix(?:\s*[:\-–—]\s*.+)?
    )\s*$
    """
)

BARE_MAIN_START_PATTERN = re.compile(r"(?im)^\s*(?:1|I|One)\s*$")

FRONT_LABEL_PATTERN = re.compile(
    r"""(?imx)
    ^\s*(
        Copyright(?:\s+Notice)?
        |Dedication
        |Contents
        |Table\s+of\s+Contents
        |Also\s+by(?:\s+.+)?
        |Praise\s+for(?:\s+.+)?
        |About\s+the\s+Author
        |About\s+the\s+Story
        |Title\s+Page
        |Publisher(?:\s+Information)?
        |ISBN(?:\s+.+)?
        |Disclaimer
        |Summary(?:\s*:.+)?
        |Rating(?:\s*:.+)?
        |Relationships?(?:\s*:.+)?
        |Characters?(?:\s*:.+)?
        |Warnings?(?:\s*:.+)?
        |Additional\s+Tags(?:\s*:.+)?
        |Archive\s+Warnings?(?:\s*:.+)?
        |Category(?:\s*:.+)?
        |Fandom(?:\s*:.+)?
        |Language(?:\s*:.+)?
        |Published(?:\s*:.+)?
        |Updated(?:\s*:.+)?
        |Words(?:\s*:.+)?
        |Chapters(?:\s*:.+)?
        |Status(?:\s*:.+)?
        |Posted\s+originally(?:\s+on)?(?:\s*:.+)?
        |Notes?(?:\s*:.+)?
        |Reviews?(?:\s*:.+)?
        |Favou?rites?(?:\s*:.+)?
        |Follows?(?:\s*:.+)?
        |Story\s+ID(?:\s*:.+)?
        |By\s+.+
        |https?://\S+
    )\s*$
    """
)

LIKELY_REMOVE_RE = re.compile(
    r"copyright|contents|table of contents|also by|praise for|publisher|isbn|http|www\.|rating|relationships?|characters?|warnings?|additional tags|archive warning|category|fandom|language|published|updated|words|chapters|status|posted originally|reviews?|favou?rites?|follows?|story id",
    re.I,
)

LIKELY_KEEP_RE = re.compile(r"dedication|prologue|foreword|author'?s note|notes?|acknowledgements?", re.I)

@dataclass

class Settings:

    voice: str = DEFAULT_VOICE

    rate: int = DEFAULT_RATE

    bitrate: int = DEFAULT_BITRATE

    output_format: Optional[str] = None

    original_action: Optional[str] = None



@dataclass
class Section:
    heading: str
    text: str
    kind: str = "main"
    kept: bool = True

@dataclass
class SourceBook:
    path: Path
    title: str
    author: str
    text: str
    source_type: str
    warnings: list[str] = field(default_factory=list)

@dataclass
class ExtractedSource:
    text: str
    source_type: str
    metadata_title: Optional[str] = None
    metadata_author: Optional[str] = None
    cover_art: Optional[tuple[str, bytes]] = None
    details: list[str] = field(default_factory=list)


def say(message: str = "") -> None:
    print(message, flush=True)


def run_command(command: list[str], description: str) -> subprocess.CompletedProcess:
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed while doing: {description}\n\n"
            f"Command: {' '.join(command)}\n\n"
            f"Error:\n{result.stderr.strip()}"
        )
    return result


def check_tool(tool_name: str) -> None:
    if shutil.which(tool_name) is not None:
        return

    install_hints = {
        "ffmpeg": "Install it with: brew install ffmpeg",
        "ffprobe": "Install it with: brew install ffmpeg",
        "pdftotext": "Install it with: brew install poppler",
        "say": "The macOS 'say' command could not be found. Audiobook Maker requires macOS.",
    }
    hint = install_hints.get(tool_name, f"Install '{tool_name}' and make sure it is on your PATH.")
    raise RuntimeError(f"Missing required tool: {tool_name}. {hint}")


