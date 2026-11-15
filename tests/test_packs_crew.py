"""tests.test_packs_crew -- extension API 2.0, a pack's crew (Halo 3.6.0.0 R5b; halo_harness/packs/crew_v1.py,
crew/store.py's pack scope; docs/EXTENSION_API.md "A pack's crew"):

1. the shipped doc-review pack (2.0: crew/agents, crew/workflows, crew/maps), enabled: its agents, workflow and map are
   read in place as `doc-review--<name>`; a session built here can spawn its agent, its map compiles, and the Workflow
   tool's names include its workflow; nothing of it is in a session while it is disabled; no 1.x line for it;
2. a 1.x pack (bios, a lineup, a plain workflow, a workflow with a human gate), enabled: its bios are agents, its lineup
   a map (main, a box per card, the routing words as `says`, the cap), its plain workflow a workflow; `halo pack list`
   and `halo pack doctor` say in one line what is not carried; the pack still installs and enables on 2.0;
3. 3.6.0.0 R5c (the judge's S1-S4, S9, S11, the two suspects): a bare 3.5 name of exactly one pack's map / agent /
   workflow reads it (`--map`, `halo maps use`, `--agent`, a workflow's name) with one line naming it in full, several
   name them all, and `--team` / config `team:` say the exact command; a lineup naming Halo's own bios (default-model,
   auto-*, the stock names) is a map that compiles, `extends:` is followed, one naming no agent here is left out and
   named; a lineup's delegation is the map's depth and parallel caps (a session runs at that depth); `halo pack list`
   counts agents, maps and workflows and says "made for extension API 1.x ... read as 1.x"; `tools.allow: [WebFetch]` is
   WebFetch only; a workflow that is not plain runs on the run engine (`halo orchestra new --workflow`) and the line
   says so.
Run: python -m tests.test_packs_crew
"""
from __future__ import annotations

import contextlib
import json
import os
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
# 3.6.0.0 R5c: a second 1.x pack with Halo's own bio names, `extends:`, a delegation and a WebFetch-only bio
MORE = {
    "pack.yaml": ('id: more-pack\nname: More pack\nversion: 1.0.0\ndescription: a 1.x pack leaning on Halo bios\n'
                  'halo_api: {min: "1.0"}\ncontributes:\n  agents: [agents/fetcher.yaml]\n'
                  '  teams: [teams/base.yaml, teams/child.yaml, teams/odd.yaml]\n'),
    "agents/fetcher.yaml": "name: fetcher\ndescription: Opens the pages it is given.\ntools: {allow: [Read, WebFetch]}\n",
    "teams/base.yaml": ("name: base\nagents:\n  - {agent: default-model, role: main}\n  - {agent: auto-coder, role: coder}\n"
                        "  - {agent: fetcher, role: researcher}\nrouting: {fix: coder, fetch: researcher}\n"
                        "delegation: {max_depth: 3, max_parallel: 2}\n"),
    "teams/child.yaml": "name: child\nextends: base\nbudget: {max_budget_usd: 5}\n",
    "teams/odd.yaml": "name: odd\nagents:\n  - {agent: default-model, role: main}\n  - {agent: watchdog, role: watch}\n",
}


def _more_pack(h) -> Path:
    src = h.sources / "more-pack"
    for rel, text in MORE.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    return src


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


@test
def test_a_bare_35_name_reads_the_packs_one(ctx: Ctx):
    import io
    from contextlib import redirect_stderr
    from halo_harness.crew import store
    from halo_harness.crew.compile import compile_map, for_session
    from halo_harness.crew.old_files import team_line
    from halo_harness.theme import get_config_value, set_config_value
    with PacksHome() as h:
        h.install(_old_pack(h), enable=True)
        c = compile_map("hunt", cwd=h.repo)
        ctx.check(f"compile_map('hunt') reads old-pack--hunt, got {c.name} {c.problems}",
                  c.name == "old-pack--hunt" and not c.problems)
        got, lines = for_session("hunt", cwd=h.repo)
        ctx.check(f"--map hunt: the map, one line naming it in full, got {getattr(got, 'name', None)} {lines}",
                  getattr(got, "name", None) == "old-pack--hunt" and lines == [
                      "halo: map hunt is old-pack--hunt (an enabled pack's; its full name from now on)"])
        from halo_harness.crew.flow_door import named
        ctx.check("an agent and a workflow read bare too, and the Workflow tool runs it by that name",
                  (store.load("agent", "scout", cwd=h.repo) or {}).get("name") == "old-pack--scout"
                  and (store.load("workflow", "sweep", cwd=h.repo) or {}).get("name") == "old-pack--sweep"
                  and (named("sweep", h.repo) or {}).get("name") == "old-pack--sweep"
                  and store.resolve("workflow", "sweep", cwd=h.repo)[1].startswith("halo: workflow sweep is old-pack--sweep"))
        from halo_harness.maps_cli import cmd_maps
        cwd = os.getcwd()
        os.chdir(h.repo)
        try:
            err = io.StringIO()
            with redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = cmd_maps(["use", "hunt"])
        finally:
            os.chdir(cwd)
        ctx.check(f"halo maps use hunt: the full name in use, one line, got {code} {get_config_value('crew.map', None)} "
                  f"{err.getvalue()!r}", code == 0 and get_config_value("crew.map", None) == "old-pack--hunt"
                  and "map hunt is old-pack--hunt" in err.getvalue())
        from halo_harness import headless
        for flags, agent, want in (({}, "scout", "halo: agent scout is old-pack--scout (an enabled pack's; its full name from now on)"),
                                   ({"team": "hunt"}, None, "(--map old-pack--hunt runs it)")):
            err = io.StringIO()
            with redirect_stderr(err):
                s_ = headless.build_session(cwd=h.repo, model_ref_raw="or:v/eyes", print_mode=True, cli_flags=flags,
                                            agent=agent).session
            s_.close_runtimes()
            ctx.check(f"{'--agent scout' if agent else '--team hunt'}: one line with the full name, got {err.getvalue()!r}",
                      want in err.getvalue() and "unknown --agent" not in err.getvalue())
        set_config_value("crew.map", None)
        set_config_value("team", "hunt")
        ctx.check(f"config team: hunt says the exact command, got {team_line()!r}", "halo maps use old-pack--hunt" in team_line())
        h.install(_more_pack(h), enable=True)
        (h.sources / "twin-pack").mkdir()
        for rel, text in OLD.items():
            text = text.replace("id: old-pack", "id: twin-pack")
            (h.sources / "twin-pack" / rel).parent.mkdir(parents=True, exist_ok=True)
            (h.sources / "twin-pack" / rel).write_text(text, encoding="utf-8")
        h.install(h.sources / "twin-pack", enable=True)
        _n, said = store.resolve("map", "hunt", cwd=h.repo)
        ctx.check(f"two packs' hunt: one line naming both, got {said!r}",
                  said == "halo: map hunt could be old-pack--hunt, twin-pack--hunt: name one in full")


@test
def test_halos_bio_names_extends_and_delegation_are_carried(ctx: Ctx):
    from halo_harness.crew import store
    from halo_harness.crew.compile import compile_map
    from halo_harness.crew.map_control import control_for
    from halo_harness.crew.spec import crew_specs
    with PacksHome() as h:
        h.install(_more_pack(h), enable=True)
        base = compile_map("more-pack--base", cwd=h.repo)
        ctx.check(f"default-model is main, auto-coder the starter coder, got {base.problems} {base.main.get('agent')} "
                  f"{base.agent_targets()}", not base.problems and base.main.get("agent") == "main"
                  and base.agent_targets() == ["coder", "more-pack--fetcher"])
        ctx.check(f"the delegation is the map's caps, got {base.delegation}", base.delegation == {"max_depth": 3, "max_parallel": 2})
        mc = control_for(base, cwd=h.repo)
        ctx.check(f"its control answers them (no knob set), got {mc.delegation} {mc.yields_to('agents.max_depth')}",
                  mc.delegation == {"max_depth": 3, "max_parallel": 2} and not mc.yields_to("agents.max_depth"))
        child = compile_map("more-pack--child", cwd=h.repo)
        ctx.check(f"extends: base's cards and delegation, its own cap, got {child.problems} {child.agent_targets()} "
                  f"{child.delegation} {child.cap_usd}", not child.problems and child.agent_targets() == base.agent_targets()
                  and child.delegation == base.delegation and child.cap_usd == 5)
        ctx.check("a lineup naming no agent here is not carried", store.find("map", "more-pack--odd", cwd=h.repo) is None)
        code, out, _err = h.cli("list")
        row = next((x for x in out.splitlines() if x.startswith("more-pack ")), "")
        line = next((x for x in out.splitlines() if x.startswith("pack more-pack:")), "")
        ctx.check(f"halo pack list counts agents and maps, and says what it was made for, got {row!r}",
                  "offers 1 agent, 2 maps" in row and "bio" not in row.split("  (made")[0]
                  and "lineup" not in row.split("  (made")[0]
                  and "made for extension API 1.0 or a later 1.x; read by this Halo's 2.0 as 1.x" in row)
        ctx.check(f"and names the lineup it left, with why, got {line!r}",
                  "lineup odd not carried (names watchdog, which is no agent here)" in line and "EXTENSION_API.md" in line
                  and line.count("(") == line.count(")"))
        spec = crew_specs(h.repo).get("more-pack--fetcher")
        ctx.check(f"tools.allow [Read, WebFetch] is WebFetch only, got {getattr(spec, 'tools', None)}",
                  spec is not None and "WebFetch" in spec.tools and "WebSearch" not in spec.tools)
        agent = store.clean(store.load("agent", "more-pack--fetcher", cwd=h.repo) or {})
        ctx.check(f"its uses say fetch, got {agent.get('uses')}", agent.get("uses") == ["read", "fetch"])


@test
def test_a_session_on_a_1x_map_runs_at_its_depth(ctx: Ctx):
    from halo_harness import headless
    with PacksHome() as h:
        h.install(_more_pack(h), enable=True)
        s = headless.build_session(cwd=h.repo, model_ref_raw="or:v/eyes", print_mode=True,
                                   cli_flags={"map": "more-pack--base"}).session
        try:
            rt = s.agent_runtime
            got = (getattr(s.team_control, "map_name", None), rt.max_depth, rt.max_concurrent)
        finally:
            s.close_runtimes()
    ctx.check(f"the map's depth and parallel caps, got {got}", got[0] == "more-pack--base" and got[1] == 3 and got[2] == 2)


@test
def test_a_workflow_that_is_not_plain_runs_on_the_run_engine(ctx: Ctx):
    import io
    from halo_harness.orchestra_cli import cmd_orchestra
    from halo_harness.packs.crew_v1 import left_line
    from halo_harness.packs.discover import find
    with PacksHome() as h:
        h.install(_old_pack(h), enable=True)
        line = left_line(find("old-pack", cwd=h.repo))
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cmd_orchestra(["new", "--workflow", "old-pack/gated", "--repo", str(h.repo)])
    ctx.check(f"the line says where it runs, got {line!r}", "1 workflow (gated) run on the run engine only "
              "(halo orchestra new --workflow old-pack/<name>)" in line)
    ctx.check(f"and it does: halo orchestra new --workflow old-pack/gated, got {code} {out.getvalue()[-300:]!r}",
              code == 0 and "workflow old-pack/gated" in out.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
