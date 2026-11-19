"""Print the CHANGELOG section for a release, after checking the tag matches the package version.

    python scripts/release_notes.py v0.1.0 > notes.md

Fails if the tag doesn't match `py_term.__version__` or CHANGELOG.md has no `## 0.1.0` section.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def package_version() -> str:
    text = (ROOT / "src" / "py_term" / "__init__.py").read_text()
    m = re.search(r'^__version__ = "([^"]+)"', text, re.M)
    if not m:
        raise SystemExit("no __version__ in src/py_term/__init__.py")
    return m.group(1)


def notes(version: str, changelog: str) -> str:
    m = re.search(rf"^## {re.escape(version)}\s*$(.*?)(?=^## |\Z)", changelog, re.M | re.S)
    if not m or not m.group(1).strip():
        raise SystemExit(f"CHANGELOG.md has no '## {version}' section (rename '## Unreleased' when releasing)")
    return m.group(1).strip() + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        raise SystemExit("usage: release_notes.py vX.Y.Z")
    version = argv[0].removeprefix("refs/tags/").removeprefix("v")
    if version != package_version():
        raise SystemExit(f"tag v{version} doesn't match __version__ {package_version()}")
    sys.stdout.write(notes(version, (ROOT / "CHANGELOG.md").read_text()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
