"""tests.test_found_live_third -- the small ones of Halo 3.4.1.1 "Found live, the third pass" (the 3.4.1.0 two-machine
check, defects 38-66), one test each where nothing bigger pins them: 46 the TUI's mode word, 49 an away member's today
after a hub restart, and the cosmetic ones.
Run: python -m tests.test_found_live_third
"""
from __future__ import annotations
from tests.helpers import fleet_pack as _fleet_pack  # noqa: E402  (the fleet pack on, its modules by their old names)
_fleet_pack.on()

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
def test_49_an_away_member_the_hub_has_not_heard_today_is_unknown(ctx: Ctx):
    import time
    from halo_harness.fleet.hub_links import Member
    from halo_harness.live import caps
    m = Member({"id": "h-pc", "name": "you@tower"}, None)
    f = m.today_fields()
    ctx.check(f"a hub that restarted has heard nothing: unknown, not $0: {f}", f["cost_today"] is None and f["cost_today_complete"] is False)
    spent = caps.spend({"harnesses": [{"id": "h-pc", "name": "you@tower", "sessions": [], **f}]}, time.time())
    ctx.check(f"the caps say the fleet's figure is not whole: {spent['complete']} {spent['harnesses'][0].get('unknown')}",
              spent["complete"] is False and "not heard since the hub started" in spent["harnesses"][0]["unknown"][0])
    m.note_costs([], {"cost_today": 0.360901, "sessions_today": 20})
    f = m.today_fields()
    ctx.check(f"its next announce says it: {f['cost_today']}", f["cost_today"] == 0.360901 and f["cost_today_complete"] is True)
    fmt = (REPO / "halo_harness" / "studio" / "ui" / "src" / "routes" / "orchestra" / "format.ts").read_text(encoding="utf-8")
    ctx.check("Live's machine box says unknown for it", 'h.cost_today === null' in fmt and 'return "unknown"' in fmt)


@test
def test_38_39_41_the_fix_once_both_rules_and_the_pipe(ctx: Ctx):
    from halo_harness.fleet.mission_doc import mission_md, status_table
    doc = {"id": "m-1", "state": "running", "goal": "scan", "parts": {"2": {"harness_name": "kali@kali", "state": "failed",
                                                                             "error": "not done: nobody answered Bash nmap --version | head -1"}}}
    table = status_table(doc)
    ctx.check(f"41: the plain table keeps the pipe (it read `/ head -1`, like a path): {table!r}",
              "nmap --version | head -1" in table and "/ head" not in table)
    md = mission_md(doc, {"parts": [{"id": "1", "kind": "files", "title": "run a | b", "reason": "x", "needs": [], "claims": []}]})
    ctx.check("MISSION.md's markdown table escapes it", "run a \\| b" in md)
    src = (REPO / "halo_harness" / "packs" / "doctor.py").read_text(encoding="utf-8")
    ctx.check("38: pack doctor says the update command once, as the fix (test_packs_shipped_newer runs it)",
              'r["line"].removesuffix(f": {fix(r)}")' in src)
    fw = (REPO / "halo_harness" / "peers" / "firewall.py").read_text(encoding="utf-8")
    ctx.check("39: the firewall line counts the UDP twins (test_fleet_firewall runs it)", "for TCP{f' and {udp} for UDP'" in fw)


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
