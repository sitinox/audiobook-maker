from types import SimpleNamespace

import audiobook_maker.files as files


def test_keep_leaves_original_in_place(tmp_path):

    source = tmp_path / "Book.txt"

    source.write_text("test", encoding="utf-8")

    result = files.handle_successful_original(
        source,
        "keep",
        tmp_path / "Converted Originals",
    )

    assert source.exists()

    assert result == "Original kept in Books to Convert."


def test_archive_moves_original(tmp_path, monkeypatch):

    source = tmp_path / "Book.txt"

    source.write_text("test", encoding="utf-8")

    archive = tmp_path / "Converted Originals"

    result = files.handle_successful_original(
        source,
        "archive",
        archive,
    )

    assert not source.exists()

    assert (archive / "Book.txt").exists()

    assert result == "Original moved to Converted Originals as: Book.txt"


def test_archive_uses_unique_name(tmp_path, monkeypatch):

    source = tmp_path / "Book.txt"

    source.write_text("new", encoding="utf-8")

    archive = tmp_path / "Converted Originals"

    archive.mkdir()

    (archive / "Book.txt").write_text("existing", encoding="utf-8")

    result = files.handle_successful_original(
        source,
        "archive",
        archive,
    )

    assert not source.exists()

    assert (archive / "Book.txt").read_text(encoding="utf-8") == "existing"

    assert (archive / "Book (2).txt").read_text(encoding="utf-8") == "new"

    assert result == "Original moved to Converted Originals as: Book (2).txt"


def test_trash_reports_success_when_original_disappears(tmp_path, monkeypatch):

    source = tmp_path / "Book.txt"

    source.write_text("test", encoding="utf-8")

    def fake_run(*args, **kwargs):

        source.unlink()

        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(files.subprocess, "run", fake_run)

    result = files.handle_successful_original(
        source,
        "trash",
        tmp_path / "Converted Originals",
    )

    assert not source.exists()

    assert result == "Original moved to the Bin."
