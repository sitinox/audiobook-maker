from pathlib import Path

from audiobook_maker.cli import main
from audiobook_maker.common import VERSION


def test_version_is_v1():

    assert VERSION == "v1.0.0"


def test_version_command(monkeypatch, capsys):

    monkeypatch.setattr("sys.argv", ["audiobook", "--version"])

    result = main()

    output = capsys.readouterr().out

    assert result == 0

    assert "v1.0.0" in output


def test_packaged_changelog_matches_repository_changelog():
    repository = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
    packaged = Path(__file__).resolve().parents[1] / "audiobook_maker" / "CHANGELOG.md"
    assert packaged.read_text(encoding="utf-8") == repository.read_text(encoding="utf-8")
