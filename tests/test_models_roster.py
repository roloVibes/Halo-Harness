"""tests.test_models_roster -- the model roster in the main agent's context
(Halo 3.1.9.0 R1, "whatever agent is main should know which model is the
best from cost, intelligence, what they are best at"):

1. `roster_block` stays within 40 lines on a big catalog (the per-kind
   strongest / cheapest, then one line per model, then "+N more"), and
   carries names only: no provider key, no URL, no path;
2. a real Session with the roster on appends ONE `roster` snapshot at each
   of the three sites -- a new session, `/clear`, after compaction -- and
   the derived request carries it; a child (agent_depth 1) gets none;
   the system prompt never carries the model list: it is byte-identical
   across a catalog change, and on vs off differs only by the Agent tool's
   one roster sentence;
3. config `models.roster: false` (and HALO_MODELS_ROSTER=0) appends nothing,
   and the Agent tool's description names the roster only while it is on.
A loopback mock upstream for the compaction summary; no real model call.
Run: python -m tests.test_models_roster
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import catalog_facts_seed as S  # noqa: E402
from tests.helpers.mock_openai import MockUpstream, SCENARIOS, _finish  # noqa: E402
from halo_harness.models_best_at import index  # noqa: E402

test, TESTS = new_registry()
_SUMMARY = "\n".join(f"## {h}\nnotes." for h in ("Primary Request and Intent", "Key Technical Concepts", "Files and Code",
                                                 "Errors and Fixes", "Pending Jobs", "Current Work", "Next Step",
                                                 "Critical Context"))


def _scn_summary(h, body):
    _finish(h, [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
                {"choices": [{"index": 0, "delta": {"content": _SUMMARY}}]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}])


SCENARIOS["roster-summary"] = _scn_summary


def _big_catalog(state: Path) -> None:
    rows = json.loads((state / "models.json").read_text(encoding="utf-8"))
    for i in range(60):
        rows[f"bulk/m{i:02d}"] = {"context_length": 64000 + i, "input_modalities": ["text"], "output_modalities": ["text"],
                                  "supported_parameters": ["tools"], "pricing": {"prompt": "0.0000005", "completion": "0.000001"}}
    (state / "models.json").write_text(json.dumps(rows), encoding="utf-8")


def _clean(ctx: Ctx, text: str, state: Path, env: dict, where: str) -> None:
    ctx.check(f"{where}: no provider key", not any(v in text for v in env.values()))
    ctx.check(f"{where}: no URL and no path", "http" not in text and str(state) not in text and "\\" not in text
              and str(state.parent) not in text)


@test
def test_the_block_is_short_and_names_only(ctx: Ctx):
    from halo_harness.providers.roster import MAX_LINES, roster_block
    with S.home() as (_root, state):
        env = S.seed(state)
        _big_catalog(state)
        text = roster_block(state)
        lines = text.splitlines()
        ctx.check(f"at most {MAX_LINES} lines on a 70-model catalog, got {len(lines)}", 0 < len(lines) <= MAX_LINES)
        ctx.check("the per-kind picks come first", lines[0].startswith("# Model roster") and any(l.startswith("- audio: ") for l in lines))
        ctx.check(f"one line per model with price, ctx, inputs, tools, reasoning, best at, got {lines[-3]!r}",
                  any(" ctx  in text+image" in l and " best at " in l for l in lines))
        ctx.check("the rest are counted, not dropped silently", "more: `halo models analyze`" in lines[-1])
        ctx.check("the session's model leads the model lines",
                  roster_block(state, current_ref="or:bulk/m59").split("Models:\n", 1)[1].startswith("- or:bulk/m59"))
        _clean(ctx, text, state, env, "the block")


def _session(state: Path, mock, *, depth: int = 0):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    proj = state.parent / "proj"
    proj.mkdir(exist_ok=True)
    os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
    model = "or:mock/roster-summary"
    return Session(cwd=proj, model_ref=parse_model_ref(model), agent_depth=depth,
                   model_profile=ModelProfile(context_tokens=10_000, max_output_tokens=1_000),
                   creds=ProviderCreds(base_url=mock.base_url, api_key="k"), state_dir=state, model_label=model,
                   session_context=SessionContext(cwd=proj, model_label=model), openrouter_base_url=mock.base_url,
                   max_turns=5, permission_engine=PermissionEngine(mode="auto", cwd=proj))


def _rosters(session) -> list:
    return [n for n in session.log.nodes() if n.get("type") == "snapshot" and n.get("kind") == "roster"]


@test
def test_the_snapshot_lands_at_all_three_sites(ctx: Ctx):
    from halo_harness.agent.derive import derive_request
    mock = MockUpstream().start()
    try:
        with S.home() as (_root, state):
            env = S.seed(state)
            index(state)  # the catalog analyzed once, so a session start reads a fresh cache
            os.environ["HALO_MODELS_ROSTER"] = "1"
            session = _session(state, mock)
            ctx.check("a new session: one roster snapshot", len(_rosters(session)) == 1)
            text = _rosters(session)[0]["content"][0]["text"]
            _clean(ctx, text, state, env, "the snapshot")
            ctx.check("it names the catalog's models", "- or:v/eyes  $1.00/$2.00" in text and "- ant:opus " in text)
            _sys, messages, _tools = derive_request(session.log, tools=None)
            ctx.check("the derived request carries it as user-role text",
                      any("# Model roster" in b.get("text", "") for m in messages if m.get("role") == "user"
                          for b in (m.get("content") or []) if isinstance(b, dict)))
            session.clear()
            ctx.check("/clear: the fresh log has one roster snapshot", len(_rosters(session)) == 1)
            for i in range(60):
                session.log.append_user([{"type": "text", "text": f"question {i} " + "x" * 400}])
                session.log.append_assistant(content=[{"type": "text", "text": f"answer {i} " + "y" * 400}], stop_reason="end_turn")
            list(session._run_compaction(1, trigger="auto"))
            nodes = session.log.nodes()
            cut = max(i for i, n in enumerate(nodes) if n.get("type") == "compacted")
            ctx.check("after compaction: the roster is re-attached past the compacted marker",
                      any(n.get("kind") == "roster" for n in nodes[cut:]))
            child = _session(state, mock, depth=1)
            ctx.check("a child session (agent_depth 1) gets no roster", not _rosters(child))
    finally:
        mock.stop()
        os.environ.pop("BRIDGE_OPENROUTER_BASE_URL", None)


@test
def test_config_off_appends_nothing_and_the_prompt_stays_byte_stable(ctx: Ctx):
    from halo_harness.theme import set_config_value
    from halo_harness.tools.agent import AgentTool
    mock = MockUpstream().start()
    try:
        with S.home() as (_root, state):
            S.seed(state)
            index(state)  # the catalog analyzed once, so a session start reads a fresh cache
            os.environ.pop("HALO_MODELS_ROSTER", None)
            on = _session(state, mock)
            desc_on = AgentTool().description
            _big_catalog(state)
            stale = _session(state, mock)  # a session start never waits: the stale roster now, a rebuild behind it
            from halo_harness.models_best_at import wait_for_rebuild
            wait_for_rebuild(state, 30)
            later = _session(state, mock)
            ctx.check("the session after the rebuild sees the new catalog",
                      _rosters(stale)[0]["content"] == _rosters(on)[0]["content"]
                      and "more: `halo models analyze`" in _rosters(later)[0]["content"][0]["text"])
            ctx.check("a catalog change changes the roster snapshot, never the system prompt",
                      _rosters(on)[0]["content"] != _rosters(later)[0]["content"]
                      and on.session_context.system_prompt == later.session_context.system_prompt
                      and "# Model roster" not in on.session_context.system_prompt)
            set_config_value("models.roster", False)
            off = _session(state, mock)
            desc_off = AgentTool().description
            ctx.check("the default (config unset) is on", len(_rosters(on)) == 1)
            ctx.check("models.roster: false appends nothing", not _rosters(off))
            sentence = (" The roster in your context says what each model is good at; name a model with `model` "
                        "when a sub-task needs one.")
            ctx.check("on vs off: the system prompt differs only by the Agent tool's roster sentence",
                      sentence in on.session_context.system_prompt
                      and on.session_context.system_prompt.replace(sentence, "") == off.session_context.system_prompt)
            ctx.check("the Agent tool names the roster only while it is on",
                      "the roster in your context" in desc_on.lower() and "roster" not in desc_off.lower())
            set_config_value("models.roster", True)
            os.environ["HALO_MODELS_ROSTER"] = "0"
            ctx.check("HALO_MODELS_ROSTER=0 overrides the config", not _rosters(_session(state, mock)))
    finally:
        mock.stop()
        os.environ.pop("BRIDGE_OPENROUTER_BASE_URL", None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="models roster tests"))
