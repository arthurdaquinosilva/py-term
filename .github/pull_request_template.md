## What and why

<!-- What does this change, and what problem does it solve? Link the issue if there is one. -->

## Checklist

- [ ] Tests cover the change (a fix comes with a test that fails without it)
- [ ] `ruff check .`, `ruff format --check .`, `mypy` and `pytest` pass
- [ ] `CHANGELOG.md` has a line under `## Unreleased` if users will notice
- [ ] Docs updated (`docs/`), and `scripts/gen_magic_docs.py` re-run if magics changed
- [ ] No breaking change to settings, flags or magics, or it follows [docs/stability.md](../docs/stability.md)
