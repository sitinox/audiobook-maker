import re
from typing import Optional

from .common import (
    BARE_MAIN_START_PATTERN,
    FRONT_LABEL_PATTERN,
    LIKELY_KEEP_RE,
    LIKELY_REMOVE_RE,
    MAIN_HEADING_PATTERN,
    Section,
    say,
)
from .extractors import epub_heading_is_weak
from .settings import ask
from .text_utils import preview_text, word_count


def find_first_main_heading(text: str) -> Optional[re.Match]:

    # Structured EPUBs explicitly mark the first trusted chapter boundary.

    structured = re.search(
        r"(?m)^<<<AUDIOBOOK_STRUCTURED_CHAPTER_START>>>$",
        text,
    )

    if structured:
        return structured

    # Rich chapter headings such as:

    #

    # I. Introduction

    # XII. In the Darkness

    #

    # must also count as genuine book starts.

    rich_roman = re.search(
        r"(?im)^[IVXLCDM]+\.\s+\S.+$",
        text,
    )

    normal_matches = list(MAIN_HEADING_PATTERN.finditer(text))

    bare_matches = list(BARE_MAIN_START_PATTERN.finditer(text))

    candidates = []

    if rich_roman:
        candidates.append(rich_roman)

    if normal_matches:
        candidates.append(normal_matches[0])

    if bare_matches:
        candidates.append(bare_matches[0])

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda match: match.start(),
    )


def split_front_matter(front_text: str) -> list[Section]:
    front_text = front_text.strip()
    if not front_text:
        return []

    label_matches = list(FRONT_LABEL_PATTERN.finditer(front_text))
    sections: list[Section] = []

    if not label_matches:
        return [Section("Opening Material", front_text, kind="front")]

    if label_matches[0].start() > 0:
        opening = front_text[: label_matches[0].start()].strip()
        if opening:
            sections.append(Section("Opening Material", opening, kind="front"))

    for index, match in enumerate(label_matches):
        heading = match.group(1).strip()
        start = match.start()
        end = (
            label_matches[index + 1].start() if index + 1 < len(label_matches) else len(front_text)
        )
        body = front_text[start:end].strip()
        if body:
            sections.append(Section(heading, body, kind="front"))

    return sections


def split_main_sections(main_text: str) -> list[Section]:

    text = main_text.strip()

    if not text:
        return []

    # ---------------------------------------------------------------

    # STRONG EPUB STRUCTURE FAST PATH

    #

    # When extraction has already proved that each spine document maps to

    # one real TOC chapter, those boundaries are authoritative.

    #

    # Do NOT run regex chapter detection over these documents.

    # Doing so would rediscover:

    #

    # I. Introduction

    #

    # as separate fragments and create duplicate/tiny tracks.

    # ---------------------------------------------------------------

    structured_pattern = re.compile(
        r"(?ms)"
        r"^<<<AUDIOBOOK_STRUCTURED_CHAPTER_START>>>$\n"
        r"(.*?)\n"
        r"^<<<AUDIOBOOK_STRUCTURED_CHAPTER_BODY>>>$\n"
        r"(.*?)\n"
        r"^<<<AUDIOBOOK_STRUCTURED_CHAPTER_END>>>$"
    )

    structured_matches = list(structured_pattern.finditer(text))

    if structured_matches:
        sections = []

        for match in structured_matches:
            heading = re.sub(
                r"\s+",
                " ",
                match.group(1),
            ).strip()

            body = match.group(2).strip()

            if not body:
                continue

            sections.append(
                Section(
                    clean_section_heading_title(heading),
                    body,
                    kind="main",
                )
            )

        if sections:
            return sections

    # ---------------------------------------------------------------

    # FALLBACK MODE

    #

    # Used only when the source does not provide trustworthy structural

    # chapter boundaries.

    # ---------------------------------------------------------------

    line_pattern = re.compile(
        r"(?im)^("
        r"(?:chapter|part|book|stave|letter|section)\s+"
        r"(?:[IVXLCDM]+|\d+|[A-Za-z]+)"
        r"(?:\s*[-:–—.]\s*.+)?"
        r"|"
        r"[IVXLCDM]+\.\s+.+"
        r"|"
        r"(?:prologue|epilogue|introduction|afterword|preface)"
        r")\s*$"
    )

    matches = list(line_pattern.finditer(text))

    if not matches:
        matches = list(MAIN_HEADING_PATTERN.finditer(text))

    if not matches:
        matches = list(BARE_MAIN_START_PATTERN.finditer(text))

    if not matches:
        return [
            Section(
                "Full Book",
                text,
                kind="main",
            )
        ]

    sections = []

    if matches[0].start() > 0:
        lead = text[: matches[0].start()].strip()

        if lead and word_count(lead) > 10:
            sections.append(
                Section(
                    "Opening",
                    lead,
                    kind="main",
                )
            )

    for index, match in enumerate(matches):
        heading = re.sub(
            r"\s+",
            " ",
            (match.group(1) if match.lastindex else match.group(0)),
        ).strip()

        start = match.start()

        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)

        body = text[start:end].strip()

        if body:
            sections.append(
                Section(
                    heading,
                    body,
                    kind="main",
                )
            )

    # ---------------------------------------------------------------

    # DUPLICATE / TINY-TRACK PROTECTION

    # ---------------------------------------------------------------

    def normalise_identity(value):

        value = re.sub(
            r"[^\w\s]",
            " ",
            value,
        )

        return (
            re.sub(
                r"\s+",
                " ",
                value,
            )
            .strip()
            .lower()
        )

    def core_identity(heading):

        cleaned = normalise_identity(heading)

        match = re.match(
            r"^(chapter|part|book|stave|letter|section)"
            r"\s+"
            r"([a-z0-9]+)",
            cleaned,
        )

        if match:
            return (
                match.group(1),
                match.group(2),
            )

        roman = re.match(
            r"^([ivxlcdm]+)\b",
            cleaned,
        )

        if roman:
            return (
                "chapter",
                roman.group(1),
            )

        return None

    resolved = []

    for section in sections:
        if resolved:
            previous = resolved[-1]

            previous_id = core_identity(previous.heading)

            current_id = core_identity(section.heading)

            if previous_id is not None and previous_id == current_id:
                # Same chapter identity twice:

                #

                # Stave I

                # Stave I - Marley's Ghost

                #

                # Keep the richer title, combine the material, and create one

                # track only.

                richer = max(
                    [
                        previous.heading,
                        section.heading,
                    ],
                    key=lambda value: len(normalise_identity(value)),
                )

                resolved[-1] = Section(
                    clean_section_heading_title(richer),
                    previous.text + "\n\n" + section.text,
                    kind=previous.kind,
                )

                continue

        resolved.append(section)

    final_sections = []

    protected_short_titles = {
        "prologue",
        "epilogue",
        "introduction",
        "preface",
        "afterword",
    }

    for section in resolved:
        words = word_count(section.text)

        title_key = normalise_identity(section.heading)

        # A tiny section is allowed only when its heading strongly proves that

        # it is an intentional standalone section.

        intentional_short = title_key in protected_short_titles

        if words < 80 and not intentional_short and final_sections:
            previous = final_sections[-1]

            previous_id = core_identity(previous.heading)

            current_id = core_identity(section.heading)

            if current_id is None or current_id == previous_id:
                final_sections[-1] = Section(
                    previous.heading,
                    previous.text + "\n\n" + section.text,
                    kind=previous.kind,
                )

                continue

        final_sections.append(section)

    return final_sections


def headings_match_for_merge(first: str, second: str) -> bool:
    return re.sub(r"\s+", " ", first).strip().lower() == re.sub(r"\s+", " ", second).strip().lower()


def subtitle_is_generic(line: str) -> bool:
    return bool(re.fullmatch(r"(?:chapter|part|book|stave|letter|section)", line.strip(), re.I))


def clean_section_heading_title(heading: str) -> str:
    heading = re.sub(r"\s+", " ", heading).strip()
    heading = re.sub(r"\s*[:–—]\s*", " - ", heading)
    heading = re.sub(r"\s*-\s*", " - ", heading)

    # Do not keep useless duplicated labels like "Stave I - Stave"
    # or "Chapter 3 - Chapter". These are usually EPUB layout labels,
    # not meaningful subtitles.
    generic_labels = "Stave|Chapter|Part|Book|Letter|Section"
    numbered_labels = "Stave|Chapter|Part|Book|Letter|Section"
    heading = re.sub(
        rf"^((?:{numbered_labels})\s+(?:[IVXLCDM]+|\d+|[A-Za-z]+))\s*-\s*(?:{generic_labels})$",
        r"\1",
        heading,
        flags=re.I,
    )

    # Also catch accidental doubled forms such as "Stave I Stave".
    heading = re.sub(
        rf"^((?:{numbered_labels})\s+(?:[IVXLCDM]+|\d+|[A-Za-z]+))\s+(?:{generic_labels})$",
        r"\1",
        heading,
        flags=re.I,
    )

    return re.sub(r"\s+", " ", heading).strip()


def subtitle_from_section_text(text: str, heading: str) -> Optional[str]:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    heading_key = heading.lower()
    for line in lines[:20]:
        if not line:
            continue
        if line.lower() == heading_key:
            continue
        if MAIN_HEADING_PATTERN.match(line):
            continue
        if epub_heading_is_weak(line):
            continue
        if subtitle_is_generic(line):
            continue
        if word_count(line) <= 12:
            return line
    return None


def merge_tiny_duplicate_heading_sections(sections: list[Section]) -> list[Section]:
    merged: list[Section] = []
    index = 0

    while index < len(sections):
        current = sections[index]
        next_section = sections[index + 1] if index + 1 < len(sections) else None

        if (
            next_section is not None
            and word_count(current.text) <= 8
            and headings_match_for_merge(current.heading, next_section.heading)
        ):
            subtitle = subtitle_from_section_text(next_section.text, current.heading)
            new_heading = current.heading
            if subtitle:
                new_heading = f"{current.heading}: {subtitle}"
            new_heading = clean_section_heading_title(new_heading)

            # Usually the following section already contains the heading and real body.
            # Use it as the spoken text so we do not create a separate one-second heading track.
            spoken_text = next_section.text
            if current.heading.lower() not in spoken_text[:250].lower():
                spoken_text = f"{current.heading}\n\n{spoken_text}"

            merged.append(Section(new_heading, spoken_text, kind=current.kind))
            index += 2
            continue

        merged.append(current)
        index += 1

    return merged


def classify_front_section(section: Section) -> str:
    heading = section.heading or "Opening Material"
    body_start = section.text[:300]
    combined = f"{heading}\n{body_start}"
    if LIKELY_REMOVE_RE.search(combined):
        return "likely remove"
    if LIKELY_KEEP_RE.search(combined):
        return "likely keep"
    if word_count(section.text) <= 5:
        return "short opening"
    return "unknown"


def review_front_matter(front_sections: list[Section]) -> list[Section]:

    if not front_sections:
        return []

    kept = []

    for index, section in enumerate(
        front_sections,
        start=1,
    ):
        while True:
            assessment = classify_front_section(section)

            say(f"Front matter section {index} of {len(front_sections)}.")

            say(f"Heading: {section.heading or 'Opening Material'}.")

            say(f"Assessment: {assessment}.")

            say(f"Preview: {preview_text(section.text)}")

            answer = (
                ask("Type y to keep this section, n to remove it, or r to repeat.").strip().lower()
            )

            if answer in {
                "y",
                "yes",
                "keep",
            }:
                kept.append(section)

                break

            if answer in {
                "n",
                "no",
                "remove",
            }:
                break

            if answer == "r":
                continue

            say("Please type y, n, or r.")

    return kept


def split_book_text(text: str) -> tuple[list[Section], list[Section], str]:
    first_main = find_first_main_heading(text)
    if not first_main:
        return [], [Section("Full Book", text.strip(), kind="main")], "Full Book"

    front_text = text[: first_main.start()].strip()
    main_text = text[first_main.start() :].strip()
    front_sections = split_front_matter(front_text)
    main_sections = split_main_sections(main_text)
    main_start = main_sections[0].heading if main_sections else "Full Book"
    return front_sections, main_sections, main_start


def contains_title_and_author(text: str, title: str, author: str) -> bool:
    normal = re.sub(r"\s+", " ", text).lower()
    title_norm = re.sub(r"\s+", " ", title).lower()
    author_norm = re.sub(r"\s+", " ", author).lower()
    return title_norm in normal[:1200] and author_norm in normal[:1200]


def should_create_intro(kept_front: list[Section], title: str, author: str) -> bool:
    combined = "\n\n".join(section.text for section in kept_front)
    return not contains_title_and_author(combined, title, author)


def normalize_heading_for_compare(value: str) -> str:
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


def looks_like_generic_heading_label(value: str) -> bool:
    key = normalize_heading_for_compare(value)
    return key in {"chapter", "part", "book", "stave", "section", "volume", "letter"}


def clean_spoken_section_text(text: str, heading: str) -> str:

    lines = [
        re.sub(
            r"\s+",
            " ",
            line,
        ).strip()
        for line in text.splitlines()
    ]

    lines = [line for line in lines if line]

    if not lines:
        return text.strip()

    heading_clean = clean_section_heading_title(heading).strip()

    label = ""

    subtitle = ""

    structured_match = re.match(
        r"(?i)^("
        r"(?:chapter|part|book|stave|letter|section)"
        r"\s+"
        r"(?:[IVXLCDM]+|\d+|[A-Za-z]+)"
        r"|"
        r"[IVXLCDM]+"
        r")"
        r"(?:\s*[.:\-–—]\s*(.+))?$",
        heading_clean,
    )

    if structured_match:
        label = (structured_match.group(1) or "").strip()

        subtitle = (structured_match.group(2) or "").strip()

    else:
        label = heading_clean

    def normalized(value):

        value = re.sub(
            r"[^\w\s]",
            " ",
            value,
        )

        return (
            re.sub(
                r"\s+",
                " ",
                value,
            )
            .strip()
            .lower()
        )

    label_key = normalized(label)

    subtitle_key = normalized(subtitle)

    heading_key = normalized(heading_clean)

    while lines:
        first_key = normalized(lines[0])

        if first_key and first_key in {
            label_key,
            subtitle_key,
            heading_key,
        }:
            lines.pop(0)

            continue

        break

    if not subtitle and lines and len(lines[0].split()) <= 12:
        candidate = lines[0]

        candidate_key = normalized(candidate)

        if (
            candidate_key
            and candidate_key
            not in {
                label_key,
                heading_key,
            }
            and not candidate.endswith(
                (
                    ".",
                    "!",
                    "?",
                    ":",
                    ";",
                )
            )
        ):
            subtitle = candidate

            subtitle_key = candidate_key

            lines.pop(0)

    while lines:
        first_key = normalized(lines[0])

        if first_key and first_key in {
            label_key,
            subtitle_key,
            heading_key,
        }:
            lines.pop(0)

            continue

        break

    blocks = []

    if label:
        blocks.append(label)

    if subtitle:
        blocks.append(subtitle)

    body = "\n".join(lines).strip()

    if body:
        blocks.append(body)

    return "\n\n".join(blocks).strip()


def build_track_plan(
    title: str, author: str, kept_front: list[Section], main_sections: list[Section]
) -> list[Section]:
    tracks: list[Section] = []
    if should_create_intro(kept_front, title, author):
        intro_text = f"{title}. By {author}."
        tracks.append(Section(title, intro_text, kind="intro"))
    tracks.extend(kept_front)
    tracks.extend(main_sections)
    return tracks
