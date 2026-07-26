import posixpath
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from .common import (
    BeautifulSoup, EXTRACTED_TEXT_DIR, ExtractedSource, ITEM_DOCUMENT,
    ITEM_IMAGE, MAIN_HEADING_PATTERN, docx, ebook_epub, run_command,
)
from .text_utils import clean_text, safe_filename

def extract_pdf_text(source_path: Path, output_text_path: Path) -> str:
    run_command(["pdftotext", "-layout", str(source_path), str(output_text_path)], f"Extracting text from {source_path.name}")
    return output_text_path.read_text(encoding="utf-8", errors="ignore")


def extract_txt_text(source_path: Path, output_text_path: Path) -> str:
    data = source_path.read_text(encoding="utf-8", errors="ignore")
    output_text_path.write_text(data, encoding="utf-8")
    return data


def extract_docx_text(source_path: Path, output_text_path: Path) -> str:
    if docx is None:
        raise RuntimeError("DOCX support needs python-docx. Install it with: python3 -m pip install python-docx")
    document = docx.Document(str(source_path))
    paragraphs = [p.text for p in document.paragraphs if p.text and p.text.strip()]
    text = "\n\n".join(paragraphs)
    output_text_path.write_text(text, encoding="utf-8")
    return text


def epub_metadata_value(book: Any, namespace: str, name: str) -> Optional[str]:
    try:
        values = book.get_metadata(namespace, name)
    except Exception:
        return None
    if not values:
        return None
    value = values[0][0]
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value or None


def epub_heading_is_weak(candidate: str) -> bool:
    candidate = re.sub(r"\s+", " ", candidate).strip()
    if not candidate:
        return True
    if re.fullmatch(r"\d+", candidate):
        return True
    if re.fullmatch(r"[IVXLCDM]+", candidate, re.I):
        return True
    if re.fullmatch(r"(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)", candidate, re.I):
        return True
    return False


def choose_best_epub_heading(candidates: list[str]) -> Optional[str]:
    cleaned: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if not candidate:
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(candidate)

    if not cleaned:
        return None

    for candidate in cleaned:
        if MAIN_HEADING_PATTERN.match(candidate):
            return candidate

    if len(cleaned) >= 2 and epub_heading_is_weak(cleaned[0]) and not epub_heading_is_weak(cleaned[1]):
        return f"Chapter {cleaned[0]}: {cleaned[1]}"

    for candidate in cleaned:
        if not epub_heading_is_weak(candidate):
            return candidate

    return cleaned[0]


def epub_item_text(item: Any) -> tuple[str, Optional[str]]:

    if BeautifulSoup is None:

        raise RuntimeError(

            "EPUB support needs beautifulsoup4. "

            "Install it with: python3 -m pip install beautifulsoup4"

        )

    soup = BeautifulSoup(item.get_content(), "html.parser")

    for unwanted in soup(["script", "style", "nav"]):

        unwanted.decompose()

    chapter_label_re = re.compile(

        r"^(?:chapter|part|book|stave|letter|section)"

        r"\s+(?:[IVXLCDM]+|\d+|[A-Za-z]+)"

        r"(?:\b.*)?$",

        re.I,

    )

    # Examine the smallest likely structural containers first.

    containers = list(

        soup.find_all(

            ["ol", "ul", "table", "section", "div"]

        )

    )

    for container in reversed(containers):

        if container.parent is None:

            continue

        links = container.find_all("a", href=True)

        if len(links) < 3:

            continue

        chapter_like_links = 0

        for link in links:

            label = re.sub(

                r"\s+",

                " ",

                link.get_text(" ", strip=True),

            ).strip()

            if chapter_label_re.match(label):

                chapter_like_links += 1

        if chapter_like_links < 3:

            continue

        container_text = re.sub(

            r"\s+",

            " ",

            container.get_text(" ", strip=True),

        ).strip()

        total_words = len(container_text.split())

        # A contents/index block is a compact structure containing several

        # linked chapter/stave labels. Remove that block only.

        if total_words <= 1200:

            container.decompose()

    heading_candidates = []

    for tag_name in [

        "h1",

        "h2",

        "h3",

        "h4",

        "h5",

        "h6",

        "title",

    ]:

        for tag in soup.find_all(tag_name):

            candidate = re.sub(

                r"\s+",

                " ",

                tag.get_text(" ", strip=True),

            ).strip()

            if candidate:

                heading_candidates.append(candidate)

    heading = choose_best_epub_heading(

        heading_candidates

    )

    text = soup.get_text("\n", strip=True)

    lines = [

        re.sub(r"\s+", " ", line).strip()

        for line in text.splitlines()

    ]

    text = "\n".join(

        line for line in lines if line

    )

    return text, heading


def epub_is_nav_or_toc(item: Any, text: str) -> bool:

    name = ""

    try:

        name = item.get_name().lower()

    except Exception:

        pass

    id_value = str(

        getattr(item, "id", "")

    ).lower()

    combined_name = f"{name} {id_value}"

    word_total = len(text.split())

    sample = text[:1500].lower()

    obvious_toc_name = any(

        token in combined_name

        for token in [

            "nav",

            "toc",

            "contents",

            "table_of_contents",

        ]

    )

    # Only throw away the whole EPUB document when it is clearly a small,

    # navigation-only document. Mixed documents survive because epub_item_text

    # removes just their TOC block and preserves their front matter.

    if obvious_toc_name and word_total < 500:

        return True

    if (

        "table of contents" in sample

        and word_total < 500

    ):

        return True

    return False


def _companion_cover_art(source_path: Path) -> Optional[tuple[str, bytes]]:

    mime_types = {

        ".jpg": "image/jpeg",

        ".jpeg": "image/jpeg",

        ".png": "image/png",

    }

    for suffix, mime in mime_types.items():

        candidate = source_path.with_suffix(suffix)

        if not candidate.is_file():

            continue

        try:

            data = candidate.read_bytes()

        except Exception:

            continue

        if data:

            return mime, data

    return None

def find_epub_cover_art(

    source_path: Path,

    book: Any,

) -> Optional[tuple[str, bytes]]:

    import posixpath

    import zipfile

    import xml.etree.ElementTree as ET

    def local_name(tag: str) -> str:

        return tag.rsplit("}", 1)[-1].lower()

    def normalise_mime(mime: Optional[str], path: str) -> Optional[str]:

        value = (mime or "").lower().strip()

        if value in {"image/jpeg", "image/jpg"}:

            return "image/jpeg"

        if value == "image/png":

            return "image/png"

        suffix = Path(path).suffix.lower()

        if suffix in {".jpg", ".jpeg"}:

            return "image/jpeg"

        if suffix == ".png":

            return "image/png"

        return None

    def valid_image(mime: Optional[str], data: bytes) -> bool:

        if not data:

            return False

        if mime == "image/jpeg":

            return data.startswith(b"\xff\xd8\xff")

        if mime == "image/png":

            return data.startswith(b"\x89PNG\r\n\x1a\n")

        return False

    def read_manifest_item(

        archive,

        opf_directory: str,

        item: dict,

    ) -> Optional[tuple[str, bytes]]:

        href = item.get("href", "").strip()

        if not href:

            return None

        archive_path = posixpath.normpath(

            posixpath.join(

                opf_directory,

                href.split("#", 1)[0],

            )

        )

        mime = normalise_mime(

            item.get("media-type"),
             archive_path,

        )

        if not mime:

            return None

        try:

            data = archive.read(archive_path)

        except Exception:

            return None

        if not valid_image(mime, data):

            return None

        return mime, data

    try:

        with zipfile.ZipFile(source_path, "r") as archive:

            container_data = archive.read(

                "META-INF/container.xml"

            )

            container_root = ET.fromstring(

                container_data

            )

            opf_path = None

            for element in container_root.iter():

                if local_name(element.tag) != "rootfile":

                    continue

                candidate = element.attrib.get(

                    "full-path"

                )

                if candidate:

                    opf_path = candidate

                    break

            if not opf_path:

                raise ValueError(

                    "EPUB package document was not found."

                )

            opf_root = ET.fromstring(

                archive.read(opf_path)

            )

            opf_directory = posixpath.dirname(

                opf_path

            )

            manifest = {}

            manifest_items = []

            for element in opf_root.iter():

                if local_name(element.tag) != "item":

                    continue

                item = dict(element.attrib)

                item_id = item.get("id")

                manifest_items.append(item)

                if item_id:

                    manifest[item_id] = item

            # EPUB 3: explicit cover-image property.

            for item in manifest_items:

                properties = set(

                    item.get(

                        "properties",

                        "",

                    ).split()

                )

                if "cover-image" not in properties:

                    continue

                result = read_manifest_item(

                    archive,

                    opf_directory,

                    item,

                )

                if result:

                    return result

            # EPUB 2: <meta name="cover" content="image-id">.

            for element in opf_root.iter():

                if local_name(element.tag) != "meta":

                    continue

                if (

                    element.attrib.get(

                        "name",

                        "",

                    ).lower()

                    != "cover"

                ):

                    continue

                cover_id = element.attrib.get(

                    "content"

                )

                if not cover_id:

                    continue

                item = manifest.get(

                    cover_id

                )

                if not item:

                    continue

                result = read_manifest_item(

                    archive,

                    opf_directory,

                    item,

                )

                if result:

                    return result

            # EPUB guide references can identify a cover document/image.

            for element in opf_root.iter():

                if local_name(element.tag) != "reference":

                    continue

                if (

                    "cover"

                    not in element.attrib.get(

                        "type",

                        "",

                    ).lower()

                ):

                    continue

                href = element.attrib.get(

                    "href",

                    ""

                )

                href_base = href.split(

                    "#",

                    1,

                )[0]

                for item in manifest_items:

                    if (

                        item.get(

                            "href",

                            "",

                        ).split("#", 1)[0]

                        != href_base

                    ):

                        continue

                    result = read_manifest_item(

                        archive,

                        opf_directory,

                        item,

                    )

                    if result:

                        return result

            # Inspect likely cover wrapper XHTML/SVG files and follow

            # their image references.

            wrapper_items = []

            for item in manifest_items:

                identity = (

                    item.get("id", "")

                    + " "

                    + item.get("href", "")

                ).lower()

                media_type = item.get(

                    "media-type",

                    ""

                ).lower()

                if (

                    "cover" in identity

                    and (

                        "xhtml" in media_type

                        or "html" in media_type

                        or "svg" in media_type

                    )

                ):

                    wrapper_items.append(item)

            for wrapper in wrapper_items:

                wrapper_href = wrapper.get(

                    "href",

                    ""

                )

                wrapper_path = posixpath.normpath(

                    posixpath.join(

                        opf_directory,

                        wrapper_href,

                    )

                )

                try:

                    wrapper_root = ET.fromstring(

                        archive.read(

                            wrapper_path

                        )

                    )

                except Exception:

                    continue

                wrapper_directory = posixpath.dirname(

                    wrapper_path

                )

                for element in wrapper_root.iter():

                    reference = (

                        element.attrib.get("src")

                        or element.attrib.get("href")

                        or element.attrib.get(

                            "{http://www.w3.org/1999/xlink}href"

                        )

                    )

                    if not reference:

                        continue

                    image_path = posixpath.normpath(

                        posixpath.join(

                            wrapper_directory,

                            reference.split("#", 1)[0],

                        )

                    )

                    mime = normalise_mime(

                        None,

                        image_path,

                    )

                    if not mime:

                        continue

                    try:

                        data = archive.read(

                            image_path

                        )

                    except Exception:

                        continue

                    if valid_image(

                        mime,

                        data,

                    ):

                        return mime, data

            # Final EPUB-native fallback: an actual image manifest item

            # whose ID or filename clearly identifies it as a cover.

            for item in manifest_items:

                identity = (

                    item.get("id", "")

                    + " "

                    + item.get("href", "")

                ).lower()

                if "cover" not in identity:

                    continue

                result = read_manifest_item(

                    archive,

                    opf_directory,

                    item,

                )

                if result:

                    return result

    except Exception:

        pass

    # EbookLib fallback for unusual EPUBs.

    try:

        items = list(

            book.get_items()

        )

    except Exception:

        items = []

    for item in items:

        try:

            if item.get_type() != ITEM_IMAGE:

                continue

        except Exception:

            continue

        try:

            name = item.get_name().lower()

        except Exception:

            name = ""

        try:

            item_id = str(

                item.id

            ).lower()

        except Exception:

            item_id = ""

        if "cover" not in name and "cover" not in item_id:

            continue

        try:

            data = item.get_content()

        except Exception:

            continue

        mime = normalise_mime(

            getattr(

                item,

                "media_type",

                None,

            ),

            name,

        )

        if (

            mime

            and valid_image(

                mime,

                data,

            )

        ):

            return mime, data

    # User-supplied companion image:

    # Book.epub + Book.jpg/png.

    return _companion_cover_art(

        source_path

    )


def _extract_epub_multi_anchor_structure(

    book: Any,

) -> Optional[tuple[str, list[str]]]:

    """

    Use EPUB TOC anchors as chapter boundaries when several real

    chapters live inside one or more XHTML spine documents.

    Returns None unless the structure is strong enough to trust.

    """

    import posixpath

    import re

    from urllib.parse import unquote

    from bs4 import BeautifulSoup

    STRUCTURED_START = (

        "<<<AUDIOBOOK_STRUCTURED_CHAPTER_START>>>"

    )

    STRUCTURED_BODY = (

        "<<<AUDIOBOOK_STRUCTURED_CHAPTER_BODY>>>"

    )

    STRUCTURED_END = (

        "<<<AUDIOBOOK_STRUCTURED_CHAPTER_END>>>"

    )

    number_words = (

        "one|two|three|four|five|six|seven|eight|nine|ten|"

        "eleven|twelve|thirteen|fourteen|fifteen|sixteen|"

        "seventeen|eighteen|nineteen|twenty"

    )

    major_pattern = re.compile(

        r"^(?:"

        r"(?:chapter|part|book|stave)\s+"

        r"(?:[IVXLCDM]+|\d+|"

        + number_words

        + r")\b"

        r"|"

        r"[IVXLCDM]+\.\s+\S+"

        r")",

        re.I,

    )

    def clean_title(value: Any) -> str:

        return re.sub(

            r"\s+",

            " ",

            str(value or ""),

        ).strip()

    def is_major_title(title: str) -> bool:

        return bool(

            major_pattern.match(

                clean_title(title)

            )

        )

    def flatten_toc(items):

        flattened = []

        for item in items:

            if isinstance(item, tuple):

                section, children = item

                flattened.append(

                    (

                        clean_title(

                            getattr(

                                section,

                                "title",

                                "",

                            )

                        ),

                        str(

                            getattr(

                                section,

                                "href",

                                "",

                            )

                            or ""

                        ),

                    )

                )

                flattened.extend(

                    flatten_toc(children)

                )

            else:

                flattened.append(

                    (

                        clean_title(

                            getattr(

                                item,

                                "title",

                                "",

                            )

                        ),

                        str(

                            getattr(

                                item,

                                "href",

                                "",

                            )

                            or ""

                        ),

                    )

                )

        return flattened

    toc_entries = flatten_toc(

        getattr(

            book,

            "toc",

            [],

        )

    )

    if not toc_entries:

        return None

    major_entries = []

    for index, (title, href) in enumerate(

        toc_entries

    ):

        if not title or not href:

            continue

        if not is_major_title(title):

            continue

        document_name, separator, fragment = (

            href.partition("#")

        )

        if not separator or not fragment:

            continue

        major_entries.append(

            {

                "toc_index": index,

                "label": title,

                "href": href,

                "document": unquote(

                    document_name

                ),

                "fragment": unquote(

                    fragment

                ),

            }

        )

    if len(major_entries) < 3:

        return None

    counts_by_document = {}

    for entry in major_entries:

        key = posixpath.normpath(

            entry["document"]

        )

        counts_by_document[key] = (

            counts_by_document.get(

                key,

                0,

            )

            + 1

        )

    # Only activate this mode when multiple chapter anchors occur

    # inside at least one XHTML document. One-chapter-per-document

    # EPUBs continue using the existing strong structural mode.

    if max(

        counts_by_document.values(),

        default=0,

    ) < 2:

        return None

    # Pair a major label with the immediately following TOC subtitle

    # when that subtitle points into the same document.

    chapters = []

    for entry in major_entries:

        toc_index = entry[

            "toc_index"

        ]

        title = entry[

            "label"

        ]

        subtitle = None

        subtitle_fragment = None

        next_index = toc_index + 1

        if next_index < len(

            toc_entries

        ):

            next_title, next_href = (

                toc_entries[

                    next_index

                ]

            )

            if (

                next_title

                and next_href

                and not is_major_title(

                    next_title

                )

            ):

                next_document, separator, next_fragment = (

                    next_href.partition(

                        "#"

                    )

                )

                same_document = (

                    posixpath.normpath(

                        unquote(

                            next_document

                        )

                    )

                    == posixpath.normpath(

                        entry[

                            "document"

                        ]

                    )

                )

                obvious_nonchapter = bool(

                    re.search(

                        r"project\s+gutenberg|"

                        r"contents|"

                        r"illustrations|"

                        r"characters|"

                        r"preface|"

                        r"license",

                        next_title,

                        re.I,

                    )

                )

                if (

                    separator

                    and next_fragment

                    and same_document

                    and not obvious_nonchapter

                ):

                    subtitle = clean_title(

                        next_title

                    )

                    subtitle_fragment = (

                        unquote(

                            next_fragment

                        )

                    )

        combined_title = title

        if subtitle:

            combined_title = (

                title

                + " - "

                + subtitle

            )

        chapters.append(

            {

                "title": combined_title,

                "label": title,

                "subtitle": subtitle,

                "document": entry[

                    "document"

                ],

                "fragment": entry[

                    "fragment"

                ],

                "body_fragment": (

                    subtitle_fragment

                    or entry[

                        "fragment"

                    ]

                ),

            }

        )

    # Build ordered readable spine documents.

    spine_documents = []

    for spine_entry in getattr(

        book,

        "spine",

        [],

    ):

        if isinstance(

            spine_entry,

            (tuple, list),

        ):

            item_id = spine_entry[0]

        else:

            item_id = spine_entry

        try:

            item = book.get_item_with_id(

                item_id

            )

        except Exception:

            item = None

        if item is None:

            continue

        try:

            name = item.get_name()

        except Exception:

            continue

        identity = (

            str(

                getattr(

                    item,

                    "id",

                    "",

                )

            )

            + " "

            + str(

                name

            )

        ).lower()

        # Covers/nav are not prose. Explicit Gutenberg footer/license

        # documents must never enter the chapter stream.

        if (

            "coverpage" in identity

            or "toc.xhtml" in identity

            or "pg-footer" in identity

            or "gutenberg-license" in identity

        ):

            continue

        try:

            raw = item.get_content().decode(

                "utf-8",

                errors="replace",

            )

        except AttributeError:

            try:

                raw = str(

                    item.get_content(),

                    "utf-8",

                    errors="replace",

                )

            except Exception:

                continue

        spine_documents.append(

            {

                "name": posixpath.normpath(

                    str(name)

                ),

                "raw": raw,

            }

        )

    if not spine_documents:

        return None

    def document_matches(

        spine_name: str,

        toc_name: str,

    ) -> bool:

        spine_norm = posixpath.normpath(

            spine_name

        )

        toc_norm = posixpath.normpath(

            toc_name

        )

        return (

            spine_norm == toc_norm

            or posixpath.basename(

                spine_norm

            )

            == posixpath.basename(

                toc_norm

            )

        )

    def find_fragment_position(

        raw: str,

        fragment: str,

    ) -> Optional[int]:

        escaped = re.escape(

            fragment

        )

        pattern = re.compile(

            r"""\bid\s*=\s*["']"""

            + escaped

            + r"""["']""",

            re.I,

        )

        match = pattern.search(

            raw

        )

        if not match:

            return None

        # Start at the opening tag that owns the ID.

        tag_start = raw.rfind(

            "<", 
            0,

            match.start(),

        )

        return (

            tag_start

            if tag_start >= 0

            else match.start()

        )

    located = []

    for chapter in chapters:

        found = None

        for document_index, document in enumerate(

            spine_documents

        ):

            if not document_matches(

                document[

                    "name"

                ],

                chapter[

                    "document"

                ],

            ):

                continue

            position = find_fragment_position(

                document[

                    "raw"

                ],

                chapter[

                    "fragment"

                ],

            )

            if position is None:

                continue

            body_position = find_fragment_position(

                document[

                    "raw"

                ],

                chapter[

                    "body_fragment"

                ],

            )

            if body_position is None:

                body_position = position

            found = {

                **chapter,

                "document_index": (

                    document_index

                ),

                "position": position,

                "body_position": (

                    body_position

                ),

            }

            break

        if found:

            located.append(

                found

            )

    if len(located) < 3:

        return None

    # Require most detected chapter labels to resolve to real anchors.

    if len(located) / len(chapters) < 0.75:

        return None

    located.sort(

        key=lambda item: (

            item[

                "document_index"

            ],

            item[

                "position"

            ],

        )

    )

    def html_to_text(

        html: str,

    ) -> str:

        soup = BeautifulSoup(

            html,

            "html.parser",

        )

        for unwanted in soup(

            [

                "script",

                "style",

            ]

        ):

            unwanted.decompose()

        text = soup.get_text(

            "\n",

            strip=True,

        )

        lines = [

            re.sub(

                r"\s+",

                " ",

                line,

            ).strip()

            for line in text.splitlines()

        ]

        return "\n".join(

            line

            for line in lines

            if line

        )

    def stream_slice(

        start_doc: int,

        start_pos: int,

        end_doc: int,

        end_pos: int,

    ) -> str:

        pieces = []

        if start_doc == end_doc:

            return (

                spine_documents[

                    start_doc

                ][

                    "raw"

                ][

                    start_pos:

                    end_pos

                ]

            )

        pieces.append(

            spine_documents[

                start_doc

            ][

                "raw"

            ][

                start_pos:

            ]

        )

        for document_index in range(

            start_doc + 1,

            end_doc,

        ):

            pieces.append(

                spine_documents[

                    document_index

                ][

                    "raw"

                ]

            )

        pieces.append(

            spine_documents[

                end_doc

            ][

                "raw"

            ][

                :end_pos

            ]

        )

        return "\n".join(

            pieces

        )

    # Preserve everything before the first real chapter as normal text.

    first = located[0]

    front_html = stream_slice(

        0,

        0,

        first[

            "document_index"

        ],

        first[

            "position"

        ],

    )

    front_text = html_to_text(

        front_html

    )

    # Strip Gutenberg machine boilerplate before the actual ebook start.

    start_marker = re.search(

        r"\*{3}\s*START OF THE PROJECT GUTENBERG EBOOK.*?\*{3}",

        front_text,

        re.I,

    )

    if start_marker:

        front_text = front_text[

            start_marker.end():

        ].strip()

    output_parts = []

    if front_text:

        output_parts.append(

            front_text

        )

    for index, chapter in enumerate(

        located

    ):

        start_doc = chapter[

            "document_index"

        ]

        start_pos = chapter[

            "body_position"

        ]

        if index + 1 < len(

            located

        ):

            next_chapter = located[

                index + 1

            ]

            end_doc = next_chapter[

                "document_index"

            ]

            end_pos = next_chapter[

                "position"

            ]

        else:

            end_doc = len(

                spine_documents

            ) - 1

            end_pos = len(

                spine_documents[

                    end_doc

                ][

                    "raw"

                ]

            )

        chapter_html = stream_slice(

            start_doc,

            start_pos,

            end_doc,

            end_pos,

        )

        body_text = html_to_text(

            chapter_html

        )

        # The structural marker supplies the spoken heading, so remove

        # duplicate heading lines from the beginning of the body.

        body_lines = body_text.splitlines()

        removable = {

            clean_title(

                chapter[

                    "label"

                ]

            ).casefold(),

        }

        if chapter[

            "subtitle"

        ]:

            removable.add(

                clean_title(

                    chapter[

                        "subtitle"

                    ]

                ).casefold()

            )

        cleaned_lines = []

        for line_index, line in enumerate(

            body_lines

        ):

            normalised = clean_title(

                line

            ).casefold()

            if (

                line_index < 8

                and normalised in removable

            ):

                continue

            cleaned_lines.append(

                line

            )

        body_text = "\n".join(

            cleaned_lines

        ).strip()

        output_parts.extend(

            [

                STRUCTURED_START,

                chapter[

                    "title"

                ],

                STRUCTURED_BODY,

                body_text,

                STRUCTURED_END,

            ]

        )

    text = "\n\n".join(

        part

        for part in output_parts

        if part

    ).strip()

    if not text:

        return None

    details = [

        "EPUB chapter detection: TOC anchor structural mode",

        (

            "EPUB structurally identified chapters: "

            + str(

                len(

                    located

                )

            )

        ),

        (

            "EPUB document items read: "

            + str(

                len(

                    spine_documents

                )

            )

        ),

        "EPUB navigation/contents items skipped: structural TOC boundaries used",

        "EPUB extraction method: multi-document TOC anchor stream",

    ]

    return text, details


def extract_epub_text(source_path: Path, output_text_path: Path) -> ExtractedSource:

    if ebook_epub is None:

        raise RuntimeError(

            "EPUB support needs ebooklib. "

            "Install it with: python3 -m pip install ebooklib beautifulsoup4"

        )

    if BeautifulSoup is None:

        raise RuntimeError(

            "EPUB support needs beautifulsoup4. "

            "Install it with: python3 -m pip install ebooklib beautifulsoup4"

        )

    book = ebook_epub.read_epub(str(source_path))

    metadata_title = epub_metadata_value(book, "DC", "title")

    metadata_author = epub_metadata_value(book, "DC", "creator")

    cover_art = find_epub_cover_art(source_path, book)

    details = [

        f"EPUB metadata title found: {'yes' if metadata_title else 'no'}",

        f"EPUB metadata author found: {'yes' if metadata_author else 'no'}",

        f"EPUB cover art found: {'yes' if cover_art else 'no'}",

    ]



    multi_anchor_result = _extract_epub_multi_anchor_structure(book)

    if multi_anchor_result:

        structured_text, structural_details = multi_anchor_result

        details.extend(structural_details)

        return ExtractedSource(

            structured_text,

            "EPUB",

            metadata_title,

            metadata_author,

            cover_art,

            details,

        )


    # ---------------------------------------------------------------

    # Build a proper map of EPUB navigation entries.

    #

    # We keep every title associated with each XHTML document because:

    #

    # one TOC entry -> one spine document

    #     Very strong evidence that the document itself is one chapter.

    #

    # several TOC entries -> one spine document

    #     The document probably contains several chapters internally,

    #     so we must fall back to heading-based splitting.

    # ---------------------------------------------------------------

    toc_by_document = {}

    def walk_toc(entries):

        for entry in entries:

            if isinstance(entry, (tuple, list)):

                walk_toc(entry)

                continue

            href = getattr(entry, "href", None)

            title = getattr(entry, "title", None)

            if href and title:

                document = href.split("#", 1)[0]

                cleaned_title = re.sub(

                    r"\s+",

                    " ",

                    str(title),

                ).strip()

                if cleaned_title:

                    toc_by_document.setdefault(

                        document,

                        [],

                    ).append(cleaned_title)

    try:

        walk_toc(book.toc)

    except Exception:

        pass

    documents = []

    nav_items_skipped = 0

    for spine_entry in getattr(book, "spine", []):

        idref = (

            spine_entry[0]

            if isinstance(spine_entry, (tuple, list))

            else spine_entry

        )

        item = book.get_item_with_id(idref)

        if item is None:

            continue

        try:

            if item.get_type() != ITEM_DOCUMENT:

                continue

        except Exception:

            continue

        soup = BeautifulSoup(

            item.get_content(),

            "html.parser",

        )

        for unwanted in soup(["script", "style", "nav"]):

            unwanted.decompose()

        try:

            name = item.get_name()

        except Exception:

            name = ""

        item_id = str(

            getattr(item, "id", "")

        )

        raw_text = soup.get_text(

            "\n",

            strip=True,

        )

        lines = [

            re.sub(r"\s+", " ", line).strip()

            for line in raw_text.splitlines()

            if line.strip()

        ]

        text = "\n".join(lines).strip()

        if not text:

            continue

        # Navigation-only resources are still discarded.

        if epub_is_nav_or_toc(item, text):

            nav_items_skipped += 1

            continue

        headings = []

        for tag_name in ["h1", "h2", "h3"]:

            for tag in soup.find_all(tag_name):

                value = re.sub(

                    r"\s+",

                    " ",

                    tag.get_text(

                        " ",

                        strip=True,

                    ),

                ).strip()

                if value:

                    headings.append(value)

        toc_titles = toc_by_document.get(

            name,

            [],

        )

        html_heading = choose_best_epub_heading(

            headings

        )

        word_total = len(

            text.split()

        )

        combined_identity = (

            f"{item_id} {name}"

        ).lower()

        obvious_nonchapter = any(

            token in combined_identity

            for token in [

                "cover",

                "titlepage",

                "title-page",

                "copyright",

                "colophon",

                "pg-header",

                "pg-footer",

                "license",

            ]

        )

        heading_sample = (

            " ".join(headings[:3])

        ).lower()

        if any(

            phrase in heading_sample

            for phrase in [

                "table of contents",

                "contents",

                "full project gutenberg",

                "project gutenberg ebook",

            ]

        ):

            obvious_nonchapter = True

        documents.append(

            {

                "name": name,

                "id": item_id,

                "text": text,

                "words": word_total,

                "toc_titles": toc_titles,

                "html_heading": html_heading,

                "obvious_nonchapter": obvious_nonchapter,

            }

        )

    # ---------------------------------------------------------------

    # Decide whether this EPUB has strong one-document-per-chapter

    # structure.

    #

    # A document qualifies strongly when:

    # - it contains meaningful body text;

    # - it is not obvious front/back matter;

    # - exactly one TOC entry points to that document.

    #

    # We only activate this mode when at least three such documents exist

    # and they represent most of the meaningful book text.

    # ---------------------------------------------------------------

    strong_documents = []

    for document in documents:

        if document["obvious_nonchapter"]:

            continue

        if document["words"] < 80:

            continue

        if len(document["toc_titles"]) == 1:

            strong_documents.append(document)

    meaningful_words = sum(

        document["words"]

        for document in documents

        if not document["obvious_nonchapter"]

    )

    strong_words = sum(

        document["words"]

        for document in strong_documents

    )

    structured_mode = (

        len(strong_documents) >= 3

        and meaningful_words > 0

        and strong_words / meaningful_words >= 0.60

    )

    parts = []

    if structured_mode:

        strong_ids = {

            id(document)

            for document in strong_documents

        }

        first_strong_seen = False

        for document in documents:

            if id(document) not in strong_ids:

                # Material before the first real chapter remains ordinary

                # text so the existing front-matter reviewer can ask the user

                # about it individually.

                #

                # Material after the chapter sequence is deliberately omitted

                # from the chapter stream rather than becoming a bogus final

                # audiobook chapter.

                if not first_strong_seen:

                    parts.append(

                        document["text"]

                    )

                continue

            first_strong_seen = True

            heading = (

                document["toc_titles"][0]

                or document["html_heading"]

                or "Untitled Chapter"

            )

            heading = re.sub(

                r"\s+",

                " ",

                heading,

            ).strip()

            parts.append(

                "<<<AUDIOBOOK_STRUCTURED_CHAPTER_START>>>"

            )

            parts.append(

                heading

            )

            parts.append(

                "<<<AUDIOBOOK_STRUCTURED_CHAPTER_BODY>>>"

            )

            parts.append(

                document["text"]

            )

            parts.append(

                "<<<AUDIOBOOK_STRUCTURED_CHAPTER_END>>>"

            )

        details.append(

            "EPUB chapter detection: strong structural mode"

        )

        details.append(

            f"EPUB structurally identified chapters: "

            f"{len(strong_documents)}"

        )

    else:

        # No trustworthy one-document-per-chapter structure.

        #

        # Preserve the full spine text and allow the general heading parser

        # to split it. This covers EPUBs where many chapters live inside one

        # XHTML file, such as some editions of A Christmas Carol.

        for document in documents:

            heading = document["html_heading"]

            if (

                heading

                and heading.lower()

                not in document["text"][:300].lower()

            ):

                parts.append(heading)

            parts.append(

                document["text"]

            )

        details.append(

            "EPUB chapter detection: heading fallback mode"

        )

    details.append(

        f"EPUB document items read: {len(documents)}"

    )

    details.append(

        f"EPUB navigation/contents items skipped: "

        f"{nav_items_skipped}"

    )

    details.append(

        "EPUB extraction method: structured spine extraction"

    )

    text = "\n\n".join(parts)

    output_text_path.write_text(

        text,

        encoding="utf-8",

    )

    return ExtractedSource(

        clean_text(text),

        "EPUB",

        metadata_title,

        metadata_author,

        cover_art,

        details,

    )


def _find_pdf_cover_art(

    source_path: Path,

) -> Optional[tuple[str, bytes]]:

    """

    Render the first PDF page as cover art.

    Failure is deliberately non-fatal.

    """

    import subprocess

    import tempfile

    with tempfile.TemporaryDirectory(

        prefix="audiobook_pdf_cover_"

    ) as temp_directory:

        output_base = (

            Path(temp_directory)

            / "cover"

        )

        try:

            result = subprocess.run(

                [

                    "pdftoppm",

                    "-f",

                    "1",

                    "-l",

                    "1",

                    "-singlefile",

                    "-jpeg",

                    "-jpegopt",

                    "quality=90",

                    "-scale-to",

                    "1600",

                    str(source_path),

                    str(output_base),

                ],

                stdout=subprocess.DEVNULL,

                stderr=subprocess.DEVNULL,

                check=False,

            )

        except Exception:

            return None

        if result.returncode != 0:

            return None

        image_path = output_base.with_suffix(

            ".jpg"

        )

        if not image_path.is_file():

            return None

        try:

            data = image_path.read_bytes()

        except Exception:

            return None

        # Reject obviously empty or broken renders.

        if (

            len(data) < 5000

            or not data.startswith(

                b"\xff\xd8\xff"

            )

        ):

            return None

        return "image/jpeg", data

def _find_docx_cover_art(

    source_path: Path,

) -> Optional[tuple[str, bytes]]:

    """

    Find the first image referenced near the beginning of a DOCX.

    Images appearing only after substantial body text are ignored so

    ordinary illustrations are not automatically mistaken for covers.

    """

    import posixpath

    import re

    import zipfile

    import xml.etree.ElementTree as ET

    REL_NS = (

        "http://schemas.openxmlformats.org/"

        "officeDocument/2006/relationships"

    )

    PACKAGE_REL_NS = (

        "http://schemas.openxmlformats.org/"

        "package/2006/relationships"

    )

    DRAWING_NS = (

        "http://schemas.openxmlformats.org/"

        "drawingml/2006/main"

    )

    WORD_NS = (

        "http://schemas.openxmlformats.org/"

        "wordprocessingml/2006/main"

    )

    def mime_for_name(

        name: str,

    ) -> Optional[str]:

        suffix = Path(

            name

        ).suffix.lower()

        if suffix in {

            ".jpg",

            ".jpeg",

        }:

            return "image/jpeg"

        if suffix == ".png":

            return "image/png"

        return None

    def valid_image(

        mime: str,

        data: bytes,

    ) -> bool:

        if mime == "image/jpeg":

            return data.startswith(

                b"\xff\xd8\xff"

            )

        if mime == "image/png":

            return data.startswith(

                b"\x89PNG\r\n\x1a\n"

            )

        return False

    try:

        with zipfile.ZipFile(

            source_path,

            "r",

        ) as archive:

            document_xml = archive.read(

                "word/document.xml"

            )

            relationships_xml = archive.read(

                "word/_rels/document.xml.rels"

            )

            document_root = ET.fromstring(

                document_xml

            )

            relationships_root = ET.fromstring(

                relationships_xml

            )

            relationship_targets = {}

            for relationship in relationships_root:

                relationship_id = (

                    relationship.attrib.get(

                        "Id"

                    )

                )

                target = (

                    relationship.attrib.get(

                        "Target"

                    )

                )

                if (

                    relationship_id

                    and target

                ):

                    relationship_targets[

                        relationship_id

                    ] = target

            words_before_image = 0

            chosen_relationship = None

            for element in document_root.iter():

                if element.tag == (

                    "{"

                    + WORD_NS

                    + "}t"

                ):

                    words_before_image += len(

                        re.findall(

                            r"\S+",

                            element.text

                            or "",

                        )

                    )

                if words_before_image > 250:

                    break

                relationship_id = (

                    element.attrib.get(

                        "{"

                        + REL_NS

                        + "}embed"

                    )

                )

                if relationship_id:

                    chosen_relationship = (

                        relationship_id

                    )

                    break

            if not chosen_relationship:

                return None

            target = relationship_targets.get(

                chosen_relationship

            )

            if not target:

                return None

            image_path = posixpath.normpath(

                posixpath.join(

                    "word",

                    target,

                )

            )

            mime = mime_for_name(

                image_path

            )

            if not mime:

                return None

            try:

                data = archive.read(

                    image_path

                )

            except Exception:

                return None

            if (

                not data

                or not valid_image(

                    mime,

                    data,

                )

            ):

                return None

            return mime, data

    except Exception:

        return None

def _cover_with_fallback(

    source_path: Path,

    native_cover: Optional[

        tuple[str, bytes]

    ],

    native_description: str,

) -> tuple[

    Optional[tuple[str, bytes]],

    str,

]:

    """

    Prefer a same-name companion image, then use source-native artwork.

    """

    companion = _companion_cover_art(

        source_path

    )

    if companion:

        return (

            companion,

            "companion image",

        )

    if native_cover:

        return (

            native_cover,

            native_description,

        )



    return None, "none"


def extract_source_text( 
    source_path: Path,

    book_title: str,

) -> ExtractedSource:

    EXTRACTED_TEXT_DIR.mkdir(

        parents=True,

        exist_ok=True,

    )

    source_type = (

        source_path

        .suffix

        .lower()

        .lstrip(".")

        .upper()

    )

    output_text_path = (

        EXTRACTED_TEXT_DIR

        / f"{safe_filename(book_title)}.txt"

    )

    suffix = source_path.suffix.lower()

    if suffix == ".pdf":

        raw = extract_pdf_text(

            source_path,

            output_text_path,

        )

        native_cover = (

            _find_pdf_cover_art(

                source_path

            )

        )

        cover_art, cover_source = (

            _cover_with_fallback(

                source_path,

                native_cover,

                "PDF page 1",

            )

        )

        return ExtractedSource(

            clean_text(raw),

            "PDF",

            None,

            None,

            cover_art,

            [

                (

                    "Cover art source: "

                    + cover_source

                )

            ],

        )

    if suffix == ".txt":

        raw = extract_txt_text(

            source_path,

            output_text_path,

        )

        cover_art, cover_source = (

            _cover_with_fallback(

                source_path,

                None,

                "",

            )

        )

        return ExtractedSource(

            clean_text(raw),

            "TXT",

            None,

            None,

            cover_art,

            [

                (

                    "Cover art source: "

                    + cover_source

                )

            ],

        )

    if suffix == ".docx":

        raw = extract_docx_text(

            source_path,

            output_text_path,

        )

        native_cover = (

            _find_docx_cover_art(

                source_path

            )

        )

        cover_art, cover_source = (

            _cover_with_fallback(

                source_path,

                native_cover,

                "DOCX early document image",

            )

        )

        return ExtractedSource(

            clean_text(raw),

            "DOCX",

            None,

            None,

            cover_art,

            [

                (

                    "Cover art source: "

                    + cover_source

                )

            ],

        )

    if suffix == ".epub":

        return extract_epub_text(

            source_path,

            output_text_path,

        )

    raise RuntimeError(

        "Unsupported file type: "

        + source_path.suffix

    )


