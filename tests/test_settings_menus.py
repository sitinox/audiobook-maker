from audiobook_maker import settings


def _answers(monkeypatch, values):
    iterator = iter(values)
    monkeypatch.setattr(settings, "ask", lambda _prompt: next(iterator))
    monkeypatch.setattr(settings, "say", lambda _message: None)


def test_output_format_menu_repeats_then_selects(monkeypatch):
    _answers(monkeypatch, ["r", "2"])
    assert settings.choose_output_format() == "m4b"


def test_run_original_action_accepts_saved_default(monkeypatch):
    _answers(monkeypatch, [""])
    assert settings.choose_run_original_action("archive") == "archive"


def test_book_original_action_can_apply_to_remaining_books(monkeypatch):
    _answers(monkeypatch, ["5"])
    assert settings.choose_book_original_action("Example") == ("archive", True)
