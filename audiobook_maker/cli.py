import argparse
from importlib.resources import files

from .common import (
    BeautifulSoup, ID3, MAX_SPEECH_RATE,
    MIN_SPEECH_RATE, ProjectPaths, SAMPLE_RATE,
    SUPPORTED_EXTENSIONS, Settings, VERSION, check_tool,
    docx, ebook_epub, say,
)
from .settings import (
    check_voice, choose_book_original_action, choose_run_original_action,
    confirm_settings, load_settings, original_action_description,
    output_format_description, save_settings,
)
from .files import find_supported_sources, handle_successful_original
from .notifications import notify_run_complete
from .pipeline import ConversionOutcome, process_source

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
    parser.add_argument("--force", action="store_true", help="Remake MP3 files even if they already exist.")
    parser.add_argument("--voice", help="Override the saved macOS voice for this run and save it.")
    parser.add_argument("--rate", type=speech_rate, metavar="WPM", help=f"Override the saved speech rate for this run ({MIN_SPEECH_RATE}-{MAX_SPEECH_RATE} words per minute) and save it.")
    parser.add_argument("--bitrate", type=int, choices=[128, 192, 256, 320], help="Override the saved MP3 bitrate for this run and save it.")
    parser.add_argument("--settings", action="store_true", help="Show current settings and project folders, then exit.")
    parser.add_argument("--changelog", action="store_true", help="Show the built-in changelog, then exit.")
    parser.add_argument("--version", action="store_true", help="Show the script version, then exit.")
    return parser.parse_args()


def show_settings(settings: Settings, paths: ProjectPaths) -> None:

    say(f"Audiobook Maker {VERSION}")

    say(f"Voice: {settings.voice}")

    say(f"Speech rate: {settings.rate} words per minute")

    say(f"Audio: {SAMPLE_RATE / 1000:.1f} kHz, {settings.bitrate} kbps")

    say(

        f"Output format: "

        f"{output_format_description(settings.output_format)}"

    )

    say(

        f"After successful conversion: "

        f"{original_action_description(settings.original_action)}"

    )

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


def main() -> int:
    args = parse_args()
    say(f"Audiobook Maker {VERSION}")
    say("==========================")

    if args.version:
        say(VERSION)
        return 0

    if args.changelog:
        show_changelog()
        return 0

    settings = load_settings()
    if args.voice:
        settings.voice = args.voice
    if args.rate is not None:
        settings.rate = args.rate
    if args.bitrate:
        settings.bitrate = args.bitrate
    save_settings(settings)

    if settings.project_dir is None:
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
    settings.voice = check_voice(settings.voice)
    save_settings(settings)
    if ID3 is None:
        raise RuntimeError("Missing required Python package: mutagen. Install it with: python3 -m pip install mutagen")

    settings = confirm_settings(settings)

    if settings.project_dir is None:
        raise RuntimeError("Project folder was not configured.")

    paths = ProjectPaths.from_project_dir(settings.project_dir)

    for folder in paths.required_directories():
        folder.mkdir(parents=True, exist_ok=True)

    sources = find_supported_sources(paths.source_dir)
    if not sources:
        say(f"No supported files found in: {paths.source_dir}")
        say("Supported files: PDF, TXT, DOCX, EPUB.")
        return 0

    if any(p.suffix.lower() == ".pdf" for p in sources):
        check_tool("pdftotext")
    if any(p.suffix.lower() == ".docx" for p in sources) and docx is None:
        raise RuntimeError("DOCX support needs python-docx. Install it with: python3 -m pip install python-docx")
    if any(p.suffix.lower() == ".epub" for p in sources):
        if ebook_epub is None or BeautifulSoup is None:
            raise RuntimeError("EPUB support needs ebooklib and beautifulsoup4. Install them with: python3 -m pip install ebooklib beautifulsoup4")

    counts = {ext: sum(1 for p in sources if p.suffix.lower() == ext) for ext in SUPPORTED_EXTENSIONS}
    say(f"Found {len(sources)} source file(s).")
    say(f"PDF: {counts.get('.pdf', 0)}, TXT: {counts.get('.txt', 0)}, DOCX: {counts.get('.docx', 0)}, EPUB: {counts.get('.epub', 0)}")

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
            )
            if outcome is ConversionOutcome.COMPLETED:
                action = run_original_action
                if run_original_action == "ask":
                    action, apply_to_remaining = choose_book_original_action(source.name)
                    if apply_to_remaining:
                        run_original_action = action
                        say(f"This choice will also apply to all remaining successful books in this run: {original_action_description(action)}")
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


