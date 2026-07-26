import os
import shutil
import tempfile
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

from .audio import (
    create_audio_from_text,
    estimate_duration_seconds,
    format_duration,
    get_audio_duration,
    tag_mp3,
)
from .chapters import (
    build_track_plan,
    clean_section_heading_title,
    clean_spoken_section_text,
    review_front_matter,
    split_book_text,
)
from .common import (
    VERSION,
    ProjectPaths,
    Settings,
    say,
)
from .extractors import extract_source_text
from .files import unique_filename, write_report
from .m4b import M4BChapter, create_m4b
from .settings import ask, choose_author, choose_title, output_format_description
from .text_utils import (
    clean_heading_for_filename,
    pretty_title_from_filename,
    safe_filename,
    suggest_title_author,
    word_count,
)


class ConversionOutcome(Enum):
    COMPLETED = auto()

    CANCELLED = auto()

    FAILED = auto()


def _write_cover_art_to_temp(
    cover_art: Optional[tuple[str, bytes]],
    temp_dir: Path,
) -> Optional[Path]:

    if not cover_art:
        return None

    mime, data = cover_art

    suffixes = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    cover_path = temp_dir / f"cover{suffixes.get(mime.lower(), '.jpg')}"

    cover_path.write_bytes(data)

    return cover_path


def _publish_mp3_directory(
    staged_dir: Path,
    output_dir: Path,
) -> None:

    output_dir.parent.mkdir(parents=True, exist_ok=True)

    backup_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.backup-",
            dir=output_dir.parent,
        )
    )

    backup_dir.rmdir()

    had_existing_output = output_dir.exists()

    if had_existing_output:
        os.replace(output_dir, backup_dir)

    try:
        os.replace(staged_dir, output_dir)

    except Exception:
        if had_existing_output and backup_dir.exists():
            os.replace(backup_dir, output_dir)

        raise

    if backup_dir.exists():
        shutil.rmtree(backup_dir)


def _output_directories(
    book_finished_dir: Path,
    output_format: str,
) -> tuple[Optional[Path], Optional[Path]]:

    if output_format == "mp3":
        return book_finished_dir, None

    if output_format == "m4b":
        return None, book_finished_dir

    if output_format == "both":
        return book_finished_dir / "MP3", book_finished_dir

    raise ValueError(f"Unsupported output format: {output_format}")


@dataclass
class PreparedBook:
    source_path: Path
    extracted: Any
    source_type: str
    title: str
    author: str
    book_title: str
    text: str
    words_total: int
    warnings: list[str]
    front_sections: list[Any]
    main_sections: list[Any]
    main_start: str


@dataclass
class TrackPlan:
    tracks: list[Any]
    kept_front: list[Any]
    kept_words: int


@dataclass
class OutputPlan:
    output_format: str
    book_finished_dir: Path
    chapter_text_dir: Path
    mp3_output_dir: Optional[Path]
    m4b_output_dir: Optional[Path]
    report_path: Path


@dataclass
class ConversionResult:
    actual_seconds: float
    m4b_result: Any


def _analyse_extracted_book(
    source_path: Path,
    settings: Settings,
    paths: ProjectPaths,
) -> tuple[Any, str, str, str, int, list[str], list[Any], list[Any], str]:
    raw_guess_title = pretty_title_from_filename(source_path)
    safe_guess = safe_filename(raw_guess_title)
    extracted = extract_source_text(
        source_path,
        safe_guess,
        paths.extracted_text_dir,
    )
    text = extracted.text
    words_total = word_count(text)
    warnings: list[str] = []

    if len(text) < 500 or words_total < 100:
        warnings.append(
            "Extracted text is very short. This source may be scanned, empty, or badly extracted."
        )

    front_sections, main_sections, main_start = split_book_text(text)

    if len(main_sections) == 1:
        warnings.append("Only 1 main section found. Chapter detection may have failed.")

    if len(main_sections) > 150:
        warnings.append("Very high section count. Chapter detection may be too aggressive.")

    guessed_title, guessed_author = suggest_title_author(source_path, text)
    suggested_title = extracted.metadata_title or guessed_title
    suggested_author = extracted.metadata_author or guessed_author

    return (
        extracted,
        safe_guess,
        suggested_title,
        suggested_author,
        words_total,
        warnings,
        front_sections,
        main_sections,
        main_start,
    )


def _choose_book_identity(
    source_path: Path,
    suggested_title: str,
    suggested_author: str,
    run_authors: list[str],
) -> tuple[str, str]:
    say("")
    say(f"Processing: {source_path.name}")

    title = choose_title(source_path, suggested_title)
    author = choose_author(
        source_path,
        suggested_author,
        run_authors,
    )
    return title, author


def _prepare_book(
    source_path: Path,
    settings: Settings,
    run_authors: list[str],
    paths: ProjectPaths,
) -> PreparedBook:
    (
        extracted,
        safe_guess,
        suggested_title,
        suggested_author,
        words_total,
        warnings,
        front_sections,
        main_sections,
        main_start,
    ) = _analyse_extracted_book(source_path, settings, paths)

    title, author = _choose_book_identity(
        source_path,
        suggested_title,
        suggested_author,
        run_authors,
    )
    book_title = safe_filename(title)

    if book_title != safe_guess:
        (paths.extracted_text_dir / f"{book_title}.txt").write_text(
            extracted.text,
            encoding="utf-8",
        )

    return PreparedBook(
        source_path=source_path,
        extracted=extracted,
        source_type=extracted.source_type,
        title=title,
        author=author,
        book_title=book_title,
        text=extracted.text,
        words_total=words_total,
        warnings=warnings,
        front_sections=front_sections,
        main_sections=main_sections,
        main_start=main_start,
    )


def _announce_book_analysis(book: PreparedBook, settings: Settings) -> None:
    say(f"Source type: {book.source_type}")
    say(f"Text extracted: {book.words_total} words.")
    say(f"Main book starts at: {book.main_start}.")
    say(f"Main sections found: {len(book.main_sections)}.")

    if book.source_type == "EPUB":
        for detail in book.extracted.details:
            say(detail)

    estimated = estimate_duration_seconds(book.words_total, settings.rate)
    say(f"Estimated length: about {format_duration(estimated)}.")

    for warning in book.warnings:
        say(f"Warning: {warning}")


def _review_track_plan(book: PreparedBook, settings: Settings) -> Optional[TrackPlan]:
    kept_front = review_front_matter(book.front_sections)
    tracks = build_track_plan(
        book.title,
        book.author,
        kept_front,
        book.main_sections,
    )
    kept_words = sum(word_count(section.text) for section in tracks)

    say("")
    say(f"Tracks to create/tag: {len(tracks)}.")
    say(f"Words to speak: {kept_words}.")
    say(
        "Estimated spoken audio length: about "
        f"{format_duration(estimate_duration_seconds(kept_words, settings.rate))}."
    )

    while True:
        choice = ask("Type yes to create audio, stop to cancel this book, or r.").lower()

        if choice == "r":
            say(f"Tracks to create/tag: {len(tracks)}.")
            say(f"Words to speak: {kept_words}.")
            continue

        if choice == "yes":
            return TrackPlan(
                tracks=tracks,
                kept_front=kept_front,
                kept_words=kept_words,
            )

        if choice == "stop":
            say(f"Skipped: {book.title}")
            return None

        say("Please type yes, stop, or r.")


def _prepare_output_plan(
    book: PreparedBook,
    settings: Settings,
    paths: ProjectPaths,
) -> OutputPlan:
    output_format = settings.output_format or "mp3"
    book_finished_dir = paths.finished_dir / book.book_title
    chapter_text_dir = paths.chapter_text_dir / book.book_title
    mp3_output_dir, m4b_output_dir = _output_directories(
        book_finished_dir,
        output_format,
    )

    book_finished_dir.mkdir(parents=True, exist_ok=True)

    if mp3_output_dir is not None:
        mp3_output_dir.mkdir(parents=True, exist_ok=True)

    chapter_text_dir.mkdir(parents=True, exist_ok=True)
    paths.reports_dir.mkdir(parents=True, exist_ok=True)

    return OutputPlan(
        output_format=output_format,
        book_finished_dir=book_finished_dir,
        chapter_text_dir=chapter_text_dir,
        mp3_output_dir=mp3_output_dir,
        m4b_output_dir=m4b_output_dir,
        report_path=paths.reports_dir / f"{book.book_title} report.txt",
    )


def _initial_conversion_report(
    book: PreparedBook,
    track_plan: TrackPlan,
    output_plan: OutputPlan,
    settings: Settings,
) -> list[str]:
    report = [
        f"Report for: {book.title}",
        f"Script version: {VERSION}",
        f"Source file: {book.source_path}",
        f"Source type: {book.source_type}",
        f"Author: {book.author}",
        f"Voice: {settings.voice}",
        f"Rate: {settings.rate} words per minute",
        f"Output format: {output_format_description(output_plan.output_format)}",
        f"MP3 bitrate setting: {settings.bitrate} kbps",
        f"Total extracted words: {book.words_total}",
        f"Words to speak: {track_plan.kept_words}",
        (
            "Estimated spoken length: "
            f"{format_duration(estimate_duration_seconds(track_plan.kept_words, settings.rate))}"
        ),
        f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"Front matter found: {len(book.front_sections)}",
        f"Front matter kept: {len(track_plan.kept_front)}",
        f"Main sections found: {len(book.main_sections)}",
        f"Tracks planned: {len(track_plan.tracks)}",
        f"Cover art available: {'yes' if book.extracted.cover_art else 'no'}",
        "",
    ]

    if book.extracted.details:
        report.append("Source extraction details:")
        report.extend(f"- {detail}" for detail in book.extracted.details)
        report.append("")

    if book.warnings:
        report.append("Warnings:")
        report.extend(f"- {warning}" for warning in book.warnings)
        report.append("")

    return report


def _track_output_details(
    index: int,
    tracks: list[Any],
    title: str,
) -> tuple[str, int, str]:
    section = tracks[index - 1]

    if section.kind == "intro":
        return "000", 1, title

    number = index - 1 if tracks and tracks[0].kind == "intro" else index
    return (
        str(number).zfill(3),
        index,
        clean_section_heading_title(section.heading),
    )


def _convert_track(
    *,
    index: int,
    tracks: list[Any],
    book: PreparedBook,
    output_plan: OutputPlan,
    settings: Settings,
    force: bool,
    temp_dir: Path,
    mp3_staging_dir: Optional[Path],
    used_names: set[str],
    report: list[str],
) -> tuple[M4BChapter, float]:
    section = tracks[index - 1]
    display_number, track_number, base_heading = _track_output_details(
        index,
        tracks,
        book.title,
    )
    clean_heading = unique_filename(
        clean_heading_for_filename(base_heading),
        used_names,
    )
    text_filename = f"{book.book_title} - {display_number} - {clean_heading}.txt"
    mp3_filename = f"{book.book_title} - {display_number} - {clean_heading}.mp3"
    text_file = output_plan.chapter_text_dir / text_filename

    if output_plan.mp3_output_dir is None:
        mp3_file = temp_dir / mp3_filename
        existing_mp3_file = None
    else:
        if mp3_staging_dir is None:
            raise RuntimeError("MP3 staging directory was not prepared.")

        existing_mp3_file = output_plan.mp3_output_dir / mp3_filename
        mp3_file = mp3_staging_dir / mp3_filename

    spoken_text = clean_spoken_section_text(
        section.text,
        base_heading,
    )
    text_file.write_text(spoken_text, encoding="utf-8")

    can_skip_existing = existing_mp3_file is not None and existing_mp3_file.exists() and not force

    if can_skip_existing:
        say(
            f"Skipping {display_number} of "
            f"{str(len(tracks)).zfill(3)}: "
            f"{base_heading} — already exists."
        )
        shutil.copy2(existing_mp3_file, mp3_file)
        report.append(f"Skipped existing: {mp3_file.name}")
    else:
        say(
            f"Creating {display_number} of "
            f"{str(len(tracks)).zfill(3)}: "
            f"{base_heading} — "
            f"{word_count(spoken_text)} words."
        )
        create_audio_from_text(
            text_file,
            mp3_file,
            temp_dir,
            settings,
        )

        if output_plan.mp3_output_dir is not None:
            report.append(f"Created: {mp3_file.name}")

    if output_plan.mp3_output_dir is not None:
        tag_mp3(
            mp3_file,
            book.title,
            book.author,
            base_heading,
            track_number,
            len(tracks),
            settings,
            book.extracted.cover_art,
        )

    duration = get_audio_duration(mp3_file)

    if output_plan.mp3_output_dir is not None:
        report.append(f"Tagged: {mp3_file.name} — {format_duration(duration)}")

    return M4BChapter(title=base_heading, audio_path=mp3_file), duration


def _create_m4b_output(
    *,
    book: PreparedBook,
    output_plan: OutputPlan,
    settings: Settings,
    chapters: list[M4BChapter],
    temp_dir: Path,
    report: list[str],
) -> Any:
    if output_plan.output_format not in {"m4b", "both"}:
        return None

    say("")
    say("Creating chapterised M4B.")

    cover_path = _write_cover_art_to_temp(
        book.extracted.cover_art,
        temp_dir,
    )

    if output_plan.m4b_output_dir is None:
        raise RuntimeError("M4B output directory was not prepared.")

    m4b_result = create_m4b(
        chapters=chapters,
        output_path=output_plan.m4b_output_dir / f"{book.book_title}.m4b",
        title=book.title,
        author=book.author,
        narrator=f"macOS {settings.voice}",
        cover_path=cover_path,
        bitrate_kbps=settings.bitrate,
        extra_metadata={
            "date": str(datetime.now().year),
            "encoder": f"Audiobook Maker {VERSION}",
        },
    )

    report.append("")
    report.append(f"M4B created: {m4b_result.output_path.name}")
    report.append(f"M4B chapters: {m4b_result.chapter_count}")
    report.append(f"M4B duration: {format_duration(m4b_result.duration_seconds)}")
    report.append(f"M4B cover art embedded: {'yes' if m4b_result.has_cover_art else 'no'}")

    return m4b_result


def _run_conversion(
    *,
    book: PreparedBook,
    track_plan: TrackPlan,
    output_plan: OutputPlan,
    settings: Settings,
    force: bool,
    report: list[str],
) -> ConversionResult:
    actual_seconds = 0.0
    used_names: set[str] = set()

    mp3_staging_context = (
        tempfile.TemporaryDirectory(
            prefix=f".{output_plan.mp3_output_dir.name}.staging-",
            dir=output_plan.mp3_output_dir.parent,
        )
        if output_plan.mp3_output_dir is not None
        else nullcontext(None)
    )

    with (
        tempfile.TemporaryDirectory(prefix="audiobook_maker_") as temp,
        mp3_staging_context as mp3_staging,
    ):
        temp_dir = Path(temp)
        mp3_staging_dir = Path(mp3_staging) if mp3_staging is not None else None
        m4b_chapters: list[M4BChapter] = []

        for index in range(1, len(track_plan.tracks) + 1):
            chapter, duration = _convert_track(
                index=index,
                tracks=track_plan.tracks,
                book=book,
                output_plan=output_plan,
                settings=settings,
                force=force,
                temp_dir=temp_dir,
                mp3_staging_dir=mp3_staging_dir,
                used_names=used_names,
                report=report,
            )
            m4b_chapters.append(chapter)
            actual_seconds += duration

        m4b_result = _create_m4b_output(
            book=book,
            output_plan=output_plan,
            settings=settings,
            chapters=m4b_chapters,
            temp_dir=temp_dir,
            report=report,
        )

        if output_plan.mp3_output_dir is not None:
            if mp3_staging_dir is None:
                raise RuntimeError("MP3 staging directory was not prepared.")

            _publish_mp3_directory(
                mp3_staging_dir,
                output_plan.mp3_output_dir,
            )

    return ConversionResult(
        actual_seconds=actual_seconds,
        m4b_result=m4b_result,
    )


def _finish_conversion(
    *,
    book: PreparedBook,
    output_plan: OutputPlan,
    result: ConversionResult,
    report: list[str],
) -> None:
    report.append("")
    report.append(f"Actual audio length: {format_duration(result.actual_seconds)}")
    report.append(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    write_report(output_plan.report_path, report)

    if output_plan.output_format in {"mp3", "both"}:
        say("MP3 tagging complete.")

    if result.m4b_result is not None:
        say(f"M4B created: {result.m4b_result.output_path.name}.")
        say(f"M4B chapters: {result.m4b_result.chapter_count}.")

    say(f"Actual audio length: {format_duration(result.actual_seconds)}.")
    say(f"Report saved: {output_plan.report_path.name}")
    say(f"Done: {book.title}")


def process_source(
    source_path: Path,
    settings: Settings,
    run_authors: list[str],
    force: bool,
    paths: ProjectPaths,
) -> ConversionOutcome:
    book = _prepare_book(
        source_path,
        settings,
        run_authors,
        paths,
    )
    _announce_book_analysis(book, settings)

    track_plan = _review_track_plan(book, settings)

    if track_plan is None:
        return ConversionOutcome.CANCELLED

    output_plan = _prepare_output_plan(book, settings, paths)
    report = _initial_conversion_report(
        book,
        track_plan,
        output_plan,
        settings,
    )
    result = _run_conversion(
        book=book,
        track_plan=track_plan,
        output_plan=output_plan,
        settings=settings,
        force=force,
        report=report,
    )
    _finish_conversion(
        book=book,
        output_plan=output_plan,
        result=result,
        report=report,
    )

    return ConversionOutcome.COMPLETED
