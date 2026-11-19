"""Command-line entry point."""

from __future__ import annotations

import argparse
import shlex
import sys
from typing import TYPE_CHECKING

from py_term import __version__
from py_term.theme import PALETTES

if TYPE_CHECKING:
    from py_term.config import Profile


_profile: Profile | None = None  # set once loaded, so the crash handler can put reports next to the history


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=":py", description="A modern interactive Python shell.")
    parser.add_argument("file", nargs="?", help="python file to run")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="arguments passed to the file")
    parser.add_argument("-c", dest="command", help="run a command")
    parser.add_argument("-m", dest="module", help="run a library module as a script")
    parser.add_argument("-i", action="store_true", help="stay interactive after running a file, module or command")
    parser.add_argument("--profile", help="use a named profile (separate config, startup files and history)")
    parser.add_argument("--theme", choices=list(PALETTES), help="color theme")
    parser.add_argument("--vi", action="store_true", help="vi key bindings")
    parser.add_argument("--no-startup", action="store_true", help="skip startup files, exec_lines and extensions")
    parser.add_argument("--debug", action="store_true", help="write a debug log to the data directory (also: PY_TERM_LOG=debug)")
    parser.add_argument("--doctor", action="store_true", help="print versions, terminal facts and paths for a bug report, then exit")
    parser.add_argument("--version", action="version", version=f":py {__version__}")
    opts = parser.parse_args(argv)
    try:
        return _main(opts)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        # Anything reaching here is a bug in :py, not in the user's code (which runs inside run_cell).
        from py_term import diagnostics

        diagnostics.log.exception("fatal internal error")
        report = diagnostics.write_crash_report(e, _profile, where="startup or batch run")
        sys.stderr.write(f":py: {diagnostics.internal_error_message(e, report)}\n")
        return 70  # EX_SOFTWARE


def _main(opts: argparse.Namespace) -> int:
    global _profile
    # Like `python`: code in the session sees an empty argv, not :py's own options.
    # (%run sets sys.argv for the scripts it runs.)
    sys.argv = ["-c"] if opts.command is not None else [""]

    from py_term import diagnostics
    from py_term.config import load_profile, load_settings
    from py_term.shell import Shell

    profile = _profile = load_profile(opts.profile)
    log_path = diagnostics.setup_logging(profile, diagnostics.log_level(opts.debug))
    settings, warnings = load_settings(profile)
    for w in warnings:
        diagnostics.log.warning("config: %s", w)
    if opts.doctor:
        return diagnostics.doctor(profile, warnings, log_path)
    if opts.theme:
        settings.theme = opts.theme
    if opts.vi:
        settings.editing_mode = "vi"
    if opts.no_startup:
        settings.exec_lines, settings.exec_files, settings.extensions = [], [], []

    shell = Shell(settings=settings, profile=profile)
    try:
        status = _run_batch(shell, opts, warnings)
    except SystemExit as e:
        status = e.code if isinstance(e.code, int) else 0
    if status is not None:
        shell.close()
        return status

    from py_term.ui import Repl

    return Repl(shell).run()


def _run_batch(shell, opts: argparse.Namespace, warnings: list[str]) -> int | None:
    """Run startup and any -c/-m/file/stdin work. Returns an exit status, or None to go interactive."""
    shell.startup(warnings, run_files=not opts.no_startup)
    ran = False
    if opts.command is not None:
        shell.run_cell(opts.command)
        ran = True
    if opts.module:
        shell.run_cell(f"%run -m {shlex.join([opts.module, *([opts.file] if opts.file else []), *opts.args])}")
        ran = True
    elif opts.file:
        shell.run_cell(f"%run {shlex.join([opts.file, *opts.args])}")
        ran = True
    if ran and not opts.i:
        if shell.exit_status is not None:
            return shell.exit_status
        return 0 if shell.last_ok else 1
    if not sys.stdin.isatty():
        shell.run_cell(sys.stdin.read())
        return 0 if shell.last_ok else 1
    return None
