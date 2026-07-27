from argparse import Namespace

import audiobook_maker.cli as cli
from audiobook_maker.common import ConversionOptions, Settings
from audiobook_maker.pipeline import ConversionOutcome


def fail_prompt(*_args, **_kwargs):
    raise AssertionError("Interactive function was called.")


def test_main_non_interactive_never_prompts(tmp_path, monkeypatch):
    project_dir = tmp_path / "Project"
    source_dir = project_dir / "Books to Convert"
    source_dir.mkdir(parents=True)
    source = source_dir / "Example.txt"
    source.write_text("Example source text.", encoding="utf-8")

    args = Namespace(
        source=source,
        process_all=False,
        non_interactive=True,
        title="Example Book",
        author="Example Author",
        front_matter="skip",
        output="mp3",
        original="keep",
        project_dir=project_dir,
        force=False,
        voice="Daniel",
        rate=300,
        bitrate=192,
        jobs=3,
        settings=False,
        changelog=False,
        version=False,
    )

    saved = []
    processed = []
    handled = []

    monkeypatch.setattr(cli, "parse_args", lambda: args)
    monkeypatch.setattr(cli, "load_settings", lambda: Settings())
    monkeypatch.setattr(cli, "save_settings", saved.append)
    monkeypatch.setattr(cli, "confirm_settings", fail_prompt)
    monkeypatch.setattr(cli, "check_voice", fail_prompt)
    monkeypatch.setattr(cli, "choose_run_original_action", fail_prompt)
    monkeypatch.setattr(cli, "choose_book_original_action", fail_prompt)
    monkeypatch.setattr(cli, "get_installed_voices", lambda: ["Daniel"])
    monkeypatch.setattr(cli, "check_tool", lambda _name: None)
    monkeypatch.setattr(cli, "notify_run_complete", lambda *_args: None)
    monkeypatch.setattr(cli, "say", lambda *_args: None)
    monkeypatch.setattr(cli, "ID3", object())

    def process_source(
        source_path,
        settings,
        run_authors,
        force,
        paths,
        options,
    ):
        processed.append(
            (
                source_path,
                settings,
                run_authors,
                force,
                paths,
                options,
            )
        )
        return ConversionOutcome.COMPLETED

    monkeypatch.setattr(cli, "process_source", process_source)

    def handle_original(source_path, action, converted_dir):
        handled.append((source_path, action, converted_dir))
        return "Original kept."

    monkeypatch.setattr(cli, "handle_successful_original", handle_original)

    result = cli.main()

    assert result == 0
    assert len(processed) == 1

    (
        processed_source,
        processed_settings,
        _run_authors,
        processed_force,
        processed_paths,
        processed_options,
    ) = processed[0]

    assert processed_source == source
    assert processed_force is False
    assert processed_paths.project_dir == project_dir
    assert processed_settings.project_dir == project_dir
    assert processed_settings.output_format == "mp3"
    assert processed_settings.original_action == "keep"
    assert processed_settings.voice == "Daniel"
    assert processed_settings.rate == 300
    assert processed_settings.bitrate == 192
    assert processed_options == ConversionOptions(
        non_interactive=True,
        source=source,
        process_all=False,
        title="Example Book",
        author="Example Author",
        front_matter="skip",
        jobs=3,
    )
    assert handled == [
        (
            source,
            "keep",
            project_dir / "Converted Originals",
        )
    ]
    assert saved
