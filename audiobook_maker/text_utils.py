import re
from pathlib import Path
from typing import Optional

from .common import DIVIDER_PATTERN, PAGE_NUMBER_PATTERN, URL_PATTERN

def safe_filename(name: str, limit: int = 180) -> str:
    name = name.replace("’", "'").replace("“", '"').replace("”", '"')
    name = re.sub(r"\s*[:–—]\s*", " - ", name)
    name = re.sub(r"[/:\\?%*|\"<>]", "-", name)
    name = re.sub(r"\s+", " ", name).strip(" .-_")
    return (name or "Untitled")[:limit]


def pretty_title_from_filename(path: Path) -> str:
    name = path.stem
    name = re.sub(r"[_]+", " ", name)
    name = re.sub(r"[-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or path.stem


def clean_heading_for_filename(heading):

    heading = re.sub(

        r"\s+",

        " ",

        heading,

    ).strip()

    heading = re.sub(

        r"\s*[:–—]\s*",

        " - ",

        heading,

    )

    heading = re.sub(

        r"\s*-\s*",

        " - ",

        heading,

    )

    generic = (

        "Stave|Chapter|Part|Book|"

        "Letter|Section"

    )

    heading = re.sub(

        rf"^((?:{generic})\s+"

        rf"(?:[IVXLCDM]+|\d+|[A-Za-z]+))"

        rf"\s*-\s*(?:{generic})$",

        r"\1",

        heading,

        flags=re.I,

    )

    heading = re.sub(

        rf"^((?:{generic})\s+"

        rf"(?:[IVXLCDM]+|\d+|[A-Za-z]+))"

        rf"\s+(?:{generic})$",

        r"\1",

        heading,

        flags=re.I,

    )

    heading = re.sub(

        r"\s+",

        " ",

        heading,

    ).strip()

    return safe_filename(

        heading,

        120,

    )


def word_count(text: str) -> int:
    return len(re.findall(r"\b\S+\b", text))


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\u00a0", " ", text)
    text = PAGE_NUMBER_PATTERN.sub("", text)
    text = DIVIDER_PATTERN.sub("\n\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def first_meaningful_lines(text: str, limit: int = 80) -> list[str]:
    lines = []
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            lines.append(cleaned)
        if len(lines) >= limit:
            break
    return lines


def suggest_title_author(path: Path, text: str) -> tuple[str, Optional[str]]:
    lines = first_meaningful_lines(text, 120)
    fallback_title = pretty_title_from_filename(path)
    suggested_title = fallback_title
    suggested_author = None

    for line in lines[:30]:
        if URL_PATTERN.search(line):
            continue
        if re.match(r"(?i)^(summary|rating|relationships?|characters?|warnings?|fandom|category|language|published|updated|words|chapters|status)\b", line):
            continue
        if re.match(r"(?i)^by\s+.+", line):
            continue
        if 1 <= len(line.split()) <= 12:
            suggested_title = re.sub(r"\s+", " ", line).strip()
            break

    author_patterns = [
        r"(?i)^by\s+(.+?)\s*$",
        r"(?i)^author\s*:\s*(.+?)\s*$",
        r"(?i)^written\s+by\s+(.+?)\s*$",
    ]
    for line in lines[:80]:
        for pattern in author_patterns:
            match = re.match(pattern, line)
            if match:
                candidate = match.group(1).strip()
                candidate = re.sub(r"\s+", " ", candidate)
                if 1 <= len(candidate.split()) <= 8 and not URL_PATTERN.search(candidate):
                    suggested_author = candidate
                    return suggested_title, suggested_author

    return suggested_title, suggested_author


def preview_text(text: str, limit: int = 160) -> str:
    preview = re.sub(r"\s+", " ", text).strip()
    if len(preview) > limit:
        preview = preview[: limit - 3].rstrip() + "..."
    return preview


