import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .common import SUPPORTED_EXTENSIONS


def unique_destination(directory: Path, source_name: str) -> Path:
    candidate = directory / source_name
    if not candidate.exists():
        return candidate
    stem = Path(source_name).stem
    suffix = Path(source_name).suffix
    number = 2
    while True:
        candidate = directory / f"{stem} ({number}){suffix}"
        if not candidate.exists():
            return candidate
        number += 1


def handle_successful_original(
    source_path: Path,
    action: Optional[str],
    converted_originals_dir: Path,
) -> str:
    if action == "keep" or action is None:
        return "Original kept in Books to Convert."

    if action == "archive":
        converted_originals_dir.mkdir(parents=True, exist_ok=True)
        destination = unique_destination(converted_originals_dir, source_path.name)
        shutil.move(str(source_path), str(destination))
        return f"Original moved to Converted Originals as: {destination.name}"

    if action == "trash":
        result = subprocess.run(
            [
                "osascript",
                "-e",
                "on run argv",
                "-e",
                'tell application "Finder" to delete POSIX file (item 1 of argv)',
                "-e",
                "end run",
                str(source_path),
            ],
            text=True,
            capture_output=True,
        )
        # Finder can report an AppleScript error after moving the file.
        # Check whether the original actually remains before declaring failure.
        if not source_path.exists():
            return "Original moved to the Bin."

        error_detail = (
            result.stderr.strip()
            or result.stdout.strip()
            or "macOS did not provide an error message."
        )

        raise RuntimeError(
            "The audiobook was created, but the original is still present "
            "and could not be moved to the Bin. " + error_detail
        )

    return "Original kept in Books to Convert."


def find_supported_sources(source_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in source_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def unique_filename(base_name: str, used: set[str]) -> str:
    candidate = base_name
    counter = 2
    while candidate.lower() in used:
        candidate = f"{base_name} {counter}"
        counter += 1
    used.add(candidate.lower())
    return candidate


def write_report(report_path: Path, lines: list[str]) -> None:
    report_path.write_text("\n".join(lines), encoding="utf-8")
