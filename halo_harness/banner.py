"""halo_harness.banner -- the HALO wordmark (2.0.5 round 2d; the block art
is 2.0.11 round A2).

One place holds the art so `halo --version` (cli.py), the launch intro
(tui/intro_lines.py, typed out row by row in a gradient), the README's
banner block and the hero image (tools/hero_svg.py builds docs/media/hero.svg
from these rows) all render the exact same thing; tests pin each copy
against this module.

Two forms:

* `BANNER_ART` -- the block-letter wordmark under a shaded halo ring, drawn
  from Unicode block elements and the box-drawing "shadow" glyphs. Rows are
  under 48 columns. Rows 0-2 are the ring (`RING_ROWS`), the rest the
  letters; the intro paints the ring gold and the letters in a gradient.
* `BANNER` -- the plain-ASCII figlet-style form, kept for consoles that
  cannot encode the block elements (`halo --version` on a cp1252 stream)
  and for any text-only surface.

Pure data + joins, no I/O. `banner_for_encoding` is the one chooser.
"""

from __future__ import annotations

# -- the block art ----------------------------------------------------------

_RING = (
    "    ░▒▓▓▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▓▓▒░",
    "  ▒▓█▀                               ▀█▓▒",
    "    ░▒▓▓▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▓▓▒░",
)

_LETTERS = (
    "    ██╗  ██╗ █████╗ ██╗      ██████╗",
    "    ██║  ██║██╔══██╗██║     ██╔═══██╗",
    "    ███████║███████║██║     ██║   ██║",
    "    ██╔══██║██╔══██║██║     ██║   ██║",
    "    ██║  ██║██║  ██║███████╗╚██████╔╝",
    "    ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝ ╚═════╝",
)

#: The number of leading rows that draw the halo ring (styled differently).
RING_ROWS: int = len(_RING)

BANNER_ART_ROWS: tuple[str, ...] = _RING + _LETTERS

#: The block art as one block, no trailing newline.
BANNER_ART: str = "\n".join(BANNER_ART_ROWS)

# -- the ASCII fallback -----------------------------------------------------

# figlet-standard-style glyphs, 5 rows tall, each row exactly 7 or 9 cols.
_H = (" _   _ ", "| | | |", "| |_| |", "|  _  |", "|_| |_|")
_A = ("    _    ", "   / \\   ", "  / _ \\  ", " / ___ \\ ", "/_/   \\_\\")
_L = (" _     ", "| |    ", "| |    ", "| |___ ", "|_____|")
_O = ("  ___  ", " / _ \\ ", "| | | |", "| |_| |", " \\___/ ")

BANNER_ROWS: tuple[str, ...] = tuple(" ".join(row) for row in zip(_H, _A, _L, _O))

#: The ASCII banner as one block, no trailing newline.
BANNER: str = "\n".join(BANNER_ROWS)


def banner_for_encoding(encoding: str | None) -> str:
    """The block art when `encoding` (a stream's `.encoding`) can carry it,
    the ASCII form otherwise. `None` (no encoding known) -> ASCII."""
    if not encoding:
        return BANNER
    try:
        BANNER_ART.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return BANNER
    return BANNER_ART


def banner_with_version(version_line: str, encoding: str | None = "utf-8") -> str:
    """The full `halo --version` output: the wordmark, then the version
    line (`halo 2.0.5 (9f34d6d, master)` -- update.format_version_line's
    own shape) on its own row underneath."""
    return f"{banner_for_encoding(encoding)}\n{version_line}"
