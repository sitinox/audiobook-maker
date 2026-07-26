from pathlib import Path

import pytest

from audiobook_maker.pipeline import _output_directories


def test_mp3_output_directories():

    root = Path("/tmp/Test Book")

    mp3_dir, m4b_dir = _output_directories(root, "mp3")

    assert mp3_dir == root

    assert m4b_dir is None


def test_m4b_output_directories():

    root = Path("/tmp/Test Book")

    mp3_dir, m4b_dir = _output_directories(root, "m4b")

    assert mp3_dir is None

    assert m4b_dir == root


def test_both_output_directories():

    root = Path("/tmp/Test Book")

    mp3_dir, m4b_dir = _output_directories(root, "both")

    assert mp3_dir == root / "MP3"

    assert m4b_dir == root


def test_invalid_output_format():

    with pytest.raises(ValueError):
        _output_directories(Path("/tmp/Test Book"), "cassette")
