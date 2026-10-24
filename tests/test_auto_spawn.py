"""tests.test_auto_spawn -- an `auto` member's model is picked at spawn
(Halo 3.1.9.0 R2, "the Auto lineup"): a real Session under the default auto
lineup, a mocked upstream, a seeded best-at index (`~/.halo/models/
best-at.json`; the suite's HALO_AUTO_INDEX_BUILD=0 reads it and never builds
the catalog), Agent calls through `run_agent_call`:

1. a screenshot task routes to media and runs on the vision model the pick
   chose; the reason rides on the agent row (`model_reason`, in its
   `agent_state` frame), its meta.json and its first transcript note
   ("auto: <model> -- <reason>"); a writer task runs on the cheap one;
2. main's `model:` on the call overrides the pick (the override slot), and a
   tier's model comes before `auto`;
3. a pick that does not resolve here runs on main's model, saying so;
4. a lineup without `auto` runs as before: its pinned model, no reason, no note.
No real model call. Run: python -m tests.test_auto_spawn
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_default_provider_credentials()
test, TESTS = new_registry()


def _facts(pin, pout, ins, *, tools=True, reasoning="none", ctx=100000):
    return {"provider": "openrouter", "price_in_per_m": pin, "price_out_per_m": pout, "modalities_in": ins,
            "modalities_out": ["text"], "tools": tools, "reasoning": {"kind": reasoning}, "context_tokens": ctx, "local": False}


ROWS = {
    "or:mock/auto-eyes": {"kinds": ["visual"], "scores": {"visual": 0.9, "code": 0.7, "bulk": 0.5},
                          "facts": _facts(0.3, 1.2, ["text", "image"])},
    "or:mock/auto-cheap": {"kinds": ["bulk"], "scores": {"bulk": 0.95, "code": 0.6}, "facts": _facts(0.05, 0.2, ["text"])},
    "or:mock/auto-main": {"kinds": ["code"], "scores": {"code": 0.9, "research": 0.9},
                          "facts": _facts(2.0, 8.0, ["text"], reasoning="native", ctx=200000)},
}
EYES = "an image in the task, the best vision model within 3x the cheapest ($0.30/$1.20 per 1M)"


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="auto-spawn-"))
        os.environ["BRIDGE_TEST_HOME"], os.environ["BRIDGE_STATE_DIR"] = str(d), str(d / ".halo")
        self.state_dir, self.cwd = d / ".halo", d / "project"
        self.cwd.mkdir(parents=True)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _seed_index(state_dir: Path, rows: dict) -> None:
    path = state_dir / "models" / "best-at.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": 1, "built": time.time(), "sources": {}, "rows": rows, "best": {}}), encoding="utf-8")


def _session(e: _Env, mock):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.config.agents_md import discover_agents
    from halo_harness.hooks import HookRunner
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.roles import resolve_role_table
    return Session(cwd=e.cwd, model_ref=parse_model_ref("or:mock/auto-main"), model_profile=ModelProfile(),
                   creds=ProviderCreds(base_url=mock.base_url, api_key="k"), state_dir=e.state_dir,
                   model_label="mock/auto-main", session_context=SessionContext(cwd=e.cwd, model_label="mock/auto-main"),
                   openrouter_base_url=mock.base_url, max_turns=10, agents=discover_agents(e.cwd, settings=None),
                   roles=resolve_role_table(provider="openrouter"),
                   hook_runner=HookRunner({}, cwd=e.cwd, session_id="auto-spawn", transcript_path=str(e.state_dir / "t.jsonl")))


def _dispatch(session, tool_id, prompt, **extra):
    tu = {"type": "tool_use", "id": tool_id, "name": "Agent",
          "input": {"description": extra.pop("description", "task"), "prompt": prompt, "subagent_type": "general-purpose", **extra}}
    events = list(session._dispatch_tools(1, [tu]))
    return next(ev for ev in events if ev.kind == "tool_result").data.get("content", "")


def _child(session, tool_id) -> dict:
    from halo_harness.agent.agent_registry import tree_for
    rows = [r for r in tree_for(session).public_rows() if r.get("kind") != "job" and r["agent_id"] != "main"]
    meta = {}
    for r in rows:
        mp = Path(r["transcript"]).with_suffix(".meta.json") if r.get("transcript") else None
        m = json.loads(mp.read_text(encoding="utf-8")) if mp is not None and mp.exists() else {}
        if m.get("parent_tool_use_id") == tool_id:
            meta = {"row": r, "meta": m}
    return meta


def _notes(transcript: str) -> list:
    from halo_harness.agent.agent_transcript import entries_from_nodes
    nodes = [json.loads(x) for x in Path(transcript).read_text(encoding="utf-8").splitlines() if x.strip()]
    return entries_from_nodes(nodes)


def _mock():
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
    from tests.test_teams_runtime import _text
    for name, said in (("auto-eyes", "EYES SAW IT"), ("auto-cheap", "CHEAP DONE"), ("auto-main", "MAIN RAN"),
                       ("auto-override", "OVERRIDE RAN"), ("auto-tier", "TIER RAN"), ("plain-worker", "PLAIN RAN")):
        SCENARIOS[name] = (lambda text: lambda h, b: _finish(h, _text(text)))(said)
    return MockUpstream().start()


@test
def test_the_pick_runs_the_child_and_rides_on_its_row_frame_meta_and_note(ctx: Ctx):
    from halo_harness.agent.agent_registry import tree_for
    mock = _mock()
    try:
        with _Env() as e:
            _seed_index(e.state_dir, ROWS)
            session = _session(e, mock)
            frames: list = []
            tree_for(session).add_listener(lambda kind, aid, data: frames.append((kind, aid, dict(data))))
            out = _dispatch(session, "c1", "Look at shot.png and say what the screenshot shows",
                            description="describe the screenshot")
            ctx.check(f"routed to media, run on the vision model the pick chose, got {out[:120]!r}", "EYES SAW IT" in out)
            got = _child(session, "c1")
            row, meta = got.get("row") or {}, got.get("meta") or {}
            ctx.check(f"the agent row names the model and why, got {row.get('model')!r} {row.get('model_reason')!r}",
                      row.get("model") == "or:mock/auto-eyes" and row.get("model_reason") == EYES and row.get("role") == "media")
            states = [d for k, aid, d in frames if k == "agent_state" and aid == row.get("agent_id")]
            ctx.check("its first agent_state frame already carries the reason", states and states[0].get("model_reason") == EYES)
            ctx.check(f"so does its meta.json, got {meta.get('model_reason')!r}", meta.get("model_reason") == EYES)
            entries = _notes(row["transcript"])
            ctx.check(f"its transcript opens with the pick's note, got {entries[:2]}",
                      entries and entries[0] == {"kind": "note", "text": f"auto: or:mock/auto-eyes -- {EYES}", "ts": entries[0].get("ts")})
            out = _dispatch(session, "c2", "Summarize notes.md in two lines", description="summarize the notes")
            row = _child(session, "c2").get("row") or {}
            ctx.check(f"a writer task runs on the cheap, fast model, got {out[:80]!r} {row.get('model_reason')!r}",
                      "CHEAP DONE" in out and row.get("model") == "or:mock/auto-cheap"
                      and row.get("model_reason", "").startswith("no special needs, the best cheap, fast model"))
    finally:
        mock.stop()


@test
def test_mains_model_and_a_tiers_model_come_before_the_pick(ctx: Ctx):
    from halo_harness.teams_yaml import save_team_template
    from halo_harness.theme import set_config_value
    mock = _mock()
    try:
        with _Env() as e:
            _seed_index(e.state_dir, ROWS)
            session = _session(e, mock)
            out = _dispatch(session, "c1", "Look at shot.png", description="describe the screenshot", model="or:mock/auto-override")
            row = _child(session, "c1").get("row") or {}
            ctx.check(f"main's model: on the call wins, with no pick, got {out[:80]!r} {row.get('model')!r} {row.get('model_reason')!r}",
                      "OVERRIDE RAN" in out and row.get("model") == "or:mock/auto-override" and not row.get("model_reason"))
            ok, problems = save_team_template("tiered", {
                "description": "a tier names the pool's model",
                "agents": [{"agent": "default-model", "role": "main"}, {"agent": "auto-coder", "role": "coder"}],
                "routing": {"fix": "coder"},
                "tiers": [{"name": "main", "members": ["main"]}, {"name": "pool", "members": ["coder"], "model": "or:mock/auto-tier"}],
            }, state_dir=e.state_dir)
            ctx.check(f"the tiered lineup saves, got {problems}", ok)
            set_config_value("team", "tiered")
            session = _session(e, mock)
            out = _dispatch(session, "c2", "fix the bug in basket.py", description="fix the bug")
            row = _child(session, "c2").get("row") or {}
            ctx.check(f"a tier's model comes before `auto`, got {out[:80]!r} {row.get('model')!r}",
                      "TIER RAN" in out and row.get("model") == "or:mock/auto-tier" and not row.get("model_reason"))
    finally:
        mock.stop()


@test
def test_a_pick_that_does_not_resolve_runs_on_mains_model(ctx: Ctx):
    mock = _mock()
    saved = {k: os.environ.pop(k) for k in ("OPENAI_API_KEY", "OPENAI_BASE_URL") if k in os.environ}
    try:
        with _Env() as e:
            eyes = {"kinds": ["visual"], "scores": {"visual": 0.9}, "facts": _facts(0.1, 0.1, ["text", "image"])}
            for ref, why in (("nowhere-eyes", "nowhere-eyes does not resolve here; using main's"),
                             ("oai:gpt-eyes", "oai:gpt-eyes has no credentials here; using main's")):
                _seed_index(e.state_dir, {ref: eyes})
                session = _session(e, mock)
                out = _dispatch(session, "c1", "Look at shot.png", description="describe the screenshot")
                row = _child(session, "c1").get("row") or {}
                ctx.check(f"{ref}: main's model runs it and the reason says why, got {out[:80]!r} {row.get('model_reason')!r}",
                          "MAIN RAN" in out and row.get("model") == "or:mock/auto-main" and row.get("model_reason") == why)
    finally:
        os.environ.update(saved)
        mock.stop()


@test
def test_a_lineup_without_auto_runs_as_before(ctx: Ctx):
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_yaml import save_team_template
    from halo_harness.theme import set_config_value
    mock = _mock()
    try:
        with _Env() as e:
            _seed_index(e.state_dir, ROWS)
            save_agent_bio("plain-bio", {"description": "pinned", "models": {"preference": "or:mock/plain-worker"}},
                           state_dir=e.state_dir)
            ok, _p = save_team_template("plain", {"description": "no auto here", "routing": {"screenshot": "worker"},
                                                  "agents": [{"agent": "default-model", "role": "main"},
                                                             {"agent": "plain-bio", "role": "subagent", "as": "worker"}]},
                                        state_dir=e.state_dir)
            set_config_value("team", "plain")
            session = _session(e, mock)
            out = _dispatch(session, "c1", "Look at shot.png", description="describe the screenshot")
            row = _child(session, "c1").get("row") or {}
            ctx.check(f"the pinned model runs it, no reason, got {out[:80]!r} {row.get('model')!r} {row.get('model_reason')!r}",
                      ok and "PLAIN RAN" in out and row.get("model") == "or:mock/plain-worker" and row.get("model_reason") is None)
            ctx.check("and no pick note opens its transcript",
                      not any(x.get("kind") == "note" and str(x.get("text", "")).startswith("auto:") for x in _notes(row["transcript"])))
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
