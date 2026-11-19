"""Diagnostics: debug log levels, crash reports, internal-error handling and `--doctor`."""

import io
import logging
import sys

import pytest

from py_term import diagnostics


@pytest.fixture
def xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "c"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "d"))
    monkeypatch.delenv("PY_TERM_LOG", raising=False)
    yield tmp_path / "d" / "py-term"
    sys.argv = ["pytest"]
    for handler in list(diagnostics.log.handlers):
        if not isinstance(handler, logging.NullHandler):
            diagnostics.log.removeHandler(handler)
            handler.close()
    diagnostics.log.setLevel(logging.NOTSET)


@pytest.mark.parametrize(
    ("env", "level"),
    [
        ("", None),
        ("0", None),
        ("off", None),
        ("1", logging.DEBUG),
        ("debug", logging.DEBUG),
        ("INFO", logging.INFO),
        ("nonsense", logging.DEBUG),
    ],
)
def test_log_level_from_env(env, level):
    assert diagnostics.log_level(env=env) == level


def test_debug_flag_wins():
    assert diagnostics.log_level(debug=True, env="off") == logging.DEBUG


def test_setup_logging_writes_to_the_data_dir(profile):
    path = diagnostics.setup_logging(profile, logging.DEBUG)
    try:
        assert path == profile.data_dir / "py-term.log"
        diagnostics.log.debug("hello from the test")
        for h in diagnostics.log.handlers:
            h.flush()
        assert "hello from the test" in path.read_text()
    finally:
        for h in list(diagnostics.log.handlers):
            if not isinstance(h, logging.NullHandler):
                diagnostics.log.removeHandler(h)
                h.close()
        diagnostics.log.setLevel(logging.NOTSET)


def test_logging_off_by_default(profile):
    assert diagnostics.setup_logging(profile, None) is None
    assert not (profile.data_dir / "py-term.log").exists()


def test_crash_report_has_versions_and_traceback(profile):
    try:
        raise RuntimeError("boom")
    except RuntimeError as e:
        report = diagnostics.write_crash_report(e, profile, where="a test")
    assert report is not None and report.parent == profile.data_dir / "crashes"
    text = report.read_text()
    assert "where: a test" in text
    assert "python:" in text and "prompt_toolkit:" in text and "TERM:" in text
    assert "RuntimeError: boom" in text and "Traceback" in text


def test_crash_reports_are_pruned(profile):
    directory = diagnostics.crash_dir(profile)
    directory.mkdir(parents=True)
    for i in range(25):
        (directory / f"crash-20260101-0000{i:02d}-1.txt").write_text("old")
    diagnostics.write_crash_report(ValueError("x"), profile)
    assert len(list(directory.glob("crash-*.txt"))) == 20


def test_internal_error_message():
    msg = diagnostics.internal_error_message(KeyError("k"), None)
    assert msg == "internal error in :py (KeyError: 'k')"


def test_doctor_lists_versions_terminal_and_paths(profile):
    out = io.StringIO()
    status = diagnostics.doctor(profile, [], out=out)
    text = out.getvalue()
    assert status == 0
    for needle in (
        "prompt_toolkit",
        "rich",
        "jedi",
        "TERM:",
        "truecolor",
        str(profile.config_file),
        "real IPython installed",
        "no problems found",
    ):
        assert needle in text


def test_doctor_reports_config_warnings(profile):
    out = io.StringIO()
    assert diagnostics.doctor(profile, ["unknown setting 'colour'"], out=out) == 1
    assert "unknown setting 'colour'" in out.getvalue()


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"TERM": "xterm-kitty"}, "supported"),
        ({"TERM": "xterm-256color", "TERM_PROGRAM": "iTerm.app"}, "supported"),
        ({"TERM": "tmux-256color", "TMUX": "/tmp/tmux-1/default,1,0"}, "inside tmux"),
        ({"TERM": "xterm-256color"}, "unknown"),
    ],
)
def test_terminal_facts_modified_keys(env, expected):
    facts = diagnostics.terminal_facts(env=env, stream=io.StringIO())
    assert facts["modified keys (Shift+Enter)"].startswith(expected)
    assert facts["tty"] is False


def test_cli_doctor(xdg, capsys):
    from py_term import cli

    assert cli.main(["--doctor"]) == 0
    assert ":py" in capsys.readouterr().out


def test_cli_debug_writes_log(xdg):
    from py_term import cli

    assert cli.main(["--debug", "-c", "1"]) == 0
    assert "starting" in (xdg / "py-term.log").read_text()


def test_cli_internal_error_writes_a_report_and_exits_70(xdg, monkeypatch, capsys):
    from py_term import cli
    from py_term.shell import Shell

    def broken(*args, **kwargs):
        raise RuntimeError("startup exploded")

    monkeypatch.setattr(Shell, "startup", broken)
    assert cli.main(["-c", "1"]) == 70
    err = capsys.readouterr().err
    assert "internal error in :py (RuntimeError: startup exploded)" in err
    reports = list((xdg / "crashes").glob("crash-*.txt"))
    assert len(reports) == 1 and "startup exploded" in reports[0].read_text()


def test_user_errors_are_not_internal_errors(xdg, capsys):
    from py_term import cli

    assert cli.main(["-c", "1/0"]) == 1
    assert not (xdg / "crashes").exists()


def test_repl_survives_an_internal_error(shell, monkeypatch):
    from py_term.ui import Repl

    repl = Repl.__new__(Repl)  # skip the prompt_toolkit app: only the loop is under test
    repl.shell = shell
    repl.banner = lambda: None
    inputs = iter(["x = 1", "boom", "x += 1", None])

    def read():
        text = next(inputs)
        if text == "boom":
            raise RuntimeError("key binding bug")
        return text

    repl.read = read
    assert repl.run() == 0
    assert shell.ns["x"] == 2
    assert len(list(diagnostics.crash_dir(shell.profile).glob("crash-*.txt"))) == 1


def test_repl_gives_up_after_repeated_internal_errors(shell):
    from py_term.ui import Repl

    repl = Repl.__new__(Repl)
    repl.shell = shell
    repl.banner = lambda: None

    def read():
        raise RuntimeError("always broken")

    repl.read = read
    assert repl.run() == 70


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_private_data_is_owner_only(profile):
    import stat

    from py_term.history import HistoryManager

    def mode(p):
        return stat.S_IMODE(p.stat().st_mode)

    profile.ensure()
    assert mode(profile.data_dir) == 0o700
    history = HistoryManager(profile.history_db)
    history.db.close()
    assert mode(profile.history_db) == 0o600
    report = diagnostics.write_crash_report(ValueError("x"), profile)
    assert report is not None and mode(report) == 0o600
    assert mode(report.parent) == 0o700
    log = diagnostics.setup_logging(profile, logging.DEBUG)
    try:
        assert log is not None and mode(log) == 0o600
    finally:
        for h in list(diagnostics.log.handlers):
            if not isinstance(h, logging.NullHandler):
                diagnostics.log.removeHandler(h)
                h.close()
        diagnostics.log.setLevel(logging.NOTSET)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_named_profile_makes_the_base_folder_private(tmp_path, monkeypatch):
    import stat

    from py_term.config import load_profile

    (tmp_path / "share").mkdir(mode=0o755)
    (tmp_path / "share").chmod(0o755)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    profile = load_profile("work")
    for d in (profile.data_dir, tmp_path / "share" / "py-term"):
        assert stat.S_IMODE(d.stat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path / "share").stat().st_mode) == 0o755  # XDG_DATA_HOME itself is left alone
