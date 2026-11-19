"""`!cmd` in a pseudo-terminal: output, exit status, keys, Ctrl+C, width and full-screen programs."""

import os
import sys
import threading
import time

import pytest

from py_term import pty_run

pytestmark = pytest.mark.skipif(os.name != "posix", reason="pseudo-terminals are POSIX only")


@pytest.fixture
def terminal():
    """A fake terminal for :py: keys are written to `keys`, :py reads them from `fd`."""
    import pty

    from py_term.pty_run import _set_size

    master, slave = pty.openpty()
    _set_size(slave, 24, 80)

    class Terminal:
        fd = slave

        def keys(self, data, delay=0.0):
            if delay:
                threading.Timer(delay, os.write, (master, data)).start()
            else:
                os.write(master, data)

        def run(self, cmd, indent=0):
            self.text, self.raw = [], []
            code = pty_run.run(cmd, self.text.append, self.raw.append, indent=indent, stdin_fd=slave, term_fd=slave)
            return code, "".join(self.text), b"".join(self.raw)

    yield Terminal()
    os.close(master)
    os.close(slave)


def test_output_and_exit_status(terminal):
    code, text, raw = terminal.run("printf 'one\\ntwo\\n'; exit 3")
    assert code == 3
    assert text.replace("\r\n", "\n") == "one\ntwo\n"
    assert raw == b""


def test_command_sees_a_terminal(terminal):
    _, text, _ = terminal.run("test -t 0 && test -t 1 && test -t 2 && echo yes-a-tty")
    assert "yes-a-tty" in text


def test_width_leaves_room_for_the_indent(terminal):
    _, text, _ = terminal.run("stty size", indent=5)
    assert text.split() == ["24", "75"]


def test_keys_reach_the_command(terminal):
    terminal.keys(b"hello\r")
    _, text, _ = terminal.run("read answer; echo got:$answer")
    assert "got:hello" in text


def test_ctrl_c_stops_the_command_not_py(terminal):
    terminal.keys(b"\x03", delay=0.3)
    start = time.monotonic()
    code, _, _ = terminal.run("sleep 10")
    assert time.monotonic() - start < 5
    assert code != 0


def test_full_screen_output_goes_to_the_terminal_untouched(terminal):
    cmd = "printf 'before\\n\\033[?1049hFULL SCREEN\\033[?1049lafter\\n'"
    _, text, raw = terminal.run(cmd, indent=5)
    assert "before" in text and "after" in text and "FULL" not in text
    assert raw == b"\x1b[?1049hFULL SCREEN\x1b[?1049l"


def test_full_screen_programs_get_the_whole_width(terminal):
    _, _, raw = terminal.run("printf '\\033[?1049h'; stty size; printf '\\033[?1049l'", indent=5)
    assert b"24 80" in raw


def test_terminal_is_restored_if_the_command_dies_in_full_screen(terminal):
    _, _, raw = terminal.run("printf '\\033[?1049hstuck'", indent=5)
    assert raw.endswith(b"\x1b[?1049l\x1b[?25h")


def test_terminal_mode_is_restored(terminal):
    import termios

    before = termios.tcgetattr(terminal.fd)
    terminal.run("true")
    assert termios.tcgetattr(terminal.fd) == before


def test_utf8_split_across_reads(terminal):
    _, text, _ = terminal.run("printf '\\342\\234'; sleep 0.1; printf '\\223 done\\n'")
    assert "✓ done" in text


@pytest.mark.parametrize(
    ("chunks", "expected"),
    [
        ([b"plain"], [(False, b"plain")]),
        ([b"a\x1b[?1049hB\x1b[?1049lc"], [(False, b"a"), (True, b"\x1b[?1049h"), (True, b"B"), (True, b"\x1b[?1049l"), (False, b"c")]),
        ([b"a\x1b[?10", b"49hB"], [(False, b"a"), (True, b"\x1b[?1049h"), (True, b"B")]),  # marker split across reads
        ([b"x\x1b[?47h"], [(False, b"x"), (True, b"\x1b[?47h")]),
    ],
)
def test_alt_screen_splitter(chunks, expected):
    splitter = pty_run.AltScreenSplitter()
    runs = [run for chunk in chunks for run in splitter.feed(chunk)] + splitter.flush()
    assert runs == expected


def test_interrupting_py_stops_the_command(terminal, monkeypatch):
    import subprocess

    started = []
    real_popen = subprocess.Popen

    def popen(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        started.append(proc)
        return proc

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(pty_run.select, "select", interrupted)
    with pytest.raises(KeyboardInterrupt):
        terminal.run("sleep 30")
    assert started and started[0].poll() is not None


def test_not_available_without_a_terminal(tmp_path):
    with open(tmp_path / "f", "w") as f:
        assert not pty_run.available(stdin=f, stdout=sys.__stdout__)


def test_capture_still_uses_a_pipe(shell):
    shell.run_cell("x = !echo captured")
    assert list(shell.ns["x"]) == ["captured"]
