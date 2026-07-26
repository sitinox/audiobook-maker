from pathlib import Path

import pytest

from audiobook_maker.cli import conversion_options_from_args, parse_args


def test_yes_is_alias_for_non_interactive(monkeypatch):
    monkeypatch.setattr("sys.argv", ["audiobook", "--yes"])
    assert parse_args().non_interactive is True


def test_source_enables_non_interactive_mode(monkeypatch):
    monkeypatch.setattr("sys.argv", ["audiobook", "--source", "Example.epub"])
    args = parse_args()
    assert args.non_interactive is True
    assert args.source == Path("Example.epub")


def test_all_and_source_are_mutually_exclusive(monkeypatch):
    monkeypatch.setattr("sys.argv", ["audiobook", "--all", "--source", "Example.epub"])
    with pytest.raises(SystemExit) as error:
        parse_args()
    assert error.value.code == 2


def test_title_requires_single_source(monkeypatch):
    monkeypatch.setattr("sys.argv", ["audiobook", "--title", "Example"])
    with pytest.raises(SystemExit) as error:
        parse_args()
    assert error.value.code == 2


def test_non_interactive_choices_are_parsed(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "audiobook",
            "--source",
            "Example.epub",
            "--title",
            "Example Book",
            "--author",
            "Example Author",
            "--front-matter",
            "keep",
            "--output",
            "both",
            "--original",
            "archive",
            "--project-dir",
            "/tmp/Audiobooks",
        ],
    )
    args = parse_args()
    options = conversion_options_from_args(args)
    assert options.non_interactive is True
    assert options.source == Path("Example.epub")
    assert options.process_all is False
    assert options.title == "Example Book"
    assert options.author == "Example Author"
    assert options.front_matter == "keep"
    assert args.output == "both"
    assert args.original == "archive"
    assert args.project_dir == Path("/tmp/Audiobooks")


def test_interactive_defaults_remain_unchanged(monkeypatch):
    monkeypatch.setattr("sys.argv", ["audiobook"])
    options = conversion_options_from_args(parse_args())
    assert options.non_interactive is False
    assert options.source is None
    assert options.process_all is False
    assert options.title is None
    assert options.author is None
    assert options.front_matter is None
