from pathlib import Path
import subprocess
import sys


def test_non_epub_cover_regression():
    script = Path(__file__).with_name("non_epub_cover_regression.py")

    result = subprocess.run(
        [sys.executable, str(script)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, (
        "Non-EPUB cover regression failed.\n\n"
        f"Standard output:\n{result.stdout}\n\n"
        f"Standard error:\n{result.stderr}"
    )

    assert "ALL NON-EPUB COVER TESTS PASSED" in result.stdout
