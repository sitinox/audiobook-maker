
from pathlib import Path

import shutil

import subprocess

import pytest

from audiobook_maker.m4b import M4BChapter, create_m4b

def make_test_mp3(path: Path) -> None:

    subprocess.run(

        [

            "ffmpeg",

            "-y",

            "-f",

            "lavfi",

            "-i",

            "anullsrc=r=44100:cl=mono",

            "-t",

            "0.5",

            "-q:a",

            "5",

            str(path),

        ],

        check=True,

        stdout=subprocess.DEVNULL,

        stderr=subprocess.DEVNULL,

    )

def test_create_m4b_with_chapters_and_metadata(tmp_path):

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):

        pytest.skip("ffmpeg and ffprobe are required for the M4B test")

    chapter_one = tmp_path / "chapter_one.mp3"

    chapter_two = tmp_path / "chapter_two.mp3"

    output = tmp_path / "test_audiobook.m4b"

    make_test_mp3(chapter_one)

    make_test_mp3(chapter_two)

    result = create_m4b(

        chapters=[

            M4BChapter("Chapter One", chapter_one),

            M4BChapter("Chapter Two", chapter_two),

        ],

        output_path=output,

        title="Disposable Test Book",

        author="Audiobook Maker Tests",

        narrator="Daniel",

        bitrate_kbps=128,

    )

    assert result.output_path.exists()

    assert result.output_path.suffix == ".m4b"

    assert result.chapter_count == 2

    assert result.duration_seconds > 0.8

    assert result.metadata.get("title") == "Disposable Test Book"

    assert result.metadata.get("artist") == "Audiobook Maker Tests"

    assert result.has_cover_art is False

