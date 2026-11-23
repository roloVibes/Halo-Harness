"""tests.test_routed_rows -- Halo 3.6.0.15 OP2 rule O2-1: a helper's row says where its agent comes from and why Auto
sent it. `agent_hooks.register_child` puts `spawn.source` (the source of the spec the child runs) and run_agent_call,
the caller of the team's `route_call`, adds `spawn.routed` {word, card} to a child Auto routed (`agent_hooks.mark_routed`,
right after the child is built). A call that names a `role` and a fan-out child (`count`) are not routed.

A real top Session on Auto (the default map) over the loopback mock (tests/helpers/crew_rig.py: a scratch home,
`OLLAMA_HOST` on a dead port), main scripted to call Agent once; nothing calls a real model. Every scenario and env var
is put back in a finally.
Run: python -m tests.test_routed_rows
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MODEL = "or:mock/routed-rows"
JOB = "ROUTED-JOB"


def _session(rig):
    """A new top session in the rig's project on Auto with the agents a new session discovers (the shape of
    tests/test_usable_at_once.py `_session`; the agents as headless.build_session hands them)."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.crew.map_session import prepare
    from halo_harness.crew.session_start import start_agents
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.tools.registry import ToolRegistry, default_tools
    cwd = rig.proj
    compiled = prepare(None, cwd)[0]
    return Session(agents=start_agents(cwd, compiled),cwd=cwd, model_ref=parse_model_ref(MODEL), model_profile=ModelProfile(),
                   creds=ProviderCreds(base_url=rig.mock.base_url, api_key="k"),
                   state_dir=Path(tempfile.mkdtemp(prefix="sess-", dir=str(rig.root))), model_label=MODEL,
                   crew_map=compiled, openrouter_base_url=rig.mock.base_url, max_turns=4,
                   session_context=SessionContext(cwd=cwd, model_label=MODEL, tool_registry=ToolRegistry(default_tools())),
                   permission_engine=PermissionEngine(mode="default", cwd=cwd))


def _children(session) -> list:
    from halo_harness.agent.agent_registry import tree_for
    return [r for r in tree_for(session).public_rows() if r.get("kind") != "job" and r.get("agent_id") != "main"]


def _run(call: dict, *, his: "str | None" = None) -> list:
    """main calls Agent once with `call`, then ends; every child answers "Done here.". Returns the children's rows."""
    from tests.helpers.crew_rig import CrewRig
    from tests.helpers.mock_openai import SCENARIOS, _finish
    from tests.helpers.session_rig import text_step, tool_step
    main_seen: list = []

    def scenario(handler, body):
        first = next((json.dumps(m.get("content")) for m in body.get("messages") or []
                      if isinstance(m, dict) and m.get("role") == "user"), "")
        if JOB in first:
            _finish(handler, text_step("Done here."))
            return
        main_seen.append(body)
        _finish(handler, tool_step(("Agent", call, "call_r")) if len(main_seen) == 1 else text_step("All done."))

    with CrewRig() as rig:
        SCENARIOS["routed-rows"] = scenario
        try:
            if his:
                folder = rig.state / "crew" / "agents"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"{his}.yaml").write_text(
                    f"format: agent/1\nname: {his}\ndoes: Sorts the files it is given.\nmodel: auto\nuses:\n- read\n"
                    "careful: ask-changes\n", encoding="utf-8")
            s = _session(rig)
            list(s.turn("hand it out"))
            return _children(s)
        finally:
            SCENARIOS.pop("routed-rows", None)


def _spawn(row: dict) -> dict:
    return row.get("spawn") or {}


@test
def test_a_routed_general_call_names_its_word_and_card(ctx: Ctx):
    rows = _run({"description": "fix the login bug", "task": "fix the login bug", "prompt": f"{JOB}: look at it"})
    ctx.check(f"one child, got {[r.get('name') for r in rows]}", len(rows) == 1)
    spawn = _spawn(rows[0]) if rows else {}
    ctx.check(f"spawn.source is built-in, got {spawn.get('source')!r}", spawn.get("source") == "built-in")
    ctx.check(f"spawn.routed is {{word fix, card coder}}, got {spawn.get('routed')!r}",
              spawn.get("routed") == {"word": "fix", "card": "coder"})
    ctx.check(f"the 3.6.0.5 keys stay, got {sorted(spawn)}", {"step", "description", "lead", "task", "group"} <= set(spawn))


@test
def test_a_call_with_a_role_is_not_routed(ctx: Ctx):
    rows = _run({"description": "fix the login bug", "task": "fix the login bug", "prompt": f"{JOB}: look at it",
                 "role": "reviewer"})
    ctx.check(f"one child, got {[r.get('name') for r in rows]}", len(rows) == 1)
    spawn = _spawn(rows[0]) if rows else {}
    ctx.check(f"spawn.source is built-in, got {spawn.get('source')!r}", spawn.get("source") == "built-in")
    ctx.check(f"no routed key, got {spawn.get('routed')!r}", "routed" not in spawn)


@test
def test_a_crew_agent_row_says_its_source(ctx: Ctx):
    rows = _run({"description": "sort these", "task": "sort the files", "prompt": f"{JOB}: sort them",
                 "subagent_type": "sorter"}, his="sorter")
    ctx.check(f"one child named sorter, got {[r.get('name') for r in rows]}",
              len(rows) == 1 and rows[0].get("name") == "sorter")
    spawn = _spawn(rows[0]) if rows else {}
    ctx.check(f"spawn.source is crew:yours, got {spawn.get('source')!r}", spawn.get("source") == "crew:yours")


@test
def test_a_fanned_out_child_keeps_its_source(ctx: Ctx):
    rows = _run({"description": "fix the login bug", "task": "fix the login bug", "prompt": f"{JOB}: look at it",
                 "count": 2})
    ctx.check(f"two children, got {[r.get('name') for r in rows]}", len(rows) == 2)
    for i, row in enumerate(rows):
        spawn = _spawn(row)
        ctx.check(f"child {i}: spawn.source is built-in, got {spawn.get('source')!r}", spawn.get("source") == "built-in")
        ctx.check(f"child {i}: no routed key, got {spawn.get('routed')!r}", "routed" not in spawn)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
