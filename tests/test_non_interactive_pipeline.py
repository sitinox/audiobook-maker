from pathlib import Path

from audiobook_maker.common import ConversionOptions, ExtractedSource, Section, Settings
from audiobook_maker.pipeline import PreparedBook, _choose_book_identity, _review_track_plan


def fail_prompt(*_args, **_kwargs):
    raise AssertionError("Interactive prompt was called.")


def test_non_interactive_identity_uses_overrides_without_prompt(monkeypatch):
    monkeypatch.setattr("audiobook_maker.pipeline.choose_title", fail_prompt)
    monkeypatch.setattr("audiobook_maker.pipeline.choose_author", fail_prompt)

    title, author = _choose_book_identity(
        Path("Example.epub"),
        "Detected Title",
        "Detected Author",
        [],
        ConversionOptions(
            non_interactive=True,
            title="CLI Title",
            author="CLI Author",
        ),
    )

    assert title == "CLI Title"
    assert author == "CLI Author"


def test_non_interactive_identity_uses_detected_defaults(monkeypatch):
    monkeypatch.setattr("audiobook_maker.pipeline.choose_title", fail_prompt)
    monkeypatch.setattr("audiobook_maker.pipeline.choose_author", fail_prompt)

    title, author = _choose_book_identity(
        Path("Example.epub"),
        "Detected Title",
        "Detected Author",
        [],
        ConversionOptions(non_interactive=True),
    )

    assert title == "Detected Title"
    assert author == "Detected Author"


def make_book() -> PreparedBook:
    front = [Section("Copyright", "Copyright text", kind="front")]
    main = [Section("Chapter 1", "This is the main chapter text.", kind="main")]

    return PreparedBook(
        source_path=Path("Example.epub"),
        extracted=ExtractedSource(
            text="Copyright text\n\nChapter 1\nThis is the main chapter text.",
            source_type="EPUB",
        ),
        source_type="EPUB",
        title="Example",
        author="Author",
        book_title="Example",
        text="Copyright text\n\nChapter 1\nThis is the main chapter text.",
        words_total=10,
        warnings=[],
        front_sections=front,
        main_sections=main,
        main_start="Chapter 1",
    )


def test_non_interactive_front_matter_defaults_to_skip(monkeypatch):
    monkeypatch.setattr("audiobook_maker.pipeline.review_front_matter", fail_prompt)
    monkeypatch.setattr("audiobook_maker.pipeline.ask", fail_prompt)

    plan = _review_track_plan(
        make_book(),
        Settings(),
        ConversionOptions(non_interactive=True),
    )

    assert plan is not None
    assert plan.kept_front == []


def test_non_interactive_front_matter_can_be_kept(monkeypatch):
    monkeypatch.setattr("audiobook_maker.pipeline.review_front_matter", fail_prompt)
    monkeypatch.setattr("audiobook_maker.pipeline.ask", fail_prompt)

    book = make_book()
    plan = _review_track_plan(
        book,
        Settings(),
        ConversionOptions(non_interactive=True, front_matter="keep"),
    )

    assert plan is not None
    assert plan.kept_front == book.front_sections
