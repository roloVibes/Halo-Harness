"""tests.test_routed_to_his_agent -- Halo 3.6.0.15 OP2 rule O2-4: on Auto, a general call of main's (no type, or
`general-purpose`, no `role`, no `count`/`batch`) whose words route it to a card whose agent is one of his
(`crew:yours` / `crew:project`, named `starter_of(card)`) starts HIS agent, exactly as the call naming him would
(crew/map_run.py `_his_for_card`, read in `_drawn`): his body, his model unless main names one, his row; every other
call starts and is drawn as before, and not a word main is sent changes.

A real top Session on Auto (the default map) over the loopback mock (tests/helpers/crew_rig.py: a scratch home,
`OLLAMA_HOST` on a dead port), main scripted to call Agent once; the mock picks a scenario by the model a request names,
so a child on his model reaches the scenario `his-coder`. Nothing calls a real model. Every scenario and env var is put
back in a finally.
Run: python -m tests.test_routed_to_his_agent
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MAIN = "routed-to-his"
JOB = "ROUTED-JOB"
CALL = {"description": "fix the login bug", "task": "fix the login bug", "prompt": f"{JOB}: look at it"}
HIS = ("format: agent/1\nname: coder\ndoes: Writes the code a task needs.\ninstructions: HIS CODER\n"
       "model: or:mock/his-coder\nuses:\n- read\ncareful: ask-changes\n")
MINE_MAP = ("format: map/1\nname: mine\nboxes:\n- {id: audit, agent: reviewer}\nlines:\n"
            "- {from: main, to: audit, when: ask}\n")


def _session(rig, map_name=None):
    """A new top session in the rig's project on Auto (or on his map `map_name`), with the agents a new session
    discovers (the shape of tests/test_routed_rows.py `_session`)."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.crew.map_session import prepare
    from halo_harness.crew.session_start import start_agents
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.tools.registry import ToolRegistry, default_tools
    cwd, ref = rig.proj, f"or:mock/{MAIN}"
    compiled = prepare({"map": map_name} if map_name else None, cwd)[0]
    return Session(agents=start_agents(cwd, compiled), cwd=cwd, model_ref=parse_model_ref(ref), model_profile=ModelProfile(),
                   creds=ProviderCreds(base_url=rig.mock.base_url, api_key="k"),
                   state_dir=Path(tempfile.mkdtemp(prefix="sess-", dir=str(rig.root))), model_label=ref,
                   crew_map=compiled, openrouter_base_url=rig.mock.base_url, max_turns=4,
                   session_context=SessionContext(cwd=cwd, model_label=ref, tool_registry=ToolRegistry(default_tools())),
                   permission_engine=PermissionEngine(mode="default", cwd=cwd))


def _rows(session) -> list:
    from halo_harness.agent.agent_registry import tree_for
    tree = tree_for(session)
    return [dict(tree.row(r["agent_id"]) or r) for r in tree.public_rows()
            if r.get("kind") != "job" and r.get("agent_id") != "main"]


class _Seen:
    """What each scenario was sent: `main` (main's requests), `kids` (child requests, by scenario)."""

    def __init__(self) -> None:
        self.main: list = []
        self.kids: list = []


def _scenarios(seen: _Seen, call: dict) -> dict:
    from tests.helpers.mock_openai import _finish
    from tests.helpers.session_rig import text_step, tool_step

    def child_of(name):
        def scenario(handler, body):
            seen.kids.append((name, body))
            _finish(handler, text_step("Done here."))
        return scenario

    def main(handler, body):
        first = next((json.dumps(m.get("content")) for m in body.get("messages") or []
                      if isinstance(m, dict) and m.get("role") == "user"), "")
        if JOB in first:
            seen.kids.append((MAIN, body))
            _finish(handler, text_step("Done here."))
            return
        seen.main.append(body)
        _finish(handler, tool_step(("Agent", call, "call_r")) if len(seen.main) == 1 else text_step("All done."))
    return {MAIN: main, "his-coder": child_of("his-coder"), "main-pick": child_of("main-pick")}


def _run(rig, call: dict, *, map_name=None) -> "tuple[list, _Seen]":
    """main calls Agent once with `call`, then ends; every child answers "Done here.". (children's rows, what was sent)."""
    from tests.helpers.mock_openai import SCENARIOS
    seen = _Seen()
    added = _scenarios(seen, call)
    SCENARIOS.update(added)
    try:
        s = _session(rig, map_name)
        list(s.turn("hand it out"))
        return _rows(s), seen
    finally:
        for k in added:
            SCENARIOS.pop(k, None)


def _his(rig) -> None:
    folder = rig.state / "crew" / "agents"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "coder.yaml").write_text(HIS, encoding="utf-8")


def _system(body: dict) -> str:
    return "\n".join(json.dumps(m.get("content")) for m in body.get("messages") or []
                     if isinstance(m, dict) and m.get("role") == "system")


def _tools(body: dict) -> str:
    return json.dumps(body.get("tools") or [], sort_keys=True)


def _result(seen: _Seen, aids) -> str:
    """The tool result main reads back on its next request, its agent ids put aside."""
    msgs = (seen.main[1].get("messages") or []) if len(seen.main) > 1 else []
    text = json.dumps([m.get("content") for m in msgs if isinstance(m, dict) and m.get("role") == "tool"])
    for aid in aids:
        text = text.replace(str(aid), "<aid>")
    return re.sub(r"task_id=[^0-9a-f]*[0-9a-f]+", "task_id=<id>", text)


def _made_up(row: dict) -> bool:
    return bool((row.get("crew") or {}).get("made_up"))


@test
def test_a_routed_general_call_starts_his_agent(ctx: Ctx):
    from tests.helpers.crew_rig import CrewRig
    with CrewRig() as rig:
        _his(rig)
        rows, seen = _run(rig, dict(CALL))
    ctx.check(f"one child named coder, got {[r.get('name') for r in rows]}", len(rows) == 1 and rows[0].get("name") == "coder")
    row = rows[0] if rows else {}
    ctx.check(f"drawn as his saved agent, got {row.get('crew')}",
              row.get("crew") == {"map": "auto", "box": "main", "agent": "coder", "saved": True})
    spawn = row.get("spawn") or {}
    ctx.check(f"spawn.source is crew:yours, got {spawn.get('source')!r}", spawn.get("source") == "crew:yours")
    ctx.check(f"spawn.routed is {{word fix, card coder}}, got {spawn.get('routed')!r}",
              spawn.get("routed") == {"word": "fix", "card": "coder"})
    names = [n for n, _b in seen.kids]
    ctx.check(f"its request went to his model, got {names}", names == ["his-coder"])
    ctx.check("its system text carries his instructions",
              bool(seen.kids) and "HIS CODER" in _system(seen.kids[0][1]))


@test
def test_it_runs_as_the_call_naming_him(ctx: Ctx):
    from tests.helpers.crew_rig import CrewRig
    with CrewRig() as rig:
        _his(rig)
        routed, rseen = _run(rig, dict(CALL))
        named, nseen = _run(rig, {**CALL, "subagent_type": "coder"})
    ctx.check(f"one child each, got {len(routed)} and {len(named)}", len(routed) == 1 and len(named) == 1)
    if len(routed) != 1 or len(named) != 1 or not rseen.kids or not nseen.kids:
        return
    r, n = routed[0], named[0]
    ctx.check(f"the rows' crew are equal, got {r.get('crew')} and {n.get('crew')}", r.get("crew") == n.get("crew"))
    ctx.check(f"the rows' spawn are equal, got {r.get('spawn')} and {n.get('spawn')}", r.get("spawn") == n.get("spawn"))
    rb, nb = rseen.kids[0][1], nseen.kids[0][1]
    ctx.check("the child's system text is byte-equal", _system(rb) == _system(nb))
    ctx.check("the child's tools and their words are byte-equal", _tools(rb) == _tools(nb))
    ctx.check(f"the child's model is the same, got {rb.get('model')!r} and {nb.get('model')!r}", rb.get("model") == nb.get("model"))
    aids = [r.get("agent_id"), n.get("agent_id")]
    rr, nr = _result(rseen, aids), _result(nseen, aids)
    ctx.check(f"main reads back the same tool result, got {rr[:200]!r} and {nr[:200]!r}", rr == nr and "Done here." in rr)
    ctx.check("main's own first request is byte-equal (its system text and tools)",
              _system(rseen.main[0]) == _system(nseen.main[0]) and _tools(rseen.main[0]) == _tools(nseen.main[0]))


@test
def test_main_names_a_model_itself(ctx: Ctx):
    from tests.helpers.crew_rig import CrewRig
    with CrewRig() as rig:
        _his(rig)
        rows, seen = _run(rig, {**CALL, "model": "or:mock/main-pick"})
    ctx.check(f"one child named coder, got {[r.get('name') for r in rows]}", len(rows) == 1 and rows[0].get("name") == "coder")
    names = [n for n, _b in seen.kids]
    ctx.check(f"his coder ran on main's pick, got {names}", names == ["main-pick"])
    ctx.check("with his instructions", bool(seen.kids) and "HIS CODER" in _system(seen.kids[0][1]))


@test
def test_what_stays_as_today(ctx: Ctx):
    from tests.helpers.crew_rig import CrewRig
    with CrewRig() as rig:
        rows, seen = _run(rig, dict(CALL))
        row = rows[0] if rows else {}
        ctx.check(f"only the shipped coder: a general-purpose child, got {[r.get('name') for r in rows]}",
                  len(rows) == 1 and row.get("name") == "general-purpose")
        ctx.check(f"made up, got {row.get('crew')}", _made_up(row))
        ctx.check(f"routed as today, got {(row.get('spawn') or {}).get('routed')!r}",
                  (row.get("spawn") or {}).get("routed") == {"word": "fix", "card": "coder"})
        ctx.check(f"on main's model, got {[n for n, _b in seen.kids]}", [n for n, _b in seen.kids] == [MAIN])
        _his(rig)
        rows, seen = _run(rig, {**CALL, "subagent_type": "Explore"})
        ctx.check(f"a call naming Explore starts Explore, got {[r.get('name') for r in rows]}",
                  [r.get("name") for r in rows] == ["Explore"])
        rows, seen = _run(rig, {**CALL, "count": 2})
        ctx.check(f"a count: 2 call: two general-purpose children, got {[r.get('name') for r in rows]}",
                  [r.get("name") for r in rows] == ["general-purpose", "general-purpose"])
        ctx.check(f"not on his model, got {[n for n, _b in seen.kids]}", "his-coder" not in [n for n, _b in seen.kids])
        rows, seen = _run(rig, {**CALL, "role": "reviewer"})
        row = rows[0] if rows else {}
        ctx.check(f"a call with a role: a general-purpose child, made up, got {[r.get('name') for r in rows]} {row.get('crew')}",
                  len(rows) == 1 and row.get("name") == "general-purpose" and _made_up(row))
        ctx.check(f"not on his model, got {[n for n, _b in seen.kids]}", "his-coder" not in [n for n, _b in seen.kids])
        from halo_harness.crew import store
        p = store.path_for("map", "mine")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(MINE_MAP, encoding="utf-8")
        rows, seen = _run(rig, dict(CALL), map_name="mine")
        row = rows[0] if rows else {}
        ctx.check(f"on a map of his: a general-purpose helper, made up, got {[r.get('name') for r in rows]} {row.get('crew')}",
                  len(rows) == 1 and row.get("name") == "general-purpose"
                  and row.get("crew") == {"map": "mine", "box": "main", "agent": "general-purpose", "saved": False, "made_up": True})
        ctx.check(f"not on his model, got {[n for n, _b in seen.kids]}", "his-coder" not in [n for n, _b in seen.kids])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
