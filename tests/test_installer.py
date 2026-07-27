import os
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPOSITORY_ROOT / "Install Audiobook Maker.command"
UNINSTALLER = REPOSITORY_ROOT / "Uninstall Audiobook Maker.command"


def run_script(script: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/bin/zsh", str(script)],
        cwd=REPOSITORY_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_installer_and_uninstaller_are_executable():
    assert os.access(INSTALLER, os.X_OK)
    assert os.access(UNINSTALLER, os.X_OK)


def test_installer_declares_release_version():
    contents = INSTALLER.read_text(encoding="utf-8")

    assert 'VERSION="v1.1.0"' in contents
    assert "refs/tags/$VERSION.zip" in contents


def test_installer_is_idempotent_and_uninstaller_preserves_user_data(tmp_path):
    support_dir = tmp_path / "Application Support" / "Audiobook Maker"
    venv_dir = support_dir / "venv"
    bin_dir = tmp_path / "bin"
    profile_path = tmp_path / ".zprofile"
    project_dir = tmp_path / "My Audiobooks"
    settings_file = support_dir / "settings.json"

    project_dir.mkdir()
    (project_dir / "Book.txt").write_text("user book", encoding="utf-8")
    support_dir.mkdir(parents=True)
    settings_file.write_text('{"voice": "Daniel"}\n', encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "AUDIOBOOK_MAKER_SKIP_BREW": "1",
            "AUDIOBOOK_MAKER_SUPPORT_DIR": str(support_dir),
            "AUDIOBOOK_MAKER_VENV_DIR": str(venv_dir),
            "AUDIOBOOK_MAKER_BIN_DIR": str(bin_dir),
            "AUDIOBOOK_MAKER_PROFILE_PATH": str(profile_path),
            "AUDIOBOOK_MAKER_SOURCE_SPEC": str(REPOSITORY_ROOT),
        }
    )

    first = run_script(INSTALLER, env)
    assert first.returncode == 0, first.stdout + first.stderr
    assert (bin_dir / "audiobook").is_symlink()
    assert (
        subprocess.run(
            [str(bin_dir / "audiobook"), "--version"],
            text=True,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )

    second = run_script(INSTALLER, env)
    assert second.returncode == 0, second.stdout + second.stderr

    profile = profile_path.read_text(encoding="utf-8")
    assert profile.count("# >>> Audiobook Maker managed PATH >>>") == 1

    removed = run_script(UNINSTALLER, env)
    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert not (bin_dir / "audiobook").exists()
    assert not venv_dir.exists()

    assert settings_file.exists()
    assert settings_file.read_text(encoding="utf-8") == '{"voice": "Daniel"}\n'
    assert (project_dir / "Book.txt").read_text(encoding="utf-8") == "user book"
    assert support_dir.exists()
