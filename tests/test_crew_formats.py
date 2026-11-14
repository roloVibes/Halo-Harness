"""tests.test_crew_formats -- Halo 3.6.0.0 R1: the three crew formats and their loader (halo_harness/crew/formats.py,
store.py, spec.py; docs/CREW-FORMATS.md).

1. every shipped starter is a good file of its format (10 agents, 5 workflows, 2 maps);
2. a bad agent, workflow or map answers one plain line per problem;
3. a map whose lines make a circle has its problem line, naming the circle;
4. the loader: yours, a project's (a trusted folder only) and the starters, each with its scope; `used_by`;
5. an agent of yours is what the Agent tool can spawn by name (config/agents_md.discover_agents), its tools from
   `uses`, its permission mode from `careful`; a connected tool's entry keeps that server's tools only.
Run: python -m tests.test_crew_formats
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.config_seed import ConfigHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
GOOD = {"format": "agent/1", "name": "sec", "does": "Reviews.", "model": "auto", "uses": ["read"], "careful": "ask-changes"}


@test
def test_every_starter_is_good(ctx: Ctx):
    from halo_harness.crew import store
    from halo_harness.crew.formats import PROBLEMS
    for kind, want in (("agent", 10), ("workflow", 5), ("map", 2)):
        files = sorted((store.SHIPPED / store.KINDS[kind]).glob("*.yaml"))
        ctx.check(f"{want} shipped {kind} starters, got {[p.stem for p in files]}", len(files) == want)
        for p in files:
            bad = PROBLEMS[kind](store.read(p), name=p.stem)
            ctx.check(f"{kind} {p.stem} is good, got {bad}", bad == [])
    names = {p.stem for p in (store.SHIPPED / "agents").glob("*.yaml")}
    ctx.check("the design's ten agents", names == {"main", "planner", "researcher", "coder", "implementer", "reviewer", "tester",
                                                    "writer", "media-reader", "ops"})


@test
def test_bad_files_say_what_is_wrong(ctx: Ctx):
    from halo_harness.crew.formats import agent_problems, map_problems, workflow_problems
    ctx.check("a good agent has no problem", agent_problems(GOOD, name="sec") == [])
    cases = [({**GOOD, "format": "agent/2"}, "format"), ({**GOOD, "name": "Sec Rev"}, "name"), ({**GOOD, "does": ""}, "does"),
             ({**GOOD, "uses": ["read", "shell"]}, "uses"), ({**GOOD, "careful": "yolo"}, "careful"),
             ({**GOOD, "needs": ["pdf"], "model": "or:x/y"}, "needs"), ({**GOOD, "more": {"max_usd": -1}}, "more.max_usd"),
             ({**GOOD, "more": {"hooks": {}}}, "more.hooks"), ({**GOOD, "extends": "x"}, "extends"),
             ({**GOOD, "uses": ["read", "read"]}, "uses")]
    for raw, word in cases:
        got = agent_problems(raw, name=raw.get("name") if isinstance(raw.get("name"), str) and raw["name"] == "sec" else "")
        ctx.check(f"{word}: a line naming it, got {got}", any(g.startswith(word) or word in g for g in got))
    ctx.check("the file's name must be the agent's", agent_problems(GOOD, name="other")[0].startswith("name:"))
    wf = {"format": "workflow/1", "name": "ship", "for": "x", "steps": [{"name": "a", "agents": ["coder"], "when": {"says": []},
                                                                        "repeat": {"until": "x", "max": 40}, "after": 1}]}
    got = workflow_problems(wf, name="ship")
    ctx.check(f"a workflow: its when, its repeat, the unknown field, got {got}",
              len(got) == 3 and any("when" in g for g in got) and any("repeat" in g for g in got) and any("after" in g for g in got))
    mp = {"format": "map/1", "name": "m", "boxes": [{"id": "a", "agent": "x"}, {"id": "a", "workflow": "y"}],
          "lines": [{"from": "a", "to": "main", "when": "always"}, {"from": "main", "to": "zz", "when": "sometimes"}]}
    got = map_problems(mp, name="m")
    ctx.check(f"a map: the taken id, a line to main, a box not there, its when, got {got}", len(got) == 4)


@test
def test_a_circle_is_named_and_kept_out(ctx: Ctx):
    from halo_harness.crew.formats import circle, map_problems
    boxes = [{"id": i, "agent": i} for i in ("plan", "ship", "review")]
    lines = [{"from": "main", "to": "plan", "when": "always"}, {"from": "plan", "to": "ship", "when": "always"},
             {"from": "ship", "to": "review", "when": "always"}]
    ok = {"format": "map/1", "name": "m", "boxes": boxes, "lines": lines}
    ctx.check("a chain is no circle", map_problems(ok, name="m") == [] and circle(lines) == [])
    loop = {**ok, "lines": lines + [{"from": "review", "to": "plan", "when": "always"}]}
    got = map_problems(loop, name="m")
    ctx.check(f"the line back makes a circle, named in order, got {got}", got == [
        "the lines make a circle (plan -> ship -> review -> plan): a loop lives inside a workflow as repeat until"])
    ctx.check("a box handing work to itself", circle([{"from": "a", "to": "a"}]) == ["a", "a"])


@test
def test_the_loader_and_its_scopes(ctx: Ctx):
    from halo_harness.crew import store
    with ConfigHome() as h:
        store.write_text(store.path_for("agent", "sec", state_dir=h.state), store.dump(GOOD))
        proj = h.repo / ".halo" / "crew" / "agents" / "sec.yaml"
        store.write_text(proj, store.dump({**GOOD, "does": "the project's"}))
        rows = store.rows("agent", cwd=h.repo, state_dir=h.state)
        scopes = sorted({r["_scope"] for r in rows if r["name"] == "sec"})
        ctx.check(f"an untrusted folder's crew is not read, got {scopes}", scopes == ["yours"])
        ctx.check("a starter is found by name", store.find("agent", "reviewer", cwd=h.repo, state_dir=h.state)[1] == "starter")
        wf = {"format": "workflow/1", "name": "ship", "for": "x", "steps": [{"name": "a", "agents": ["sec"]}]}
        store.write_text(store.path_for("workflow", "ship", state_dir=h.state), store.dump(wf))
        ctx.check(f"used_by names the workflow, got {store.used_by('sec', state_dir=h.state)}", store.used_by("sec", state_dir=h.state) == ["workflow ship"])
        from halo_harness import project_gate
        was = project_gate.trusted
        project_gate.trusted = lambda cwd=None: True
        try:
            got = store.load("agent", "sec", cwd=h.repo, state_dir=h.state)
            ctx.check(f"a trusted folder's file is nearest, got {got.get('_scope')}", got.get("_scope") == "project" and got["does"] == "the project's")
        finally:
            project_gate.trusted = was


@test
def test_an_agent_of_yours_is_spawnable_by_name(ctx: Ctx):
    from halo_harness.config.agents_md import discover_agents
    from halo_harness.crew import store
    with ConfigHome() as h:
        raw = {**GOOD, "name": "gate", "uses": ["read", "bash", "mcp:github"], "careful": "own", "more": {"max_turns": 7, "offline": True}}
        store.write_text(store.path_for("agent", "gate", state_dir=h.state), store.dump(raw))
        specs = discover_agents(h.repo)
        spec = specs.get("gate")
        ctx.check("the Agent tool's list has it", spec is not None and spec.source == "crew:yours")
        if spec is None:
            return
        ctx.check(f"careful own = the auto mode, got {spec.permission_mode}", spec.permission_mode == "auto")
        ctx.check(f"max_turns 7, its does as its description, got {spec.max_turns}", spec.max_turns == 7 and spec.description == "Reviews.")
        tools = spec.resolved_tools(["Read", "Glob", "Grep", "Edit", "Bash", "WebFetch", "mcp__github__get_pr", "mcp__other__x", "TodoWrite"])
        ctx.check(f"read + bash + github's tools, no edit, no other server, offline: no web, got {tools}",
                  set(tools) == {"Read", "Glob", "Grep", "Bash", "mcp__github__get_pr", "TodoWrite"})
        store.write_text(store.path_for("agent", "gate", state_dir=h.state), "format: agent/1\nname: gate\n")
        ctx.check("a file with problems is left out", "gate" not in discover_agents(h.repo))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
