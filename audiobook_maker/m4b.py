
#!/usr/bin/env python3

from __future__ import annotations

import json

import os

import shutil

import subprocess

import tempfile

from dataclasses import dataclass

from pathlib import Path

from typing import Iterable, Mapping, Optional, Sequence

@dataclass(frozen=True)

class M4BChapter:

    title: str

    audio_path: Path

@dataclass(frozen=True)

class M4BResult:

    output_path: Path

    chapter_count: int

    duration_seconds: float

    metadata: dict[str, str]

    has_cover_art: bool

class M4BError(RuntimeError):

    """Raised when an M4B audiobook cannot be created or verified."""

def _require_command(name: str) -> str:

    path = shutil.which(name)

    if not path:

        raise M4BError(

            f"Required command '{name}' was not found. "

            f"Please install FFmpeg and make sure {name} is available."

        )

    return path

def _run(

    command: Sequence[str],

    *,

    description: str,

) -> subprocess.CompletedProcess[str]:

    try:

        result = subprocess.run(

            list(command),

            check=False,

            capture_output=True,

            text=True,

        )

    except OSError as exc:

        raise M4BError(f"{description} failed: {exc}") from exc

    if result.returncode != 0:

        details = result.stderr.strip() or result.stdout.strip()

        raise M4BError(

            f"{description} failed with exit code {result.returncode}."

            + (f"\n{details}" if details else "")

        )

    return result

def _probe_json(path: Path) -> dict:

    ffprobe = _require_command("ffprobe")

    result = _run(

        [

            ffprobe,

            "-v",

            "error",

            "-show_format",

            "-show_streams",

            "-show_chapters",

            "-of",

            "json",

            str(path),

        ],

        description=f"Probing {path.name}",

    )

    try:

        return json.loads(result.stdout)

    except json.JSONDecodeError as exc:

        raise M4BError(

            f"ffprobe returned invalid JSON for {path.name}."

        ) from exc

def get_audio_duration(path: Path) -> float:

    path = Path(path)

    if not path.is_file():

        raise M4BError(f"Audio file does not exist: {path}")

    ffprobe = _require_command("ffprobe")

    result = _run(

        [

            ffprobe,

            "-v",

            "error",

            "-show_entries",

            "format=duration",

            "-of",

            "default=noprint_wrappers=1:nokey=1",

            str(path),

        ],

        description=f"Reading duration of {path.name}",

    )

    try:

        duration = float(result.stdout.strip())

    except ValueError as exc:

        raise M4BError(

            f"Could not determine the duration of {path.name}."

        ) from exc

    if duration <= 0:

        raise M4BError(

            f"Invalid audio duration for {path.name}: {duration}"

        )

    return duration

def _escape_concat_path(path: Path) -> str:

    value = str(path.resolve())

    return value.replace("'", r"'\''")

def _escape_ffmetadata(value: str) -> str:

    return (

        str(value)

        .replace("\\", "\\\\")

        .replace("=", "\\=")

        .replace(";", "\\;")

        .replace("#", "\\#")

        .replace("\n", " ")

        .replace("\r", " ")

    )

def _normalise_metadata(

    *,

    title: str,

    author: str,

    narrator: Optional[str],

    extra_metadata: Optional[Mapping[str, str]],

) -> dict[str, str]:

    metadata: dict[str, str] = {

        "title": title.strip(),

        "album": title.strip(),

        "artist": author.strip(),

        "album_artist": author.strip(),

        "author": author.strip(),

        "genre": "Audiobook",

        "media_type": "2",

    }

    if narrator and narrator.strip():

        metadata["narrator"] = narrator.strip()

        metadata["comment"] = f"Narrated by {narrator.strip()}"

    if extra_metadata:

        for key, value in extra_metadata.items():

            clean_key = str(key).strip()

            clean_value = str(value).strip()

            if clean_key and clean_value:

                metadata[clean_key] = clean_value

    return metadata

def _write_concat_file(

    chapters: Sequence[M4BChapter],

    destination: Path,

) -> None:

    lines = []

    for chapter in chapters:

        path = Path(chapter.audio_path)

        if not path.is_file():

            raise M4BError(

                f"Chapter audio does not exist: {path}"

            )

        lines.append(

            f"file '{_escape_concat_path(path)}'"

        )

    destination.write_text(

        "\n".join(lines) + "\n",

        encoding="utf-8",

    )

def _write_ffmetadata_file(

    *,

    chapters: Sequence[M4BChapter],

    durations: Sequence[float],

    metadata: Mapping[str, str],

    destination: Path,

) -> None:

    lines = [";FFMETADATA1"]

    for key, value in metadata.items():

        lines.append(

            f"{_escape_ffmetadata(key)}={_escape_ffmetadata(value)}"

        )

    current_ms = 0

    for chapter, duration in zip(chapters, durations):

        duration_ms = max(1, round(duration * 1000))

        end_ms = current_ms + duration_ms

        lines.extend(

            [

                "",

                "[CHAPTER]",

                "TIMEBASE=1/1000",

                f"START={current_ms}",

                f"END={end_ms}",

                f"title={_escape_ffmetadata(chapter.title)}",

            ]

        )

        current_ms = end_ms

    destination.write_text(

        "\n".join(lines) + "\n",

        encoding="utf-8",

    )

def _build_combined_audio(

    *,

    concat_file: Path,

    output_path: Path,

    bitrate_kbps: int,

) -> None:

    ffmpeg = _require_command("ffmpeg")

    _run(

        [

            ffmpeg,

            "-hide_banner",

            "-loglevel",

            "error",

            "-y",

            "-f",

            "concat",

            "-safe",

            "0",

            "-i",

            str(concat_file),

            "-vn",

            "-c:a",

            "aac",

            "-b:a",

            f"{bitrate_kbps}k",

            "-movflags",

            "+faststart",

            str(output_path),

        ],

        description="Creating combined AAC audiobook audio",

    )

def _build_final_m4b(

    *,

    audio_path: Path,

    metadata_path: Path,

    output_path: Path,

    cover_path: Optional[Path],

) -> None:

    ffmpeg = _require_command("ffmpeg")

    command = [

        ffmpeg,

        "-hide_banner",

        "-loglevel",

        "error",

        "-y",

        "-i",

        str(audio_path),

        "-f",

        "ffmetadata",

        "-i",

        str(metadata_path),

    ]

    if cover_path is not None:

        command.extend(

            [

                "-i",

                str(cover_path),

                "-map",

                "0:a:0",

                "-map",

                "2:v:0",

                "-map_metadata",

                "1",

                "-map_chapters",

                "1",

                "-c:a",

                "copy",

                "-c:v",

                "mjpeg",

                "-disposition:v:0",

                "attached_pic",

                "-metadata:s:v",

                "title=Cover",

                "-metadata:s:v",

                "comment=Cover (front)",

            ]

        )

    else:

        command.extend(

            [

                "-map",

                "0:a:0",

                "-map_metadata",

                "1",

                "-map_chapters",

                "1",

                "-c:a",

                "copy",

            ]

        )

    command.extend(

        [

            "-movflags",

            "+faststart",

            "-f",

            "mp4",

            str(output_path),

        ]

    )

    _run(

        command,

        description="Writing final M4B audiobook",

    )

def verify_m4b(

    *,

    output_path: Path,

    expected_chapter_count: int,

    expected_title: Optional[str] = None,

) -> M4BResult:

    output_path = Path(output_path)

    if not output_path.is_file():

        raise M4BError(

            f"The M4B file was not created: {output_path}"

        )

    if output_path.stat().st_size <= 0:

        raise M4BError(

            f"The M4B file is empty: {output_path}"

        )

    probe = _probe_json(output_path)

    chapters = probe.get("chapters") or []

    if len(chapters) != expected_chapter_count:

        raise M4BError(

            "M4B verification failed: "

            f"expected {expected_chapter_count} chapters, "

            f"but found {len(chapters)}." 
        )

    streams = probe.get("streams") or []

    audio_streams = [

        stream

        for stream in streams

        if stream.get("codec_type") == "audio"

    ]

    if not audio_streams:

        raise M4BError(

            "M4B verification failed: no audio stream was found."

        )

    format_info = probe.get("format") or {}

    tags = {

        str(key): str(value)

        for key, value in (format_info.get("tags") or {}).items()

    }

    if expected_title:

        actual_title = tags.get("title", "").strip()

        if actual_title and actual_title != expected_title.strip():

            raise M4BError(

                "M4B verification failed: "

                f"expected title '{expected_title}', "

                f"but found '{actual_title}'."

            )

    try:

        duration_seconds = float(

            format_info.get("duration", 0.0)

        )

    except (TypeError, ValueError):

        duration_seconds = 0.0

    has_cover_art = any(

        stream.get("codec_type") == "video"

        and int(

            (stream.get("disposition") or {}).get(

                "attached_pic",

                0,

            )

        )

        == 1

        for stream in streams

    )

    return M4BResult(

        output_path=output_path,

        chapter_count=len(chapters),

        duration_seconds=duration_seconds,

        metadata=tags,

        has_cover_art=has_cover_art,

    )

def create_m4b(

    *,

    chapters: Iterable[M4BChapter],

    output_path: Path,

    title: str,

    author: str,

    narrator: Optional[str] = None,

    cover_path: Optional[Path] = None,

    bitrate_kbps: int = 128,

    extra_metadata: Optional[Mapping[str, str]] = None,

) -> M4BResult:

    chapter_list = list(chapters)

    if not chapter_list:

        raise M4BError(

            "Cannot create an M4B without any chapters."

        )

    if not title.strip():

        raise M4BError(

            "Cannot create an M4B without a title."

        )

    if not author.strip():

        raise M4BError(

            "Cannot create an M4B without an author."

        )

    if bitrate_kbps <= 0:

        raise M4BError(

            "M4B bitrate must be greater than zero."

        )

    output_path = Path(output_path)

    output_path.parent.mkdir(

        parents=True,

        exist_ok=True,

    )

    if output_path.suffix.lower() != ".m4b":

        output_path = output_path.with_suffix(".m4b")

    cover: Optional[Path] = None

    if cover_path is not None:

        candidate = Path(cover_path)

        if candidate.is_file():

            cover = candidate

        else:

            raise M4BError(

                f"Cover image does not exist: {candidate}"

            )

    for chapter in chapter_list:

        if not chapter.title.strip():

            raise M4BError(

                "Every M4B chapter must have a title."

            )

        if not Path(chapter.audio_path).is_file():

            raise M4BError(

                f"Chapter audio does not exist: "

                f"{chapter.audio_path}"

            )

    durations = [

        get_audio_duration(

            Path(chapter.audio_path)

        )

        for chapter in chapter_list

    ]

    metadata = _normalise_metadata(

        title=title,

        author=author,

        narrator=narrator,

        extra_metadata=extra_metadata,

    )

    with tempfile.TemporaryDirectory(

        prefix="audiobook-maker-m4b-"

    ) as temp_dir_name:

        temp_dir = Path(temp_dir_name)

        concat_file = temp_dir / "chapters.txt"

        metadata_file = temp_dir / "metadata.ffmeta"

        combined_audio = temp_dir / "combined.m4a"

        _write_concat_file(

            chapter_list,

            concat_file,

        )

        _write_ffmetadata_file(

            chapters=chapter_list,

            durations=durations,

            metadata=metadata,

            destination=metadata_file,

        )

        _build_combined_audio(

            concat_file=concat_file,

            output_path=combined_audio,

            bitrate_kbps=bitrate_kbps,

        )

        staged_output = temp_dir / output_path.name

        _build_final_m4b(

            audio_path=combined_audio,

            metadata_path=metadata_file,

            output_path=staged_output,

            cover_path=cover,

        )

        verified = verify_m4b(

            output_path=staged_output,

            expected_chapter_count=len(chapter_list),

            expected_title=title,

        )

        os.replace(staged_output, output_path)

    return M4BResult(

        output_path=output_path,

        chapter_count=verified.chapter_count,

        duration_seconds=verified.duration_seconds,

        metadata=verified.metadata,

        has_cover_art=verified.has_cover_art,

    )

