"""tests.test_learned_params -- Halo 2.0.5 round 3 (2.0.3-brief.md item
G1): the generalised learned-param-rejection engine (providers.
learned_params) -- detection/planning for every rejection shape seen so
far, persistence (fresh vs stale, precedence, forget/forget-all), the
`halo rules`/`/rules` surfaces, and one live end-to-end retry through
agent/loop.py against a mock Databricks gateway. No network, no real
model.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_databricks import MockDatabricks
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()


class _Env:
    """`Session.__init__` builds a real `SessionLog`, which opens/writes
    under `bridge_home()` the moment the Session exists -- never derived
    from `fh["home"]` on its own (the same guard test_hotfix_101_fix_
    effort_retry.py uses)."""

    def __init__(self, fh):
        self._fh = fh

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        os.environ["BRIDGE_TEST_HOME"] = str(self._fh["home"])
        os.environ.pop("BRIDGE_STATE_DIR", None)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _new_dbx_session(fh, mock, *, model: str, effort=None):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    session_ctx = SessionContext(cwd=fh["proj"], model_label=model)
    model_ref = parse_model_ref(model)
    return Session(
        cwd=fh["proj"], model_ref=model_ref, model_profile=ModelProfile(),
        creds=ProviderCreds(base_url=mock.root, api_key="test-token"),
        state_dir=Path(tempfile.mkdtemp(prefix="learned-params-")), model_label=model,
        session_context=session_ctx, max_turns=6, effort=effort,
    )


# ---------------------------------------------------------------------------
# Detection: every rejection shape the brief names, plus the hard
# exclusions (tools, a field never actually sent, a status outside 400/422).
# ---------------------------------------------------------------------------

@test
def test_detects_gpt6_reasoning_effort_with_tools(ctx: Ctx):
    from halo_harness.providers.learned_params import detect_param_rejection
    fix = detect_param_rejection(
        400,
        "Function tools with reasoning_effort are not supported for gpt-6-sol in /v1/chat/completions. "
        "To use function tools, use /v1/responses or set reasoning_effort to 'none'.",
        {"tools": [{"type": "function"}], "reasoning_effort": "high"},
    )
    ctx.check(f"got {fix}", fix is not None and fix.field == "reasoning_effort" and fix.action == "clamp")
    ctx.check(f"clamps to the one value the message offers, got {fix}", fix.value == "none")


@test
def test_detects_glm_thinking_rejection(ctx: Ctx):
    from halo_harness.providers.learned_params import detect_param_rejection
    fix = detect_param_rejection(
        400, "Unsupported parameter: 'thinking' is not supported with this model.",
        {"thinking": {"type": "adaptive"}},
    )
    ctx.check(f"got {fix}", fix is not None and fix.field == "thinking" and fix.action == "drop")


@test
def test_detects_claude_output_config_xhigh_and_clamps_to_max(ctx: Ctx):
    from halo_harness.providers.learned_params import detect_param_rejection
    fix = detect_param_rejection(
        400, "output_config.effort: Input should be 'low', 'medium', 'high' or 'max'",
        {"output_config": {"effort": "xhigh"}},
    )
    ctx.check(f"got {fix}", fix is not None and fix.field == "output_config" and fix.action == "clamp")
    ctx.check(f"clamps to max, same convention as profiles.clamp_effort, got {fix}", fix.value == "max")


@test
def test_detects_unknown_field_400(ctx: Ctx):
    from halo_harness.providers.learned_params import detect_param_rejection
    fix = detect_param_rejection(400, 'json: unknown field "metadata"', {"metadata": {"a": 1}})
    ctx.check(f"got {fix}", fix is not None and fix.field == "metadata" and fix.action == "drop")


@test
def test_detects_allowed_values_422_and_clamps(ctx: Ctx):
    from halo_harness.providers.learned_params import detect_param_rejection
    fix = detect_param_rejection(
        422, "Invalid value for parameter 'tool_choice': must be one of 'auto', 'none', 'required'.",
        {"tool_choice": "foo"},
    )
    ctx.check(f"got {fix}", fix is not None and fix.field == "tool_choice" and fix.action == "clamp")
    ctx.check(f"clamps to one of the allowed values, got {fix}", fix.value in ("auto", "none", "required"))


@test
def test_400_naming_no_field_plans_nothing(ctx: Ctx):
    from halo_harness.providers.learned_params import detect_param_rejection
    fix = detect_param_rejection(400, "The request could not be processed.", {"temperature": 0.7})
    ctx.check(f"no fix -- normal error translation applies unchanged, got {fix}", fix is None)


@test
def test_never_fires_outside_400_422(ctx: Ctx):
    from halo_harness.providers.learned_params import detect_param_rejection
    fix = detect_param_rejection(500, 'unknown field "metadata"', {"metadata": 1})
    ctx.check("500 is never a param rejection, regardless of wording", fix is None)


@test
def test_never_fires_on_tools_despite_being_a_databricks_allowlist_word(ctx: Ctx):
    """`tools` keeps its OWN never-silently-drop handling (`providers.
    errors.is_tools_rejected_message`) -- this engine must never touch it,
    even though it is one of the Databricks allowlist words the brief
    points at as part of the watched-field union."""
    from halo_harness.providers.learned_params import WATCHED_PARAM_FIELDS, detect_param_rejection
    ctx.check("'tools' is deliberately excluded from the watched fields", "tools" not in WATCHED_PARAM_FIELDS)
    fix = detect_param_rejection(400, 'json: unknown field "tools"', {"tools": [1]})
    ctx.check(f"no fix planned for tools, got {fix}", fix is None)


@test
def test_never_fires_on_a_field_the_request_never_sent(ctx: Ctx):
    from halo_harness.providers.learned_params import detect_param_rejection
    fix = detect_param_rejection(400, "Unsupported parameter: 'store'.", {"temperature": 0.5})
    ctx.check(f"'store' was never actually sent, got {fix}", fix is None)


# ---------------------------------------------------------------------------
# apply_param_fix: drop, clamp, and the nested output_config.effort shape.
# ---------------------------------------------------------------------------

@test
def test_apply_drop_removes_the_whole_key_without_mutating_the_input(ctx: Ctx):
    from halo_harness.providers.learned_params import ParamFix, apply_param_fix
    body = {"thinking": {"type": "adaptive"}, "messages": []}
    new_body = apply_param_fix(body, ParamFix(field="thinking", action="drop"))
    ctx.check(f"got {new_body}", "thinking" not in new_body and "messages" in new_body)
    ctx.check("input dict was not mutated", "thinking" in body)


@test
def test_apply_clamp_nested_output_config_preserves_siblings(ctx: Ctx):
    from halo_harness.providers.learned_params import ParamFix, apply_param_fix
    body = {"output_config": {"effort": "xhigh", "other": 1}}
    new_body = apply_param_fix(body, ParamFix(field="output_config", action="clamp", value="max"))
    ctx.check(f"got {new_body}", new_body["output_config"] == {"effort": "max", "other": 1})


@test
def test_apply_clamp_flat_field(ctx: Ctx):
    from halo_harness.providers.learned_params import ParamFix, apply_param_fix
    new_body = apply_param_fix({"tool_choice": "foo"}, ParamFix(field="tool_choice", action="clamp", value="auto"))
    ctx.check(f"got {new_body}", new_body["tool_choice"] == "auto")


# ---------------------------------------------------------------------------
# Persistence: on-disk shape, fresh vs stale (30-day TTL), precedence,
# forget / forget-all, list_param_rules, and the xp: ignored-parameters
# reader surviving the module split untouched.
# ---------------------------------------------------------------------------

@test
def test_persistence_shape_matches_the_brief(ctx: Ctx):
    from halo_harness.providers.learned_params import ParamFix, learn_param_fix
    from halo_harness.providers.learned_rules import _path
    state_dir = Path(tempfile.mkdtemp(prefix="learned-params-shape-"))
    learn_param_fix(state_dir, "databricks", "m-shape",
                     ParamFix(field="thinking", action="drop", error="Unsupported parameter: 'thinking'"))
    data = json.loads(_path(state_dir).read_text(encoding="utf-8"))
    row = data["databricks:m-shape"]["params"]["thinking"]
    ctx.check(f"keys, got {row}", set(row) == {"action", "value", "error", "date"})
    ctx.check("action is drop", row["action"] == "drop")
    ctx.check("value is None for a drop", row["value"] is None)
    ctx.check("error is the upstream message", row["error"].startswith("Unsupported parameter"))


@test
def test_stale_rule_is_not_applied_preemptively_but_still_listed(ctx: Ctx):
    from halo_harness.providers.learned_params import ParamFix, learn_param_fix, learned_param_fix, list_param_rules
    from halo_harness.providers.learned_rules import _path
    state_dir = Path(tempfile.mkdtemp(prefix="learned-params-stale-"))
    learn_param_fix(state_dir, "databricks", "m-stale", ParamFix(field="stop", action="drop", error="x"))
    path = _path(state_dir)
    data = json.loads(path.read_text(encoding="utf-8"))
    old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(timespec="seconds")
    data["databricks:m-stale"]["params"]["stop"]["date"] = old
    path.write_text(json.dumps(data), encoding="utf-8")
    ctx.check("stale (31d) -- not pre-emptively applied",
              learned_param_fix(state_dir, "databricks", "m-stale", "stop") is None)
    rows = list_param_rules(state_dir)
    ctx.check(f"still listed (so a person can see/forget it), got {rows}",
              any(r["endpoint"] == "databricks:m-stale" and r["field"] == "stop" for r in rows))


@test
def test_fresh_rule_within_30_days_is_applied_preemptively(ctx: Ctx):
    from halo_harness.providers.learned_params import ParamFix, learn_param_fix, learned_param_fix
    from halo_harness.providers.learned_rules import _path
    state_dir = Path(tempfile.mkdtemp(prefix="learned-params-fresh-"))
    learn_param_fix(state_dir, "databricks", "m-fresh", ParamFix(field="stop", action="drop", error="x"))
    path = _path(state_dir)
    data = json.loads(path.read_text(encoding="utf-8"))
    recent = (datetime.now(timezone.utc) - timedelta(days=29)).isoformat(timespec="seconds")
    data["databricks:m-fresh"]["params"]["stop"]["date"] = recent
    path.write_text(json.dumps(data), encoding="utf-8")
    ctx.check("still fresh at 29 days", learned_param_fix(state_dir, "databricks", "m-fresh", "stop") is not None)


@test
def test_model_table_row_wins_over_a_learned_temperature_rule(ctx: Ctx):
    from dataclasses import dataclass as _dc
    from halo_harness.providers.learned_params import table_value_wins

    @_dc
    class _FakeProfile:
        temperature: float = None
        top_p: float = None

    ctx.check("no table value -- the learned rule may apply", not table_value_wins("temperature", _FakeProfile()))
    ctx.check("table value present -- the learned rule is blocked (today's precedence)",
              table_value_wins("temperature", _FakeProfile(temperature=0.3)))
    ctx.check("fields other than temperature/top_p have no table-sourced value to defer to",
              not table_value_wins("metadata", _FakeProfile(temperature=0.3)))


@test
def test_forget_clears_only_params_leaves_other_learned_fields(ctx: Ctx):
    from halo_harness.providers.learned_params import ParamFix, forget_param_fixes, learn_param_fix, learned_param_fix
    from halo_harness.providers.learned_rules import learn_tools_rejected, learned_tools_rejected
    state_dir = Path(tempfile.mkdtemp(prefix="learned-params-forget-"))
    learn_param_fix(state_dir, "databricks", "m-forget", ParamFix(field="store", action="drop", error="x"))
    learn_tools_rejected(state_dir, "databricks", "m-forget")
    ctx.check("forgot something", forget_param_fixes(state_dir, "databricks:m-forget"))
    ctx.check("the params fix is gone", learned_param_fix(state_dir, "databricks", "m-forget", "store") is None)
    ctx.check("tools_rejected (a DIFFERENT learned field, own forget surface) survives",
              learned_tools_rejected(state_dir, "databricks", "m-forget"))
    ctx.check("forgetting again finds nothing left", not forget_param_fixes(state_dir, "databricks:m-forget"))


@test
def test_forget_all_clears_every_endpoint(ctx: Ctx):
    from halo_harness.providers.learned_params import (
        ParamFix, forget_all_param_rules, learn_param_fix, list_param_rules,
    )
    state_dir = Path(tempfile.mkdtemp(prefix="learned-params-forget-all-"))
    learn_param_fix(state_dir, "databricks", "a", ParamFix(field="store", action="drop", error="x"))
    learn_param_fix(state_dir, "databricks", "b", ParamFix(field="strict", action="drop", error="x"))
    cleared = forget_all_param_rules(state_dir)
    ctx.check(f"cleared both endpoints, got {cleared}", cleared == 2)
    ctx.check("nothing left", list_param_rules(state_dir) == [])


@test
def test_list_param_rules_reports_endpoint_field_action_age(ctx: Ctx):
    from halo_harness.providers.learned_params import ParamFix, learn_param_fix, list_param_rules
    state_dir = Path(tempfile.mkdtemp(prefix="learned-params-list-"))
    learn_param_fix(state_dir, "databricks", "m-list",
                     ParamFix(field="response_format", action="clamp", value="text", error="x"))
    rows = list_param_rules(state_dir)
    ctx.check(f"one row, got {rows}", len(rows) == 1)
    row = rows[0]
    ctx.check("endpoint", row["endpoint"] == "databricks:m-list")
    ctx.check("field", row["field"] == "response_format")
    ctx.check("action", row["action"] == "clamp")
    ctx.check(f"has a non-negative numeric age, got {row['age_s']!r}",
              isinstance(row["age_s"], float) and row["age_s"] >= 0)


@test
def test_xp_ignored_params_reader_unaffected_by_the_params_split(ctx: Ctx):
    """2.0.4 round 2's x-experiential-ignored-parameters learning
    (`providers.learned_rules.learned_ignored_params`/`learn_ignored_
    params`) feeds the SAME `learned-rules.json` row this round's new
    "params" sub-object lives in -- the two coexist without clobbering
    each other after the module split into providers.learned_params."""
    from halo_harness.providers.learned_params import ParamFix, learn_param_fix, learned_param_fix
    from halo_harness.providers.learned_rules import learn_ignored_params, learned_ignored_params
    state_dir = Path(tempfile.mkdtemp(prefix="learned-params-xp-"))
    learn_ignored_params(state_dir, "experiential", "m-xp", "temperature,top_p")
    learn_param_fix(state_dir, "experiential", "m-xp", ParamFix(field="store", action="drop", error="x"))
    ctx.check("ignored_params still reads back",
              learned_ignored_params(state_dir, "experiential", "m-xp") == "temperature,top_p")
    ctx.check("the new params fix reads back too, same row",
              learned_param_fix(state_dir, "experiential", "m-xp", "store") is not None)


# ---------------------------------------------------------------------------
# Live, end to end: exactly one retry, the fix actually applied, the house-
# voice transcript line, the on-disk shape, and pre-emptive application on
# a LATER step -- through agent/loop.py against a mock Databricks gateway.
# ---------------------------------------------------------------------------

@test
def test_live_retry_applies_fix_persists_and_announces(ctx: Ctx):
    from halo_harness.providers.learned_params import learned_param_fix
    fh = build_fake_home()
    with _Env(fh):
        mock = MockDatabricks().start()
        try:
            session = _new_dbx_session(fh, mock, model="dbx:databricks-gpt-5-param-reject-unless-dropped")
            events_seen = list(session.turn("hello"))
            errors = [e for e in events_seen if e.kind == "error"]
            ctx.check(f"no error surfaced, got kinds={[e.kind for e in events_seen]}", errors == [])
            ctx.check(f"exactly two upstream attempts, got {len(mock.requests)}", len(mock.requests) == 2)
            first_body, second_body = mock.requests[0]["body"] or {}, mock.requests[1]["body"] or {}
            ctx.check(f"first attempt carried max_tokens, got {first_body}", "max_tokens" in first_body)
            ctx.check(f"retry DROPPED max_tokens entirely, got {second_body}", "max_tokens" not in second_body)

            note_texts = [e.data.get("text", "") for e in events_seen if e.kind == "notification"]
            matching = [t for t in note_texts if "max_tokens" in t and "remembered for this endpoint" in t]
            ctx.check(f"the house-voice transcript line was printed exactly once, got {note_texts}",
                      len(matching) == 1)
            ctx.check(f"names the provider and describes the fix, got {matching}",
                      matching and matching[0].startswith("Databricks") and "dropped it" in matching[0])

            fix = learned_param_fix(session.state_dir, "databricks", session.model_ref.model, "max_tokens")
            ctx.check(f"persisted on disk, got {fix}", fix is not None and fix["action"] == "drop")
        finally:
            mock.stop()


@test
def test_live_retry_is_preemptive_on_a_later_step(ctx: Ctx):
    """The second turn against the same endpoint never re-pays the round
    trip -- the learned fix is applied before the first attempt even goes
    out, so there is exactly ONE upstream request for turn 2, not two."""
    fh = build_fake_home()
    with _Env(fh):
        mock = MockDatabricks().start()
        try:
            session = _new_dbx_session(fh, mock, model="dbx:databricks-gpt-5-param-reject-unless-dropped")
            list(session.turn("hello"))
            count_after_first_turn = len(mock.requests)
            list(session.turn("hello again"))
            new_requests = mock.requests[count_after_first_turn:]
            ctx.check(f"exactly one upstream attempt on the second turn, got {len(new_requests)}",
                      len(new_requests) == 1)
            ctx.check(f"max_tokens was never sent at all, got {new_requests[0]['body']}",
                      "max_tokens" not in (new_requests[0]["body"] or {}))
        finally:
            mock.stop()


# ---------------------------------------------------------------------------
# `halo rules` / `/rules` / `halo models refresh --forget-rules` (deliverable
# 2) -- the CLI and slash-command surfaces over the same persistence layer.
# ---------------------------------------------------------------------------

class _StateEnv:
    """Scopes BRIDGE_STATE_DIR directly (the CLI commands under test call
    `bridge_home()` with no Session/BRIDGE_TEST_HOME involved at all)."""

    def __enter__(self):
        self._saved = os.environ.get("BRIDGE_STATE_DIR")
        self.state_dir = Path(tempfile.mkdtemp(prefix="learned-params-cli-"))
        os.environ["BRIDGE_STATE_DIR"] = str(self.state_dir)
        return self

    def __exit__(self, *exc):
        if self._saved is None:
            os.environ.pop("BRIDGE_STATE_DIR", None)
        else:
            os.environ["BRIDGE_STATE_DIR"] = self._saved


@test
def test_halo_rules_cli_lists_and_forgets(ctx: Ctx):
    import io
    from contextlib import redirect_stdout
    from halo_harness.providers.learned_params import ParamFix, learn_param_fix
    from halo_harness.rules_cli import cmd_rules
    with _StateEnv() as env:
        learn_param_fix(env.state_dir, "databricks", "cli-m1", ParamFix(field="metadata", action="drop", error="x"))
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cmd_rules([])
        ctx.check(f"exit 0, got {rc}", rc == 0)
        ctx.check(f"lists endpoint+field, got {out.getvalue()!r}",
                  "databricks:cli-m1" in out.getvalue() and "metadata" in out.getvalue())

        out2 = io.StringIO()
        with redirect_stdout(out2):
            rc2 = cmd_rules(["--forget", "databricks:cli-m1"])
        ctx.check(f"forget exit 0, got {rc2}", rc2 == 0)

        out3 = io.StringIO()
        with redirect_stdout(out3):
            rc3 = cmd_rules(["--forget", "databricks:cli-m1"])
        ctx.check(f"forgetting again is a non-zero no-op, got rc={rc3}", rc3 == 1)


@test
def test_slash_rules_renders_the_same_listing_and_forgets(ctx: Ctx):
    from halo_harness.commands.builtins import _cmd_rules
    from halo_harness.providers.learned_params import ParamFix, learn_param_fix, learned_param_fix

    class _FakeFacade:
        pass

    with _StateEnv() as env:
        learn_param_fix(env.state_dir, "databricks", "slash-m1", ParamFix(field="strict", action="drop", error="x"))
        text = _cmd_rules("", _FakeFacade())
        ctx.check(f"lists it, got {text!r}", "databricks:slash-m1" in text and "strict" in text)
        forgot = _cmd_rules("forget databricks:slash-m1", _FakeFacade())
        ctx.check(f"forgot it, got {forgot!r}", "forgot" in forgot)
        ctx.check("gone", learned_param_fix(env.state_dir, "databricks", "slash-m1", "strict") is None)
        usage = _cmd_rules("forget", _FakeFacade())
        ctx.check(f"bare 'forget' with no endpoint is a usage message, got {usage!r}", usage.startswith("Usage:"))


@test
def test_models_forget_rules_flag_clears_every_endpoint(ctx: Ctx):
    import io
    from contextlib import redirect_stdout
    from halo_harness.catalog_cli import cmd_models
    from halo_harness.providers.learned_params import ParamFix, learn_param_fix, list_param_rules
    with _StateEnv() as env:
        learn_param_fix(env.state_dir, "databricks", "a", ParamFix(field="store", action="drop", error="x"))
        learn_param_fix(env.state_dir, "databricks", "b", ParamFix(field="strict", action="drop", error="x"))
        out = io.StringIO()
        with redirect_stdout(out):
            cmd_models(["--forget-rules"])
        ctx.check(f"printed a result line, got {out.getvalue()!r}", "2 endpoint" in out.getvalue())
        ctx.check("every endpoint's params cleared", list_param_rules(env.state_dir) == [])


# ---------------------------------------------------------------------------
# `halo doctor --work --probe-all --learn` (deliverable 2): cost estimate
# printed first, learns from live 400s against a mock Databricks gateway,
# never sends a thing without the flag.
# ---------------------------------------------------------------------------

@test
def test_doctor_probe_all_learn_prints_estimate_first_and_learns(ctx: Ctx):
    import io
    from contextlib import redirect_stdout
    from halo_harness.doctor import cmd_doctor
    from halo_harness.providers.databricks import write_dbx_endpoints_json
    from halo_harness.providers.learned_params import list_param_rules

    def _parsed(name, fm_name):
        return {"name": name, "task": "llm/v1/chat", "ready": None, "permission_level": None,
                "endpoint_type": None, "ai_gateway_v2_supported": None,
                "api_types": ["mlflow/v1/chat/completions"], "foundation_model_name": fm_name, "model_class": None}

    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_ENV_FILE",
                                             "BRIDGE_DBX_BASE_URL", "BRIDGE_DBX_TOKEN")}
    d = Path(tempfile.mkdtemp(prefix="learned-params-doctor-learn-"))
    state_dir = d / ".halo"
    os.environ["BRIDGE_TEST_HOME"] = str(d)
    os.environ["BRIDGE_STATE_DIR"] = str(state_dir)
    os.environ["BRIDGE_ENV_FILE"] = str(d / "no-env-file")
    mock = MockDatabricks().start()
    try:
        os.environ["BRIDGE_DBX_BASE_URL"] = mock.root
        os.environ["BRIDGE_DBX_TOKEN"] = "tok"
        endpoint = "databricks-glm-5-3-learn-probe"
        # The mlflow/v1/chat route sends the FOUNDATION model name (not the
        # endpoint name) as the wire body's "model" field -- the mock's own
        # scenario dispatch keys off whichever of the two actually lands on
        # the wire (mock_databricks.py's do_POST reads body["model"] first),
        # so the scenario suffix has to live on `foundation_model_name` here.
        write_dbx_endpoints_json(state_dir, [_parsed(endpoint, "glm-5-3-stream-options-reject")])

        out_without = io.StringIO()
        with redirect_stdout(out_without):
            cmd_doctor(["--work", "--probe-all"])
        probes_without_learn = len(mock.requests)

        out = io.StringIO()
        with redirect_stdout(out):
            cmd_doctor(["--work", "--probe-all", "--learn"])
        text = out.getvalue()
        estimate_pos = text.find("probe request(s)")
        learned_pos = text.find("Learned ")
        ctx.check(f"cost estimate line present, got:\n{text}", estimate_pos != -1)
        ctx.check("cost estimate printed BEFORE the learned-count line", 0 <= estimate_pos < learned_pos)
        ctx.check(f"without --learn, no probe requests were sent at all beyond the plain pong, got "
                  f"{probes_without_learn}", probes_without_learn == 1)

        rows = list_param_rules(state_dir)
        ctx.check(f"learned exactly the one field this endpoint rejects, got {rows}",
                  len(rows) == 1 and rows[0]["field"] == "stream_options" and rows[0]["action"] == "drop")
        ctx.check(f"keyed to the probed endpoint, got {rows}", rows[0]["endpoint"] == f"databricks:{endpoint}")
    finally:
        mock.stop()
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
