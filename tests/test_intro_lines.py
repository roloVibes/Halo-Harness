"""2.0.3 launch intro pool (rolo, 2026-10-05): the intro rotates through a
range of lines instead of always the same one. Pins the pool's shape, the
Red Dragon line's presence, the version substitution, the numbered pick
for `/intro <n>`, and the argument parser.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


@test
def test_pool_shape(ctx: Ctx):
    from halo_harness.tui.intro_lines import INTRO_LINES
    ctx.check("the pool has more than one line (a range, not a single copy)", len(INTRO_LINES) > 1)
    ctx.check("every line carries the {version} placeholder exactly once",
              all(line.count("{version}") == 1 for line in INTRO_LINES))
    ctx.check("every line ends with 'halo {version}'", all(line.endswith("halo {version}") for line in INTRO_LINES))
    ctx.check("the original copy-of-a-copy line is still in the pool",
              any(line.startswith("I am just a copy, of a copy, of a copy...") for line in INTRO_LINES))
    ctx.check("the Red Dragon line is in the pool",
              any("Red Dragon" in line and "keep it on the down low.. halo {version}" in line for line in INTRO_LINES))
    ctx.check("no duplicates", len(set(INTRO_LINES)) == len(INTRO_LINES))


@test
def test_intro_text_fills_the_version_and_picks_from_the_pool(ctx: Ctx):
    from halo_harness.tui.intro_lines import INTRO_LINES, intro_text
    pool = {line.format(version="9.9.9") for line in INTRO_LINES}
    rng = random.Random(1234)
    picks = {intro_text("9.9.9", rng=rng) for _ in range(60)}
    ctx.check("every random pick is a pool line with the version filled in", picks <= pool)
    ctx.check(f"60 seeded picks reach more than one line, got {len(picks)}", len(picks) > 1)
    ctx.check("the version lands at the end of the line", all(p.endswith("halo 9.9.9") for p in picks))
    ctx.check("index 0 is the first line", intro_text("1.2.3", index=0) == INTRO_LINES[0].format(version="1.2.3"))
    ctx.check("an out-of-range index wraps instead of raising",
              intro_text("1.2.3", index=len(INTRO_LINES) + 1) == INTRO_LINES[1].format(version="1.2.3"))


@test
def test_parse_intro_index(ctx: Ctx):
    from halo_harness.tui.intro_lines import parse_intro_index
    ctx.check("empty argument -> random (None)", parse_intro_index("") is None)
    ctx.check("whitespace -> None", parse_intro_index("   ") is None)
    ctx.check("'2' -> index 1 (numbered from 1 for people)", parse_intro_index("2") == 1)
    ctx.check("'1' -> index 0", parse_intro_index(" 1 ") == 0)
    ctx.check("'0' -> None (there is no line zero)", parse_intro_index("0") is None)
    ctx.check("text -> None", parse_intro_index("dragon") is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
