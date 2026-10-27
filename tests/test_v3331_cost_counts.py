"""tests.test_v3331_cost_counts -- Halo 3.3.3.1 "cost counts what it knows",
through the real loop (agent/loop.py Session over the scripted mock upstream,
tests/helpers/mock_openai.py; no model call, no real provider):

1. main on an unpriced model spawns two priced sub-agents (1.25 and 1.10):
   the turn's `message_end` / `status` frames say `cost_usd` 2.35 (the
   children's sum), `cost_complete` False and `cost_unknown` main's ref; the
   status the fleet reads (`Session.status_event`, fleet/local_view.py's
   session row) carries the same three; the TUI's `/cost` line says
   "$2.3500+" with the one detail line naming main's model;
2. `--max-budget-usd` trips on the known part: a priced child's spend over
   the budget stops a `-p` run whose main model has no price at all
   (before 3.3.3.1 its cost was None and the budget could never trip);
3. the status bar's figure: "$x+" when incomplete, the token totals when
   nothing is priced yet, "$x" when complete.
Run: python -m tests.test_v3331_cost_counts
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.fake_home import build_fake_home  # noqa: E402
from tests.helpers.mock_openai import MockUpstream, SCENARIOS, ScriptedTurns  # noqa: E402
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402

ensure_default_provider_credentials()
test, TESTS = new_registry()
PARENT = "or:mock/v3331-parent"


def _usage(cost=None) -> dict:
    u = {"prompt_tokens": 100, "completion_tokens": 20}
    if cost is not None:
        u["cost"] = cost
    return {"choices": [], "usage": u}


def _text(text: str, cost=None) -> list:
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"content": text}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}, _usage(cost)]


def _tasks(*models: str) -> list:
    calls = [{"index": i, "id": f"call_kid_{i}", "type": "function", "function": {"name": "Task", "arguments": json.dumps(
        {"description": f"kid {i}", "prompt": "do it", "subagent_type": "general-purpose", "model": m})}}
        for i, m in enumerate(models)]
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": calls}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]}, _usage()]


def _script(kid_costs) -> list:
    kids = []
    for i, c in enumerate(kid_costs):
        name = f"v3331-kid-{i}"
        SCENARIOS[name] = ScriptedTurns([_text(f"kid {i} done", cost=c)])
        kids.append(f"or:mock/{name}")
    SCENARIOS["v3331-parent"] = ScriptedTurns([_tasks(*kids), _text("all done")])
    return kids


@test
def test_an_unpriced_main_with_priced_children_counts_what_it_knows(ctx: Ctx):
    from tests.test_h9b_findings import _general_purpose_spec, _new_session
    from halo_harness.fleet.local_view import session_row
    mock = MockUpstream().start()
    try:
        _script([1.25, 1.10])
        session = _new_session(mock=mock, model=PARENT, agents={"general-purpose": _general_purpose_spec()})
        evs = list(session.turn("spend through two sub-agents"))
        own = [e for e in evs if e.agent_id is None and e.kind in ("message_end", "status")]
        last_end = [e for e in own if e.kind == "message_end"][-1].data
        last_status = [e for e in own if e.kind == "status"][-1].data
        for label, d in (("message_end", last_end), ("status", last_status)):
            ctx.check(f"{label}: the children's 2.35, incomplete, main's ref named, got "
                      f"{d.get('cost_usd')} {d.get('cost_complete')} {d.get('cost_unknown')}",
                      abs((d.get("cost_usd") or 0) - 2.35) < 1e-9 and d.get("cost_complete") is False
                      and d.get("cost_unknown") == [PARENT])
        row = session_row({"session_id": "s"}, dict(session.status_event().data), [])
        ctx.check(f"the fleet's session row carries the three, got {row.get('cost_usd')} {row.get('cost_complete')} "
                  f"{row.get('cost_unknown')}", abs(row["cost_usd"] - 2.35) < 1e-9 and row["cost_complete"] is False
                  and row["cost_unknown"] == [PARENT])
        from halo_harness.commands.builtins import _cost_figure
        fig, detail = _cost_figure(session)
        ctx.check(f"/cost: the figure with a + and one detail line, got {fig!r} {detail!r}",
                  fig == "$2.3500+" and detail == "+ main's model mock/v3331-parent reports no price; "
                                                  "this is what the priced agents spent")
        ctx.check(f"main's two calls are the unknown ones, got {session.cost_meter.unknown_calls}",
                  session.cost_meter.unknown_calls == 2)
    finally:
        mock.stop()


@test
def test_max_budget_trips_on_the_known_part(ctx: Ctx):
    from tests.test_h9b_findings import _hermetic_child_env
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        _script([0.05])
        env = _hermetic_child_env()
        env.update({"BRIDGE_TEST_HOME": str(fh["home"]), "BRIDGE_OPENROUTER_BASE_URL": mock.base_url,
                    "OPENROUTER_API_KEY": "test-key", "PYTHONPATH": str(REPO), "BRIDGE_TEST_NO_BACKGROUND_NET": "1"})
        args = [sys.executable, "-m", "halo_harness", "-p", "spend through a sub-agent", "--model", PARENT,
                "--cwd", str(fh["proj"]), "--output-format", "json", "--permission-mode", "auto", "--max-budget-usd", "0.01"]
        r = subprocess.run(args, env=env, cwd=str(REPO), capture_output=True, text=True, timeout=60)
        obj = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
        ctx.check(f"exit 1 on the budget, got {r.returncode} {r.stderr[-400:]!r}", r.returncode == 1)
        ctx.check(f"subtype error_max_budget_usd, got {obj.get('subtype')!r}", obj.get("subtype") == "error_max_budget_usd")
        ctx.check(f"the result says the known part and that it is incomplete, got {obj.get('total_cost_usd')} "
                  f"{obj.get('cost_complete')}", abs((obj.get("total_cost_usd") or 0) - 0.05) < 1e-9
                  and obj.get("cost_complete") is False)
    finally:
        mock.stop()


@test
def test_the_status_bar_figure(ctx: Ctx):
    from halo_harness.model_display import describe_cost, format_status_cost
    ctx.check("incomplete with a priced part: $x+", format_status_cost(3.6348, 10, 2, complete=False) == "$3.6348+")
    ctx.check("nothing priced yet: the token totals", format_status_cost(0.0, 12000, 3000, complete=False) == "in 12k out 3k")
    ctx.check("complete: the plain figure", format_status_cost(0.5, 1, 1, complete=True) == "$0.5000")
    ctx.check("an older frame with no flag: the plain figure", format_status_cost(0.5) == "$0.5000")
    fig, detail = describe_cost({"cost_usd": 0.0, "cost_complete": False, "cost_unknown": ["dbx:x"]}, "dbx:x")
    ctx.check(f"/cost with nothing priced and nothing spent, got {fig!r} {detail!r}",
              fig == "n/a (no priced call yet)" and detail == "+ main's model x reports no price")
    ctx.check("complete: no detail line", describe_cost({"cost_usd": 1.0, "cost_complete": True}, "x") == ("$1.0000", None))


if __name__ == "__main__":
    os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
