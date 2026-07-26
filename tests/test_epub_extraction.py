from pathlib import Path
from types import SimpleNamespace

from audiobook_maker import extractors


class FakeItem:
    def __init__(self, item_id: str, name: str, html: str, item_type: int = 9):

        self.id = item_id

        self._name = name

        self._html = html.encode("utf-8")

        self._type = item_type

    def get_name(self):

        return self._name

    def get_content(self):

        return self._html

    def get_type(self):

        return self._type


class FakeBook:
    def __init__(self, items, spine, toc, metadata=None):

        self._items = {item.id: item for item in items}

        self.spine = spine

        self.toc = toc

        self._metadata = metadata or {}

    def get_item_with_id(self, item_id):

        return self._items.get(item_id)

    def get_metadata(self, namespace, name):

        return self._metadata.get((namespace, name), [])


def toc_entry(title: str, href: str):

    return SimpleNamespace(title=title, href=href)


def test_multi_anchor_epub_uses_toc_anchors(monkeypatch):

    html = """

    <html><body>

    <p>Front matter text.</p>

    <h1 id="chapter-1">Chapter I</h1>

    <p>First chapter body.</p>

    <h2 id="chapter-2">Chapter II</h2>

    <p>Second chapter body.</p>

    <h2 id="chapter-3">Chapter III</h2>

    <p>Third chapter body.</p>

    </body></html>

    """

    item = FakeItem("book", "book.xhtml", html)

    book = FakeBook(
        [item],
        [("book", "yes")],
        [
            toc_entry("Chapter I", "book.xhtml#chapter-1"),
            toc_entry("Chapter II", "book.xhtml#chapter-2"),
            toc_entry("Chapter III", "book.xhtml#chapter-3"),
        ],
    )

    result = extractors._extract_epub_multi_anchor_structure(book)

    assert result is not None

    text, details = result

    assert "<<<AUDIOBOOK_STRUCTURED_CHAPTER_START>>>" in text

    assert text.count("<<<AUDIOBOOK_STRUCTURED_CHAPTER_START>>>") == 3

    assert "Chapter I" in text

    assert "First chapter body." in text

    assert "Chapter II" in text

    assert "Second chapter body." in text

    assert "Chapter III" in text

    assert "Third chapter body." in text

    assert any("TOC anchor structural mode" in detail for detail in details)


def test_extract_epub_text_uses_one_document_per_chapter_structure(monkeypatch, tmp_path):

    items = [
        FakeItem("front", "front.xhtml", "<html><body><p>Dedication text.</p></body></html>"),
        FakeItem(
            "c1",
            "chapter1.xhtml",
            "<html><body><h1>Chapter One</h1><p>" + "word " * 100 + "</p></body></html>",
        ),
        FakeItem(
            "c2",
            "chapter2.xhtml",
            "<html><body><h1>Chapter Two</h1><p>" + "word " * 100 + "</p></body></html>",
        ),
        FakeItem(
            "c3",
            "chapter3.xhtml",
            "<html><body><h1>Chapter Three</h1><p>" + "word " * 100 + "</p></body></html>",
        ),
    ]

    book = FakeBook(
        items,
        [("front", "yes"), ("c1", "yes"), ("c2", "yes"), ("c3", "yes")],
        [
            toc_entry("Chapter One", "chapter1.xhtml"),
            toc_entry("Chapter Two", "chapter2.xhtml"),
            toc_entry("Chapter Three", "chapter3.xhtml"),
        ],
        {
            ("DC", "title"): [("Test Book", {})],
            ("DC", "creator"): [("Test Author", {})],
        },
    )

    monkeypatch.setattr(extractors.ebook_epub, "read_epub", lambda path: book)

    monkeypatch.setattr(extractors, "find_epub_cover_art", lambda source, parsed: None)

    output = tmp_path / "book.txt"

    result = extractors.extract_epub_text(Path("book.epub"), output)

    assert result.source_type == "EPUB"

    assert result.metadata_title == "Test Book"

    assert result.metadata_author == "Test Author"

    assert result.text.count("<<<AUDIOBOOK_STRUCTURED_CHAPTER_START>>>") == 3

    assert "Dedication text." in result.text

    assert any("strong structural mode" in detail for detail in result.details)

    assert output.exists()


def test_extract_epub_text_falls_back_to_heading_mode(monkeypatch, tmp_path):

    html = """

    <html><body>

    <h1>Chapter One</h1>

    <p>First body text.</p>

    <h1>Chapter Two</h1>

    <p>Second body text.</p>

    </body></html>

    """

    item = FakeItem("book", "book.xhtml", html)

    book = FakeBook(
        [item],
        [("book", "yes")],
        [],
    )

    monkeypatch.setattr(extractors.ebook_epub, "read_epub", lambda path: book)

    monkeypatch.setattr(extractors, "find_epub_cover_art", lambda source, parsed: None)

    output = tmp_path / "book.txt"

    result = extractors.extract_epub_text(Path("book.epub"), output)

    assert "Chapter One" in result.text

    assert "First body text." in result.text

    assert "Chapter Two" in result.text

    assert "Second body text." in result.text

    assert any("heading fallback mode" in detail for detail in result.details)

    assert output.exists()
