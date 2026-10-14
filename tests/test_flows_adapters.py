"""tests.test_flows_adapters -- the real org adapter's in-session half
(Halo 3.0.4.0 round R3): `flows.adapters.run_org_on` runs a two-level org
(Lead -> Artist, the Artist approval-gated) from a NON-interactive session
against the mocked upstream, the way `halo flow run` does. The Artist's
gate is two hops down: it must reach the flow's approval sink live (never
the stdin prompt), an edit answer re-runs the Artist with the instruction,
and every position's final text comes back from the streamed Agent results.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fake_home import build_fake_home  # noqa: E402
from tests.helpers.mock_openai import MockUpstream  # noqa: E402
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_default_provider_credentials()

test, TESTS = new_registry()


def _chunks_text(text: str):
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"content": text}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}]


def _chunks_agent(tool_id: str, subagent_type: str, prompt: str):
    args = json.dumps({"description": "task", "prompt": prompt, "subagent_type": subagent_type})
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": [
                {"index": 0, "id": tool_id, "type": "function", "function": {"name": "Agent", "arguments": args}}]}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]}]


def _session(fh, mock, state_dir):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    return Session(cwd=fh["proj"], model_ref=parse_model_ref("or:mock/flow-top-unused"), model_profile=ModelProfile(),
                   creds=ProviderCreds(base_url=mock.base_url, api_key="k"), state_dir=state_dir,
                   model_label="mock/flow-top-unused", session_context=SessionContext(cwd=fh["proj"], model_label="m"),
                   openrouter_base_url=mock.base_url, max_turns=20, agents=[])


class _NoStdin:
    def readline(self):
        raise AssertionError("the gate fell back to the stdin prompt")


@test
def test_two_hop_gate_reaches_the_flow_sink_and_positions_come_back(ctx: Ctx):
    from halo_harness.flows.adapters import run_org_on
    from tests.helpers.mock_openai import SCENARIOS, _finish
    fh = build_fake_home()
    old_home = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
    mock = MockUpstream().start()
    artist_prompts = []
    try:
        def lead(h, body):
            msgs = (body or {}).get("messages") or []
            if any(m.get("role") == "tool" for m in msgs):
                _finish(h, _chunks_text("Lead: the plan is done"))
            else:
                _finish(h, _chunks_agent("call_art", "Artist", "one image prompt please"))

        def artist(h, body):
            msgs = (body or {}).get("messages") or []
            artist_prompts.append(json.dumps(msgs))
            _finish(h, _chunks_text(f"draft {len(artist_prompts)}: a lighthouse"))
        SCENARIOS["flow-lead"], SCENARIOS["flow-artist"] = lead, artist
        org = {"name": "flowpair", "budget_usd": 1.0, "positions": [
            {"title": "Lead", "model": "or:mock/flow-lead", "reports": ["Artist"]},
            {"title": "Artist", "model": "or:mock/flow-artist", "reports": [], "requires_approval": True}]}
        session = _session(fh, mock, Path(tempfile.mkdtemp(prefix="flow-adapter-")))
        asked, notes = [], []

        def sink(req):
            asked.append(req)
            return {"action": "edit", "instruction": "more neon"} if len(asked) == 1 else {"action": "accept"}
        old_stdin, sys.stdin = sys.stdin, _NoStdin()
        try:
            res = run_org_on(session, "flowpair", org, "make a hero image", lambda t, d=None: notes.append(t), sink)
        finally:
            sys.stdin = old_stdin
        ctx.check(f"the session is not interactive, the gate still reached the sink twice, got {asked}",
                  not session.interactive and [a["position"] for a in asked] == ["Artist", "Artist"])
        ctx.check("the sink saw each draft", asked[0]["text"].startswith("draft 1") and asked[1]["text"].startswith("draft 2"))
        ctx.check("the edit re-ran the Artist with the instruction", len(artist_prompts) == 2 and "more neon" in artist_prompts[1])
        ctx.check(f"the root's text is the result, got {res['text']!r}", res["text"].startswith("Lead: the plan is done")
                  and not res["is_error"])
        ctx.check(f"both positions' final texts came back, got {res['positions']}",
                  res["positions"]["Lead"]["text"].startswith("Lead: the plan")
                  and "draft 2: a lighthouse" in res["positions"]["Artist"]["text"])
        ctx.check(f"start/finish lines reached on_event, got {notes}", any("started" in n for n in notes)
                  and any("finished" in n for n in notes))
    finally:
        mock.stop()
        if old_home is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = old_home


@test
def test_org_budget_is_capped_by_the_step(ctx: Ctx):
    from halo_harness.flows.adapters import org_for_run
    ctx.check("min(org 3.00, step 0.40)", org_for_run("marketing", 0.4)["budget_usd"] == 0.4)
    ctx.check("the org's own when the step allows more", org_for_run("marketing", 10)["budget_usd"] == 3.0)
    ctx.check("no step budget keeps the org's", org_for_run("marketing", None)["budget_usd"] == 3.0)
    try:
        org_for_run("no-such-org", 1)
        raised = False
    except RuntimeError:
        raised = True
    ctx.check("an unknown org raises", raised)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="flow adapter tests"))
