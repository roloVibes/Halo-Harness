"""halo_harness.banner -- the ASCII-art HALO wordmark (2.0.5 round 2d).

One place builds the banner so `halo --version` (cli.py) and the intro
line pool's first entry (tui/intro_lines.py) render the exact same art;
the README carries a fenced copy of the same rows, and tests pin the
copy against this module so the three can never drift apart. The letters
are spelled out per-glyph and joined by width -- hand-joined rows drift.

Pure data + one join, no imports, no I/O.
"""

from __future__ import annotations

# figlet-standard-style glyphs, 5 rows tall, each row exactly 7 or 9 cols.
_H = (" _   _ ", "| | | |", "| |_| |", "|  _  |", "|_| |_|")
_A = ("    _    ", "   / \\   ", "  / _ \\  ", " / ___ \\ ", "/_/   \\_\\")
_L = (" _     ", "| |    ", "| |    ", "| |___ ", "|_____|")
_O = ("  ___  ", " / _ \\ ", "| | | |", "| |_| |", " \\___/ ")

BANNER_ROWS: tuple[str, ...] = tuple(" ".join(row) for row in zip(_H, _A, _L, _O))

#: The banner as one block, no trailing newline.
BANNER: str = "\n".join(BANNER_ROWS)


def banner_with_version(version_line: str) -> str:
    """The full `halo --version` output: the wordmark, then the version
    line (`halo 2.0.5 (9f34d6d, master)` -- update.format_version_line's
    own shape) on its own row underneath."""
    return f"{BANNER}\n{version_line}"
