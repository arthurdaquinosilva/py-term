"""GUI event loop & plotting magics: %gui, %matplotlib."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

from py_term.inputhooks import GUIS
from py_term.magics import MagicError, line_magic

if TYPE_CHECKING:
    from py_term.shell import Shell


@line_magic("gui", doc="keep a GUI event loop running at the prompt: %gui qt|tk|osx|gtk3|gtk4|wx|asyncio (no arg disables)")
def m_gui(shell: Shell, args: str):
    name = args.strip() or None
    try:
        shell.enable_gui(name)
    except (ValueError, ImportError) as e:
        raise MagicError(str(e)) from None
    if name:
        shell.print(
            Text.assemble(
                ("event loop → ", "py_term.muted"), (name, "py_term.accent.bold"), ("  (runs while the prompt waits)", "py_term.faint")
            )
        )
    else:
        shell.print(Text("event loop integration off", style="py_term.muted"))


@line_magic(
    "matplotlib", doc="matplotlib figures in the terminal (inline) or in responsive windows: %matplotlib [inline|qt|tk|osx|…] · -l list"
)
def m_matplotlib(shell: Shell, args: str):
    name = args.strip()
    if name in ("-l", "--list"):
        shell.print(Text("event loops: " + ", ".join(g for g in GUIS if g != "asyncio"), style="py_term.fg"))
        shell.print(
            Text(
                "backends: inline (drawn in the terminal), or any matplotlib backend, e.g. QtAgg, TkAgg, macosx, agg", style="py_term.muted"
            )
        )
        return
    if name in ("widget", "ipympl", "notebook", "nbagg"):
        raise MagicError(f"%matplotlib {name} needs a notebook — in a terminal use inline or a GUI backend (qt, tk, osx)")
    try:
        gui, backend = shell.enable_matplotlib(name or None)
    except ImportError as e:
        raise MagicError(f"{e} — %pip install matplotlib") from None
    except (ValueError, RuntimeError) as e:
        raise MagicError(str(e)) from None
    if name == "inline":
        from py_term import images

        sup = images.support(shell.settings.images)
        detail = (
            f"  · figures drawn in the terminal ({sup.describe()})"
            if sup.protocol
            else f"  · images {sup.describe()}: figures show as placeholders"
        )
        shell.print(Text.assemble(("matplotlib → ", "py_term.muted"), ("inline", "py_term.accent.bold"), (detail, "py_term.faint")))
        return
    shell.print(
        Text.assemble(
            ("matplotlib → ", "py_term.muted"),
            (backend, "py_term.accent.bold"),
            (f"  · event loop {gui}" if gui else "  · no GUI event loop needed", "py_term.faint"),
        )
    )
