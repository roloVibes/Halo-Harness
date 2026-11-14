"""tests.test_found_live_third -- the small ones of Halo 3.4.1.1 "Found live, the third pass" (the 3.4.1.0 two-machine
check, defects 38-66), one test each where nothing bigger pins them: 46 the TUI's mode word, 49 an away member's today
after a hub restart, and the cosmetic ones.
Run: python -m tests.test_found_live_third
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


@test
def test_46_the_tui_calls_default_default(ctx: Ctx):
    from halo_harness.tui.theme import mode_glyph
    ctx.check(f"the status bar's word for `default` is default (its cards, Studio and the note say so): {mode_glyph('default')!r}",
              mode_glyph("default") == "⏸ default" and "manual" not in mode_glyph("default"))


@test
def test_47_a_new_files_diff(ctx: Ctx):
    from halo_harness.tui.widgets.diffview import unified_diff_text
    got = unified_diff_text("", "8", path="/tmp/t/srepo/total.txt").splitlines()
    ctx.check(f"a Write of a new file: @@ -0,0 +1 @@ then +8, no `-` line, got {got}",
              got[2] == "@@ -0,0 +1 @@" and got[3:] == ["+8"])
    got = unified_diff_text("a\nb", "a\nc").splitlines()
    ctx.check(f"a last line without its newline never runs into the next one, got {got}", "-b" in got and "+c" in got)
    ctx.check("nothing changed says so", unified_diff_text("", "") == "(no changes)")


@test
def test_61_compare_says_how_often_it_asked(ctx: Ctx):
    from halo_harness.live.compare_text import differed
    row = lambda key, a, b, better="a": {"key": key, "label": key, "a": {"value": a, "text": ""}, "b": {"value": b, "text": ""},  # noqa: E731
                                         "better": better}
    rows = [row("ended", 0, 0, "same"), row("cost", 0, 0, "same") | {"word": "same"}, row("wall", 1, 1, "same"), row("models", [], [], "same"),
            row("failures", 0, 0, "same"), row("asks", 2, 3), row("retries", 0, 0, "same"), row("tokens", 1, 1, "same"),
            row("agents", 1, 1, "same")]
    lines = differed(rows, {}, {})
    ctx.check(f"`A asked you 2 times; B 3 times.`, not `2 ask to yous`, got {lines}",
              any(x == "A asked you 2 times; B 3 times." for x in lines) and not any("ask to yous" in x for x in lines))


@test
def test_55_no_source_says_an_invalid_escape(ctx: Ctx):
    """`halo replay clip` first printed replay_clip.py:131's SyntaxWarning (a `\\s` in a plain string); permissions_ps.py's
    docstring had one too. No module of Halo's may: each compiles here with that warning made an error."""
    import warnings
    bad = []
    for p in sorted((REPO / "halo_harness").rglob("*.py")):
        if "node_modules" in p.parts:
            continue
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always")
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
        bad += [f"{p.relative_to(REPO)}: {w.message}" for w in seen if "invalid escape sequence" in str(w.message)]
    ctx.check(f"no invalid escape sequence anywhere, got {bad[:5]}", bad == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
