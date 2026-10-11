"""halo_harness.tui.dialogs.remote_digits -- the large pairing code of the
`/remote` dialog: a 3x5 block font (original) and a clock formatter."""

from __future__ import annotations

import time

_FONT = {
    "0": ("###", "# #", "# #", "# #", "###"), "1": (" # ", "## ", " # ", " # ", "###"),
    "2": ("###", "  #", "###", "#  ", "###"), "3": ("###", "  #", "###", "  #", "###"),
    "4": ("# #", "# #", "###", "  #", "  #"), "5": ("###", "#  ", "###", "  #", "###"),
    "6": ("###", "#  ", "###", "# #", "###"), "7": ("###", "  #", "  #", "  #", "  #"),
    "8": ("###", "# #", "###", "# #", "###"), "9": ("###", "# #", "###", "  #", "###"),
}


def big_digits(code: str) -> str:
    """The code in a 3x5 block font, five lines."""
    rows = ["  ".join(_FONT[c][r] for c in code if c in _FONT) for r in range(5)]
    return "\n".join(r.replace("#", "█") for r in rows)


def when(ts) -> str:
    try:
        return time.strftime("%H:%M", time.localtime(float(ts)))
    except (TypeError, ValueError, OSError):
        return "?"
