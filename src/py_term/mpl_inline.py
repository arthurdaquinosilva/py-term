"""matplotlib backend for `%matplotlib inline`: figures are drawn in the terminal, under the cell.

Selected as `module://py_term.mpl_inline`. Like a notebook's inline backend, every figure a cell
creates or changes is shown when the cell finishes (or at `plt.show()`), then closed.
"""

from __future__ import annotations

from typing import Any

from matplotlib.backend_bases import FigureManagerBase
from matplotlib.backends.backend_agg import FigureCanvasAgg

BACKEND = "module://py_term.mpl_inline"

FigureCanvas = FigureCanvasAgg
FigureManager = FigureManagerBase


def show(block: Any = None, close: bool = True) -> None:
    """Draw every open figure inline, then close them."""
    from matplotlib import pyplot as plt
    from matplotlib._pylab_helpers import Gcf

    from py_term import images
    from py_term.shell import Shell

    shell = Shell.active
    for manager in Gcf.get_all_fig_managers():
        figure = manager.canvas.figure
        if not figure.axes and not figure.texts and not figure.images:
            continue  # an empty figure (e.g. plt.figure() alone): nothing to show
        png = images.figure_png(figure)
        if png is None:
            continue
        renderable = images.TerminalImage(png, "figure")
        if shell is not None:
            shell.print(renderable)
        else:
            from rich.console import Console

            Console().print(renderable)
    if close:
        plt.close("all")


def flush_figures() -> None:
    """Called after each cell: show what the cell drew, as a notebook does."""
    from matplotlib._pylab_helpers import Gcf

    if Gcf.get_all_fig_managers():
        show()


def is_active() -> bool:
    return backend_name() == BACKEND


def backend_name() -> str | None:
    """The configured backend without resolving it (resolving can import a GUI toolkit)."""
    import sys

    mpl = sys.modules.get("matplotlib")
    if mpl is None:
        return None
    raw = getattr(mpl.rcParams, "_get_backend_or_none", None)
    try:
        return raw() if raw else dict.__getitem__(mpl.rcParams, "backend")
    except Exception:
        return None
