import argparse
from importlib.resources import files
from pathlib import Path

from .audio import ID3
from .common import (
    MAX_SPEECH_RATE,
    MIN_SPEECH_RATE,
    SAMPLE_RATE,
    SUPPORTED_EXTENSIONS,
    VERSION,
    BeautifulSoup,
    ConversionOptions,
    ProjectPaths,
    Settings,
    check_tool,
    docx,
    ebook_epub,
    say,
)
from .files import find_supported_sources, handle_successful_original
from .notifications import notify_run_complete
from .pipeline import ConversionOutcome, process_source
from .settings import (
    check_voice,
    choose_book_original_action,
    choose_run_original_action,
    confirm_settings,
    get_installed_voices,
    load_settings,
    original_action_description,
    output_format_description,
    save_settings,
)


def speech_rate(value: str) -> int:
    try:
        rate = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Speech rate must be a whole number.") from error
    if not MIN_SPEECH_RATE <= rate <= MAX_SPEECH_RATE:
        raise argparse.ArgumentTypeError(
            f"Speech rate must be between {MIN_SPEECH_RATE} and {MAX_SPEECH_RATE}."
        )
    return rate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Audiobook Maker {VERSION}. Convert PDF, TXT, DOCX, and EPUB sources into chapterised MP3, M4B, or combined audiobooks.",
        epilog="Put source files in the 'Books to Convert' folder. Supported files: .pdf, .txt, .docx, and .epub. Audiobook Maker suggests title and author, reviews front matter, creates MP3 or M4B output, embeds chapters, metadata and cover art when available, verifies durations, and saves reports.",
    )
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--source",
        type=Path,
        metavar="FILE",
        help="Process one explicit PDF, TXT, DOCX, or EPUB source file.",
    )
    source_group.add_argument(
        "--all",
        dest="process_all",
        action="store_true",
        help="Process every supported source in the Books to Convert folder.",
    )
    parser.add_argument(
        "--non-interactive",
        "--yes",
        dest="non_interactive",
        action="store_true",
        help="Run without prompts, using command-line choices, saved settings, and defaults.",
    )
    parser.add_argument("--title", help="Override the detected title. Only valid with --source.")
    parser.add_argument("--author", help="Override the detected author for this run.")
    parser.add_argument(
        "--front-matter",
        choices=["keep", "skip"],
        help="In non-interactive mode, keep or skip all detected front matter.",
    )
    parser.add_argument(
        "--output",
        choices=["mp3", "m4b", "both"],
        help="Override the saved output format for this run.",
    )
    parser.add_argument(
        "--original",
        choices=["keep", "archive", "trash"],
        help="Choose what happens to successfully converted source files.",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        metavar="FOLDER",
        help="Use this project folder for the current run.",
    )
    parser.add_argument(
        "--force", action="store_true", help="Remake MP3 files even if they already exist."
    )
    parser.add_argument("--voice", help="Override the saved macOS voice for this run and save it.")
    parser.add_argument(
        "--rate",
        type=speech_rate,
        metavar="WPM",
        help=f"Override the saved speech rate for this run ({MIN_SPEECH_RATE}-{MAX_SPEECH_RATE} words per minute) and save it.",
    )
    parser.add_argument(
        "--bitrate",
        type=int,
        choices=[128, 192, 256, 320],
        help="Override the saved MP3 bitrate for this run and save it.",
    )
    parser.add_argument(
        "--settings",
        action="store_true",
        help="Show current settings and project folders, then exit.",
    )
    parser.add_argument(
        "--changelog", action="store_true", help="Show the built-in changelog, then exit."
    )
    parser.add_argument(
        "--version", action="store_true", help="Show the script version, then exit."
    )

    args = parser.parse_args()

    if args.title and args.source is None:
        parser.error("--title requires --source.")

    automation_choices = [
        args.source,
        args.process_all,
        args.title,
        args.author,
        args.front_matter,
        args.output,
        args.original,
        args.project_dir,
    ]
    if any(value is not None and value is not False for value in automation_choices):
        args.non_interactive = True

    return args


def conversion_options_from_args(args: argparse.Namespace) -> ConversionOptions:
    return ConversionOptions(
        non_interactive=getattr(args, "non_interactive", False),
        source=getattr(args, "source", None),
        process_all=getattr(args, "process_all", False),
        title=getattr(args, "title", None),
        author=getattr(args, "author", None),
        front_matter=getattr(args, "front_matter", None),
    )


def show_settings(settings: Settings, paths: ProjectPaths) -> None:

    say(f"Audiobook Maker {VERSION}")

    say(f"Voice: {settings.voice}")

    say(f"Speech rate: {settings.rate} words per minute")

    say(f"Audio: {SAMPLE_RATE / 1000:.1f} kHz, {settings.bitrate} kbps")

    say(f"Output format: {output_format_description(settings.output_format)}")

    say(f"After successful conversion: {original_action_description(settings.original_action)}")

    say("Supported formats: PDF, TXT, DOCX, EPUB")

    say(f"Stable version: {VERSION}")

    say(
        "Output support: MP3, M4B, or both, with embedded chapters, "
        "metadata, cover art, duration verification, and saved reports."
    )

    say(
        "Cover support: EPUB artwork, companion images, PDF first-page "
        "artwork, and suitable early DOCX images."
    )

    say(f"Project folder: {paths.project_dir}")

    say(f"Source folder: {paths.source_dir}")

    say(f"Finished audiobooks folder: {paths.finished_dir}")

    say(f"Converted originals folder: {paths.converted_originals_dir}")

    say(f"Reports folder: {paths.reports_dir}")


def show_changelog() -> None:
    changelog = files("audiobook_maker").joinpath("CHANGELOG.md").read_text(encoding="utf-8")
    say(changelog.strip())


def _apply_cli_settings(
    settings: Settings,
    args: argparse.Namespace,
) -> Settings:

    voice = getattr(args, "voice", None)

    rate = getattr(args, "rate", None)

    bitrate = getattr(args, "bitrate", None)

    output = getattr(args, "output", None)

    original = getattr(args, "original", None)

    project_dir = getattr(args, "project_dir", None)

    if voice:
        settings.voice = voice

    if rate is not None:
        settings.rate = rate

    if bitrate:
        settings.bitrate = bitrate

    if output:
        settings.output_format = output

    if original:
        settings.original_action = original

    if project_dir:
        settings.project_dir = project_dir.expanduser()

    return settings


def _resolve_sources(
    args: argparse.Namespace,
    paths: ProjectPaths,
) -> list[Path]:

    explicit_source = getattr(args, "source", None)

    if explicit_source is not None:
        source = explicit_source.expanduser()

        if not source.exists():
            raise RuntimeError(f"Source file was not found: {source}")

        if not source.is_file():
            raise RuntimeError(f"Source path is not a file: {source}")

        if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise RuntimeError("Unsupported source type. Supported files: PDF, TXT, DOCX, EPUB.")
        return [source]

    return find_supported_sources(paths.source_dir)


def _validate_non_interactive_settings(
    settings: Settings,
) -> None:
    missing = []

    if settings.project_dir is None:
        missing.append("--project-dir or a saved project folder")

    if settings.output_format not in {"mp3", "m4b", "both"}:
        missing.append("--output or a saved output format")

    if settings.original_action not in {"keep", "archive", "trash"}:
        missing.append("--original or a saved original-file action")

    if missing:
        raise RuntimeError("Non-interactive mode needs " + ", ".join(missing) + ".")


def _check_voice_non_interactively(voice: str) -> str:
    available = get_installed_voices()

    if voice not in available:
        raise RuntimeError(
            f'The voice "{voice}" is not installed on this Mac. '
            "Choose an installed voice with --voice."
        )

    return voice


def main() -> int:
    args = parse_args()
    options = conversion_options_from_args(args)

    say(f"Audiobook Maker {VERSION}")
    say("==========================")

    if args.version:
        say(VERSION)
        return 0

    if args.changelog:
        show_changelog()
        return 0

    settings = _apply_cli_settings(load_settings(), args)

    if options.non_interactive:
        _validate_non_interactive_settings(settings)
    elif settings.project_dir is None:
        settings = confirm_settings(settings)

    if settings.project_dir is None:
        raise RuntimeError("Project folder was not configured.")

    paths = ProjectPaths.from_project_dir(settings.project_dir)

    for folder in paths.required_directories():
        folder.mkdir(parents=True, exist_ok=True)

    if args.settings:
        show_settings(settings, paths)
        return 0

    check_tool("say")
    check_tool("ffmpeg")
    check_tool("ffprobe")

    if options.non_interactive:
        settings.voice = _check_voice_non_interactively(settings.voice)
    else:
        settings.voice = check_voice(settings.voice)

    save_settings(settings)

    if not options.non_interactive:
        settings = confirm_settings(settings)

        if settings.project_dir is None:
            raise RuntimeError("Project folder was not configured.")

        paths = ProjectPaths.from_project_dir(settings.project_dir)

        for folder in paths.required_directories():
            folder.mkdir(parents=True, exist_ok=True)

    if ID3 is None:
        raise RuntimeError(
            "Missing required Python package: mutagen. "
            "Install it with: python3 -m pip install mutagen"
        )

    sources = _resolve_sources(args, paths)

    if not sources:
        say(f"No supported files found in: {paths.source_dir}")
        say("Supported files: PDF, TXT, DOCX, EPUB.")
        return 0

    if any(path.suffix.lower() == ".pdf" for path in sources):
        check_tool("pdftotext")

    if any(path.suffix.lower() == ".docx" for path in sources) and docx is None:
        raise RuntimeError(
            "DOCX support needs python-docx. Install it with: python3 -m pip install python-docx"
        )

    if any(path.suffix.lower() == ".epub" for path in sources):
        if ebook_epub is None or BeautifulSoup is None:
            raise RuntimeError(
                "EPUB support needs ebooklib and beautifulsoup4. "
                "Install them with: python3 -m pip install ebooklib beautifulsoup4"
            )

    counts = {
        extension: sum(1 for path in sources if path.suffix.lower() == extension)
        for extension in SUPPORTED_EXTENSIONS
    }
    say(f"Found {len(sources)} source file(s).")
    say(
        f"PDF: {counts.get('.pdf', 0)}, "
        f"TXT: {counts.get('.txt', 0)}, "
        f"DOCX: {counts.get('.docx', 0)}, "
        f"EPUB: {counts.get('.epub', 0)}"
    )

    if options.non_interactive:
        run_original_action = settings.original_action or "archive"
    else:
        run_original_action = choose_run_original_action(settings.original_action or "archive")

    run_authors: list[str] = []
    completed = 0
    failed = 0

    for index, source in enumerate(sources, start=1):
        say("")
        say(f"Source {index} of {len(sources)}")

        try:
            outcome = process_source(
                source,
                settings,
                run_authors,
                args.force,
                paths,
                options,
            )

            if outcome is ConversionOutcome.COMPLETED:
                action = run_original_action

                if not options.non_interactive and run_original_action == "ask":
                    action, apply_to_remaining = choose_book_original_action(source.name)

                    if apply_to_remaining:
                        run_original_action = action
                        say(
                            "This choice will also apply to all remaining "
                            "successful books in this run: "
                            f"{original_action_description(action)}"
                        )

                original_result = handle_successful_original(
                    source,
                    action,
                    paths.converted_originals_dir,
                )
                say(original_result)
                completed += 1
        except Exception as error:
            failed += 1
            say("")
            say(f"Failed: {source.name}")
            say(str(error))

    say("")
    say("Run complete.")
    say(f"Books completed: {completed}")
    say(f"Books failed: {failed}")
    say(f"Finished audiobooks are in: {paths.finished_dir}")
    notify_run_complete(completed, failed, settings.voice)

    return 1 if failed else 0
