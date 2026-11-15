"""tests.test_lineup_defaults -- Halo 3.3.16.0 R1b: "not set = Halo does ..." (the inspector says one thing at a time).
What Halo does when a lineup leaves a section out is one line per section in halo_harness/field_help.py
(`LINEUP_DEFAULTS`), read from the code that applies the section (each line names it in a comment), served by
`GET /api/field-help` as `lineup_defaults`, printed by the terminal's lineup view under each unset section and listed
in docs/ROLES.md; the numbers in the lines are the code's own. `halo studio --edit lineup:<name>:<block>` opens one
block's page, the blocks the same in Python and in the shell. No model is called.
Run: python -m tests.test_lineup_defaults
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"


@test
def test_every_section_has_its_default_and_names_its_source(ctx: Ctx):
    from halo_harness import field_help
    from halo_harness.teams_yaml import TOP_SECTIONS
    keys = [*TOP_SECTIONS, "isolation"]
    ctx.check(f"one line per section and isolation, got {sorted(field_help.LINEUP_DEFAULTS)}", sorted(field_help.LINEUP_DEFAULTS) == sorted(keys))
    ctx.check("lineup_default reads it, '' for anything else", field_help.lineup_default("tiers") == field_help.LINEUP_DEFAULTS["tiers"]
              and field_help.lineup_default("nope") == "")
    src = (REPO / "halo_harness" / "field_help.py").read_text(encoding="utf-8")
    block = src[src.index("LINEUP_DEFAULTS = {"):src.index("}", src.index("LINEUP_DEFAULTS = {"))]
    for key in keys:
        m = re.search(r"#([^\n]*)\n\s*\"" + key + r"\":", block)
        ctx.check(f"{key}: a comment names the code it is read from, got {m and m.group(1)!r}", bool(m) and "." in m.group(1))
    ctx.check("served as lineup_defaults", field_help.as_json()["lineup_defaults"] == field_help.LINEUP_DEFAULTS)


@test
def test_the_numbers_are_the_codes(ctx: Ctx):
    from halo_harness import field_help
    from halo_harness.agent.subagent import MAX_CONCURRENT_AGENTS, MAX_DEPTH
    from halo_harness.models_auto import DEFAULT_BAND
    d = field_help.LINEUP_DEFAULTS
    ctx.check("delegation: the spawn cap and the depth cap", f"up to {MAX_CONCURRENT_AGENTS} run at once" in d["delegation"]
              and f"agents.max_depth {MAX_DEPTH}" in d["delegation"])
    ctx.check("budget: the auto pick's band", f"band {DEFAULT_BAND}" in d["budget"])
    from halo_harness.teams_runtime import TeamControl
    tc = TeamControl(name="t", template={})
    ctx.check("no escalation: no switch", tc.escalation_decision(tool_failures=True, context_overflow=True) is None)
    ctx.check("no budget: never stops", tc.budget_refusal() is None)
    ctx.check("no pipeline: no gate", tc.stage_for("x", "y") is None and tc.gate_block(None) is None)
    ctx.check("no tiers: no tier gate", tc.tier_gate("a", "b") is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
