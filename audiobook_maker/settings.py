import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from .common import (
    DEFAULT_BITRATE, DEFAULT_RATE, DEFAULT_VOICE, MAX_SPEECH_RATE,
    MIN_SPEECH_RATE, SAMPLE_RATE, SETTINGS_PATH, Settings, say,
)

def get_installed_voices() -> list[str]:
    result = subprocess.run(["say", "-v", "?"], text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("Could not list the speech voices available on this Mac.")

    voices: list[str] = []
    for line in result.stdout.splitlines():
        details = line.split("#", 1)[0].rstrip()
        parts = details.rsplit(None, 1)
        if len(parts) != 2:
            continue

        voice, language = parts
        if "_" not in language:
            continue

        voice = voice.strip()
        if voice and voice not in voices:
            voices.append(voice)

    if not voices:
        raise RuntimeError("No usable macOS speech voices were found.")

    return voices


def choose_installed_voice(current_voice: Optional[str] = None) -> str:
    voices = get_installed_voices()

    if current_voice and current_voice not in voices:
        say(f'The saved voice "{current_voice}" is not available on this Mac.')

    while True:
        say("")
        say("Voices available on this Mac:")
        for number, voice in enumerate(voices, start=1):
            say(f"{number}. {voice}")

        choice = ask(
            "Type the number of the voice you want, or type r to repeat the list."
        ).lower()

        if choice == "r":
            continue
        if choice.isdigit():
            number = int(choice)
            if 1 <= number <= len(voices):
                return voices[number - 1]

        say("Please type one of the numbers in the list, or type r.")


def check_voice(voice: str) -> str:
    voices = get_installed_voices()
    if voice in voices:
        return voice
    return choose_installed_voice(voice)




def _valid_rate(value: object) -> int:
    rate = int(value)
    if not MIN_SPEECH_RATE <= rate <= MAX_SPEECH_RATE:
        raise ValueError(
            f"Speech rate must be between {MIN_SPEECH_RATE} and {MAX_SPEECH_RATE}."
        )
    return rate


def _corrupt_settings_backup_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = SETTINGS_PATH.with_name(f"{SETTINGS_PATH.name}.corrupt-{timestamp}")
    counter = 2
    while candidate.exists():
        candidate = SETTINGS_PATH.with_name(
            f"{SETTINGS_PATH.name}.corrupt-{timestamp}-{counter}"
        )
        counter += 1
    return candidate


def load_settings() -> Settings:
    if not SETTINGS_PATH.exists():
        return Settings()

    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        original_action = data.get("original_action")
        if original_action not in {"keep", "archive", "trash"}:
            original_action = None

        output_format = data.get("output_format")
        if output_format not in {"mp3", "m4b", "both"}:
            output_format = None

        bitrate = int(data.get("bitrate", DEFAULT_BITRATE))
        if bitrate not in {128, 192, 256, 320}:
            bitrate = DEFAULT_BITRATE

        return Settings(
            voice=str(data.get("voice", DEFAULT_VOICE)),
            rate=_valid_rate(data.get("rate", DEFAULT_RATE)),
            bitrate=bitrate,
            output_format=output_format,
            original_action=original_action,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        backup_path = _corrupt_settings_backup_path()
        try:
            SETTINGS_PATH.replace(backup_path)
            say(
                f"Settings could not be read and were preserved as {backup_path.name}. "
                f"Using defaults. Details: {error}"
            )
        except OSError as backup_error:
            say(
                "Settings could not be read. Using defaults. "
                f"The damaged file could not be preserved: {backup_error}"
            )
        return Settings()


def save_settings(settings: Settings) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "voice": settings.voice,
            "rate": _valid_rate(settings.rate),
            "bitrate": settings.bitrate,
            "output_format": settings.output_format,
            "original_action": settings.original_action,
        },
        indent=2,
    ) + "\n"

    temporary_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=SETTINGS_PATH.parent,
            prefix=f".{SETTINGS_PATH.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(payload)
            temporary_file.flush()
            temporary_path = Path(temporary_file.name)
        temporary_path.replace(SETTINGS_PATH)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def output_format_description(output_format: Optional[str]) -> str:
    descriptions = {
        "mp3": "MP3 chapters",
        "m4b": "Chapterised M4B",
        "both": "Both MP3 chapters and M4B",
    }
    return descriptions.get(output_format, "Not chosen yet")


def _choose_numbered_option(
    introduction: str,
    options: list[tuple[str, str, object]],
    prompt: str,
    invalid_message: str,
    *,
    default: object = None,
    allow_default: bool = False,
) -> object:
    """Speak a numbered menu and return the selected value."""
    choices = {number: value for number, _label, value in options}

    while True:
        say("")
        say(introduction)
        for number, label, _value in options:
            say(f"{number}. {label}")

        choice = ask(prompt).lower()
        if choice == "r":
            continue
        if allow_default and choice == "":
            return default
        if choice in choices:
            return choices[choice]

        say(invalid_message)


def choose_output_format() -> str:
    return str(
        _choose_numbered_option(
            "Choose the audiobook output format.",
            [
                ("1", "MP3 chapters.", "mp3"),
                ("2", "Chapterised M4B.", "m4b"),
                ("3", "Both MP3 chapters and M4B.", "both"),
            ],
            "Type 1, 2, or 3, or type r to repeat the choices.",
            "Please type 1, 2, 3, or r.",
        )
    )


def original_action_description(action: Optional[str]) -> str:
    descriptions = {
        "keep": "Keep the original in Books to Convert",
        "archive": "Move the original to Converted Originals",
        "trash": "Move the original to the Bin",
    }
    return descriptions.get(action, "Not chosen yet")


def choose_original_action() -> str:
    return str(
        _choose_numbered_option(
            "After a book converts successfully, what should normally happen to its original file?",
            [
                ("1", "Keep it in Books to Convert.", "keep"),
                ("2", "Move it to Converted Originals. Recommended.", "archive"),
                ("3", "Move it to the Bin.", "trash"),
            ],
            "Type 1, 2, or 3, or type r to repeat the choices.",
            "Please type 1, 2, 3, or r.",
        )
    )


def choose_run_original_action(default_action: str) -> str:
    return str(
        _choose_numbered_option(
            "What should happen to original books after successful conversion during this run?",
            [
                ("1", "Keep every successful original in Books to Convert for this run.", "keep"),
                ("2", "Move every successful original to Converted Originals for this run.", "archive"),
                ("3", "Move every successful original to the Bin for this run.", "trash"),
                ("4", "Ask me after each successful book.", "ask"),
            ],
            (
                "Press Enter, type 1, 2, 3, or 4, or type r to repeat the choices. "
                f"Press Enter to use: {original_action_description(default_action)}."
            ),
            "Please press Enter, type 1, 2, 3, 4, or r.",
            default=default_action,
            allow_default=True,
        )
    )


def choose_book_original_action(book_name: str) -> tuple[str, bool]:
    result = _choose_numbered_option(
        f"What should happen to the original file for {book_name}?",
        [
            ("1", "Keep this original in Books to Convert.", ("keep", False)),
            ("2", "Move this original to Converted Originals.", ("archive", False)),
            ("3", "Move this original to the Bin.", ("trash", False)),
            ("4", "Keep this and all remaining successful originals in Books to Convert.", ("keep", True)),
            ("5", "Move this and all remaining successful originals to Converted Originals.", ("archive", True)),
            ("6", "Move this and all remaining successful originals to the Bin.", ("trash", True)),
        ],
        "Type 1, 2, 3, 4, 5, or 6, or type r to repeat the choices.",
        "Please type 1, 2, 3, 4, 5, 6, or r.",
    )
    if not isinstance(result, tuple):
        raise RuntimeError("Unexpected original-file action selection.")
    return result


def ask(prompt: str) -> str:
    say(prompt)
    return input().strip()




def confirm_settings(settings: Settings) -> Settings:

    while True:

        say(f"Voice: {settings.voice}")

        say(f"Speech rate: {settings.rate} words per minute")

        say(f"Audio: {SAMPLE_RATE / 1000:.1f} kHz, {settings.bitrate} kbps")

        if settings.output_format is None:

            settings.output_format = choose_output_format()

            save_settings(settings)

        say(

            f"Output format: "

            f"{output_format_description(settings.output_format)}"

        )

        if settings.original_action is None:

            settings.original_action = choose_original_action()

            save_settings(settings)

        say(

            f"After successful conversion: "

            f"{original_action_description(settings.original_action)}"

        )

        choice = ask(

            "Press Enter to use these settings, or type change."

        ).lower()

        if choice == "":

            save_settings(settings)

            return settings

        if choice in {"change", "c"}:

            settings = change_settings(settings)

            save_settings(settings)

            return settings

        say("Please press Enter or type change.")



def change_settings(settings: Settings) -> Settings:

    say(f"Voice is currently {settings.voice}.")

    voice_choice = ask(

        "Press Enter to keep it, or type change to choose another installed voice."

    ).lower()

    if voice_choice in {"change", "c"}:

        settings.voice = choose_installed_voice()

    elif voice_choice:

        say("Voice unchanged. Type change to choose from the installed voices.")

    while True:

        rate_choice = ask(

            f"Speech rate is currently {settings.rate}. Press Enter to keep it, or type a new number."

        )

        if not rate_choice:

            break

        try:

            settings.rate = _valid_rate(rate_choice)

            break

        except (ValueError, TypeError):

            say(f"Please type a number from {MIN_SPEECH_RATE} to {MAX_SPEECH_RATE}.")

    while True:

        say("Bitrate choices: 128 smaller, 192 recommended, 256 higher, 320 maximum.")

        bitrate_choice = ask(

            f"Bitrate is currently {settings.bitrate}. Press Enter to keep it, or type 128, 192, 256, or 320."

        )

        if not bitrate_choice:

            break

        try:

            bitrate = int(bitrate_choice)

            if bitrate in {128, 192, 256, 320}:

                settings.bitrate = bitrate

                break

        except ValueError:

            pass

        say("Please choose 128, 192, 256, or 320.")

    while True:

        say(

            f"Output format is currently: "

            f"{output_format_description(settings.output_format)}."

        )

        output_choice = ask(

            "Press Enter to keep it, type change to choose another output format, or type r to repeat."

        ).lower()

        if output_choice == "":

            break

        if output_choice in {"change", "c"}:

            settings.output_format = choose_output_format()

            break

        if output_choice == "r":

            continue

        say("Please press Enter, type change, or type r.")

    say(

        f"Original-file action is currently: "

        f"{original_action_description(settings.original_action)}."

    )

    original_choice = ask(

        "Press Enter to keep it, or type change to choose what happens after successful conversion."

    ).lower()

    if original_choice in {"change", "c"}:

        settings.original_action = choose_original_action()

    elif original_choice:

        say("Original-file action unchanged. Type change to choose another option.")

    return settings

def choose_title(source_path: Path, suggested_title: str) -> str:
    while True:
        say(f"Suggested title: {suggested_title}")
        answer = ask("Press Enter to accept, type r to repeat, or type a different title.")
        if answer == "":
            return suggested_title
        if answer.lower() == "r":
            continue
        return answer


def choose_author(source_path: Path, suggested_author: Optional[str], run_authors: list[str]) -> str:
    while True:
        if suggested_author:
            say(f"Suggested author: {suggested_author}")
            answer = ask("Press Enter to accept, type r to repeat, type list to choose a previous author, or type a different author.")
            if answer == "":
                author = suggested_author
                break
            if answer.lower() == "r":
                continue
            if answer.lower() == "list" and run_authors:
                suggested_author = None
                continue
            if answer.strip():
                author = answer.strip()
                break

        elif run_authors:
            say("Authors used in this run:")
            for index, author_name in enumerate(run_authors, start=1):
                say(f"{index}. {author_name}")
            answer = ask("Type a number to choose an author, type r to repeat this list, or type a new author.")
            if answer.lower() == "r":
                continue
            if answer.isdigit() and 1 <= int(answer) <= len(run_authors):
                author = run_authors[int(answer) - 1]
                break
            if answer.strip():
                author = answer.strip()
                break

        else:
            answer = ask(f"Author for {source_path.name}:")
            if answer.strip():
                author = answer.strip()
                break

        say("Please enter an author, accept the suggestion, or choose one from the list.")

    if author in run_authors:
        run_authors.remove(author)
    run_authors.append(author)
    return author


