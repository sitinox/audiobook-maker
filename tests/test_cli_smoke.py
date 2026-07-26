
from audiobook_maker.cli import main

from audiobook_maker.common import VERSION

def test_version_is_v5():

    assert VERSION == "v5.1.0"

def test_version_command(monkeypatch, capsys):

    monkeypatch.setattr("sys.argv", ["audiobook", "--version"])

    result = main()

    output = capsys.readouterr().out

    assert result == 0

    assert "v5.1.0" in output

