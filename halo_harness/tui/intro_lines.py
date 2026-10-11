"""halo_harness.tui.intro_lines -- the pool of launch intro lines.

2.0.0 shipped one intro line (`I am just a copy, of a copy, of a copy...
halo <version>`), typed out character by character by
`tui/widgets/transcript.py::IntroLine` the first time a fresh interactive
session mounts. 2.0.3 (rolo, 2026-10-05): the intro rotates through a
range of lines instead of always the same one, and `/intro` replays a
fresh pick (or a specific one by number: `/intro 2`). 2.0.11 round A2
(rolo, 2026-10-11): the pool is the block-art wordmark plus the two
original lines -- the NIN line and the Red Dragon line -- and nothing
else; the art reveals row by row with the ring in gold and the letters in
a gradient (`banner_row_styles`).

Every entry carries the `{version}` placeholder; `intro_text()` fills it
with the installed version. Lines are plain text, no markup.
"""

from __future__ import annotations

import random

from halo_harness.banner import BANNER_ART, RING_ROWS

INTRO_LINES: tuple[str, ...] = (
    # The block-art wordmark (the same rows `halo --version` prints on a
    # UTF-8 console and the hero image draws) -- the art reveals row by
    # row, then the version lands on its own line under it.
    BANNER_ART + "\nhalo {version}",
    "I am just a copy, of a copy, of a copy... halo {version}",
    "Yeah, thanks. Took the restrictor plate off to give the Red Dragon a little more juice. "
    "But it's not exactly street legal, so keep it on the down low.. halo {version}",
)


def intro_text(version: str, index: int | None = None, rng: random.Random | None = None) -> str:
    """Return one filled-in intro line. `index` (any int; wraps) picks a
    specific line for `/intro <n>` and tests; otherwise a random one from
    `INTRO_LINES` (`rng` lets a test seed the pick)."""
    lines = INTRO_LINES
    if index is not None:
        line = lines[index % len(lines)]
    else:
        line = (rng or random).choice(lines)
    return line.format(version=version)


def parse_intro_index(args: str) -> int | None:
    """`/intro 2` -> 1 (lines are numbered from 1 for people); anything
    else, including an empty argument, -> None (random pick)."""
    text = (args or "").strip()
    if text.isdigit() and int(text) >= 1:
        return int(text) - 1
    return None


def is_banner_intro(text: str) -> bool:
    """True for the art entry (filled in or not): the one that reveals row
    by row in colour instead of character by character."""
    return text.startswith(BANNER_ART)


def _hex(color: str) -> tuple[int, int, int] | None:
    c = (color or "").strip().lstrip("#")
    if len(c) != 6:
        return None
    try:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except ValueError:
        return None


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> str:
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def banner_row_styles(palette: dict) -> list[str]:
    """One Rich style per row of the art entry (ring rows, letter rows, the
    version line): the ring in the palette's warning gold, the letters in a
    top-to-bottom gradient from the accent to the user colour, the version
    line muted. `palette` is the app's CSS-variable dict (`bridge-*` keys);
    a missing or unparsable colour falls back to the plain style."""
    rows = BANNER_ART.split("\n")
    gold = palette.get("bridge-warning", "") or ""
    a, b = _hex(palette.get("bridge-accent", "")), _hex(palette.get("bridge-user", ""))
    letters = len(rows) - RING_ROWS
    styles = [f"bold {gold}" if gold else "bold" for _ in range(RING_ROWS)]
    for i in range(letters):
        t = i / max(1, letters - 1)
        styles.append(f"bold {_mix(a, b, t)}" if a and b else "bold")
    styles.append(palette.get("bridge-muted", "") or "")
    return styles
