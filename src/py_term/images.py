"""Inline images in the terminal, through the kitty graphics protocol or iTerm2's inline images.

Which protocol to use comes from the `images` setting (`auto`, `kitty`, `iterm`, `off`) or the
`PY_TERM_IMAGES` environment variable. `auto` recognises kitty and Ghostty (kitty protocol) and
iTerm2, WezTerm and mintty (iTerm2 protocol), also from inside tmux, where the escape sequences go
through tmux's passthrough (`set -g allow-passthrough on`).

An image is drawn without moving the cursor, into rows reserved with newlines first. That keeps
the terminal, tmux and Rich agreeing on where the cursor is, so text after the image lands below it.
When there is no supported terminal (or output isn't a terminal at all), a one-line placeholder is
shown instead.
"""

from __future__ import annotations

import base64
import io
import math
import os
import shutil
import struct
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from rich.segment import ControlType, Segment
from rich.text import Text

from py_term.diagnostics import log

if TYPE_CHECKING:
    from rich.console import Console, ConsoleOptions, RenderResult

PROTOCOLS = ("kitty", "iterm")
_ESC = "\x1b"
_KITTY_CHUNK = 4096
_FALLBACK_CELL = (8, 16)  # pixels per cell when the terminal doesn't say


# ---------------------------------------------------------------- detection


@dataclass(frozen=True)
class Support:
    """What the terminal can do. `protocol` is None when images can't be shown; `reason` says why."""

    protocol: str | None
    tmux: bool = False
    reason: str = ""

    def describe(self) -> str:
        if self.protocol is None:
            return f"off ({self.reason})" if self.reason else "off"
        name = {"kitty": "kitty graphics protocol", "iterm": "iTerm2 inline images"}[self.protocol]
        return name + (", through tmux" if self.tmux else "")


def _outer_terminal(env: dict[str, str]) -> str | None:
    """The protocol of the terminal emulator itself, from variables that survive tmux and ssh."""
    term, program = env.get("TERM", ""), env.get("TERM_PROGRAM", "")
    if "kitty" in term or env.get("KITTY_WINDOW_ID") or program.lower() == "ghostty" or env.get("GHOSTTY_RESOURCES_DIR"):
        return "kitty"
    if program in ("iTerm.app", "WezTerm", "mintty") or env.get("LC_TERMINAL") == "iTerm2" or env.get("ITERM_SESSION_ID"):
        return "iterm"
    if env.get("WEZTERM_PANE") or env.get("WEZTERM_EXECUTABLE"):
        return "iterm"
    return None


def tmux_passthrough(run: Any = subprocess.run) -> bool:
    try:
        result = run(["tmux", "show-options", "-gqv", "allow-passthrough"], capture_output=True, text=True, timeout=1)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.stdout.strip() in ("on", "all")


def detect(setting: str = "auto", env: dict[str, str] | None = None, tty: bool | None = None, run: Any = subprocess.run) -> Support:
    env = dict(os.environ) if env is None else env
    choice = (env.get("PY_TERM_IMAGES") or setting or "auto").strip().lower()
    if choice in ("off", "none", "no", "false", "0"):
        return Support(None, reason="turned off")
    in_tmux = bool(env.get("TMUX"))
    if choice in PROTOCOLS:
        return Support(choice, tmux=in_tmux)
    if tty is None:
        stream = sys.__stdout__
        tty = bool(stream and stream.isatty())
    if not tty:
        return Support(None, reason="output is not a terminal")
    if env.get("STY"):
        return Support(None, reason="GNU screen can't pass images through")
    protocol = _outer_terminal(env)
    if protocol is None:
        return Support(None, reason="terminal not recognised; set images = \"kitty\" or \"iterm\" if it supports one")
    if in_tmux and not tmux_passthrough(run):
        return Support(None, tmux=True, reason="inside tmux: add `set -g allow-passthrough on` to ~/.tmux.conf")
    return Support(protocol, tmux=in_tmux)


_support: dict[str, Support] = {}


def support(setting: str = "auto") -> Support:
    """Detected once per session and setting (tmux is asked at most once)."""
    if setting not in _support:
        _support[setting] = detect(setting)
        log.debug("inline images (%s): %s", setting, _support[setting].describe())
    return _support[setting]


def reset() -> None:
    _support.clear()


# ---------------------------------------------------------------- image facts


def image_size(data: bytes) -> tuple[int, int] | None:
    """Pixel size of a PNG, GIF or JPEG, read from its header (no imaging library needed)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        w, h = struct.unpack(">II", data[16:24])
        return int(w), int(h)
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        w, h = struct.unpack("<HH", data[6:10])
        return int(w), int(h)
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            (length,) = struct.unpack(">H", data[i + 2 : i + 4])
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5 : i + 9])
                return int(w), int(h)
            i += 2 + length
    return None


def image_format(data: bytes) -> str | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:2] == b"\xff\xd8":
        return "jpeg"
    return None


def to_png(data: bytes) -> bytes | None:
    """Convert another raster format to PNG (kitty only takes PNG). Needs Pillow."""
    try:
        from PIL import Image as PILImage
    except ImportError:
        return None
    try:
        with PILImage.open(io.BytesIO(data)) as im:
            out = io.BytesIO()
            im.save(out, format="PNG")
            return out.getvalue()
    except Exception:
        log.debug("converting an image to PNG failed", exc_info=True)
        return None


def svg_to_png(svg: str | bytes) -> bytes | None:
    """Rasterise SVG with cairosvg when it's installed."""
    try:
        import cairosvg  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        return cairosvg.svg2png(bytestring=svg.encode() if isinstance(svg, str) else svg)
    except Exception:
        log.debug("rasterising SVG failed", exc_info=True)
        return None


def cell_size(fd: int | None = None) -> tuple[int, int]:
    """Pixels per character cell, from the terminal's window size report."""
    try:
        import fcntl
        import termios

        stream = sys.__stdout__
        fd = fd if fd is not None else (stream.fileno() if stream else 1)
        rows, cols, xpix, ypix = struct.unpack("HHHH", fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0" * 8))
        if rows and cols and xpix and ypix:
            return max(1, xpix // cols), max(1, ypix // rows)
    except (ImportError, OSError, ValueError, AttributeError):
        pass
    return _FALLBACK_CELL


def fit(
    pixels: tuple[int, int], cell: tuple[int, int], max_cols: int, max_rows: int, want: tuple[int | None, int | None] = (None, None)
) -> tuple[int, int]:
    """Columns and rows an image takes: its natural size (or the requested pixel size), shrunk to fit."""
    w, h = pixels
    want_w, want_h = want
    if want_w and want_h:
        w, h = want_w, want_h
    elif want_w:
        w, h = want_w, round(h * want_w / w) if w else h
    elif want_h:
        w, h = round(w * want_h / h) if h else w, want_h
    cols = max(1, math.ceil(w / cell[0]))
    rows = max(1, math.ceil(h / cell[1]))
    scale = min(1.0, max_cols / cols, max_rows / rows)
    if scale < 1.0:
        cols = max(1, math.floor(cols * scale))
        rows = max(1, math.floor(rows * scale))
    return cols, rows


# ---------------------------------------------------------------- escape sequences


def _passthrough(seq: str) -> str:
    """Wrap an escape sequence so tmux hands it to the outer terminal."""
    return f"{_ESC}Ptmux;{seq.replace(_ESC, _ESC + _ESC)}{_ESC}\\"


def kitty_sequence(png: bytes, cols: int, rows: int, tmux: bool = False) -> str:
    """Transmit and display a PNG in one go, without moving the cursor (C=1) or replying (q=2)."""
    payload = base64.standard_b64encode(png).decode("ascii")
    chunks = [payload[i : i + _KITTY_CHUNK] for i in range(0, len(payload), _KITTY_CHUNK)] or [""]
    parts = []
    for n, chunk in enumerate(chunks):
        more = 1 if n < len(chunks) - 1 else 0
        keys = f"a=T,f=100,c={cols},r={rows},C=1,q=2,m={more}" if n == 0 else f"m={more}"
        seq = f"{_ESC}_G{keys};{chunk}{_ESC}\\"
        parts.append(_passthrough(seq) if tmux else seq)
    return "".join(parts)


def iterm_sequence(data: bytes, cols: int, rows: int, tmux: bool = False) -> str:
    """iTerm2's OSC 1337 inline file, sized in cells, leaving the cursor where it was."""
    payload = base64.standard_b64encode(data).decode("ascii")
    args = f"inline=1;size={len(data)};width={cols};height={rows};preserveAspectRatio=1;doNotMoveCursor=1"
    seq = f"{_ESC}]1337;File={args}:{payload}\a"
    return _passthrough(seq) if tmux else seq


# ---------------------------------------------------------------- the renderable


class TerminalImage:
    """A Rich renderable that draws an image inline, or a placeholder line when it can't.

    `data` is PNG, JPEG or GIF bytes. `width`/`height` are the size wanted in pixels."""

    def __init__(self, data: bytes, label: str = "image", width: int | None = None, height: int | None = None, source: str = "") -> None:
        self.data = data
        self.label = label
        self.width = width
        self.height = height
        self.source = source

    def placeholder(self, note: str = "") -> Text:
        size = image_size(self.data)
        bits = [b for b in (self.source, f"{size[0]} × {size[1]} px" if size else "", f"{len(self.data):,} bytes", note) if b]
        return Text.assemble(("▣ ", "py_term.accent"), (self.label, "py_term.fg"), ("  " + " · ".join(bits), "py_term.faint"))

    def _encoded(self, protocol: str) -> bytes | None:
        if protocol == "kitty" and image_format(self.data) != "png":
            return to_png(self.data)
        return self.data if image_format(self.data) else None

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        sup = support(_setting())
        if sup.protocol is None or not console.is_terminal or console.is_dumb_terminal:
            yield self.placeholder()
            return
        data = self._encoded(sup.protocol)
        size = image_size(data) if data else None
        if data is None or size is None:
            note = "install Pillow to show this format in kitty" if sup.protocol == "kitty" else "unsupported format"
            yield self.placeholder(note)
            return
        terminal_rows = shutil.get_terminal_size(fallback=(80, 24)).lines
        cols, rows = fit(size, cell_size(), max(1, options.max_width), max(1, terminal_rows - 3), (self.width, self.height))
        seq = kitty_sequence(data, cols, rows, sup.tmux) if sup.protocol == "kitty" else iterm_sequence(data, cols, rows, sup.tmux)
        yield from image_segments(seq, rows)


def image_segments(seq: str, rows: int) -> Iterable[Segment]:
    """Reserve `rows` lines, go back to the top, draw (the cursor stays put), then return to the bottom.

    Everything is one control segment, so Rich neither measures nor wraps the long escape sequence.
    It starts with a no-op SGR reset so that a line prefix (the `⎿` under a cell) goes on the image's
    first row rather than below it."""
    up = f"{_ESC}[{rows - 1}A" if rows > 1 else ""
    down = f"{_ESC}[{rows - 1}B" if rows > 1 else ""
    yield Segment(f"{_ESC}[m" + "\n" * (rows - 1) + up + seq + down, None, [(ControlType.BELL,)])
    yield Segment.line()


def _setting() -> str:
    from py_term.shell import Shell

    shell = Shell.active
    return getattr(getattr(shell, "settings", None), "images", "auto") if shell else "auto"


# ---------------------------------------------------------------- from Python objects


def figure_png(fig: Any, dpi: int | None = None) -> bytes | None:
    """Render a matplotlib Figure to PNG, cropped to its contents like a notebook does."""
    try:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi or fig.dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
        return buf.getvalue()
    except Exception:
        log.debug("rendering a matplotlib figure failed", exc_info=True)
        return None


def is_figure(value: Any) -> bool:
    cls = type(value)
    return cls.__module__.startswith("matplotlib.") and any(c.__name__ == "Figure" for c in cls.__mro__)


def from_mime(bundle: dict[str, Any], label: str = "image") -> TerminalImage | None:
    """A TerminalImage from a mime bundle's image/png, image/jpeg or image/svg+xml entry."""
    for mime in ("image/png", "image/jpeg", "image/gif"):
        if mime in bundle and (data := _as_bytes(bundle[mime])) is not None:
            return TerminalImage(data, label)
    if "image/svg+xml" in bundle and (png := svg_to_png(bundle["image/svg+xml"])) is not None:
        return TerminalImage(png, "svg")
    return None


def _as_bytes(value: Any) -> bytes | None:
    if isinstance(value, tuple):
        value = value[0]
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        try:
            return base64.b64decode(value, validate=False)
        except ValueError:
            return None
    return None
