# Releasing

:py is published only on GitHub, not on PyPI. Each release carries the wheel, the sdist, a `SHA256SUMS` file and build provenance attestations. `install.sh` installs the latest release's wheel after checking it against `SHA256SUMS`.

## Cutting a release

1. Set `__version__` in `src/py_term/__init__.py`. It's the only place the version lives; `pyproject.toml` reads it from there.
2. In `CHANGELOG.md`, rename `## Unreleased` to `## X.Y.Z` (and start a new empty `## Unreleased` above it).
3. Check the notes and the build locally:

   ```sh
   python scripts/release_notes.py vX.Y.Z
   rm -rf dist && python -m build
   ```

4. Commit, push to `main`, then tag and push the tag:

   ```sh
   git tag vX.Y.Z && git push origin vX.Y.Z
   ```

The `release` workflow (`.github/workflows/release.yml`) then checks that the tag matches `__version__` and that CHANGELOG has a section for it, runs lint, types and tests, builds, smoke-tests the wheel, writes `SHA256SUMS`, attests the build and creates the GitHub release with the CHANGELOG section as its notes.

Anyone can verify a downloaded artifact:

```sh
sha256sum -c SHA256SUMS --ignore-missing
gh attestation verify py_term-X.Y.Z-py3-none-any.whl --repo arthurdaquinosilva/py-term
```

## The installer

`install.sh` is served straight from `main` and looks up the latest release itself, so it needs no change per release. `PY_TERM_VERSION=X.Y.Z` picks a release and `PY_TERM_VERSION=main` the development version. Releases with no `SHA256SUMS` fall back to the tag's source archive. Keep the script working on plain `sh` (dash): `tests/test_install_script.py` runs it through `sh -n` and shellcheck, and checks checksum verification against a fake `curl`.

## Dependencies

Runtime dependencies have lower bounds only, so :py keeps installing next to other tools. Instead of upper bounds, the `tests` workflow also runs every Monday against the newest releases of everything, and Dependabot keeps the GitHub Actions current.
