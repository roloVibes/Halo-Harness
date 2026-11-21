"""tests.test_crew_compile -- Halo 3.6.0.0 R3: a map compiles to what a session already runs (halo_harness/crew/
compile.py, map_control.py, map_session.py; docs/CREW-sessions.md).

0. THE DEFAULT SESSION IS A 3.5 PLAIN SESSION (3.6.0.0 R5 fix): the session a user with no map gets runs on the
   starter map as a drawing -- its main tools (Workflow included), model, mode, the first request's system text, the
   Agent / Workflow tools' words, delegation depth and parallelism, the child model picks (and the routing that named
   the member), no money cap, every discovered agent spawnable and winning over a starter agent of its name, the
   starter's coder in the user's own files, `halo roles point` reaching the child, and roles off = no map at all --
   all equal what the 3.5 lineup gave (RECORDED_*, recorded on 4979de40 / fbc52502);
1. PARITY of a chosen map: a map that mirrors the old auto lineup (main + a "main decides per task" line to each pool
   member, each agent file mirroring its auto bio, and the media workflow) gives a session whose main tools, main model
   and mode, and -- for the same tasks -- the spawned child's model pick (models_auto, a seeded catalog) and permission
   mode equal what the lineup gave; the child's tools are its `uses` (agent/1), every tool under the lineup: the one
   designed difference of a map you chose;
2. the compile: main's config, the hand-off table, the chains, the specs (role = the agent's name), the cap;
3. a map with a problem (a missing agent, a circle, a bad file) gives its problem lines and the starter map instead;
4. a changed map compiles again at the next hand-off and says so once; with `crew.map` unset the starter map is used.
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


# 3.6.0.0 R5: what the auto lineup gave for this test (recorded on 4979de40, the last tree that had the lineup on a
# session's path; the platform's own shell tool, PowerShell on Windows, left out): main's tools, model and mode, and per
# task the pool member it routed to, that child's model pick and mode, and the child's tools (every tool main had).
RECORDED_MAIN_TOOLS = [
    "Agent", "AskUserQuestion", "Bash", "BashOutput", "Browser",  # 3.6.0.8: the built-in Browser tool, in every session
    "Edit", "EnterPlanMode", "ExitPlanMode", "Glob", "Grep",
    "ListMcpResourcesTool", "Media", "NotebookEdit", "Read", "ReadMcpResourceTool", "Screenshot", "Skill", "Task",
    "TaskCreate", "TaskList", "TaskStop", "TaskUpdate", "TodoWrite", "ToolSearch", "WebFetch", "WebSearch",
    "Workflow", "Write", "knowledge_add", "knowledge_search"
]
RECORDED_MAIN = ("or:v/eyes", "default")
RECORDED_CHILD_TOOLS = [
    "AskUserQuestion", "Bash", "BashOutput", "Edit", "EnterPlanMode", "ExitPlanMode", "Glob", "Grep",
    "ListMcpResourcesTool", "Media", "NotebookEdit", "Read", "ReadMcpResourceTool", "Screenshot", "Skill",
    "TaskCreate", "TaskList", "TaskStop", "TaskUpdate", "TodoWrite", "ToolSearch", "WebFetch", "WebSearch",
    "Workflow", "Write", "knowledge_add", "knowledge_search"
]
RECORDED_PICKS = {
    "plan the migration of the billing tables": ["planner", "dbx:databricks-gemini-x-pro", "default"],
    "research how the cache invalidates": ["researcher", "dbx:databricks-gemini-9-flash", "default"],
    "implement the retry in client.py": ["coder", "dbx:databricks-gemini-9-flash", "default"],
    "review the diff for the login change": ["reviewer", "dbx:databricks-gemini-x-pro", "default"],
    "describe the screenshot shot.png": ["media", "dbx:databricks-gemini-9-flash", "default"],
    "summarize the release notes": ["writer", "or:v/cheap", "default"],
    "deploy the staging build": ["ops", "or:v/cheap", "default"],
}
SHELL = {"PowerShell"}
# 3.6.0.0 R5 fix: more of what a plain 3.5 session had (fbc52502, the same seeded home): the depth and parallelism of
# its delegation, no money cap, nothing appended to the system prompt, and the closing words of its Agent tool.
RECORDED_DELEGATION = (2, 4)
RECORDED_BUDGET = {"band": "mid"}
RECORDED_AGENT_TAIL = "The lineup is auto: a sub-agent's model is picked for its task; say `model:` to choose yourself."
STARTER = {"media": "media-reader"}  # the lineup's alias -> the starter agent drawn for it


def _system(session) -> str:
    from halo_harness.agent.derive import derive_request
    return derive_request(session.log)[0]


@test
def test_the_default_session_is_a_plain_session(ctx: Ctx):
    from halo_harness.crew import map_run
    from halo_harness.models_best_at import rebuild
    from halo_harness.tools.base import ToolResult
    with S.home("crew-default-") as (root, state):
        env = S.seed(state)
        rebuild(state, list(S.rows_by_ref(state, env).values()))
        repo = root / "repo"
        (repo / ".claude" / "agents").mkdir(parents=True)
        (repo / ".claude" / "agents" / "my-helper.md").write_text(
            "---\nname: my-helper\ndescription: a project's own helper\n---\nYou help.\n", encoding="utf-8")
        s = _session(repo, {})
        tc = s.team_control
        ctx.check(f"no map set: the session draws Auto, the default map, got {getattr(getattr(tc, 'map', None), 'name', None)}",
                  getattr(tc, "is_map", False) and tc.map.name == "auto" and tc.map.source == "default")
        have = sorted(set(s.tool_registry.names()) - SHELL)
        ctx.check(f"main's tools are a plain session's (Workflow too), got only-recorded "
                  f"{sorted(set(RECORDED_MAIN_TOOLS) - set(have))} only-now {sorted(set(have) - set(RECORDED_MAIN_TOOLS))}",
                  have == sorted(RECORDED_MAIN_TOOLS))
        ctx.check(f"main's model and mode, got {s.model_ref.raw}/{s.permission_engine.mode}",
                  (s.model_ref.raw, s.permission_engine.mode) == RECORDED_MAIN)
        plain_system = _system(s)
        ctx.check("main's starter instructions are not in the system prompt",
                  "You are main, the agent the person talks to" not in plain_system and "Your instructions (the map" not in plain_system)
        agent_words, flow_words = s.tool_registry.get("Agent").description, s.tool_registry.get("Workflow").description
        ctx.check("the Agent tool says what a plain session's said (no 'runs on the map', no 'only to these')",
                  agent_words.endswith(RECORDED_AGENT_TAIL) and "runs on the map" not in agent_words)
        ctx.check("the Workflow tool is a plain session's (not a map's)", "runs on the map" not in flow_words)
        rt = s.agent_runtime
        ctx.check(f"delegation as the lineup's, got depth {rt.max_depth} parallel {rt.max_concurrent}",
                  (rt.max_depth, rt.max_concurrent) == RECORDED_DELEGATION)
        tc.record_spend(1000.0)
        ctx.check(f"no money cap, got budget {tc.budget} refusal {tc.budget_refusal()!r}",
                  tc.budget == RECORDED_BUDGET and tc.budget_refusal() is None)
        ctx.check("the starter's coder works in the user's own files", rt.agents["coder"].isolation is None)
        calls = []

        def inner(**kw):
            calls.append(kw["tool_input"])
            return [], ToolResult("ok")
        wants = ["Explore", "my-helper", "reviewer", "coder", "general-purpose", ""]
        for want in wants:
            ti = {"subagent_type": want, "description": "look around", "prompt": "find the config loader"}
            _e, tr = map_run.agent_call(inner, runtime=rt, tool_id="t1", tool_input=dict(ti), tool_name="Agent")
            ctx.check(f"spawn {want!r}: runs as in a plain session (passed on unchanged, result unchanged), got "
                      f"{tr.content!r}", not tr.is_error and tr.content == "ok" and calls and calls[-1] == ti)
        for task, (alias, model, mode) in RECORDED_PICKS.items():
            kind, routed = tc.route_call({"prompt": task}, task)
            ctx.check(f"{task!r}: routed to {alias} as the lineup did, got {routed}", routed == alias)
            got = _child(s, rt.agents[STARTER.get(alias, alias)], None, task)
            ctx.check(f"{task!r}: the starter's {STARTER.get(alias, alias)} picks {model} as the lineup's {alias} did, got "
                      f"{got['model']}", got["model"] == model and got["mode"] == mode)
        s.close_runtimes()
        from halo_harness.ollama_steward.dead_tag import cmd_point
        cmd_point(["researcher", "dbx:databricks-gemini-x-pro"])
        (root / ".claude" / "agents").mkdir(parents=True)
        (root / ".claude" / "agents" / "reviewer.md").write_text(
            "---\nname: reviewer\ndescription: my own reviewer\n---\nYou review my way.\n", encoding="utf-8")
        s = _session(repo, {})
        ctx.check(f"a user's agent wins over the starter's of its name, got {s.agent_runtime.agents['reviewer'].source}",
                  s.agent_runtime.agents["reviewer"].source == "user")
        got = _child(s, s.agent_runtime.agents["researcher"], None, "research how the cache invalidates")
        ctx.check(f"halo roles point researcher <model> reaches the starter's researcher, got {got['model']}",
                  got["model"] == "dbx:databricks-gemini-x-pro")
        s.close_runtimes()
        from halo_harness.roles import set_roles_enabled
        set_roles_enabled(False)
        s = _session(repo, {})
        ctx.check(f"roles off (One model for everything): no map at all, got {getattr(s.team_control, 'name', None)}",
                  s.team_control is None)
        bare = ("- **Agent**", "- **Task**")  # roles on / off words in those two tools' lines, as on 3.5 (checked above)
        ctx.check("the default map adds nothing to the system prompt: the same text as a session on no map at all",
                  [x for x in _system(s).splitlines() if not x.startswith(bare)]
                  == [x for x in plain_system.splitlines() if not x.startswith(bare)])
        s.close_runtimes()


@test
def test_the_starter_carries_the_lineup_needs_and_no_cap(ctx: Ctx):
    """The starter's agents say the needs a plain session's cards picked by (one source in a session: crew/plain.py's
    file; this pins the drawing to it), the starter has no cap, and a cap on a default map is never applied."""
    from halo_harness.crew.compile import compile_map
    from halo_harness.crew.map_control import MapControl, PlainMap, control_for
    from halo_harness.crew.plain import load
    with S.home("crew-starter-") as (root, _state):
        c = compile_map("auto", cwd=root)
        plain = load()
        ctx.check("a plain session's answers are read (templates/crew/plain/session.yaml)", plain is not None)
        for alias in plain.cards:
            if alias == "main":
                continue
            want = plain.needs_of(alias)
            ctx.check(f"starter {STARTER.get(alias, alias)} needs {c.needs_of(STARTER.get(alias, alias))}, the lineup's {alias} {want}",
                      c.needs_of(STARTER.get(alias, alias)) == want)
        ctx.check("the starter has no cap", c.cap_usd is None)
        capped = compile_map("ship-it", cwd=root)
        capped.source = "default"
        ctx.check("a default map's cap is never applied", MapControl(capped).budget_refusal() is None
                  and "max_budget_usd" not in MapControl(capped).budget and capped.cap_usd == 20.0)
        mc = control_for(compile_map("starter", cwd=root))
        ctx.check("starter named anywhere runs as Auto (a PlainMap)", type(mc) is PlainMap and mc.map.name == "auto")


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
        default, mapped = _session(repo, {}), _session(repo, {"map": "mirror"})
        dc, mc = default.team_control, mapped.team_control
        ctx.check(f"no map set: the session runs on Auto, the default map, got {getattr(getattr(dc, 'map', None), 'name', None)}",
                  getattr(dc, "is_map", False) and dc.map.name == "auto" and getattr(mc, "is_map", False))
        ctx.check(f"the starter map hands work to the auto lineup's pool, got {sorted(dc.map.agent_targets())}",
                  sorted(dc.map.agent_targets()) == sorted(["planner", "researcher", "coder", "reviewer", "writer",
                                                            "media-reader", "ops"]))
        have = sorted(set(mapped.tool_registry.names()) - SHELL)
        ctx.check(f"main's tools are the lineup's, got only-recorded {sorted(set(RECORDED_MAIN_TOOLS) - set(have))} "
                  f"only-map {sorted(set(have) - set(RECORDED_MAIN_TOOLS))}", have == sorted(RECORDED_MAIN_TOOLS))
        ctx.check(f"main's model and mode, got {mapped.model_ref.raw}/{mapped.permission_engine.mode}",
                  (mapped.model_ref.raw, mapped.permission_engine.mode) == RECORDED_MAIN)
        ctx.check("the Agent tool's targets are the pool's names", set(mc.map.agent_targets()) == set(POOL))
        rows = []
        for task, who in TASKS:
            alias, model, mode = RECORDED_PICKS[task]
            h, _why, refusal = _choose(mc, "agent", who, task, (), mapped.agent_runtime)  # main decides per task: it names who
            b = _child(mapped, mapped.agent_runtime.agents[h["name"]], None, task)
            rows.append((task, alias, model, h["name"], b))
            ctx.check(f"{task!r}: the lineup routed to {alias}, the map's main names {who}", alias == who and not refusal)
            ctx.check(f"{task!r}: the same model pick, got {model} vs {b['model']}", model == b["model"])
            ctx.check(f"{task!r}: the same permission mode, got {mode} vs {b['mode']}", mode == b["mode"])
            want = sorted({"TodoWrite", *[t for k in ("read", "edit", "bash", "web") for t in TOOLS[k]]} & set(RECORDED_CHILD_TOOLS))
            got = sorted(set(b["tools"]) - SHELL)
            ctx.check(f"{task!r}: the map's child has its uses, the lineup's had every tool", got == want and
                      set(got) <= set(RECORDED_CHILD_TOOLS))
        picks = {r[4]["model"] for r in rows}
        ctx.check(f"the picks differ by need (the catalog is seeded), got {sorted(picks)}", len(picks) >= 2)
        for task, alias, model, name, b in rows:
            print(f"  parity | {task[:34]:<34} | recorded {alias:<10} {model:<26} | map {name:<10} {b['model']:<26} "
                  f"{b['mode']:<8} {len(b['tools'])} tools")
        for s in (default, mapped):
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
        s = compile_map("auto", cwd=root)
        ctx.check("auto: seven agent targets, each spec's role its own name, modes from careful",
                  len(s.agent_targets()) == 7 and all(sp.role == n for n, sp in s.specs.items())
                  and s.specs["coder"].permission_mode == "acceptEdits" and s.specs["planner"].permission_mode == "default")
        ctx.check("an agent's needs reach Auto in its words", s.needs_of("researcher") == ["long-context"])


@test
def test_a_map_with_a_problem_runs_the_session_on_the_starter_map(ctx: Ctx):
    from halo_harness.crew.compile import for_session
    from halo_harness.theme import set_config_value
    with S.home("crew-problem-") as (root, state):
        (state / "crew" / "maps").mkdir(parents=True)
        (state / "crew" / "maps" / "broken.yaml").write_text(
            "format: map/1\nname: broken\nboxes:\n- {id: a, agent: nobody}\n- {id: b, agent: coder}\n"
            "lines:\n- {from: main, to: a}\n- {from: a, to: b}\n- {from: b, to: a}\n", encoding="utf-8")
        got, lines = for_session("broken", cwd=root)
        text = "\n".join(lines)
        ctx.check(f"the problem lines (the circle named, the missing agent) and Auto instead, got {lines}",
                  getattr(got, "name", None) == "auto" and "circle (a -> b -> a)" in text and "no agent named nobody" in text
                  and "runs on Auto (the default)" in lines[0])
        got, lines = for_session(None, cwd=root)
        ctx.check("no map set: Auto (3.6.0.0 R5, 3.6.0.5 A1)", getattr(got, "name", None) == "auto" and lines == [])
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


def _careful(name: str, careful: str) -> str:
    return (f"format: agent/1\nname: {name}\ndoes: Talks with you.\nmodel: auto\nuses: [read, edit, bash, web]\n"
            f"careful: {careful}\n")


def _mode_of(repo: Path, flags: dict) -> "tuple[str, str]":
    import contextlib
    import io
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        s = _session(repo, flags)
    mode = s.permission_engine.mode
    s.close_runtimes()
    return mode, err.getvalue()


@test
def test_a_map_never_raises_the_mode_you_set(ctx: Ctx):
    """batch01 #2: a map's main narrows the mode the flag, config and settings resolved, never raises it (the rule a
    sub-agent has); only a map and main that are both yours may raise it, said in one line. No map: the mode as set."""
    from halo_harness.theme import set_config_value
    from tests.helpers.trust_dir import trust
    with S.home("crew-mode-") as (root, state):
        S.seed(state)
        repo = root / "repo"
        (repo / ".halo" / "crew" / "agents").mkdir(parents=True)
        (repo / ".halo" / "crew" / "agents" / "main.yaml").write_text(_careful("main", "own"), encoding="utf-8")
        trust(repo)
        plain = root / "plain"
        plain.mkdir()
        for mode in ("default", "plan"):
            set_config_value("permission_mode", mode)
            got, err = _mode_of(repo, {"map": "ship-it"})
            ctx.check(f"config {mode}: a project's main (careful: own) on ship-it keeps {mode}, got {got}; said {err!r}",
                      got == mode and ("never raises" in err) == (mode != "plan"))
            got, _err = _mode_of(repo, {})
            ctx.check(f"config {mode}: no map, the mode as set, got {got}", got == mode)
        set_config_value("permission_mode", "acceptEdits")
        got, err = _mode_of(plain, {"map": "ship-it"})
        ctx.check(f"config acceptEdits: ship-it's main (ask-changes) narrows it to default, nothing said, got {got} {err!r}",
                  got == "default" and "careful" not in err)
        got, _err = _mode_of(plain, {})
        ctx.check(f"config acceptEdits: no map, acceptEdits, got {got}", got == "acceptEdits")
        set_config_value("permission_mode", "default")
        crew = state / "crew"
        (crew / "agents").mkdir(parents=True, exist_ok=True)
        (crew / "maps").mkdir(parents=True, exist_ok=True)
        (crew / "agents" / "boss.yaml").write_text(_careful("boss", "own"), encoding="utf-8")
        (crew / "maps" / "mine.yaml").write_text("format: map/1\nname: mine\nboxes:\n- {id: code, agent: coder}\n"
                                                 "lines:\n- {from: main, to: code}\nmain: {agent: boss}\n", encoding="utf-8")
        got, err = _mode_of(plain, {"map": "mine"})
        ctx.check(f"your own map and main (careful: own) raise it to auto, said in one line, got {got} {err!r}",
                  got == "auto" and "runs in auto" in err)
        import contextlib
        import io
        import os
        from halo_harness.maps_cli import cmd_maps
        out, here = io.StringIO(), os.getcwd()
        os.chdir(plain)
        try:
            with contextlib.redirect_stdout(out):
                cmd_maps(["use", "mine"])
        finally:
            os.chdir(here)
        ctx.check(f"halo maps use mine says main runs in auto, got {out.getvalue()!r}",
                  "main runs in auto (careful: own): nothing is asked" in out.getvalue())
        from halo_harness.crew.compile import Compiled
        from halo_harness.crew.map_session import main_mode
        pack = Compiled(name="demo--review", scope="pack", source="config",
                        main={"agent": "demo--writer", "mode": "auto", "careful": "own", "scope": "pack"})
        ctx.check("a pack's map with main careful: own never raises (default, dontAsk); it narrows bypass to auto",
                  main_mode(pack, "default")[0] == "default" and main_mode(pack, "dontAsk")[0] == "dontAsk"
                  and main_mode(pack, "bypassPermissions") == ("auto", ""))
        set_config_value("crew.map", "")
        set_config_value("permission_mode", "plan")
        got, err = _mode_of(plain, {"map": "mine"})
        ctx.check(f"plan stays plan even under your own map, got {got}", got == "plan")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
