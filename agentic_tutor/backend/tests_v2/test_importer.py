"""Unit tests for the additive git-URL importer. The cloner is injected, so the clone path is
covered without any network access."""
import subprocess
from pathlib import Path

import pytest

from tutor_v2.errors import ValidationError
from tutor_v2.importer import clone_repository, validate_git_url


def test_validate_accepts_public_https():
    assert validate_git_url("https://github.com/psf/requests.git").endswith("requests.git")
    assert validate_git_url("  https://gitlab.com/group/proj  ") == "https://gitlab.com/group/proj"


@pytest.mark.parametrize("url", [
    "", "http://github.com/x/y", "git://github.com/x/y", "ssh://git@github.com/x/y",
    "file:///etc/passwd", "https://user:pass@github.com/x/y",
    "https://localhost/x", "https://127.0.0.1/x", "https://10.0.0.5/x",
    "https://192.168.1.1/x", "https://169.254.169.254/x", "https://box.local/x",
])
def test_validate_rejects_unsafe(url):
    with pytest.raises(ValidationError):
        validate_git_url(url)


def _clone_ok(url, target, timeout):
    Path(target).mkdir(parents=True)
    (Path(target) / "main.py").write_text("print('hi')\n")
    (Path(target) / ".git").mkdir()  # VCS metadata the importer must strip


def test_clone_success_registers_dir_and_strips_git(tmp_path):
    root = tmp_path / "codebases"
    target = clone_repository(git_url="https://github.com/x/y.git", name="My Repo!!",
                              dest_root=root, cloner=_clone_ok)
    assert target.is_dir() and target.parent == root.resolve()
    assert (target / "main.py").exists()
    assert not (target / ".git").exists()
    assert target.name.startswith("My-Repo-")  # slugified name + unique suffix


def test_clone_rejects_bad_url_before_touching_disk(tmp_path):
    with pytest.raises(ValidationError):
        clone_repository(git_url="ftp://x/y", name="r", dest_root=tmp_path, cloner=_clone_ok)
    assert list(tmp_path.iterdir()) == []


def test_clone_failure_cleans_up(tmp_path):
    def boom(url, target, timeout):
        Path(target).mkdir(parents=True)
        raise subprocess.CalledProcessError(128, "git")
    with pytest.raises(ValidationError):
        clone_repository(git_url="https://github.com/x/y", name="r", dest_root=tmp_path, cloner=boom)
    assert list(tmp_path.iterdir()) == []  # partial clone removed


def test_clone_timeout_cleans_up(tmp_path):
    def slow(url, target, timeout):
        Path(target).mkdir(parents=True)
        raise subprocess.TimeoutExpired("git", timeout)
    with pytest.raises(ValidationError):
        clone_repository(git_url="https://github.com/x/y", name="r", dest_root=tmp_path, cloner=slow)
    assert list(tmp_path.iterdir()) == []
