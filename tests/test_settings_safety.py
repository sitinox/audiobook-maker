import json
from pathlib import Path

import pytest

from audiobook_maker.common import DEFAULT_RATE, ProjectPaths, Settings
from audiobook_maker import settings as settings_module
from audiobook_maker.cli import parse_args


def test_cli_rejects_rate_below_supported_range(monkeypatch):
    monkeypatch.setattr("sys.argv", ["audiobook", "--rate", "-50"])
    with pytest.raises(SystemExit) as error:
        parse_args()
    assert error.value.code == 2


def test_cli_accepts_supported_rate(monkeypatch):
    monkeypatch.setattr("sys.argv", ["audiobook", "--rate", "325"])
    assert parse_args().rate == 325


def test_corrupt_settings_are_preserved(monkeypatch, tmp_path, capsys):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(settings_module, "SETTINGS_PATH", settings_path)

    loaded = settings_module.load_settings()

    assert loaded.rate == DEFAULT_RATE
    assert not settings_path.exists()
    backups = list(tmp_path.glob("settings.json.corrupt-*") )
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{not valid json"
    assert "preserved" in capsys.readouterr().out


def test_settings_are_saved_as_valid_json(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_module, "SETTINGS_PATH", settings_path)

    settings_module.save_settings(Settings(rate=300, bitrate=192))

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["rate"] == 300
    assert list(tmp_path.glob(".settings.json.*.tmp")) == []

def test_saved_project_folder_is_loaded(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    project_dir = tmp_path / "My Audiobooks"
    settings_path.write_text(
        json.dumps(
            {
                "rate": 300,
                "project_dir": str(project_dir),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_module, "SETTINGS_PATH", settings_path)

    loaded = settings_module.load_settings()

    assert loaded.project_dir == project_dir


def test_missing_project_folder_remains_unconfigured(
    monkeypatch,
    tmp_path,
):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_module, "SETTINGS_PATH", settings_path)

    loaded = settings_module.load_settings()

    assert loaded.project_dir is None


def test_project_paths_are_derived_from_selected_folder(tmp_path):
    project_dir = tmp_path / "Audiobook Workspace"

    paths = ProjectPaths.from_project_dir(project_dir)

    assert paths.project_dir == project_dir
    assert paths.source_dir == project_dir / "Books to Convert"
    assert paths.finished_dir == project_dir / "Finished MP3 Audiobooks"
    assert paths.chapter_text_dir == project_dir / "Chapter Text Files"
    assert paths.extracted_text_dir == project_dir / "Extracted Full Text"
    assert paths.reports_dir == project_dir / "Reports"
    assert paths.converted_originals_dir == (
        project_dir / "Converted Originals"
    )


def test_required_directories_stay_inside_selected_folder(tmp_path):
    project_dir = tmp_path / "Selected Location"
    paths = ProjectPaths.from_project_dir(project_dir)

    for directory in paths.required_directories():
        directory.mkdir(parents=True, exist_ok=True)

    assert all(
        directory == project_dir
        or project_dir in directory.parents
        for directory in paths.required_directories()
    )
