import json
from pathlib import Path

import pytest

from audiobook_maker.common import DEFAULT_RATE, Settings
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
