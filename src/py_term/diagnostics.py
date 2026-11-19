"""Diagnostics: the debug log, crash reports for internal errors, and `:py --doctor`.

Logging is off unless `--debug` is passed or `PY_TERM_LOG` is set (to a level such as `debug` or
`info`; `1` means debug). The log goes to `py-term.log` in the data directory and rotates at 1 MB.
"""

from __future__ import annotations

import datetime as dt
import logging
import logging.handlers
import os
import platform
import shutil
import sys
import traceback
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

if TYPE_CHECKING:
    from py_term.config import Profile

log = logging.getLogger("py_term")
log.addHandler(logging.NullHandler())

LOG_FILE_NAME = "py-term.log"
_LEVELS = {"1": logging.DEBUG, "true": logging.DEBUG, "yes": logging.DEBUG, "on": logging.DEBUG}

CORE_DEPENDENCIES = ("prompt_toolkit", "rich", "jedi", "pygments", "tomli")
OPTIONAL_PACKAGES = ("IPython", "numpy", "pandas", "polars", "matplotlib", "trio", "curio", "line_profiler")


def log_level(debug: bool = False, env: str | None = None) -> int | None:
    """The logging level asked for by `--debug` or `PY_TERM_LOG`, or None when logging stays off."""
    if debug:
        return logging.DEBUG
    value = (env if env is not None else os.environ.get("PY_TERM_LOG", "")).strip().lower()
    if not value or value in ("0", "false", "no", "off"):
        return None
    if value in _LEVELS:
        return _LEVELS[value]
    level = logging.getLevelName(value.upper())
    return level if isinstance(level, int) else logging.DEBUG


def log_file(profile: Profile | None) -> Path | None:
    return profile.data_dir / LOG_FILE_NAME if profile is not None else None


def setup_logging(profile: Profile | None, level: int | None) -> Path | None:
    """Send the `py_term` logger to the log file. Returns its path, or None when logging is off."""
    path = log_file(profile)
    if level is None or path is None:
        return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    except OSError:
        return None
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(level)
    log.info(":py %s starting (Python %s, %s)", _version(), platform.python_version(), sys.executable)
    return path


def debug_enabled() -> bool:
    return log.isEnabledFor(logging.DEBUG)


# ---------------------------------------------------------------- crash reports


def crash_dir(profile: Profile | None) -> Path:
    if profile is not None:
        return profile.data_dir / "crashes"
    import tempfile

    return Path(tempfile.gettempdir()) / "py-term-crashes"


def write_crash_report(exc: BaseException, profile: Profile | None, where: str = "") -> Path | None:
    """Write versions, terminal facts and the traceback to a file. Returns its path, or None if writing failed."""
    now = dt.datetime.now()
    directory = crash_dir(profile)
    path = directory / f"crash-{now:%Y%m%d-%H%M%S}-{os.getpid()}.txt"
    lines = [
        f":py crash report — {now:%Y-%m-%d %H:%M:%S}",
        f"where: {where or 'unknown'}",
        "",
        *environment_lines(),
        "",
        "traceback:",
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip(),
        "",
    ]
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        return None
    _prune(directory, keep=20)
    return path


def _prune(directory: Path, keep: int) -> None:
    try:
        reports = sorted(directory.glob("crash-*.txt"))
        for old in reports[:-keep]:
            old.unlink()
    except OSError:
        pass


def internal_error_message(exc: BaseException, report: Path | None) -> str:
    detail = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    where = f" · report: {report}" if report else ""
    return f"internal error in :py ({detail}){where}"


# ---------------------------------------------------------------- environment facts


def _version() -> str:
    from py_term import __version__

    return __version__


def _package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def terminal_facts(env: dict[str, str] | None = None, stream: TextIO | None = None) -> dict[str, Any]:
    env = dict(os.environ) if env is None else env
    stream = stream or sys.__stdout__ or sys.stdout
    term, program = env.get("TERM", ""), env.get("TERM_PROGRAM", "")
    colorterm = env.get("COLORTERM", "").lower()
    truecolor = colorterm in ("truecolor", "24bit") or any(
        t in term for t in ("kitty", "ghostty", "wezterm", "alacritty", "foot", "direct")
    )
    # Terminals known to honour xterm's modifyOtherKeys, which :py uses to tell Shift+Enter from Enter.
    # Most terminals report TERM=xterm-256color, so this is a best guess from TERM_PROGRAM and friends.
    haystack = f"{term} {program}".lower()
    if env.get("TMUX"):
        modified_keys = "inside tmux: needs `set -g extended-keys on`"
    elif env.get("XTERM_VERSION") or any(k in haystack for k in ("kitty", "wezterm", "ghostty", "foot", "iterm")):
        modified_keys = "supported"
    else:
        modified_keys = "unknown (Shift+Enter may act like Enter; Alt+Enter always inserts a newline)"
    try:
        tty = stream.isatty()
    except (AttributeError, ValueError):
        tty = False
    size = shutil.get_terminal_size(fallback=(0, 0))
    return {
        "TERM": term or "(unset)",
        "TERM_PROGRAM": program or "(unset)",
        "COLORTERM": env.get("COLORTERM") or "(unset)",
        "tmux": bool(env.get("TMUX")),
        "tty": tty,
        "size": f"{size.columns}x{size.lines}",
        "truecolor": truecolor,
        "modified keys (Shift+Enter)": modified_keys,
        "encoding": getattr(stream, "encoding", None) or "unknown",
    }


def environment_lines() -> list[str]:
    """Versions and terminal facts, as plain `key: value` lines (shared by crash reports and the doctor)."""
    lines = [
        f":py: {_version()} ({Path(__file__).parent})",
        f"python: {platform.python_version()} {platform.python_implementation()} ({sys.executable})",
        f"platform: {platform.platform()}",
    ]
    for name in CORE_DEPENDENCIES:
        if (version := _package_version(name)) is not None:
            lines.append(f"{name}: {version}")
    lines += [f"{key}: {value}" for key, value in terminal_facts().items()]
    return lines


def doctor(profile: Profile | None, warnings: list[str], log_path: Path | None = None, out: TextIO | None = None) -> int:
    """Print what's useful in a bug report. Returns a process exit status (1 if something looks broken)."""
    out = out or sys.stdout
    problems: list[str] = []

    def section(title: str) -> None:
        out.write(f"\n{title}\n")

    def row(key: str, value: object) -> None:
        out.write(f"  {key + ':':<30} {value}\n")

    out.write(f":py {_version()} — doctor\n")
    section("python")
    row("version", f"{platform.python_version()} ({platform.python_implementation()})")
    row("executable", sys.executable)
    row("platform", platform.platform())
    row(":py package", Path(__file__).parent)

    section("dependencies")
    for name in CORE_DEPENDENCIES:
        version = _package_version(name)
        if version is None and name == "tomli" and sys.version_info >= (3, 11):
            continue
        if version is None:
            problems.append(f"{name} is not installed")
        row(name, version or "MISSING")
    section("optional")
    for name in OPTIONAL_PACKAGES:
        row(name, _package_version(name.lower() if name != "IPython" else "ipython") or "-")

    section("terminal")
    facts = terminal_facts()
    for key, value in facts.items():
        row(key, value)
    if not facts["tty"]:
        out.write("  (stdout is not a terminal here, e.g. piped: the facts above may not match your interactive session)\n")

    section("files")
    if profile is not None:
        row("profile", profile.name)
        row("config", f"{profile.config_file} ({'exists' if profile.config_file.is_file() else 'not created'})")
        row("startup dir", profile.startup_dir)
        history = profile.history_db
        row("history", f"{history} ({_size(history)})" if history.exists() else f"{history} (not created)")
        log = log_path or log_file(profile)
        row("log", f"{log} ({'exists' if log and log.exists() else 'off · enable with --debug or PY_TERM_LOG=debug'})")
        reports = sorted(crash_dir(profile).glob("crash-*.txt")) if crash_dir(profile).is_dir() else []
        row("crash reports", f"{len(reports)} in {crash_dir(profile)}" if reports else "none")

    from py_term.ipython import real_ipython_available

    section("ipython")
    row("real IPython installed", "yes (stand-in IPython modules are not used)" if real_ipython_available() else "no (stand-ins are used)")

    if warnings:
        section("config warnings")
        for w in warnings:
            out.write(f"  ! {w}\n")
            problems.append(f"config: {w}")

    out.write("\n" + ("\n".join(f"✗ {p}" for p in problems) if problems else "✓ no problems found") + "\n")
    return 1 if problems else 0


def _size(path: Path) -> str:
    try:
        n = float(path.stat().st_size)
    except OSError:
        return "unreadable"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return ""
