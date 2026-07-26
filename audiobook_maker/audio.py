import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from mutagen.id3 import APIC, COMM, ID3, TALB, TCON, TDRC, TIT2, TPE1, TPE2, TRCK
    from mutagen.mp3 import MP3

except ImportError:
    APIC = COMM = ID3 = TALB = TCON = TDRC = TIT2 = TPE1 = TPE2 = TRCK = None

    MP3 = None

from .common import SAMPLE_RATE, Settings, run_command


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return (
            f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"
        )
    if minutes:
        return (
            f"{minutes} minute{'s' if minutes != 1 else ''} {secs} second{'s' if secs != 1 else ''}"
        )
    return f"{secs} second{'s' if secs != 1 else ''}"


def estimate_duration_seconds(words: int, rate: int) -> float:
    if rate <= 0:
        return 0.0
    return (words / rate) * 60


def get_audio_duration(mp3_path: Path) -> float:
    if MP3 is not None:
        try:
            audio = MP3(str(mp3_path))
            return float(audio.info.length)
        except Exception:
            pass
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(mp3_path),
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "ffprobe returned no details."
        raise RuntimeError(f"Could not read audio duration for {mp3_path.name}: {detail}")
    try:
        duration = float(result.stdout.strip())
    except ValueError as error:
        raise RuntimeError(
            f"Could not read audio duration for {mp3_path.name}: ffprobe returned an invalid value."
        ) from error
    if duration <= 0:
        raise RuntimeError(
            f"Could not read audio duration for {mp3_path.name}: duration was not positive."
        )
    return duration


def create_audio_from_text(
    text_file: Path, mp3_file: Path, temp_dir: Path, settings: Settings
) -> None:
    aiff_file = temp_dir / (mp3_file.stem + ".aiff")
    run_command(
        [
            "say",
            "-v",
            settings.voice,
            "-r",
            str(settings.rate),
            "-o",
            str(aiff_file),
            "-f",
            str(text_file),
        ],
        f"Creating speech audio: {mp3_file.name}",
    )
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(aiff_file),
            "-ar",
            str(SAMPLE_RATE),
            "-codec:a",
            "libmp3lame",
            "-b:a",
            f"{settings.bitrate}k",
            str(mp3_file),
        ],
        f"Converting to MP3: {mp3_file.name}",
    )


def tag_mp3(
    mp3_file: Path,
    book_title: str,
    author: str,
    track_title: str,
    track_number: int,
    total_tracks: int,
    settings: Settings,
    cover_art: Optional[tuple[str, bytes]] = None,
) -> None:
    if ID3 is None:
        raise RuntimeError(
            "ID3 tagging needs mutagen. Install it with: python3 -m pip install mutagen"
        )
    try:
        tags = ID3(str(mp3_file))
    except Exception:
        tags = ID3()
    tags.delall("TIT2")
    tags.delall("TALB")
    tags.delall("TPE1")
    tags.delall("TPE2")
    tags.delall("TRCK")
    tags.delall("TCON")
    tags.delall("COMM")
    tags.delall("TDRC")
    tags.delall("APIC")
    tags.add(TIT2(encoding=3, text=track_title))
    tags.add(TALB(encoding=3, text=book_title))
    tags.add(TPE1(encoding=3, text=author))
    tags.add(TPE2(encoding=3, text=author))
    tags.add(TRCK(encoding=3, text=f"{track_number}/{total_tracks}"))
    tags.add(TCON(encoding=3, text="Audiobook"))
    tags.add(COMM(encoding=3, lang="eng", desc="Narrator", text=f"macOS {settings.voice}"))
    tags.add(
        COMM(
            encoding=3,
            lang="eng",
            desc="Audio Encoding",
            text=f"MP3, {SAMPLE_RATE / 1000:.1f} kHz, {settings.bitrate} kbps",
        )
    )
    tags.add(TDRC(encoding=3, text=str(datetime.now().year)))
    if cover_art:
        mime, data = cover_art
        tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=data))
    tags.save(str(mp3_file), v2_version=3)
