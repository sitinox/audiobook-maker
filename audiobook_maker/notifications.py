import subprocess
from typing import Optional

def send_macos_notification(title: str, message: str, sound_name: str = "Glass") -> None:
    script = 'display notification (item 2 of argv) with title (item 1 of argv) sound name (item 3 of argv)'
    subprocess.run(
        ["osascript", "-e", "on run argv", "-e", script, "-e", "end run", title, message, sound_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def announce_result(message: str, voice: Optional[str] = None) -> None:
    command = ["say"]
    if voice:
        command.extend(["-v", voice])
    command.append(message)
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def notify_run_complete(completed: int, failed: int, voice: Optional[str]) -> None:
    if failed:
        spoken = f"Audiobook Maker finished. {completed} books completed and {failed} failed. Please check Terminal."
        send_macos_notification("Audiobook Maker", spoken, "Basso")
    else:
        noun = "book" if completed == 1 else "books"
        spoken = f"Audiobook conversion complete. {completed} {noun} completed successfully."
        send_macos_notification("Audiobook Maker", spoken, "Glass")
    announce_result(spoken, voice)


