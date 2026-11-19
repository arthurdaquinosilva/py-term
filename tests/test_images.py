"""Inline images: detection, image headers, sizing, escape sequences, rendering and %matplotlib inline."""

import base64
import io
import struct
import zlib

import pytest
from rich.console import Console
from rich.text import Text

from py_term import images


def png(width=4, height=2):
    """A valid PNG of the given size, built by hand so the tests don't need Pillow."""

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    rows = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


GIF = b"GIF89a" + struct.pack("<HH", 30, 20) + b"\x00" * 10
JPEG = (
    b"\xff\xd8"
    + b"\xff\xe0"
    + struct.pack(">H", 16)
    + b"JFIF\x00"
    + b"\x00" * 9
    + b"\xff\xc0"
    + struct.pack(">HBHH", 17, 8, 48, 64)
    + b"\x00" * 12
)


@pytest.fixture(autouse=True)
def fresh_detection():
    images.reset()
    yield
    images.reset()


@pytest.fixture
def force(monkeypatch):
    """Pretend the terminal speaks a protocol."""

    def set_protocol(protocol, tmux=False):
        monkeypatch.setattr(images, "support", lambda setting="auto": images.Support(protocol, tmux=tmux))

    return set_protocol


def terminal_console(width=80):
    return Console(file=io.StringIO(), force_terminal=True, width=width, color_system="truecolor")


# ---------------------------------------------------------------- headers


def test_image_size_and_format():
    assert images.image_size(png(4, 2)) == (4, 2) and images.image_format(png()) == "png"
    assert images.image_size(GIF) == (30, 20) and images.image_format(GIF) == "gif"
    assert images.image_size(JPEG) == (64, 48) and images.image_format(JPEG) == "jpeg"
    assert images.image_size(b"not an image") is None and images.image_format(b"nope") is None


# ---------------------------------------------------------------- detection


def no_tmux_call(*args, **kwargs):
    raise AssertionError("tmux should not be asked")


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"TERM": "xterm-kitty"}, "kitty"),
        ({"TERM": "xterm-ghostty", "TERM_PROGRAM": "ghostty"}, "kitty"),
        ({"TERM": "xterm-256color", "TERM_PROGRAM": "iTerm.app"}, "iterm"),
        ({"TERM": "xterm-256color", "TERM_PROGRAM": "WezTerm"}, "iterm"),
        ({"TERM": "xterm-256color", "LC_TERMINAL": "iTerm2"}, "iterm"),  # survives ssh
        ({"TERM": "xterm-256color"}, None),
    ],
)
def test_detect_terminals(env, expected):
    assert images.detect("auto", env=env, tty=True, run=no_tmux_call).protocol == expected


def test_detect_off_when_not_a_terminal():
    sup = images.detect("auto", env={"TERM": "xterm-kitty"}, tty=False)
    assert sup.protocol is None and "not a terminal" in sup.reason


def test_setting_and_env_override_detection():
    assert images.detect("iterm", env={"TERM": "dumb"}, tty=False).protocol == "iterm"
    assert images.detect("auto", env={"TERM": "xterm-kitty", "PY_TERM_IMAGES": "off"}, tty=True).protocol is None
    assert images.detect("off", env={"TERM": "xterm-kitty"}, tty=True).protocol is None


class FakeRun:
    def __init__(self, value):
        self.value = value

    def __call__(self, *args, **kwargs):
        class Result:
            stdout = self.value + "\n"

        return Result()


def test_tmux_needs_passthrough():
    env = {"TERM": "tmux-256color", "TMUX": "/tmp/tmux-1/default,1,0", "LC_TERMINAL": "iTerm2"}
    on = images.detect("auto", env=env, tty=True, run=FakeRun("on"))
    assert on.protocol == "iterm" and on.tmux and "through tmux" in on.describe()
    off = images.detect("auto", env=env, tty=True, run=FakeRun("off"))
    assert off.protocol is None and "allow-passthrough on" in off.reason


def test_gnu_screen_is_off():
    assert images.detect("auto", env={"TERM": "screen", "STY": "1.pts", "LC_TERMINAL": "iTerm2"}, tty=True).protocol is None


# ---------------------------------------------------------------- sizing


def test_fit_keeps_natural_size_when_it_fits():
    assert images.fit((80, 32), (8, 16), max_cols=100, max_rows=50) == (10, 2)


def test_fit_shrinks_to_the_width_and_height():
    # 1600×800 px is 200×50 cells at 8×16 px per cell
    assert images.fit((1600, 800), (8, 16), max_cols=50, max_rows=100) == (50, 12)
    # 800×1600 px is 100×100 cells
    assert images.fit((800, 1600), (8, 16), max_cols=200, max_rows=20) == (20, 20)


def test_fit_honours_a_requested_width():
    assert images.fit((800, 400), (8, 16), 200, 200, want=(160, None)) == (20, 5)


# ---------------------------------------------------------------- escape sequences


def test_iterm_sequence():
    data = png()
    seq = images.iterm_sequence(data, 10, 3)
    assert seq.startswith("\x1b]1337;File=inline=1;") and seq.endswith("\a")
    for field in (f"size={len(data)}", "width=10", "height=3", "preserveAspectRatio=1", "doNotMoveCursor=1"):
        assert field in seq
    assert base64.standard_b64encode(data).decode() in seq


def test_kitty_sequence_chunks_and_stays_quiet():
    data = bytes(range(256)) * 40  # > 4096 base64 characters
    seq = images.kitty_sequence(data, 12, 4)
    parts = seq.split("\x1b\\")[:-1]
    assert len(parts) > 1
    assert parts[0].startswith("\x1b_Ga=T,f=100,c=12,r=4,C=1,q=2,m=1;")
    assert all(p.startswith("\x1b_Gm=1;") for p in parts[1:-1])
    assert parts[-1].startswith("\x1b_Gm=0;")
    payload = "".join(p.split(";", 1)[1] for p in parts)
    assert base64.standard_b64decode(payload) == data


def test_tmux_passthrough_wraps_and_doubles_escapes():
    seq = images.iterm_sequence(png(), 1, 1, tmux=True)
    assert seq.startswith("\x1bPtmux;\x1b\x1b]1337;") and seq.endswith("\x1b\\")
    kitty = images.kitty_sequence(png(), 1, 1, tmux=True)
    assert kitty.startswith("\x1bPtmux;\x1b\x1b_G") and kitty.count("\x1bPtmux;") == 1


# ---------------------------------------------------------------- rendering


def test_placeholder_when_images_are_off(force):
    force(None)
    console = terminal_console()
    console.print(images.TerminalImage(png(4, 2), "figure"))
    out = console.file.getvalue()
    assert "figure" in out and "4 × 2 px" in out and "1337" not in out


def test_placeholder_when_output_is_not_a_terminal(force):
    force("iterm")
    console = Console(file=io.StringIO(), force_terminal=False, width=80)
    console.print(images.TerminalImage(png()))
    assert "▣ image" in console.file.getvalue()


def test_draws_in_reserved_rows(force, monkeypatch):
    force("iterm")
    monkeypatch.setattr(images, "cell_size", lambda fd=None: (8, 16))
    console = terminal_console()
    console.print(images.TerminalImage(png(80, 64)))  # 10 columns × 4 rows
    out = console.file.getvalue()
    # a blank margin line, 3 more newlines to reserve the image's rows, back up 3, draw
    assert out.startswith("\x1b[m\n\n\n\n\x1b[3A\x1b]1337;File=")
    assert "width=10;height=4" in out
    # back down to the last row, end it, then a blank margin line
    assert out.endswith("\a\x1b[3B\n\n")


def test_no_top_margin_for_a_cells_first_output():
    segments = list(images.image_segments("IMG", 3, margin_top=False))
    assert segments[0].text == "\x1b[m\n\n\x1b[2AIMG\x1b[2B"
    assert [s.text for s in segments[1:]] == ["\n", "\n"]


def test_single_row_image_moves_nowhere(force, monkeypatch):
    force("kitty")
    monkeypatch.setattr(images, "cell_size", lambda fd=None: (8, 16))
    console = terminal_console()
    console.print(images.TerminalImage(png(8, 8)))
    out = console.file.getvalue()
    assert "\x1b[0A" not in out and "[1A" not in out and "a=T,f=100,c=1,r=1" in out


def test_kitty_needs_png(force, monkeypatch):
    force("kitty")
    monkeypatch.setattr(images, "to_png", lambda data: None)  # as if Pillow were missing
    console = terminal_console()
    console.print(images.TerminalImage(GIF))
    assert "install Pillow" in console.file.getvalue()


# ---------------------------------------------------------------- objects


class WithPng:
    def _repr_png_(self):
        return png(16, 16)


class LikeSympy(WithPng):
    def _repr_latex_(self):
        return "$x$"


def test_objects_with_image_reprs_are_drawn(force):
    from py_term.display import render_value

    force("iterm")
    assert isinstance(render_value(WithPng()), images.TerminalImage)
    assert not isinstance(render_value(LikeSympy()), images.TerminalImage)


def test_objects_with_image_reprs_stay_text_without_support(force):
    from py_term.display import render_value

    force(None)
    assert not isinstance(render_value(WithPng()), images.TerminalImage)


def test_mime_bundle_images(force):
    from py_term.display import render_value

    class Bundle:
        def _repr_mimebundle_(self, **kwargs):
            return {"image/png": base64.b64encode(png()).decode(), "text/plain": "a picture"}

    force("kitty")
    assert isinstance(render_value(Bundle()), images.TerminalImage)


def test_stand_in_image_class(force):
    from py_term.ipython.display import Image

    force("iterm")
    image = Image(data=png(10, 6), width=5)
    rendered = image.__rich__()
    assert isinstance(rendered, images.TerminalImage) and rendered.width == 5
    assert image._repr_png_() == png(10, 6) and image._repr_jpeg_() is None


def test_stand_in_svg_without_cairosvg(force, monkeypatch):
    from py_term.ipython.display import SVG

    force("iterm")
    monkeypatch.setattr(images, "svg_to_png", lambda svg: None)
    rendered = SVG('<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4"/>').__rich__()
    assert isinstance(rendered, Text) and "cairosvg" in rendered.plain


def test_images_setting_is_validated():
    from py_term.config import Settings

    assert Settings().validate("images", "Kitty") == "kitty"
    with pytest.raises(ValueError):
        Settings().validate("images", "sixel")


# ---------------------------------------------------------------- matplotlib


def test_matplotlib_inline_shows_and_closes_figures(shell, capfd):
    pytest.importorskip("matplotlib")
    import matplotlib.pyplot as plt

    try:
        shell.run_cell("%matplotlib inline")
        assert shell.last_ok
        capfd.readouterr()
        shell.run_cell("import matplotlib.pyplot as plt\nplt.plot([1, 3, 2])\nNone")
        out = capfd.readouterr().out
        assert "figure" in out  # a placeholder here: pytest's output is not a terminal
        assert plt.get_fignums() == []
        shell.run_cell("x = 1")
        assert "figure" not in capfd.readouterr().out  # nothing left to show
    finally:
        plt.close("all")
        plt.switch_backend("agg")


def test_figure_value_is_drawn(shell, force):
    pytest.importorskip("matplotlib")
    import matplotlib

    matplotlib.use("agg")
    from matplotlib.figure import Figure

    from py_term.display import render_value

    force("iterm")
    fig = Figure()
    fig.add_subplot().plot([1, 2])
    rendered = render_value(fig)
    assert isinstance(rendered, images.TerminalImage) and images.image_format(rendered.data) == "png"
