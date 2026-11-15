"""tests.test_crew_readers -- Halo 3.6.0.0 R5c: the readers R5b moved off the lineup answer what the main line
(2e36cdcc, the last 3.5 tree) answered, and nothing a plain session builds reads the old layers:

1. cold (no session), for a plain home (A), a plain home whose roles.coder and main are local models (B) and a home on a
   user's map with a local agent (C; a lineup on the main line): the local lanes and their name, the swap preview's
   lines, the steward's named refs, Place's lanes, the gym's candidates, the bundle check's coder -- and the cold CLI
   `halo local place --json` -- equal the main line's answers, recorded here (RECORDED; the plain session's name is
   "plain": `auto` there, the starter map here);
2. the adviser (Local -> Models) sees a plain session's roles (roles.<name> over its cards: the main line's adviser read
   the lineup in force, which 3.6 has no more; a role no session reads, `verify`, is no lane) and a map's agents;
2b. a 3.5 home that still says `team: balanced` (every upgraded user): the readers, the cold CLI, the adviser, the
   pool's worker lane on a map and `halo roles`' first line answer as the same home without it (the judge's S-e);
3. a plain session's build and a routed spawn import none of the old lineup modules (a fresh process; the judge's S10);
4. `--agent coder` (a 3.5 bio's name; an Orchestra lane's worker asks for it) runs the starter coder, no unknown line;
5. `/workflows` lists what the Workflow tool lists: the crew workflows it runs by name, then its squares.
No model is called. Run: python -m tests.test_crew_readers
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.config_seed import ConfigHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
LAN = "http://127.0.0.1:9"  # a placeholder host nobody answers on: nothing here opens a connection to it

# What 2e36cdcc answered for the same three homes (its lineup `mine` with a `coder` card where this tree has a map).
RECORDED = {
    "A": {"bundle_coder": None, "gym": ["ol:qwen3:8b@lan"], "lanes": ["plain", []], "place": ["plain", []],
          "preview": ["NAME: no local lanes (no `ol:` models): nothing to schedule"], "steward": []},
    "B": {"bundle_coder": None, "gym": ["ol:qwen3:8b@lan"], "lanes": ["plain", [["main", "qwen3:8b", "lan"]]],
          "place": ["plain", ["main"]], "preview": [], "steward": ["ol:qwen3-coder:30b@lan"]},
    "C": {"bundle_coder": None, "gym": ["ol:qwen3:8b@lan", "ol:qwen3-coder:30b@lan"],
          "lanes": ["mine", [["coder", "qwen3-coder:30b", "lan"], ["main", "qwen3:8b", "lan"]]],
          "place": ["mine", ["coder", "main"]], "preview": [], "steward": ["ol:qwen3-coder:30b@lan"]},
}
RECORDED_CLI = {"A": ["plain", []], "B": ["plain", ["main"]], "C": ["mine", ["coder", "main"]]}


def _norm(name):
    return "plain" if name in ("auto", "starter", None, "") else name


def _cfg(home: Path, **kv) -> None:
    p = home / ".halo" / "config.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    data.update(kv)
    p.write_text(json.dumps(data), encoding="utf-8")


def _ask(home: Path) -> dict:
    from halo_harness.checks.run import gym_candidates
    from halo_harness.local_place_cli import place_lineup
    from halo_harness.local_sched.bundle_needs import coder_of
    from halo_harness.local_sched.preview import lanes_for, preview
    from halo_harness.ollama_steward.rules_drift import refs
    from halo_harness.providers.ollama import resolve_ollama_host
    lanes, _d, name = lanes_for(None)
    got = place_lineup(None)
    host = resolve_ollama_host("lan")
    c = coder_of(host, state_dir=home / ".halo") if host is not None else None
    return {"lanes": [_norm(name), sorted([ln["lane"], ln["model"], ln.get("host")] for ln in lanes)],
            "preview": [ln.replace(f"{name}:", "NAME:") for ln in preview(None).get("lines") or []],
            "steward": sorted(r[1] for r in refs(home / ".halo")),
            "place": [_norm(got.get("lineup")), sorted(str(r.get("lane")) for r in got.get("rows") or [])],
            "gym": gym_candidates(SimpleNamespace(model="ol:qwen3:8b@lan", cwd=home / "repo", state_dir=home / ".halo")),
            "bundle_coder": (c or {}).get("model") if isinstance(c, dict) else c}


def _cli(home: Path) -> list:
    r = subprocess.run([sys.executable, "-m", "halo_harness", "local", "place", "--json"], capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": str(REPO)}, cwd=str(home / "repo"), timeout=300)
    try:
        data = json.loads(r.stdout)
    except ValueError:
        return [f"exit {r.returncode}", r.stdout[-200:], r.stderr[-300:]]
    return [_norm(data.get("lineup")), sorted(str(x.get("lane")) for x in data.get("rows") or [])]


def _map_mine(home: Path) -> None:
    d = home / ".halo" / "crew"
    (d / "agents").mkdir(parents=True, exist_ok=True)
    (d / "maps").mkdir(parents=True, exist_ok=True)
    (d / "agents" / "coder.yaml").write_text("format: agent/1\nname: coder\ndoes: codes locally\nmodel: ol:qwen3-coder:30b@lan\n"
                                             "uses: [read, edit]\ncareful: ask-changes\n", encoding="utf-8")
    (d / "maps" / "mine.yaml").write_text("format: map/1\nname: mine\nmain: {agent: main}\nboxes:\n  - {id: coder, agent: coder}\n"
                                          "lines:\n  - {from: main, to: coder, when: main-decides}\n", encoding="utf-8")


@test
def test_the_moved_readers_answer_as_the_main_line(ctx: Ctx):
    with ConfigHome() as h:
        home = h.home
        _cfg(home, ollama={"hosts": {"lan": LAN}})
        got = {"A": _ask(home)}
        cli = {"A": _cli(home)}
        _cfg(home, model="ol:qwen3:8b@lan", roles={"coder": "ol:qwen3-coder:30b@lan"})
        got["B"], cli["B"] = _ask(home), _cli(home)
        _map_mine(home)
        _cfg(home, crew={"map": "mine"}, roles={})
        got["C"], cli["C"] = _ask(home), _cli(home)
    for case in ("A", "B", "C"):
        ctx.check(f"{case}: every reader as on the main line, got {got[case]}", got[case] == RECORDED[case])
        ctx.check(f"{case}: the cold CLI (halo local place --json) as on the main line, got {cli[case]}",
                  cli[case] == RECORDED_CLI[case])


@test
def test_the_adviser_sees_a_plain_sessions_roles_and_a_maps_agents(ctx: Ctx):
    from halo_harness.models_library.advise import inputs
    with ConfigHome() as h:
        home = h.home
        _cfg(home, ollama={"hosts": {"lan": LAN}}, model="ol:qwen3:8b@lan",
             roles={"coder": "ol:qwen3-coder:30b@lan", "reviewer": "ol:qwen3.5:9b@lan", "verify": "ol:gemma3:12b@lan"})
        plain = sorted((ln["lane"], ln["model"]) for ln in inputs(home / ".halo")["lanes"])
        _map_mine(home)
        _cfg(home, crew={"map": "mine"})
        mapped = sorted((ln["lane"], ln["model"]) for ln in inputs(home / ".halo")["lanes"])
    # 3.6.0.0 R5c (the judge's F1): roles.verify is no lane -- no session runs a `verify` role
    ctx.check(f"a plain session: main, and the coder and reviewer cards on your roles (no verify lane), got {plain}",
              plain == [("coder", "qwen3-coder:30b"), ("main", "qwen3:8b"), ("reviewer", "qwen3.5:9b")])
    ctx.check(f"a map: main and its agent (your roles.* are not the map's), got {mapped}",
              mapped == [("coder", "qwen3-coder:30b"), ("main", "qwen3:8b")])


@test
def test_a_35_home_that_still_says_team_balanced(ctx: Ctx):
    """3.6.0.0 R5c (the judge's S-e): config `team: balanced` is read by nobody -- the readers and the cold CLI answer as
    home B (RECORDED), the adviser sees the plain session's lanes and, with a map in use, the pool's worker lane (as
    tests/helpers/studio_pool_watch.py sets it up), and `halo roles` names no lineup."""
    from halo_harness.models_library.advise import inputs
    from halo_harness.roles import roles_state_line
    from tests.helpers.sched_lineup import write
    with ConfigHome() as h:
        home = h.home
        _cfg(home, ollama={"hosts": {"lan": LAN}}, model="ol:qwen3:8b@lan", roles={"coder": "ol:qwen3-coder:30b@lan"},
             team="balanced")
        got, cli = _ask(home), _cli(home)
        plain = sorted((ln["lane"], ln["model"]) for ln in inputs(home / ".halo")["lanes"])
        state = roles_state_line()
        write(home / ".halo", "pooled", {"worker": "ol:qwen3.8:27b@lan"})
        _cfg(home, crew={"map": "pooled"})
        pooled = sorted((ln["lane"], ln["model"]) for ln in inputs(home / ".halo")["lanes"])
        state_map = roles_state_line()
    ctx.check(f"every reader as home B, got {got}", got == RECORDED["B"])
    ctx.check(f"the cold CLI as home B, got {cli}", cli == RECORDED_CLI["B"])
    ctx.check(f"the adviser: main and the coder card, got {plain}", plain == [("coder", "qwen3-coder:30b"), ("main", "qwen3:8b")])
    ctx.check(f"the pool's map in use: its worker lane and main, got {pooled}",
              pooled == [("main", "qwen3:8b"), ("worker", "qwen3.8:27b")])
    ctx.check(f"halo roles names no lineup (the judge's S-f), got {state!r} / {state_map!r}",
              "lineup" not in state and "balanced" not in state
              and state == "roles: on (the plain session's cards, each picked per task; your role table wins card by card)"
              and state_map == "roles: on (map pooled: its agents run on their own models)")


MODS = r'''
import sys
sys.path.insert(0, sys.argv[1])
from tests.helpers import catalog_facts_seed as S
OLD = ("halo_harness.teams_runtime", "halo_harness.teams_yaml", "halo_harness.agents_yaml", "halo_harness.lineup_default",
       "halo_harness.teams_tiers", "halo_harness.lineup_preflight")
from halo_harness.models_best_at import rebuild
from halo_harness import headless
from tests.test_crew_compile import _child
with S.home("crew-readers-mods-") as (root, state):
    env = S.seed(state)
    rebuild(state, list(S.rows_by_ref(state, env).values()))
    repo = root / "repo"
    repo.mkdir()
    s = headless.build_session(cwd=repo, model_ref_raw="or:v/eyes", print_mode=True, cli_flags={}).session
    built = [m for m in OLD if m in sys.modules]
    _child(s, s.agent_runtime.agents["planner"], None, "plan the migration of the billing tables")
    spawned = [m for m in OLD if m in sys.modules]
    s.close_runtimes()
print("MODS", built, spawned)
'''


@test
def test_a_plain_session_imports_no_old_lineup_module(ctx: Ctx):
    r = subprocess.run([sys.executable, "-c", MODS, str(REPO)], capture_output=True, text=True, timeout=600,
                       env={**os.environ, "PYTHONPATH": str(REPO)})
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("MODS")), f"no MODS line: {r.stderr[-400:]}")
    ctx.check(f"a fresh process: the build and a routed spawn import no old lineup module, got {line}",
              line == "MODS [] []")


@test
def test_an_agent_flag_naming_a_35_bio_runs_its_starter(ctx: Ctx):
    from halo_harness import headless
    from tests.helpers import catalog_facts_seed as S
    with S.home("crew-readers-agent-") as (root, state):
        S.seed(state)
        repo = root / "repo"
        repo.mkdir()
        err = io.StringIO()
        with redirect_stderr(err):
            s = headless.build_session(cwd=repo, model_ref_raw="or:v/eyes", print_mode=True, cli_flags={},
                                       agent="coder").session
        try:
            spec = (s.agent_runtime.agents or {}).get("coder")
            tools = sorted(s.tool_registry.names())
        finally:
            s.close_runtimes()
    ctx.check(f"no unknown --agent line, got {err.getvalue()!r}", "unknown --agent" not in err.getvalue())
    ctx.check(f"the starter coder runs the session (its tools), got {getattr(spec, 'source', None)} {tools}",
              getattr(spec, "source", None) == "crew:starter" and "Edit" in tools and "Bash" in tools
              and "WebSearch" not in tools)


@test
def test_workflows_and_the_workflow_tool_list_the_same(ctx: Ctx):
    from halo_harness.commands.builtins import _cmd_workflows
    from halo_harness.crew.flow_door import names, tail
    from halo_harness.workflows.registry import active_lineup, enabled_squares
    with ConfigHome() as h:
        d = h.home / ".halo" / "crew" / "workflows"
        d.mkdir(parents=True)
        (d / "ship.yaml").write_text("format: workflow/1\nname: ship\nfor: Ship a change.\nsteps:\n  - {name: do, agents: [coder], "
                                     "gets: the task, hands: the change}\n", encoding="utf-8")
        text = _cmd_workflows("", SimpleNamespace(cwd=h.repo, session=None))
        crew, squares = names(h.repo), [wf.ref for wf in enabled_squares(active_lineup(), cwd=h.repo)]
        tool_tail = tail(h.repo)
    ctx.check(f"/workflows names every crew workflow the tool runs by name, got {crew} in {text!r}",
              crew == ["ship"] and all(f"  {n}  " in text for n in crew) and all(n in tool_tail for n in crew))
    ctx.check(f"and every square the tool enables, got {squares}", all(f"  {r}" in text for r in squares))
    ctx.check("not the starters the tool never runs", "Workflows a session runs by name" in text
              and "(starter)" not in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
