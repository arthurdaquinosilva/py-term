# Changelog

## Unreleased

- The rule layout leaves a blank line between your code and its first output, like the block and box layouts.
- **Images in the terminal**: `%matplotlib inline` draws figures under the cell, and `Image`, PIL images, figures and anything with an image repr are drawn too, on terminals with the kitty graphics protocol (kitty, Ghostty) or iTerm2 inline images (iTerm2, WezTerm, mintty), also inside tmux with `allow-passthrough on`. Other terminals show a placeholder. The new `images` setting (`auto`, `kitty`, `iterm`, `off`) and `PY_TERM_IMAGES` override detection, and `:py --doctor` reports it.
- History, the debug log and crash reports are readable only by you: the data folder is now `0700` and those files `0600`. Before, `history.sqlite` was readable by other accounts on the machine.

## 0.1.0

First release of :py, a modern interactive Python shell with IPython's power and a calm terminal UI.

- **Interface**: three layouts. `rule` (the default) puts the input between two horizontal rules with a one-line footer; `block` and `box` are the alternatives. Cell output hangs under a `⎿` marker with a status line (time, result type, `Out[N]`). The shared **pitch** palette is cool blue and violet on the terminal's own black, with an orange accent. Vi or emacs keys; Shift+Enter inserts a newline; pasted `>>>` and `In [N]:` prompts are stripped.
- **Help while typing**: completions with type icons, and live signatures with declared and inferred types, even for functions without annotations.
- **IPython features**: 85 magics, `obj?` and `obj??`, `!cmd` and `!!cmd`, `$var` expansion, SQLite history grouped by session with IPython's range syntax, `%autoreload`, `%debug`, `%pdb`, `%xmode`, `%timeit`, `%prun`, `%run`, `%store`, `%macro`, top-level `await` (asyncio, trio, curio), and GUI event loops.
- **IPython compatibility**: `get_ipython()`, events, input and AST transformers, display formatters and the `_repr_*_` protocol, custom magics, and extensions such as `line_profiler`. When IPython isn't installed, stand-in `IPython.*` modules let IPython code run unchanged.
- **Diagnostics**: `:py --doctor` prints versions, terminal facts and file paths for bug reports. `--debug` or `PY_TERM_LOG=debug` writes a log. An internal error prints one line with the path to a crash report, and the session keeps going.
- **Install**: a one-line installer that verifies the release wheel against `SHA256SUMS`, or `pipx` / `uv tool install` from GitHub. Python 3.10–3.14 on Linux and macOS.
