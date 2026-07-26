import os
import shutil
import tempfile
from contextlib import nullcontext
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from .common import (
    CHAPTER_TEXT_DIR, EXTRACTED_TEXT_DIR, FINISHED_DIR, REPORTS_DIR,
    Settings, VERSION, say,
)
from .settings import ask, choose_author, choose_title, output_format_description
from .text_utils import (
    clean_heading_for_filename, pretty_title_from_filename, safe_filename,
    suggest_title_author, word_count,
)
from .extractors import extract_source_text
from .chapters import (
    build_track_plan, clean_section_heading_title, clean_spoken_section_text,
    review_front_matter, split_book_text,
)
from .audio import (
    create_audio_from_text, estimate_duration_seconds, format_duration,
    get_audio_duration, tag_mp3,
)
from .files import unique_filename, write_report
from .m4b import M4BChapter, create_m4b

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

def process_source(

    source_path: Path,

    settings: Settings,

    run_authors: list[str],

    force: bool,

) -> ConversionOutcome:

    raw_guess_title = pretty_title_from_filename(source_path)

    safe_guess = safe_filename(raw_guess_title)

    extracted = extract_source_text(source_path, safe_guess)

    extracted_for_guess = extracted.text

    source_type = extracted.source_type

    guessed_title, guessed_author = suggest_title_author(

        source_path,

        extracted_for_guess,

    )

    suggested_title = extracted.metadata_title or guessed_title

    suggested_author = extracted.metadata_author or guessed_author

    say("")

    say(f"Processing: {source_path.name}")

    title = choose_title(source_path, suggested_title)

    author = choose_author(

        source_path,

        suggested_author,

        run_authors,

    )

    book_title = safe_filename(title)

    if book_title != safe_guess:

        (

            EXTRACTED_TEXT_DIR / f"{book_title}.txt"

        ).write_text(

            extracted_for_guess,

            encoding="utf-8",

        )

    text = extracted_for_guess

    words_total = word_count(text)

    warnings: list[str] = []

    if len(text) < 500 or words_total < 100:

        warnings.append(

            "Extracted text is very short. "

            "This source may be scanned, empty, or badly extracted."

        )

    front_sections, main_sections, main_start = split_book_text(text)

    if len(main_sections) == 1:

        warnings.append(

            "Only 1 main section found. Chapter detection may have failed."

        )

    if len(main_sections) > 150:

        warnings.append(

            "Very high section count. Chapter detection may be too aggressive."

        )

    say(f"Source type: {source_type}")

    say(f"Text extracted: {words_total} words.")

    say(f"Main book starts at: {main_start}.")

    say(f"Main sections found: {len(main_sections)}.")

    if source_type == "EPUB":

        for detail in extracted.details:

            say(detail)

    estimated = estimate_duration_seconds(

        words_total,

        settings.rate,

    )

    say(

        f"Estimated length: about "

        f"{format_duration(estimated)}."

    )

    for warning in warnings:

        say(f"Warning: {warning}")

    kept_front = review_front_matter(front_sections)

    tracks = build_track_plan(

        title,

        author,

        kept_front,

        main_sections,

    )

    total_tracks = len(tracks)

    kept_words = sum(

        word_count(section.text)

        for section in tracks

    )

    say("")

    say(f"Tracks to create/tag: {total_tracks}.")

    say(f"Words to speak: {kept_words}.")

    say(

        "Estimated spoken audio length: about "

        f"{format_duration(estimate_duration_seconds(kept_words, settings.rate))}."

    )

    while True:

        choice = ask(

            "Type yes to create audio, stop to cancel this book, or r."

        ).lower()

        if choice == "r":

            say(f"Tracks to create/tag: {total_tracks}.")

            say(f"Words to speak: {kept_words}.")

            continue

        if choice == "yes":

            break

        if choice == "stop":

            say(f"Skipped: {title}")

            return ConversionOutcome.CANCELLED

        say("Please type yes, stop, or r.")

    output_format = settings.output_format or "mp3"

    book_finished_dir = FINISHED_DIR / book_title

    book_chapter_text_dir = CHAPTER_TEXT_DIR / book_title

    mp3_output_dir, m4b_output_dir = _output_directories(

        book_finished_dir,

        output_format,

    )

    book_finished_dir.mkdir(

        parents=True,

        exist_ok=True,

    )

    if mp3_output_dir is not None:

        mp3_output_dir.mkdir(

            parents=True,

            exist_ok=True,

        )

    book_chapter_text_dir.mkdir(

        parents=True,

        exist_ok=True,

    )

    REPORTS_DIR.mkdir(

        parents=True,

        exist_ok=True,

    )

    report_path = (

        REPORTS_DIR / f"{book_title} report.txt"

    )

    report = [

        f"Report for: {title}",

        f"Script version: {VERSION}",

        f"Source file: {source_path}",

        f"Source type: {source_type}",

        f"Author: {author}",

        f"Voice: {settings.voice}",

        f"Rate: {settings.rate} words per minute",

        f"Output format: {output_format_description(output_format)}",

        f"MP3 bitrate setting: {settings.bitrate} kbps",

        f"Total extracted words: {words_total}",

        f"Words to speak: {kept_words}",

        (

            "Estimated spoken length: "

            f"{format_duration(estimate_duration_seconds(kept_words, settings.rate))}"

        ),

        f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",

        "",

        f"Front matter found: {len(front_sections)}",

        f"Front matter kept: {len(kept_front)}",

        f"Main sections found: {len(main_sections)}",

        f"Tracks planned: {total_tracks}",

        (

            "Cover art available: "

            f"{'yes' if extracted.cover_art else 'no'}"

        ),

        "",

    ]

    if extracted.details:

        report.append("Source extraction details:")

        report.extend(

            f"- {detail}"

            for detail in extracted.details

        )

        report.append("")

    if warnings:

        report.append("Warnings:")

        report.extend(

            f"- {warning}"

            for warning in warnings

        )

        report.append("")

    actual_seconds = 0.0

    used_names: set[str] = set()

    m4b_result = None

    mp3_staging_context = (

        tempfile.TemporaryDirectory(

            prefix=f".{mp3_output_dir.name}.staging-",

            dir=mp3_output_dir.parent,

        )

        if mp3_output_dir is not None

        else nullcontext(None)

    )

    with (

        tempfile.TemporaryDirectory(

            prefix="audiobook_maker_"

        ) as temp,

        mp3_staging_context as mp3_staging,

    ):

        temp_dir = Path(temp)

        mp3_staging_dir = (

            Path(mp3_staging)

            if mp3_staging is not None

            else None

        )

        m4b_chapters: list[M4BChapter] = []

        for index, section in enumerate(

            tracks,

            start=1,

        ):

            if section.kind == "intro":

                display_number = "000"

                track_number = 1

                base_heading = title

            else:

                if tracks and tracks[0].kind == "intro":

                    number = index - 1

                else:

                    number = index

                display_number = str(number).zfill(3)

                track_number = index

                base_heading = clean_section_heading_title(

                    section.heading

                )

            clean_heading = unique_filename(

                clean_heading_for_filename(base_heading),

                used_names,

            )

            text_filename = (

                f"{book_title} - "

                f"{display_number} - "

                f"{clean_heading}.txt"

            )

            mp3_filename = (

                f"{book_title} - "

                f"{display_number} - "

                f"{clean_heading}.mp3"

            )

            text_file = (

                book_chapter_text_dir

                / text_filename

            )

            if mp3_output_dir is None:

                mp3_file = (

                    temp_dir

                    / mp3_filename

                )

                existing_mp3_file = None

            else:

                if mp3_staging_dir is None:

                    raise RuntimeError(

                        "MP3 staging directory was not prepared."

                    )

                existing_mp3_file = (

                    mp3_output_dir

                    / mp3_filename

                )

                mp3_file = (

                    mp3_staging_dir

                    / mp3_filename

                )

            spoken_text = clean_spoken_section_text(

                section.text,

                base_heading,

            )

            text_file.write_text(

                spoken_text,

                encoding="utf-8",

            )

            can_skip_existing = (

                existing_mp3_file is not None

                and existing_mp3_file.exists()

                and not force

            )

            working_mp3 = mp3_file

            if can_skip_existing:

                say(

                    f"Skipping {display_number} of "

                    f"{str(total_tracks).zfill(3)}: "

                    f"{base_heading} — already exists."

                )

                shutil.copy2(existing_mp3_file, working_mp3)

                report.append(

                    f"Skipped existing: {mp3_file.name}"

                )

            else:

                say(

                    f"Creating {display_number} of "

                    f"{str(total_tracks).zfill(3)}: "

                    f"{base_heading} — "

                    f"{word_count(spoken_text)} words."

                )

                create_audio_from_text(

                    text_file,

                    working_mp3,

                    temp_dir,

                    settings,

                )

                if mp3_output_dir is not None:

                    report.append(

                        f"Created: {mp3_file.name}"

                    )

            if mp3_output_dir is not None:

                tag_mp3(

                    working_mp3,

                    title,

                    author,

                    base_heading,

                    track_number,

                    total_tracks,

                    settings,

                    extracted.cover_art,

                )

            duration = get_audio_duration(

                working_mp3

            )

            actual_seconds += duration

            if mp3_output_dir is not None:

                report.append(

                    f"Tagged: {mp3_file.name} — "

                    f"{format_duration(duration)}"

                )

            m4b_chapters.append(

                M4BChapter(

                    title=base_heading,

                    audio_path=mp3_file,

                )

            )

        if output_format in {"m4b", "both"}:

            say("")

            say("Creating chapterised M4B.")

            cover_path = _write_cover_art_to_temp(

                extracted.cover_art,

                temp_dir,

            )

            if m4b_output_dir is None:

                raise RuntimeError(

                    "M4B output directory was not prepared."

                )

            m4b_path = (

                m4b_output_dir

                / f"{book_title}.m4b"

            )

            m4b_result = create_m4b(

                chapters=m4b_chapters,

                output_path=m4b_path,

                title=title,

                author=author,

                narrator=f"macOS {settings.voice}",

                cover_path=cover_path,

                bitrate_kbps=settings.bitrate,

                extra_metadata={

                    "date": str(datetime.now().year),

                    "encoder": (

                        f"Audiobook Maker {VERSION}"

                    ),

                },

            )

            report.append("")

            report.append(

                f"M4B created: "

                f"{m4b_result.output_path.name}"

            )

            report.append(

                f"M4B chapters: "

                f"{m4b_result.chapter_count}"

            )

            report.append(

                "M4B duration: "

                f"{format_duration(m4b_result.duration_seconds)}"

            )

            report.append(

                "M4B cover art embedded: "

                f"{'yes' if m4b_result.has_cover_art else 'no'}"

            )

        if mp3_output_dir is not None:

            if mp3_staging_dir is None:

                raise RuntimeError(

                    "MP3 staging directory was not prepared."

                )

            _publish_mp3_directory(

                mp3_staging_dir,

                mp3_output_dir,

            )

    report.append("")

    report.append(

        "Actual audio length: "

        f"{format_duration(actual_seconds)}"

    )

    report.append(

        "Finished: "

        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    )

    write_report(

        report_path,

        report,

    )

    if output_format in {"mp3", "both"}:

        say("MP3 tagging complete.")

    if m4b_result is not None:

        say(

            f"M4B created: "

            f"{m4b_result.output_path.name}."

        )

        say(

            f"M4B chapters: "

            f"{m4b_result.chapter_count}."

        )

    say(

        "Actual audio length: "

        f"{format_duration(actual_seconds)}."

    )

    say(

        f"Report saved: "

        f"{report_path.name}"

    )

    say(f"Done: {title}")

    return ConversionOutcome.COMPLETED

