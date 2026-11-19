# :py — notes for later

Snapshot from 2026-11-19: sections 1–5 done, heading for the first release, 0.1.0. This is a working list toward a "production grade" 1.0, most important first. Tick items off or delete them as they're done.

## State

- About 8,900 lines in `src/`, 151 tests, 60% line+branch coverage (floor 58%). CI: ruff, mypy, Ubuntu and macOS on Python 3.10–3.14, a job with IPython installed, a non-blocking 3.15 job, a weekly run against the newest dependencies.
- Docs are strong: features, a generated magic reference, configuration, IPython compatibility, releasing.
- Install is GitHub only (`install.sh`, pipx when available). PyPI was dropped on purpose.

## 1. Test setup (small, do first)

- [x] Add `pythonpath = ["src"]` to `[tool.pytest.ini_options]`. Without an editable install, pytest silently imports an old :py from site-packages (that gave 10 false failures locally).
- [x] `tests/test_compat.py::test_stand_in_ipython_modules` fails when the real IPython is installed. That's a documented limit, so skip it in that case.
- [x] Add a CI job with IPython installed. It's a very common user setup and nothing tests it today.

## 2. Code quality

- [x] Replace pyflakes with **ruff** (lint and format). Add **mypy or pyright**: about 75% of functions are already annotated. Add `py.typed`.
- [x] Measure coverage with `pytest-cov` and set a minimum threshold. Thinnest areas: `ui.py` (779 lines), `shell.py` (760), `magics/history.py` (541) and the keybinding/layout paths, which is where regressions happened (see 0.2.4).
- [x] 37 broad `except` handlers, about 11 of them `except Exception: pass` (`display.py`, `signature.py`, `ui.py`, `inputhooks.py`). Keep the ones a REPL needs, but log them in debug mode.
- [x] Add Python 3.14 to CI and the classifiers. Add a non-blocking 3.15 pre-release job.

## 3. Diagnosability

- [x] No logging today. Add `:py --debug` / `PY_TERM_LOG`, writing to a log file in the data directory.
- [x] Crash handler: an internal error prints one line plus the path to a crash report (versions, `$TERM`, traceback) and doesn't kill the session.
- [x] `:py --doctor`: Python and dependency versions, terminal capabilities (modified keys, truecolor), config path, whether IPython is present.

## 4. Releases and distribution

- [x] The version is set in two places (`pyproject.toml` and `__init__.py`). Use one source (`importlib.metadata` or setuptools-scm).
- [x] Tag-triggered release workflow: test, build, attach the wheel and sdist, fill the notes from CHANGELOG. Optionally add sigstore attestations.
- [x] `install.sh` installs `main` by default. Default to the latest tagged release instead, and publish checksums.
- [x] Dependencies have no upper bounds. Add a weekly CI job against the newest dependencies, and Dependabot for Actions.
- [x] Remove `twine` from the dev extras (PyPI is gone). Document `pipx install git+…` and `uv tool install git+…` in the README.

## 5. Project hygiene

- [x] Add CONTRIBUTING.md, SECURITY.md, issue templates (the bug template asks for `--doctor` output), a PR template and pre-commit hooks.
- [x] Stability policy before 1.0: which config keys, CLI flags and magics count as breaking changes.

## Left over from 1–5

- [ ] Raise the coverage floor as tests land (`fail_under` in pyproject.toml). Thinnest: `ui.py`, `inputhooks.py`, `magics/core.py`, `magics/namespace.py`, `display.py`.
- [ ] Cut 0.1.0 with the release workflow. Until it exists, the installer falls back to `main`.
- [ ] Turn on private vulnerability reporting in the GitHub repo settings (SECURITY.md points to it).

## 6. Product gaps (from README "Known limits")

- [x] Inline images through the kitty or iTerm2 graphics protocols (`%matplotlib inline`, `Image`, `SVG`). Sixel (foot, Windows Terminal, xterm) is still open.
- [ ] A PTY for `!cmd` so interactive programs (vim, less) work.
- [ ] Better coexistence when the real IPython is installed.
- [ ] Decide on Windows support, yes or no, and say so.

## Shared with the family (:sh, :js, :sql, :http, :docs)

- The pitch palette lives in a separate copy in each repo. Consider one generator or a shared spec so the copies don't drift.
- The same release, installer, logging and `--doctor` work applies to all of them. Done in :py: copy `diagnostics.py`, `.github/workflows/release.yml`, `scripts/release_notes.py`, the checksum part of `install.sh`, the templates, CONTRIBUTING, SECURITY and docs/stability.md.
