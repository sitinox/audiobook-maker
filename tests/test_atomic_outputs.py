import pytest

import audiobook_maker.audio as audio
import audiobook_maker.m4b as m4b
import audiobook_maker.pipeline as pipeline


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
    monkeypatch.setattr(
        m4b, "_build_combined_audio", lambda **kwargs: kwargs["output_path"].write_bytes(b"audio")
    )

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
    monkeypatch.setattr(
        m4b, "_build_combined_audio", lambda **kwargs: kwargs["output_path"].write_bytes(b"audio")
    )
    monkeypatch.setattr(
        m4b, "_build_final_m4b", lambda **kwargs: kwargs["output_path"].write_bytes(b"new-complete")
    )

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


def test_later_chapter_failure_leaves_previous_mp3_audiobook_unchanged(
    tmp_path,
):

    output = tmp_path / "Book"

    output.mkdir()

    (output / "old-one.mp3").write_bytes(b"old-one")

    (output / "old-two.mp3").write_bytes(b"old-two")

    staging = tmp_path / ".Book.staging"

    staging.mkdir()

    with pytest.raises(RuntimeError, match="chapter two failed"):
        (staging / "new-one.mp3").write_bytes(b"new-one")

        raise RuntimeError("chapter two failed")

    assert {item.name: item.read_bytes() for item in output.iterdir()} == {
        "old-one.mp3": b"old-one",
        "old-two.mp3": b"old-two",
    }

    assert (staging / "new-one.mp3").read_bytes() == b"new-one"


def test_successful_mp3_publication_replaces_complete_audiobook(
    tmp_path,
):

    output = tmp_path / "Book"

    output.mkdir()

    (output / "old-one.mp3").write_bytes(b"old-one")

    (output / "obsolete-three.mp3").write_bytes(b"obsolete")

    staging = tmp_path / ".Book.staging"

    staging.mkdir()

    (staging / "new-one.mp3").write_bytes(b"new-one")

    (staging / "new-two.mp3").write_bytes(b"new-two")

    pipeline._publish_mp3_directory(staging, output)

    assert {path.name: path.read_bytes() for path in output.iterdir()} == {
        "new-one.mp3": b"new-one",
        "new-two.mp3": b"new-two",
    }

    assert not staging.exists()


def test_mp3_publication_failure_restores_previous_audiobook(
    tmp_path,
    monkeypatch,
):

    output = tmp_path / "Book"

    output.mkdir()

    (output / "old.mp3").write_bytes(b"old")

    staging = tmp_path / ".Book.staging"

    staging.mkdir()

    (staging / "new.mp3").write_bytes(b"new")

    real_replace = pipeline.os.replace

    replace_calls = 0

    def fail_when_publishing(source, destination):

        nonlocal replace_calls

        replace_calls += 1

        if replace_calls == 2:
            raise OSError("simulated publication failure")

        return real_replace(source, destination)

    monkeypatch.setattr(
        pipeline.os,
        "replace",
        fail_when_publishing,
    )

    with pytest.raises(
        OSError,
        match="simulated publication failure",
    ):
        pipeline._publish_mp3_directory(staging, output)

    assert (output / "old.mp3").read_bytes() == b"old"

    assert not (output / "new.mp3").exists()
