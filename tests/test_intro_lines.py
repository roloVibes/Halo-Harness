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
def test_banner_is_the_first_pool_entry_and_matches_readme(ctx: Ctx):
    """2.0.5 round 2d: the ASCII wordmark (banner.py) is INTRO_LINES[0] --
    banner rows, then 'halo {version}' on its own line under the art --
    and the README carries the exact same rows in its fenced banner block,
    so the intro animation, `halo --version` and the front page can never
    drift apart."""
    from halo_harness.banner import BANNER, BANNER_ART, RING_ROWS, banner_for_encoding
    from halo_harness.tui.intro_lines import INTRO_LINES, banner_row_styles, is_banner_intro
    first = INTRO_LINES[0]
    ctx.check("pool entry 0 is the block art followed by the version line",
              first == BANNER_ART + "\nhalo {version}")
    ctx.check("the pool is exactly the art, the NIN line and the Red Dragon line (2.0.11 round A2)",
              len(INTRO_LINES) == 3)
    ctx.check("every art row stays under 48 columns and every ASCII row under 80",
              all(len(row) < 48 for row in BANNER_ART.split("\n")) and all(len(row) < 80 for row in BANNER.split("\n")))
    ctx.check("the art is block elements and box-drawing shadows, no plain letters",
              not any(ch.isalpha() for ch in BANNER_ART))
    ctx.check("utf-8 streams get the art, cp1252 streams the ASCII form, no encoding the ASCII form",
              banner_for_encoding("utf-8") == BANNER_ART and banner_for_encoding("cp1252") == BANNER
              and banner_for_encoding(None) == BANNER)
    ctx.check("is_banner_intro tells the art entry from the typed lines",
              is_banner_intro(first.format(version="1")) and not any(is_banner_intro(l) for l in INTRO_LINES[1:]))
    styles = banner_row_styles({"bridge-warning": "#f9e2af", "bridge-accent": "#89b4fa",
                                "bridge-user": "#cba6f7", "bridge-muted": "#9399b2"})
    ctx.check("one style per art row plus the version line", len(styles) == len(BANNER_ART.split("\n")) + 1)
    ctx.check("ring rows are gold, the first letter row the accent, the last the user colour, the version muted",
              styles[:RING_ROWS] == ["bold #f9e2af"] * RING_ROWS and styles[RING_ROWS] == "bold #89b4fa"
              and styles[-2] == "bold #cba6f7" and styles[-1] == "#9399b2")
    ctx.check("a palette with no colours still yields plain styles",
              all(s in ("bold", "") for s in banner_row_styles({})))
    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
    # rstrip on both sides: the art itself is pinned, while invisible
    # trailing spaces inside the fenced block stay a non-issue if an
    # editor or hook ever strips them.
    ctx.check("the README's banner block is the same art, row for row",
              all(row.rstrip() in readme for row in BANNER_ART.split("\n")))


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
