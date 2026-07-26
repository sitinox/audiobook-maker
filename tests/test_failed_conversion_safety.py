
from types import SimpleNamespace

import pytest

import audiobook_maker.cli as cli

from audiobook_maker.common import Settings
from audiobook_maker.pipeline import ConversionOutcome

def test_failed_conversion_does_not_handle_original(tmp_path, monkeypatch):

    source_dir = tmp_path / "Books to Convert"

    source_dir.mkdir()

    source = source_dir / "Broken Book.txt"

    source.write_text("Disposable test source.", encoding="utf-8")

    args = SimpleNamespace(

        force=False,

        voice=None,

        rate=None,

        bitrate=None,

        settings=False,

        changelog=False,

        version=False,

    )

    settings = Settings(

        output_format="mp3",

        original_action="archive",

        project_dir=tmp_path,

    )

    handled = []

    monkeypatch.setattr(cli, "parse_args", lambda: args)

    monkeypatch.setattr(cli, "load_settings", lambda: settings)

    monkeypatch.setattr(cli, "save_settings", lambda value: None)

    monkeypatch.setattr(cli, "confirm_settings", lambda value: value)

    monkeypatch.setattr(cli, "check_tool", lambda name: None)

    monkeypatch.setattr(cli, "check_voice", lambda voice: voice)

    monkeypatch.setattr(cli, "find_supported_sources", lambda source_dir: [source])

    monkeypatch.setattr(

        cli,

        "choose_run_original_action",

        lambda default: "archive",

    )

    monkeypatch.setattr(

        cli,

        "process_source",

        lambda *args, **kwargs: (_ for _ in ()).throw(

            RuntimeError("Disposable conversion failure")

        ),

    )

    monkeypatch.setattr(

        cli,

        "handle_successful_original",

        lambda path, action, converted_dir: handled.append(

            (path, action)

        ),

    )

    monkeypatch.setattr(cli, "notify_run_complete", lambda *args: None)

    monkeypatch.setattr(cli, "say", lambda *args: None)

    monkeypatch.setattr(cli, "ID3", object())

    result = cli.main()

    assert result == 1

    assert source.exists()

    assert source.read_text(encoding="utf-8") == "Disposable test source."

    assert handled == []



@pytest.mark.parametrize("original_action", ["keep", "archive", "trash"])

def test_cancelled_conversion_does_not_handle_original(

    original_action,

    tmp_path,

    monkeypatch,

):

    source_dir = tmp_path / "Books to Convert"

    source_dir.mkdir()

    source = source_dir / "Cancelled Book.txt"

    source.write_text("Disposable test source.", encoding="utf-8")

    args = SimpleNamespace(

        force=False,

        voice=None,

        rate=None,

        bitrate=None,

        settings=False,

        changelog=False,

        version=False,

    )

    settings = Settings(

        output_format="mp3",

        original_action=original_action,

        project_dir=tmp_path,

    )

    handled = []

    messages = []

    monkeypatch.setattr(cli, "parse_args", lambda: args)

    monkeypatch.setattr(cli, "load_settings", lambda: settings)

    monkeypatch.setattr(cli, "save_settings", lambda value: None)

    monkeypatch.setattr(cli, "confirm_settings", lambda value: value)

    monkeypatch.setattr(cli, "check_tool", lambda name: None)

    monkeypatch.setattr(cli, "check_voice", lambda voice: voice)

    monkeypatch.setattr(cli, "find_supported_sources", lambda source_dir: [source])

    monkeypatch.setattr(

        cli,

        "choose_run_original_action",

        lambda default: original_action,

    )

    monkeypatch.setattr(

        cli,

        "process_source",

        lambda *args, **kwargs: ConversionOutcome.CANCELLED,

    )

    monkeypatch.setattr(

        cli,

        "handle_successful_original",

        lambda path, action, converted_dir: handled.append(

            (path, action)

        ),

    )

    monkeypatch.setattr(cli, "notify_run_complete", lambda *args: None)

    monkeypatch.setattr(cli, "say", messages.append)

    monkeypatch.setattr(cli, "ID3", object())

    result = cli.main()

    assert result == 0

    assert source.exists()

    assert source.read_text(encoding="utf-8") == "Disposable test source."

    assert handled == []

    assert "Books completed: 0" in messages

    assert "Books failed: 0" in messages

