from pathlib import Path

import pytest

import audiobook_maker.audio as audio
import audiobook_maker.m4b as m4b


def test_audio_duration_failure_is_not_silently_zero(tmp_path, monkeypatch):
    source = tmp_path / "broken.mp3"
    source.write_bytes(b"not audio")
    monkeypatch.setattr(audio, "MP3", None)

    class Result:
        returncode = 1
        stdout = ""
        stderr = "invalid data"

    monkeypatch.setattr(audio.subprocess, "run", lambda *args, **kwargs: Result())

    with pytest.raises(RuntimeError, match="invalid data"):
        audio.get_audio_duration(source)


def test_m4b_failure_preserves_existing_output(tmp_path, monkeypatch):
    chapter = tmp_path / "chapter.mp3"
    chapter.write_bytes(b"chapter")
    output = tmp_path / "book.m4b"
    output.write_bytes(b"known-good-old-output")

    monkeypatch.setattr(m4b, "get_audio_duration", lambda path: 1.0)
    monkeypatch.setattr(m4b, "_write_concat_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(m4b, "_write_ffmetadata_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(m4b, "_build_combined_audio", lambda **kwargs: kwargs["output_path"].write_bytes(b"audio"))

    def fail_final(**kwargs):
        kwargs["output_path"].write_bytes(b"partial-new-output")
        raise m4b.M4BError("simulated final write failure")

    monkeypatch.setattr(m4b, "_build_final_m4b", fail_final)

    with pytest.raises(m4b.M4BError, match="simulated"):
        m4b.create_m4b(
            chapters=[m4b.M4BChapter("One", chapter)],
            output_path=output,
            title="Book",
            author="Author",
        )

    assert output.read_bytes() == b"known-good-old-output"


def test_m4b_is_replaced_only_after_verification(tmp_path, monkeypatch):
    chapter = tmp_path / "chapter.mp3"
    chapter.write_bytes(b"chapter")
    output = tmp_path / "book.m4b"
    output.write_bytes(b"old")

    monkeypatch.setattr(m4b, "get_audio_duration", lambda path: 1.0)
    monkeypatch.setattr(m4b, "_write_concat_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(m4b, "_write_ffmetadata_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(m4b, "_build_combined_audio", lambda **kwargs: kwargs["output_path"].write_bytes(b"audio"))
    monkeypatch.setattr(m4b, "_build_final_m4b", lambda **kwargs: kwargs["output_path"].write_bytes(b"new-complete"))

    def verify(**kwargs):
        assert output.read_bytes() == b"old"
        return m4b.M4BResult(kwargs["output_path"], 1, 1.0, {"title": "Book"}, False)

    monkeypatch.setattr(m4b, "verify_m4b", verify)

    result = m4b.create_m4b(
        chapters=[m4b.M4BChapter("One", chapter)],
        output_path=output,
        title="Book",
        author="Author",
    )

    assert output.read_bytes() == b"new-complete"
    assert result.output_path == output
