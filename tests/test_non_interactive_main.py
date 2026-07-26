from argparse import Namespace

import pytest

from audiobook_maker.cli import (
    _apply_cli_settings,
    _resolve_sources,
    _validate_non_interactive_settings,
)
from audiobook_maker.common import ProjectPaths, Settings


def make_args(**overrides):
    values = {
        "voice": None,
        "rate": None,
        "bitrate": None,
        "output": None,
        "original": None,
        "project_dir": None,
        "source": None,
    }
    values.update(overrides)
    return Namespace(**values)


def test_cli_overrides_are_applied_to_settings(tmp_path):
    project_dir = tmp_path / "Project"
    settings = _apply_cli_settings(
        Settings(),
        make_args(
            voice="Daniel",
            rate=300,
            bitrate=256,
            output="both",
            original="archive",
            project_dir=project_dir,
        ),
    )

    assert settings.voice == "Daniel"
    assert settings.rate == 300
    assert settings.bitrate == 256
    assert settings.output_format == "both"
    assert settings.original_action == "archive"
    assert settings.project_dir == project_dir


def test_non_interactive_settings_require_all_saved_choices(tmp_path):
    with pytest.raises(RuntimeError) as error:
        _validate_non_interactive_settings(Settings())

    message = str(error.value)

    assert "project" in message.lower()
    assert "output" in message.lower()
    assert "original" in message.lower()


def test_non_interactive_settings_accept_complete_configuration(tmp_path):
    _validate_non_interactive_settings(
        Settings(
            project_dir=tmp_path,
            output_format="mp3",
            original_action="keep",
        )
    )


def test_explicit_source_is_resolved_outside_project_folder(tmp_path):
    project_dir = tmp_path / "Project"
    paths = ProjectPaths.from_project_dir(project_dir)

    for directory in paths.required_directories():
        directory.mkdir(parents=True, exist_ok=True)

    source = tmp_path / "Outside.epub"
    source.write_text("example", encoding="utf-8")

    resolved = _resolve_sources(
        make_args(source=source),
        paths,
    )

    assert resolved == [source]


def test_missing_explicit_source_fails(tmp_path):
    paths = ProjectPaths.from_project_dir(tmp_path / "Project")

    with pytest.raises(RuntimeError) as error:
        _resolve_sources(
            make_args(source=tmp_path / "Missing.epub"),
            paths,
        )

    assert "not found" in str(error.value).lower()


def test_unsupported_explicit_source_fails(tmp_path):
    paths = ProjectPaths.from_project_dir(tmp_path / "Project")
    source = tmp_path / "Example.md"
    source.write_text("example", encoding="utf-8")

    with pytest.raises(RuntimeError) as error:
        _resolve_sources(
            make_args(source=source),
            paths,
        )

    assert "unsupported" in str(error.value).lower()
