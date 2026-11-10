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


@test
def test_the_terminal_and_the_docs_say_the_same(ctx: Ctx):
    from halo_harness import field_help
    view = (REPO / "halo_harness" / "tui" / "dialogs" / "lineup_editor.py").read_text(encoding="utf-8")
    ctx.check("the lineup view prints the default under an unset section", 'f"(not set = Halo does: {lineup_default(section)})"' in view)
    roles = (REPO / "docs" / "ROLES.md").read_text(encoding="utf-8").replace("`", "")
    missing = [k for k, line in field_help.LINEUP_DEFAULTS.items() if line not in roles]
    ctx.check(f"docs/ROLES.md lists every line; missing {missing}", not missing)
    bundle = REPO / "halo_harness" / "studio" / "static" / "dist" / "studio.js"
    if bundle.is_file():
        js = bundle.read_text(encoding="utf-8", errors="replace")
        ctx.check("the bundle carries no copy of the lines", field_help.LINEUP_DEFAULTS["tiers"] not in js)


@test
def test_an_edit_target_opens_one_block(ctx: Ctx):
    from halo_harness.studio.edit_target import LINEUP_BLOCKS, parse
    t, _ = parse("lineup:halo-dev-cycle:budget")
    ctx.check(f"lineup:<name>:<block>, got {t}", t is not None and (t.name, t.block, t.text) == ("halo-dev-cycle", "budget", "lineup:halo-dev-cycle:budget")
              and t.query() == "?mode=agents&view=cast&edit=lineup:halo-dev-cycle:budget")
    t, _ = parse("lineup:halo-dev-cycle")
    ctx.check("no block: the summary", t is not None and t.block == "" and t.text == "lineup:halo-dev-cycle")
    for bad in ("lineup:x:nope", "bio:coder:budget", "lineup::budget"):
        got, why = parse(bad)
        ctx.check(f"{bad!r} is not a target, with a reason", got is None and why)
    defaults = (UI / "routes" / "roles" / "defaults.ts").read_text(encoding="utf-8")
    sections = (UI / "routes" / "roles" / "sections.ts").read_text(encoding="utf-8")
    head = re.findall(r'\{ id: "(\w+)", title:', defaults[defaults.index("HEAD_BLOCKS"):defaults.index("LINEUP_BLOCKS")])
    names = re.findall(r'\{ name: "(\w+)", title:', sections)
    ctx.check(f"the shell's blocks are the same, got {head + names}", tuple(head + names) == LINEUP_BLOCKS)
    edit = (UI / "shell" / "edit.ts").read_text(encoding="utf-8")
    ctx.check("the shell reads the block off the target", "lineupBlock(m[3])" in edit and "page: target.block" in edit)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
