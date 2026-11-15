"""tests.test_packs_crew -- extension API 2.0, a pack's crew (Halo 3.6.0.0 R5b; halo_harness/packs/crew_v1.py,
crew/store.py's pack scope; docs/EXTENSION_API.md "A pack's crew"):

1. the shipped doc-review pack (2.0: crew/agents, crew/workflows, crew/maps), enabled: its agents, workflow and map are
   read in place as `doc-review--<name>`; a session built here can spawn its agent, its map compiles, and the Workflow
   tool's names include its workflow; nothing of it is in a session while it is disabled; no 1.x line for it;
2. a 1.x pack (bios, a lineup, a plain workflow, a workflow with a human gate), enabled: its bios are agents, its lineup
   a map (main, a box per card, the routing words as `says`, the cap), its plain workflow a workflow; `halo pack list`
   and `halo pack doctor` say in one line what is not carried; the pack still installs and enables on 2.0.
Run: python -m tests.test_packs_crew
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

OLD = {
    "pack.yaml": ('id: old-pack\nname: Old pack\nversion: 1.0.0\ndescription: a 1.x pack with bios and a lineup\n'
                  'halo_api: {min: "1.2", max: "1.9"}\ncontributes:\n  agents: [agents/scout.yaml, agents/lead.yaml]\n'
                  '  teams: [teams/hunt.yaml]\n  workflows: [sweep, gated]\n'),
    "agents/scout.yaml": ("name: scout\ndescription: Finds what the task asks.\nmodels: {preference: default, needs: [long-context]}\n"
                          "tools: {allow: [Read, Grep, Bash]}\ncontext: {system_prompt: You find things.}\n"
                          "limits: {max_iterations: 12, max_budget_usd: 2}\n"),
    "agents/lead.yaml": "name: lead\ndescription: Leads the hunt.\nmodels: {preference: default}\ntools: {permission_mode: auto}\n",
    "teams/hunt.yaml": ("name: hunt\ndescription: the lead and a scout\nagents:\n  - {agent: lead, role: main}\n"
                        "  - {agent: scout, role: researcher, as: scout}\nrouting: {find: scout}\n"
                        "budget: {max_budget_usd: 9}\ntiers:\n  - {name: lead, members: [main]}\n"),
    "workflows/sweep.yaml": ("name: sweep\ndescription: Sweep the repo.\nstages:\n  - {id: look, title: Look around, role: scout, brief: Look, "
                             "gives: [{name: notes, kind: summary}]}\n  - {id: tell, title: Tell, role: lead, brief: Tell, after: [look]}\n"),
    "workflows/gated.yaml": ("name: gated\ndescription: Needs you.\nstages:\n  - {id: look, title: Look, role: scout, brief: Look, gate: human}\n"),
}


def _old_pack(h) -> Path:
    src = h.sources / "old-pack"
    for rel, text in OLD.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    return src


@test
def test_a_2_0_packs_crew_reaches_a_session(ctx: Ctx):
    from halo_harness.crew import store
    from halo_harness.crew.compile import compile_map
    from halo_harness.crew.flow_door import names
    from halo_harness.crew.spec import crew_specs
    from halo_harness.packs.crew_v1 import left_line
    with PacksHome() as h:
        h.install(h.source(), enable=False)
        ctx.check("disabled: nothing of it", store.load("agent", "doc-review--reviewer", cwd=h.repo) is None
                  and "doc-review--reviewer" not in crew_specs(h.repo))
        from halo_harness.packs.grants import enable
        from halo_harness.packs.discover import find
        from halo_harness.packs import registry
        enable(find("doc-review", cwd=h.repo), grant=[])
        registry.invalidate()
        got = store.load("agent", "doc-review--reviewer", cwd=h.repo) or {}
        ctx.check(f"its agent is read in place, got {got.get('_scope')} {got.get('_path')}",
                  got.get("_scope") == "pack" and str(got.get("_path", "")).replace("\\", "/").endswith("crew/agents/reviewer.yaml")
                  and got.get("name") == "doc-review--reviewer")
        ctx.check("a session can spawn it", "doc-review--reviewer" in crew_specs(h.repo))
        c = compile_map("doc-review--review", cwd=h.repo)
        ctx.check(f"its map compiles, got {c.problems}", not c.problems and c.agent_targets() == ["doc-review--reviewer"]
                  and c.main.get("agent") == "doc-review--writer")
        ctx.check(f"its workflow is offered by name, got {names(h.repo)}", "doc-review--review-docs" in names(h.repo))
        ctx.check("a 2.0 pack has no 1.x line", left_line(find("doc-review", cwd=h.repo)) == "")


@test
def test_a_1_x_packs_bios_lineup_and_plain_workflow_are_read(ctx: Ctx):
    from halo_harness.crew import store
    from halo_harness.crew.compile import compile_map
    with PacksHome() as h:
        h.install(_old_pack(h), enable=True)
        scout = store.clean(store.load("agent", "old-pack--scout", cwd=h.repo) or {})
        ctx.check(f"a bio is an agent, got {scout}", scout.get("model") == "auto" and scout.get("needs") == ["long-text"]
                  and scout.get("uses") == ["read", "bash"] and scout.get("instructions") == "You find things."
                  and scout.get("more") == {"max_turns": 12, "max_usd": 2})
        lead = store.clean(store.load("agent", "old-pack--lead", cwd=h.repo) or {})
        ctx.check(f"permission_mode auto is careful: own, got {lead.get('careful')}", lead.get("careful") == "own")
        c = compile_map("old-pack--hunt", cwd=h.repo)
        ctx.check(f"a lineup is a map, got {c.problems} {c.handoffs} {c.cap_usd}", not c.problems
                  and c.main.get("agent") == "old-pack--lead" and [h_["name"] for h_ in c.handoffs] == ["old-pack--scout"]
                  and c.handoffs[0]["when"] == {"says": ["find"]} and c.cap_usd == 9)
        wf = store.load("workflow", "old-pack--sweep", cwd=h.repo) or {}
        ctx.check(f"a plain workflow is a workflow, got {wf.get('steps')}",
                  [s["agents"] for s in wf.get("steps") or []] == [["old-pack--scout"], ["old-pack--lead"]])
        ctx.check("a gated one is not", store.load("workflow", "old-pack--gated", cwd=h.repo) is None)
        code, out, _err = h.cli("list")
        line = [x for x in out.splitlines() if x.startswith("pack old-pack:")]
        ctx.check(f"halo pack list says it in one line, got {line}", code == 0 and len(line) == 1
                  and "1 workflow (gated)" in line[0] and "tiers" in line[0])
        code, out, _err = h.cli("doctor", "--json")
        rows = [r for r in json.loads(out)["problems"] if r["check"] == "crew-1x"]
        ctx.check(f"halo pack doctor: one info row, got {rows}", len(rows) == 1 and rows[0]["severity"] == "info")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
