"""tests.test_crew_compile -- Halo 3.6.0.0 R3: a map compiles to what a session already runs (halo_harness/crew/
compile.py, map_control.py, map_session.py; docs/CREW-sessions.md).

1. PARITY: a map that mirrors today's auto lineup (main + a "main decides per task" line to each pool member, each
   agent file mirroring its auto bio, and the media workflow) gives a session whose main tools, main model and mode,
   and -- for the same tasks -- the spawned child's model pick (models_auto, a seeded catalog) and permission mode
   equal today's; the child's tools are its `uses` (agent/1), every tool under the lineup: the one designed difference;
2. the compile: main's config, the hand-off table, the chains, the specs (role = the agent's name), the cap;
3. a map with a problem (a missing agent, a circle, a bad file) gives no session config and its problem lines;
4. a changed map compiles again at the next hand-off and says so once; with `crew.map` unset nothing changes.
Seeded catalog, no model call. Run: python -m tests.test_crew_compile
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import catalog_facts_seed as S  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
POOL = {"planner": ["reasoning"], "researcher": ["long-text"], "coder": ["tools"], "reviewer": ["reasoning"], "media": [],
        "writer": [], "ops": []}
TASKS = [("plan the migration of the billing tables", "planner"), ("research how the cache invalidates", "researcher"),
         ("implement the retry in client.py", "coder"), ("review the diff for the login change", "reviewer"),
         ("describe the screenshot shot.png", "media"), ("summarize the release notes", "writer"),
         ("deploy the staging build", "ops")]
MAIN = "or:v/eyes"


def _agent(name: str, needs: list) -> str:
    n = f"needs: [{', '.join(needs)}]\n" if needs else ""
    return (f"format: agent/1\nname: {name}\ndoes: The {name} of the pool, mirrored.\nmodel: auto\n{n}"
            "uses: [read, edit, bash, web]\ncareful: ask-changes\n")


def _mirror(state: Path) -> None:
    crew = state / "crew"
    (crew / "agents").mkdir(parents=True, exist_ok=True)
    (crew / "maps").mkdir(parents=True, exist_ok=True)
    for name, needs in POOL.items():
        (crew / "agents" / f"{name}.yaml").write_text(_agent(name, needs), encoding="utf-8")
    boxes = "".join(f"- {{id: {n}, agent: {n}}}\n" for n in POOL) + "- {id: media-flow, workflow: media}\n"
    lines = "".join(f"- {{from: main, to: {n}, when: main-decides}}\n" for n in list(POOL) + ["media-flow"])
    (crew / "maps" / "mirror.yaml").write_text(f"format: map/1\nname: mirror\nboxes:\n{boxes}lines:\n{lines}main: {{agent: main}}\n",
                                               encoding="utf-8")


def _session(repo: Path, flags: dict):
    from halo_harness import headless
    return headless.build_session(cwd=repo, model_ref_raw=MAIN, print_mode=True, cli_flags=flags).session


def _child(session, spec, role, task: str) -> dict:
    from halo_harness.agent import subagent
    child, _meta = subagent._build_child_session(runtime=session.agent_runtime, spec=spec, agent_id=f"t{abs(hash(task)) % 10**8:08d}",
                                                 role_override=role, task_text=task, model_override=None, parent_tool_use_id="t")
    out = {"model": child.model_ref.raw, "mode": child.permission_engine.mode, "tools": sorted(child.tool_registry.names())}
    try:
        child.close_runtimes()
    except Exception:
        pass
    return out


@test
def test_a_map_that_mirrors_the_auto_lineup_runs_as_it(ctx: Ctx):
    from halo_harness.crew.map_run import _choose
    from halo_harness.models_best_at import rebuild
    from halo_harness.crew.spec import TOOLS
    with S.home("crew-parity-") as (root, state):
        env = S.seed(state)
        rebuild(state, list(S.rows_by_ref(state, env).values()))
        _mirror(state)
        repo = root / "repo"
        repo.mkdir()
        today, mapped = _session(repo, {}), _session(repo, {"map": "mirror"})
        tc, mc = today.team_control, mapped.team_control
        ctx.check(f"today: the auto lineup; on the map: the map, got {getattr(tc, 'name', None)} / {getattr(mc, 'name', None)}",
                  getattr(tc, "name", None) == "auto" and getattr(mc, "is_map", False))
        ctx.check(f"main's tools are the same, got only-today {sorted(set(today.tool_registry.names()) - set(mapped.tool_registry.names()))} "
                  f"only-map {sorted(set(mapped.tool_registry.names()) - set(today.tool_registry.names()))}",
                  sorted(today.tool_registry.names()) == sorted(mapped.tool_registry.names()))
        ctx.check(f"main's model and mode, got {today.model_ref.raw}/{today.permission_engine.mode} vs {mapped.model_ref.raw}/"
                  f"{mapped.permission_engine.mode}", (today.model_ref.raw, today.permission_engine.mode) ==
                  (mapped.model_ref.raw, mapped.permission_engine.mode))
        ctx.check("the Agent tool's targets are the pool's names", set(mc.map.agent_targets()) == set(POOL) and
                  set(POOL) <= set(tc.aliases))
        gp = today.agent_runtime.agents["general-purpose"]
        rows = []
        for task, who in TASKS:
            _kind, alias = tc.route_call({"description": task, "prompt": task}, task)
            h, _why, refusal = _choose(mc, "agent", who, task, (), mapped.agent_runtime)  # main decides per task: it names who
            a = _child(today, gp, alias, task)
            b = _child(mapped, mapped.agent_runtime.agents[h["name"]], None, task)
            rows.append((task, alias, a, h["name"], b))
            ctx.check(f"{task!r}: today routes to {alias}, the map's main names {who}", alias == who and not refusal)
            ctx.check(f"{task!r}: the same model pick, got {a['model']} vs {b['model']}", a["model"] == b["model"])
            ctx.check(f"{task!r}: the same permission mode, got {a['mode']} vs {b['mode']}", a["mode"] == b["mode"])
            want = sorted({"TodoWrite", *[t for k in ("read", "edit", "bash", "web") for t in TOOLS[k]]} & set(a["tools"]))
            ctx.check(f"{task!r}: the map's child has its uses, the lineup's every tool", b["tools"] == want and
                      set(b["tools"]) <= set(a["tools"]))
        picks = {r[2]["model"] for r in rows}
        ctx.check(f"the picks differ by need (the catalog is seeded), got {sorted(picks)}", len(picks) >= 2)
        for task, alias, a, name, b in rows:
            print(f"  parity | {task[:34]:<34} | today {alias:<10} {a['model']:<26} {a['mode']:<8} {len(a['tools'])} tools"
                  f" | map {name:<10} {b['model']:<26} {b['mode']:<8} {len(b['tools'])} tools")
        for s in (today, mapped):
            s.close_runtimes()


@test
def test_the_compile_main_handoffs_chains_specs_cap(ctx: Ctx):
    from halo_harness.crew.compile import compile_map
    with S.home("crew-compile-") as (root, _state):
        c = compile_map("ship-it", cwd=root)
        ctx.check(f"ship-it compiles, got {c.problems}", c.problems == [])
        ctx.check("main: the starter main (auto -> the session's model, ask-changes -> default)",
                  c.main["agent"] == "main" and c.main["model"] is None and c.main["mode"] == "default" and "bash" in c.main["uses"])
        ctx.check(f"one line from main, to the plan workflow, got {[h['line'] for h in c.handoffs]}",
                  [(h["line"], h["kind"], h["name"]) for h in c.handoffs] == [("main -> plan", "workflow", "plan")])
        ctx.check(f"the chain plan -> code -> review, got {c.chains}",
                  [e["line"] for e in c.chains["plan"]] == ["plan -> code"] and [e["line"] for e in c.chains["code"]] == ["code -> review"])
        ctx.check("the cap", c.cap_usd == 20.0)
        s = compile_map("starter", cwd=root)
        ctx.check("starter: seven agent targets, each spec's role its own name, modes from careful",
                  len(s.agent_targets()) == 7 and all(sp.role == n for n, sp in s.specs.items())
                  and s.specs["coder"].permission_mode == "acceptEdits" and s.specs["planner"].permission_mode == "default")
        ctx.check("an agent's needs reach Auto in its words", s.needs_of("media-reader") == ["vision", "pdf"])


@test
def test_a_map_with_a_problem_starts_no_half_session(ctx: Ctx):
    from halo_harness.crew.compile import for_session
    from halo_harness.theme import set_config_value
    with S.home("crew-problem-") as (root, state):
        (state / "crew" / "maps").mkdir(parents=True)
        (state / "crew" / "maps" / "broken.yaml").write_text(
            "format: map/1\nname: broken\nboxes:\n- {id: a, agent: nobody}\n- {id: b, agent: coder}\n"
            "lines:\n- {from: main, to: a}\n- {from: a, to: b}\n- {from: b, to: a}\n", encoding="utf-8")
        got, lines = for_session("broken", cwd=root)
        text = "\n".join(lines)
        ctx.check(f"no config, the problem lines (the circle named, the missing agent), got {lines}",
                  got is None and "circle (a -> b -> a)" in text and "no agent named nobody" in text and "runs as with no map" in lines[0])
        ctx.check("no map set: nothing", for_session(None, cwd=root) == (None, []))
        set_config_value("crew.map", "ship-it")
        got, lines = for_session(None, cwd=root)
        ctx.check("config crew.map: that map", got is not None and got.name == "ship-it" and lines == [])


@test
def test_a_changed_map_applies_at_the_next_hand_off_said_once(ctx: Ctx):
    import os
    import time
    from halo_harness.crew.compile import compile_map
    from halo_harness.crew.map_control import CHANGED, MapControl
    with S.home("crew-refresh-") as (root, state):
        (state / "crew" / "maps").mkdir(parents=True)
        path = state / "crew" / "maps" / "mine.yaml"
        path.write_text("format: map/1\nname: mine\nboxes:\n- {id: coder, agent: coder}\nlines:\n- {from: main, to: coder}\n", encoding="utf-8")
        mc = MapControl(compile_map("mine", cwd=root), cwd=root)
        mc.refresh()
        ctx.check("unchanged: nothing said", mc.take_notes() == [])
        path.write_text(path.read_text(encoding="utf-8") + "- {from: main, to: tester}\n", encoding="utf-8")
        os.utime(path, (time.time() + 5, time.time() + 5))
        mc.refresh()
        ctx.check("a bad change keeps the last good map, said", mc.map.agent_targets() == ["coder"] and "problem" in " ".join(mc.take_notes()))
        path.write_text("format: map/1\nname: mine\nboxes:\n- {id: coder, agent: coder}\n- {id: tester, agent: tester}\nlines:\n"
                        "- {from: main, to: coder}\n- {from: coder, to: tester, when: always}\n", encoding="utf-8")
        os.utime(path, (time.time() + 10, time.time() + 10))
        mc.refresh()
        ctx.check(f"the new chain applies, said once, got {mc.map.chains}", "coder" in mc.map.chains and mc.take_notes() == [CHANGED])
        os.utime(path, (time.time() + 20, time.time() + 20))
        mc.refresh()
        ctx.check("the same line is not said twice", mc.take_notes() == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
