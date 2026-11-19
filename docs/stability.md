# Stability policy

From 1.0 on, :py follows [semantic versioning](https://semver.org/) for the things people put in config files, scripts and muscle memory. This page says what counts.

## The public surface

A change to any of these is **breaking** and only happens in a major release, after a deprecation period:

- **Settings**: every key documented in [configuration.md](configuration.md), its type and its accepted values. Changing a default is not breaking, but it goes in the changelog.
- **Command line**: the `:py` and `py-term` commands, their flags (`-c`, `-m`, `-i`, `--profile`, `--theme`, `--vi`, `--no-startup`, `--debug`, `--doctor`, `--version`) and their exit statuses (0 success, 1 the code failed, 70 internal error, 130 interrupted).
- **Environment variables**: `PY_TERM_THEME`, `PY_TERM_PROFILE`, `PY_TERM_LOG` and the installer's `PY_TERM_VERSION`, `PY_TERM_NO_PIPX`, `PY_TERM_INSTALL_DIR`.
- **Magics**: names and documented options of everything in [magics.md](magics.md).
- **Files**: where config, startup files, history and `%store` data live, and the ability to read history databases written by earlier versions.
- **IPython compatibility**: the parts of `get_ipython()` and the stand-in `IPython.*` modules listed in [ipython-compatibility.md](ipython-compatibility.md).
- **Theme names**: removing a theme is breaking; changing its colors is not.

## Not covered

These can change in any release: the look of the UI (layout details, glyphs, colors, spacing), wording of messages, the format of the debug log, crash reports and `--doctor` output, anything undocumented, and Python modules inside `py_term` (it's an application, not a library).

## Deprecating

1. The old name keeps working and prints a one-line warning, at most once per session, naming the replacement. Config warnings also show in `:py --doctor`.
2. The changelog says what's deprecated and in which release it goes away.
3. Removal waits at least one minor release and three months, whichever is longer, and happens only in a major release.

Before 1.0, minor releases (0.x) may still break things, but they follow the same deprecation steps whenever it's practical.
