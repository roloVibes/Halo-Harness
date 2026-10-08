"""tests.test_round_1_filter_routing -- Halo 2.0.7 cyber Pillar 1
(filter-aware routing, 1.1-1.3):

  * 1.1 detection: `finish_reason: "content_filter"` (and GLM's
    "sensitive", and a native `stop_reason: "refusal"`) is recognized on
    every harness-driven response and NEVER persisted as an answer;
  * 1.2 the measured filter census: every live filter signal is recorded
    per raw model ref (nothing is ever probed -- the profile is built
    from real traffic only);
  * 1.3 transparent reroute: a filtered request is retried on the next
    fallback lane (a DIFFERENT model, never an in-place retry), the user
    is told, and with no lane left the old GLM contract stands (a clear
    never-retried error carrying whatever text did stream).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_openai import MockUpstream, SCENARIOS, ScriptedTurns
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()


def _text_step(text: str) -> list:
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": text}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]


def _filtered_step(text: str, reason: str = "content_filter") -> list:
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": text}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": reason}]},
    ]


def _new_session(*, mock, model, fallback_models=None):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds

    cwd = Path(tempfile.mkdtemp(prefix="r1fr-e2e-"))
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="r1fr-home-")))
    session_ctx = SessionContext(cwd=cwd, model_label=model, bare=True)
    return Session(
        cwd=cwd, model_ref=parse_model_ref(model), model_profile=ModelProfile(),
        creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
        state_dir=Path(tempfile.mkdtemp(prefix="r1fr-state-")), model_label=model,
        session_context=session_ctx, openrouter_base_url=mock.base_url, max_turns=10,
        permission_engine=PermissionEngine(mode="auto", cwd=cwd),
        agents={}, routes={},
        cli_flags=({"fallback_models": list(fallback_models)} if fallback_models else None),
    )


# ---- 1.2 the census ------------------------------------------------------------


@test
def test_census_records_and_ranks_lanes(ctx: Ctx):
    from halo_harness.providers.filter_census import (
        filter_free_lanes, load_filter_census, model_filter_count, record_filter_observation)

    state = Path(tempfile.mkdtemp(prefix="r1fr-census-"))
    ctx.check("empty census for a fresh state dir", load_filter_census(state) == {"observations": {}})
    ctx.check("an unobserved ref counts zero", model_filter_count(state, "or:a/b") == 0)

    record_filter_observation(state, "or:a/b", "content_filter")
    record_filter_observation(state, "or:a/b", "content_filter")
    record_filter_observation(state, "dbx:glm", "sensitive")
    ctx.check("counts accumulate per reason", model_filter_count(state, "or:a/b") == 2)
    ctx.check("one observation elsewhere", model_filter_count(state, "dbx:glm") == 1)
    on_disk = json.loads((state / "filter-census.json").read_text(encoding="utf-8"))
    ctx.check("the file carries the raw ref key and count",
              on_disk["observations"]["or:a/b"]["content_filter"] == 2)
    ctx.check("last_seen is recorded", isinstance(on_disk["observations"]["or:a/b"]["last_seen"], float))

    lanes = filter_free_lanes(state, ["or:a/b", "or:c/d", "dbx:glm"])
    ctx.check(f"only never-filtered refs are filter-free lanes, got {lanes}", lanes == ["or:c/d"])
    ctx.check("a corrupt census file reads as empty, never raises",
              _corrupt_census_reads_empty())


def _corrupt_census_reads_empty() -> bool:
    from halo_harness.providers.filter_census import load_filter_census, record_filter_observation
    state = Path(tempfile.mkdtemp(prefix="r1fr-corrupt-"))
    (state / "filter-census.json").write_text("{not json", encoding="utf-8")
    if load_filter_census(state) != {"observations": {}}:
        return False
    record_filter_observation(state, "or:x/y", "refusal")  # overwrites the corrupt file cleanly
    return load_filter_census(state)["observations"]["or:x/y"]["refusal"] == 1


# ---- 1.1 + 1.3 through a real session turn -------------------------------------


@test
def test_filtered_reply_reroutes_and_never_persists(ctx: Ctx):
    SCENARIOS["r1fr-filtered"] = ScriptedTurns([_filtered_step("I can't help with that.")])
    SCENARIOS["r1fr-lane"] = ScriptedTurns([_text_step("the real answer")])
    mock = MockUpstream().start()
    try:
        session = _new_session(mock=mock, model="or:mock/r1fr-filtered",
                               fallback_models=["or:mock/r1fr-lane"])
        evs = list(session.turn("give me the answer"))
        final_texts = [e.data.get("text", "") for e in evs if e.kind == "text_delta"]
        ctx.check("the turn completed with the FALLBACK lane's answer",
                  any("the real answer" in t for t in final_texts))
        assistant_nodes = [n for n in session.log.nodes() if n.get("type") == "assistant"]
        ctx.check("no assistant node persisted at all (the filtered attempt was discarded)",
                  not any("can't help" in "".join(b.get("text", "") for b in (n.get("content") or [])
                                                  if isinstance(b, dict)) for n in assistant_nodes))
        notifs = [e.data.get("text", "") for e in evs if e.kind == "notification"]
        ctx.check("the user was told about the filter",
                  any("filtered the reply (content_filter)" in t for t in notifs))
        ctx.check("the reroute is transparent (names the new lane)",
                  any("rerouting the filtered request to or:mock/r1fr-lane" in t for t in notifs))
        census = json.loads((session.state_dir / "filter-census.json").read_text(encoding="utf-8"))
        ctx.check("the census recorded the observation for the RAW ref",
                  census["observations"].get("or:mock/r1fr-filtered", {}).get("content_filter") == 1)
        ctx.check("the model was restored to the primary after the turn",
                  session.model_ref.raw == "or:mock/r1fr-filtered")
    finally:
        mock.stop()


@test
def test_sensitive_finish_also_reroutes(ctx: Ctx):
    SCENARIOS["r1fr-sensitive"] = ScriptedTurns([_filtered_step("no can do", reason="sensitive")])
    SCENARIOS["r1fr-lane2"] = ScriptedTurns([_text_step("lane two answers")])
    mock = MockUpstream().start()
    try:
        session = _new_session(mock=mock, model="or:mock/r1fr-sensitive",
                               fallback_models=["or:mock/r1fr-lane2"])
        evs = list(session.turn("give me the answer"))
        final_texts = [e.data.get("text", "") for e in evs if e.kind == "text_delta"]
        ctx.check("a sensitive-filtered reply reroutes to the fallback lane",
                  any("lane two answers" in t for t in final_texts))
        census = json.loads((session.state_dir / "filter-census.json").read_text(encoding="utf-8"))
        ctx.check("the census carries the sensitive observation",
                  census["observations"].get("or:mock/r1fr-sensitive", {}).get("sensitive") == 1)
    finally:
        mock.stop()


@test
def test_filtered_reply_with_no_lane_is_a_clear_never_retried_error(ctx: Ctx):
    SCENARIOS["r1fr-nolane"] = ScriptedTurns([_filtered_step("I can't help with that.")])
    mock = MockUpstream().start()
    try:
        session = _new_session(mock=mock, model="or:mock/r1fr-nolane")
        evs = list(session.turn("give me the answer"))
        errors = [e for e in evs if e.kind == "error"]
        ctx.check(f"exactly one terminal error, got {len(errors)}", len(errors) == 1)
        ctx.check("err_type is the filter reason",
                  errors[0].data.get("err_type") == "content_filter")
        ctx.check("the message carries the provider's own text",
                  "can't help" in errors[0].data.get("message", ""))
        ctx.check("nothing persisted as an answer",
                  not [n for n in session.log.nodes() if n.get("type") == "assistant"])
        ctx.check("never retried in place (one upstream request)",
                  len(mock.requests) == 1)
        census = json.loads((session.state_dir / "filter-census.json").read_text(encoding="utf-8"))
        ctx.check("the observation was still recorded",
                  census["observations"].get("or:mock/r1fr-nolane", {}).get("content_filter") == 1)
    finally:
        mock.stop()


@test
def test_both_lanes_filtered_exhausts_into_the_error(ctx: Ctx):
    SCENARIOS["r1fr-a"] = ScriptedTurns([_filtered_step("nope from a")])
    SCENARIOS["r1fr-b"] = ScriptedTurns([_filtered_step("nope from b")])
    mock = MockUpstream().start()
    try:
        session = _new_session(mock=mock, model="or:mock/r1fr-a",
                               fallback_models=["or:mock/r1fr-b"])
        evs = list(session.turn("give me the answer"))
        errors = [e for e in evs if e.kind == "error"]
        ctx.check("both lanes filtering ends in the terminal error", len(errors) == 1)
        ctx.check("the error names the last lane's filter",
                  errors[0].data.get("err_type") == "content_filter")
        ctx.check("two upstream requests total (one per lane, never more)",
                  len(mock.requests) == 2)
        census = json.loads((session.state_dir / "filter-census.json").read_text(encoding="utf-8"))
        ctx.check("both lanes are in the census",
                  census["observations"].get("or:mock/r1fr-a", {}).get("content_filter") == 1
                  and census["observations"].get("or:mock/r1fr-b", {}).get("content_filter") == 1)
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
