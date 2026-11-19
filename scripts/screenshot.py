"""Record a real :py session in a pseudo-terminal and save it as an SVG screenshot.

    python scripts/screenshot.py   # writes docs/assets/demo.svg

Needs the dev extras (pexpect, pyte). The image is the actual rendered terminal, not a mock-up.
"""

from __future__ import annotations

from _termshot import ROOT, capture, save_svg, to_text

COLS, ROWS = 96, 44

# (keys to send, seconds to wait afterwards)
SCRIPT = [
    ("def greet(name, times=1):\r", 0.4),
    ('return f"hi {name}! " * times\r', 0.4),
    ("\r", 0.8),
    ('greet("Arthur", times=2)\r', 0.8),
    ("%timeit -n 10000 greet('world')\r", 2.5),
    ('greet("world", ', 1.5),
]


def main() -> None:
    screen = capture(SCRIPT, COLS, ROWS)
    save_svg(to_text(screen), ROOT / "docs" / "assets" / "demo.svg", COLS, title=":py")


if __name__ == "__main__":
    main()
