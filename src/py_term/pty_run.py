"""Run `!cmd` in a pseudo-terminal so interactive programs (vim, less, htop, ssh, sudo, git's pager) work.

The command gets its own pty as its controlling terminal. Keys typed while it runs are passed to it
unchanged, including Ctrl+C and Ctrl+Z, which the pty turns into signals for the command, not for :py.

Ordinary output is written through the cell's output writer, so it hangs under the `⎿` like any
other output; the pty is made narrower by that indent so the command wraps its own lines to fit.
When the command switches to the terminal's alternate screen (full-screen programs do), its output
goes to the terminal untouched and the pty gets the full window size until it switches back.
"""

from __future__ import annotations

import codecs
import os
import re
import select
import signal
import struct
import subprocess
import sys
from collections.abc import Callable
from typing import Any, TextIO

from py_term.diagnostics import log

# enter / leave the alternate screen (xterm's three historical spellings)
_ALT_ENTER = (b"\x1b[?1049h", b"\x1b[?1047h", b"\x1b[?47h")
_ALT_LEAVE = (b"\x1b[?1049l", b"\x1b[?1047l", b"\x1b[?47l")
_MARKERS = re.compile(b"|".join(re.escape(m) for m in _ALT_ENTER + _ALT_LEAVE))
_LONGEST = max(len(m) for m in _ALT_ENTER + _ALT_LEAVE)
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def available(stdin: TextIO | None = None, stdout: TextIO | None = None) -> bool:
    """A pty only makes sense when :py itself talks to a terminal on both ends (and on POSIX)."""
    if os.name != "posix":
        return False
    try:
        import pty  # noqa: F401
        import termios  # noqa: F401
    except ImportError:
        return False
    stdin = stdin or sys.__stdin__
    stdout = stdout or sys.__stdout__
    try:
        return bool(stdin and stdout and stdin.isatty() and stdout.isatty())
    except (AttributeError, ValueError):
        return False


def visible_width(prefix: str) -> int:
    return len(_ANSI.sub("", prefix))


class AltScreenSplitter:
    """Splits a byte stream into (alt_screen, bytes) runs, following alternate-screen switches.

    A marker split across two reads is held back until the next read completes it."""

    def __init__(self) -> None:
        self.alt = False
        self._carry = b""

    def feed(self, data: bytes) -> list[tuple[bool, bytes]]:
        data = self._carry + data
        self._carry = b""
        runs: list[tuple[bool, bytes]] = []
        pos = 0
        for m in _MARKERS.finditer(data):
            if m.start() > pos:
                runs.append((self.alt, data[pos : m.start()]))
            marker = m.group()
            entering = marker in _ALT_ENTER
            # the switch itself belongs to the full-screen side: it must reach the terminal raw
            runs.append((True, marker))
            self.alt = entering
            pos = m.end()
        rest = data[pos:]
        # hold back a possible start of a marker at the very end
        keep = 0
        for n in range(min(len(rest), _LONGEST - 1), 0, -1):
            tail = rest[-n:]
            if any(m.startswith(tail) for m in _ALT_ENTER + _ALT_LEAVE):
                keep = n
                break
        if keep:
            self._carry = rest[-keep:]
            rest = rest[:-keep]
        if rest:
            runs.append((self.alt, rest))
        return runs

    def flush(self) -> list[tuple[bool, bytes]]:
        carry, self._carry = self._carry, b""
        return [(self.alt, carry)] if carry else []


def _get_size(fd: int) -> tuple[int, int]:
    import fcntl
    import termios

    try:
        rows, cols, _, _ = struct.unpack("HHHH", fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0" * 8))
        if rows and cols:
            return rows, cols
    except OSError:
        pass
    return 24, 80


def _set_size(fd: int, rows: int, cols: int) -> None:
    import fcntl
    import termios

    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, max(1, cols), 0, 0))
    except OSError:
        pass


def _passthrough_mode(fd: int) -> Any:
    """Keys go to the command byte for byte (no line editing, no echo, no signals for :py), while
    output processing stays on so :py's own newlines still return the carriage."""
    import termios

    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[0] &= ~(termios.IXON | termios.ICRNL | termios.INLCR | termios.IGNCR | termios.ISTRIP)
    new[3] &= ~(termios.ECHO | termios.ICANON | termios.ISIG | termios.IEXTEN)
    new[6][termios.VMIN] = 1
    new[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, new)
    return old


def _child_setup() -> None:
    """In the child, after setsid(): make the pty (already on fd 0) the controlling terminal."""
    import fcntl
    import termios

    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=0.5)
            return
        except subprocess.TimeoutExpired:
            continue


def run(
    cmd: str | list[str],
    write: Callable[[str], Any],
    write_raw: Callable[[bytes], Any],
    indent: int = 0,
    stdin_fd: int | None = None,
    term_fd: int | None = None,
    env: dict[str, str] | None = None,
) -> int:
    """Run `cmd` in a pty and return its exit status.

    `write` takes ordinary output as text (the cell's writer, which adds the indent), `write_raw`
    takes full-screen output as bytes, straight to the terminal. `stdin_fd` is the terminal keys are read from and `term_fd` the one
    whose size is mirrored (both default to :py's own)."""
    import pty
    import termios

    if stdin_fd is None:
        stdin_fd = sys.__stdin__.fileno() if sys.__stdin__ else 0
    if term_fd is None:
        term_fd = sys.__stdout__.fileno() if sys.__stdout__ else 1
    master, slave = pty.openpty()
    rows, cols = _get_size(term_fd)
    _set_size(master, rows, cols - indent)
    try:
        proc = subprocess.Popen(
            cmd,
            shell=isinstance(cmd, str),
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            start_new_session=True,
            preexec_fn=_child_setup,
            close_fds=True,
        )
    finally:
        os.close(slave)  # only the child holds the slave now, so reads hit EOF/EIO when it's done

    splitter = AltScreenSplitter()
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def emit(runs: list[tuple[bool, bytes]]) -> None:
        for alt, chunk in runs:
            if alt:
                if pending := decoder.decode(b"", final=True):
                    write(pending)
                write_raw(chunk)
                if chunk in _ALT_ENTER:
                    _set_size(master, *_get_size(term_fd))
                elif chunk in _ALT_LEAVE:
                    r, c = _get_size(term_fd)
                    _set_size(master, r, c - indent)
            elif text := decoder.decode(chunk):
                write(text)

    def on_resize(signum: int, frame: Any) -> None:
        r, c = _get_size(term_fd)
        _set_size(master, r, c if splitter.alt else c - indent)

    old_winch: Any = None
    try:
        old_winch = signal.signal(signal.SIGWINCH, on_resize)
    except (ValueError, AttributeError):  # not the main thread
        old_winch = None

    old_mode = None
    try:
        old_mode = _passthrough_mode(stdin_fd)
    except (termios.error, OSError):
        log.debug("could not put the terminal in passthrough mode", exc_info=True)

    try:
        watching = [master, stdin_fd] if old_mode is not None else [master]
        while True:
            try:
                ready, _, _ = select.select(watching, [], [], 0.05)
            except InterruptedError:
                continue
            if master in ready:
                try:
                    data = os.read(master, 65536)
                except OSError:  # EIO: every process holding the pty has exited
                    data = b""
                if not data:
                    break
                emit(splitter.feed(data))
            if stdin_fd in ready:
                try:
                    keys = os.read(stdin_fd, 4096)
                except OSError:
                    keys = b""
                if keys:
                    try:
                        os.write(master, keys)
                    except OSError:
                        pass
            if not ready and proc.poll() is not None:
                # the command is done; something it left in the background may keep the pty open
                break
        emit(splitter.flush())
        if tail := decoder.decode(b"", final=True):
            write(tail)
        if splitter.alt:  # it died inside the alternate screen: put the terminal back
            write_raw(b"\x1b[?1049l\x1b[?25h")
    except BaseException:
        # :py itself was interrupted (e.g. Ctrl+C before the keys were handed over): the command
        # runs in its own session, so stop it rather than leave it behind
        _stop(proc)
        raise
    finally:
        if old_mode is not None:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_mode)
        if old_winch is not None:
            signal.signal(signal.SIGWINCH, old_winch)
        os.close(master)
    try:
        return proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        return proc.wait()
