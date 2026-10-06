"""halo_harness.tui.intro_lines -- the pool of launch intro lines.

2.0.0 shipped one intro line (`I am just a copy, of a copy, of a copy...
halo <version>`), typed out character by character by
`tui/widgets/transcript.py::IntroLine` the first time a fresh interactive
session mounts. 2.0.3 (rolo, 2026-10-05): the intro rotates through a
range of lines instead of always the same one, and `/intro` replays a
fresh pick (or a specific one by number: `/intro 2`).

Every entry carries the `{version}` placeholder; `intro_text()` fills it
with the installed version. Add a line by appending to `INTRO_LINES`
(nothing else needs to change: the picker, `/intro <n>` and the tests all
read the tuple). Lines are plain text, no markup.
"""

from __future__ import annotations

import random

from halo_harness.banner import BANNER

INTRO_LINES: tuple[str, ...] = (
    # 2.0.5 round 2d: the ASCII wordmark is the pool's first entry (the
    # same rows `halo --version` prints and the README shows) -- the
    # banner types out, then the version lands on its own line under it.
    BANNER + "\nhalo {version}",
    "I am just a copy, of a copy, of a copy... halo {version}",
    "Yeah, thanks. Took the restrictor plate off to give the Red Dragon a little more juice. "
    "But it's not exactly street legal, so keep it on the down low.. halo {version}",
    "Local when you want it, cloud when you need it... halo {version}",
    "Your files, your models, your rules... halo {version}",
    "Same keyboard, different brain. Go on, try me... halo {version}",
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
