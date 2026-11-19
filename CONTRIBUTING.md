# Contributing to :py

Thanks for helping. Bug reports, fixes and small features are all welcome; for anything big, open an issue first so we can agree on the shape before you spend time on it.

## Setting up

```sh
git clone https://github.com/arthurdaquinosilva/py-term.git && cd py-term
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pre-commit install    # optional: run ruff on every commit
```

## Before you open a pull request

```sh
ruff check . && ruff format --check .   # lint and formatting
mypy                                    # types
python -m pytest --cov                  # tests, with the coverage floor from pyproject.toml
python scripts/gen_magic_docs.py        # if you added or changed a magic
```

CI runs the same checks on Linux and macOS, Python 3.10–3.14, with and without the real IPython installed.

- **Tests**: every fix comes with a test that fails without it. Keybinding and layout changes are where regressions have happened; `tests/test_keys.py` drives the real prompt in a pseudo-terminal.
- **Changelog**: add a line under `## Unreleased` in `CHANGELOG.md` for anything a user would notice. Write it for users, not reviewers.
- **Docs**: features belong in `docs/features.md`, settings in `docs/configuration.md`. `docs/magics.md` is generated.
- **Compatibility**: read the [stability policy](docs/stability.md) before renaming or removing a setting, flag or magic.
- **Style**: `ruff format` decides. Keep comments about *why*, not *what*.

## Reporting bugs

Use the bug report form and include the output of `:py --doctor`. If :py printed `internal error in :py`, attach the crash report it points to. It holds versions, terminal facts and a traceback; the traceback can quote lines of your code, so look it over before posting.
