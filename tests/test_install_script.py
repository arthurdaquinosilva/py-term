"""The install script must stay a valid, self-describing POSIX shell script."""

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "install.sh"


def test_is_valid_posix_sh():
    subprocess.run(["sh", "-n", str(SCRIPT)], check=True)


def test_help_lists_the_options():
    out = subprocess.run(["sh", str(SCRIPT), "--help"], capture_output=True, text=True, check=True).stdout
    for option in ("--uninstall", "PY_TERM_VERSION", "PY_TERM_NO_PIPX", "PY_TERM_INSTALL_DIR"):
        assert option in out


def test_rejects_unknown_options():
    result = subprocess.run(["sh", str(SCRIPT), "--wat"], capture_output=True, text=True)
    assert result.returncode != 0 and "unknown option" in result.stderr


def test_installs_the_published_package_name():
    assert 'PACKAGE="py-term"' in SCRIPT.read_text()


@pytest.mark.skipif(not shutil.which("shellcheck"), reason="shellcheck is not installed")
def test_shellcheck_clean():
    subprocess.run(["shellcheck", str(SCRIPT)], check=True)


FAKE_CURL = """#!/bin/sh
# Stands in for curl: answers the latest-release lookup and serves files from $FAKE_RELEASE.
dest=''; url=''; effective=''
while [ $# -gt 0 ]; do
    case "$1" in
        -o) dest=$2; shift ;;
        -w) effective=1; shift ;;
        -*) ;;
        *) url=$1 ;;
    esac
    shift
done
if [ -n "$effective" ]; then printf 'https://github.com/x/y/releases/tag/v%s' "$FAKE_LATEST"; exit 0; fi
[ -f "$FAKE_RELEASE/${url##*/}" ] || exit 22
cp "$FAKE_RELEASE/${url##*/}" "$dest"
"""


def run_installer(tmp_path, env=None, files=None, latest="0.5.0"):
    """Run install.sh with a fake curl and no pipx; returns the completed process."""
    import os

    bin_dir, release = tmp_path / "fakebin", tmp_path / "release"
    bin_dir.mkdir()
    release.mkdir()
    curl = bin_dir / "curl"
    curl.write_text(FAKE_CURL)
    curl.chmod(0o755)
    for name, content in (files or {}).items():
        (release / name).write_bytes(content if isinstance(content, bytes) else content.encode())
    full_env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "FAKE_RELEASE": str(release),
        "FAKE_LATEST": latest,
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "PY_TERM_INSTALL_DIR": str(tmp_path / "bin"),
        "PY_TERM_NO_PIPX": "1",
        **(env or {}),
    }
    if "PY_TERM_VERSION" not in (env or {}):
        full_env.pop("PY_TERM_VERSION", None)
    return subprocess.run(["sh", str(SCRIPT)], capture_output=True, text=True, env=full_env, timeout=60)


def sha(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def test_checksum_mismatch_stops_the_install(tmp_path):
    wheel = "py_term-0.5.0-py3-none-any.whl"
    result = run_installer(tmp_path, files={wheel: b"tampered", "SHA256SUMS": f"{sha(b'original')}  {wheel}\n"})
    assert result.returncode != 0
    assert "version: 0.5.0" in result.stdout
    assert "checksum mismatch" in result.stderr
    assert not (tmp_path / "data" / "py-term" / "venv").exists()


def test_wheel_missing_from_checksums_stops_the_install(tmp_path):
    wheel = "py_term-0.5.0-py3-none-any.whl"
    result = run_installer(tmp_path, files={wheel: b"x", "SHA256SUMS": f"{sha(b'x')}  something-else.tar.gz\n"})
    assert result.returncode != 0 and "does not list" in result.stderr
