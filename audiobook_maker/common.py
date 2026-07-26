#!/usr/bin/env python3

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import docx
except ImportError:
    docx = None

try:
    from ebooklib import ITEM_DOCUMENT, ITEM_IMAGE
    from ebooklib import epub as ebook_epub
except ImportError:
    ebook_epub = None
    ITEM_DOCUMENT = None
    ITEM_IMAGE = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from . import __version__

VERSION = f"v{__version__}"
DEFAULT_VOICE = "Daniel (Enhanced)"
DEFAULT_RATE = 325
MIN_SPEECH_RATE = 80
MAX_SPEECH_RATE = 500
DEFAULT_BITRATE = 192
SAMPLE_RATE = 44100
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx", ".epub"}

APPLICATION_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "Audiobook Maker"
SETTINGS_PATH = APPLICATION_SUPPORT_DIR / "settings.json"


@dataclass(frozen=True)
class ProjectPaths:
    project_dir: Path
    source_dir: Path
    finished_dir: Path
    chapter_text_dir: Path
    extracted_text_dir: Path
    reports_dir: Path
    converted_originals_dir: Path

    @classmethod
    def from_project_dir(cls, project_dir: Path) -> "ProjectPaths":
        project_dir = project_dir.expanduser()
        return cls(
            project_dir=project_dir,
            source_dir=project_dir / "Books to Convert",
            finished_dir=project_dir / "Finished MP3 Audiobooks",
            chapter_text_dir=project_dir / "Chapter Text Files",
            extracted_text_dir=project_dir / "Extracted Full Text",
            reports_dir=project_dir / "Reports",
            converted_originals_dir=project_dir / "Converted Originals",
        )

    def required_directories(self) -> tuple[Path, ...]:
        return (
            self.project_dir,
            self.source_dir,
            self.finished_dir,
            self.chapter_text_dir,
            self.extracted_text_dir,
            self.reports_dir,
            self.converted_originals_dir,
        )


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

LIKELY_KEEP_RE = re.compile(
    r"dedication|prologue|foreword|author'?s note|notes?|acknowledgements?", re.I
)


@dataclass
class Settings:
    voice: str = DEFAULT_VOICE

    rate: int = DEFAULT_RATE

    bitrate: int = DEFAULT_BITRATE

    output_format: Optional[str] = None

    original_action: Optional[str] = None

    project_dir: Optional[Path] = None


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
