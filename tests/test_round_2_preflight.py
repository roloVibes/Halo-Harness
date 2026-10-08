"""tests.test_round_2_preflight -- Halo 2.0.7 cyber Pillar 2:
verify-everything preflight + continuous canaries.

  * local tools verified BY EFFECT (the bytes are on disk, the grep
    matched -- not just "didn't raise");
  * one measured canary per lane: a real completion, a tool call the
    lane must emit and the probe must actually run, an image the lane
    must accept when its profile claims vision, and a truncation check
    (usage echo vs what was sent);
  * the canary census on disk (`<state_dir>/canary-census.json`);
  * `halo preflight` exit codes (0 all-pass / 1 any-fail / 2 usage);
  * the continuous in-run canary: truncation suspicion (one-time) and
    the periodic health note (env-tunable cadence), zero extra requests.
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


def _tool_call_step(name: str, arguments: dict, call_id: str = "call_pc1") -> list:
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"tool_calls": [
            {"index": 0, "id": call_id, "type": "function",
             "function": {"name": name, "arguments": json.dumps(arguments)}},
        ]}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
    ]


def _usage_chunks(input_tokens: int, output_tokens: int = 5) -> list:
    """A step's final chunk carrying a usage echo (mock passthrough)."""
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": "pong"}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
         "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens}},
    ]


# ---- local checks by effect -----------------------------------------------------


@test
def test_local_checks_verify_effects_and_fail_on_mismatch(ctx: Ctx):
    from halo_harness.preflight import run_local_checks

    scratch = Path(tempfile.mkdtemp(prefix="r2pf-local-"))
    checks = run_local_checks(scratch)
    by_name = {c["name"]: c for c in checks}
    ctx.check(f"three check groups ran, got {sorted(by_name)}",
              set(by_name) == {"Bash", "Write+Read+Edit", "Glob+Grep"})
    ctx.check("all pass on a healthy scratch dir", all(c["ok"] for c in checks))
    probe_file = scratch / "preflight-probe.txt"
    ctx.check("the effect is really on disk (Write+Edit both landed)",
              probe_file.exists() and "line two" in probe_file.read_text(encoding="utf-8"))

    # Effect mismatch fails the gate: sabotage Edit so the file never
    # changes, and the Write+Read+Edit check must go red.
    scratch2 = Path(tempfile.mkdtemp(prefix="r2pf-sab-"))
    from halo_harness.tools.edit import EditTool as _RealEdit
    real_edit = _RealEdit.run

    def _broken_edit(self, input, ctx2):
        from halo_harness.tools.base import ToolResult
        return ToolResult("(pretend ok)", is_error=False)  # lies: no effect

    _RealEdit.run = _broken_edit
    try:
        checks2 = run_local_checks(scratch2)
    finally:
        _RealEdit.run = real_edit
    by_name2 = {c["name"]: c for c in checks2}
    ctx.check("a lying tool fails its effect check",
              by_name2["Write+Read+Edit"]["ok"] is False)


# ---- the lane canary -------------------------------------------------------------
#
# Scenario step order keys on TOOL-RESULT count in the request (mock's
# ScriptedTurns): the canary runs its TOOL turn first (step 0 = the tool
# call, step 1 = its follow-up), so every later turn (text, vision) is
# served step 1 -- which therefore must be the usage-carrying text step.


@test
def test_lane_canary_full_pass_text_tools_and_census(ctx: Ctx):
    SCENARIOS["r2pf-lane"] = ScriptedTurns([
        _tool_call_step("PreflightProbe", {"echo": "canary42"}),  # tool turn, call 1
        _usage_chunks(2400),              # tool follow-up + text canary + vision turns
    ])
    mock = MockUpstream().start()
    try:
        from halo_harness.preflight import run_lane_canary
        state = Path(tempfile.mkdtemp(prefix="r2pf-state-"))
        result = run_lane_canary("or:mock/r2pf-lane", state_dir=state,
                                 openrouter_base_url=mock.base_url, timeout_s=60)
        ctx.check(f"canary overall ok, err={result['error']!r}", result["ok"] is True)
        ctx.check("tool canary passed (the probe really ran)",
                  result["checks"]["tools"] is True)
        ctx.check("text canary passed", result["checks"]["text"] is True)
        ctx.check("truncation check passed (usage echo covers the pad)",
                  result["checks"]["truncation"] is True)
        ctx.check("vision not claimed -> not tested", result["checks"]["vision"] is None)
        ctx.check("run_lane_canary itself does not write the census (the CLI records)",
                  not (state / "canary-census.json").exists())
        from halo_harness.preflight import record_canary_result
        record_canary_result(state, "or:mock/r2pf-lane", result)
        census = json.loads((state / "canary-census.json").read_text(encoding="utf-8"))
        entry = census["lanes"]["or:mock/r2pf-lane"]
        ctx.check("the census entry carries the verdict", entry["ok"] is True)
        ctx.check("and the checks", entry["checks"]["tools"] is True)
        ctx.check("and a recorded timestamp", isinstance(entry.get("recorded"), float))
    finally:
        mock.stop()


@test
def test_lane_canary_flags_a_lane_that_never_calls_tools(ctx: Ctx):
    """The measured core of Pillar 2: a lane whose datasheet says tools
    but whose REPLIES never emit a tool call fails the canary -- exactly
    the lying-capability case the census exists to catch."""
    SCENARIOS["r2pf-notools"] = ScriptedTurns([
        _text_step("I would rather just answer directly."),  # never calls the probe
        _usage_chunks(2400),
    ])
    mock = MockUpstream().start()
    try:
        from halo_harness.preflight import run_lane_canary
        state = Path(tempfile.mkdtemp(prefix="r2pf-state-"))
        result = run_lane_canary("or:mock/r2pf-notools", state_dir=state,
                                 openrouter_base_url=mock.base_url, timeout_s=60)
        ctx.check("overall FAIL", result["ok"] is False)
        ctx.check("tools FAILED by measurement", result["checks"]["tools"] is False)
        ctx.check("the error says the probe never ran",
                  "probe never ran" in (result["error"] or ""))
    finally:
        mock.stop()


@test
def test_lane_canary_detects_truncation(ctx: Ctx):
    """A usage echo accounting for a tiny fraction of the padded prompt is
    a silent-truncation lane -- the canary must flag it."""
    SCENARIOS["r2pf-trunc"] = ScriptedTurns([
        _tool_call_step("PreflightProbe", {"echo": "canary42"}),
        _usage_chunks(20),   # the padded text canary "sees" ~20 of ~3100 est. tokens
    ])
    mock = MockUpstream().start()
    try:
        from halo_harness.preflight import run_lane_canary
        state = Path(tempfile.mkdtemp(prefix="r2pf-state-"))
        result = run_lane_canary("or:mock/r2pf-trunc", state_dir=state,
                                 openrouter_base_url=mock.base_url, timeout_s=60)
        ctx.check("tools still passed", result["checks"]["tools"] is True)
        ctx.check("truncation flagged", result["checks"]["truncation"] is False)
        ctx.check("and it fails the lane overall", result["ok"] is False)
    finally:
        mock.stop()


@test
def test_lane_canary_vision_checked_when_claimed(ctx: Ctx):
    from halo_harness.model import ModelProfile
    SCENARIOS["r2pf-vision"] = ScriptedTurns([
        _tool_call_step("PreflightProbe", {"echo": "canary42"}),
        _usage_chunks(2400),
    ])
    mock = MockUpstream().start()
    try:
        from halo_harness.preflight import run_lane_canary
        import halo_harness.model as model_mod
        state = Path(tempfile.mkdtemp(prefix="r2pf-state-"))
        real_model_resolve = model_mod.resolve_model_profile

        def _vision_profile(ref, state_dir, routes):
            base = real_model_resolve(ref, state_dir, routes)
            return ModelProfile(vision=True, context_tokens=base.context_tokens or 128000)

        # The canary resolves profiles through halo_harness.model; claim
        # vision for this lane (the mock profile normally has it False).
        model_mod.resolve_model_profile = _vision_profile
        try:
            result = run_lane_canary("or:mock/r2pf-vision", state_dir=state,
                                     openrouter_base_url=mock.base_url, timeout_s=60)
        finally:
            model_mod.resolve_model_profile = real_model_resolve
        ctx.check(f"vision canary ran and passed, err={result['error']!r}",
                  result["checks"]["vision"] is True)
        ctx.check("overall ok", result["ok"] is True)
        ctx.check("an image turn actually reached the mock (4 model calls)",
                  len(mock.requests) == 4)
    finally:
        mock.stop()


# ---- the CLI ----------------------------------------------------------------------


@test
def test_cmd_preflight_exit_codes_and_json(ctx: Ctx):
    """Scoped home (no pinned default model in it) so `--skip-local` with
    no --lanes is a genuine usage error, never a real-lane canary."""
    import halo_harness.config.paths as paths_mod
    import halo_harness.preflight as pf
    state = Path(tempfile.mkdtemp(prefix="r2pf-cli2-state-"))
    (state / "config.json").write_text("{}", encoding="utf-8")
    real_home = paths_mod.bridge_home
    paths_mod.bridge_home = lambda: state
    pf.bridge_home = lambda: state
    try:
        ctx.check("no lanes and no local -> usage error 2",
                  pf.cmd_preflight(["--skip-local"]) == 2)
        ctx.check("unknown argument -> 2", pf.cmd_preflight(["--bogus"]) == 2)

        # A lane with no credentials fails fast (no network): exit 1.
        code = pf.cmd_preflight(["--json", "--skip-local", "--lanes", "dbx:preflight/no-creds"])
        ctx.check(f"a credential-less lane fails the gate (exit 1), got {code}", code == 1)
    finally:
        paths_mod.bridge_home = real_home
        pf.bridge_home = real_home


@test
def test_cmd_preflight_green_path_against_the_mock(ctx: Ctx):
    """The full CLI: local checks + one lane canary through the env base-url
    seam (HALO_OPENROUTER_BASE_URL), canary census written, exit 0."""
    SCENARIOS["r2pf-cli"] = ScriptedTurns([
        _tool_call_step("PreflightProbe", {"echo": "canary42"}),
        _usage_chunks(2400),
    ])
    mock = MockUpstream().start()
    saved = {k: os.environ.get(k) for k in ("HALO_OPENROUTER_BASE_URL", "BRIDGE_OPENROUTER_BASE_URL")}
    os.environ["HALO_OPENROUTER_BASE_URL"] = mock.base_url
    state = Path(tempfile.mkdtemp(prefix="r2pf-cli-state-"))
    try:
        import halo_harness.config.paths as paths_mod
        real_home = paths_mod.bridge_home
        paths_mod.bridge_home = lambda: state
        import halo_harness.preflight as pf
        pf.bridge_home = lambda: state
        try:
            code = pf.cmd_preflight(["--lanes", "or:mock/r2pf-cli"])
        finally:
            paths_mod.bridge_home = real_home
            pf.bridge_home = real_home
        ctx.check(f"preflight exits 0 on the healthy lane, got {code}", code == 0)
        census_file = state / "canary-census.json"
        ctx.check("the canary census was written", census_file.exists())
        if census_file.exists():
            entry = json.loads(census_file.read_text(encoding="utf-8"))["lanes"]["or:mock/r2pf-cli"]
            ctx.check("the census entry is a pass", entry["ok"] is True)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        mock.stop()


# ---- the continuous canary ---------------------------------------------------------


@test
def test_continuous_canary_periodic_note_and_truncation_suspect(ctx: Ctx):
    """The in-run canary: no extra requests (the mock counts them), a
    one-time truncation warning when the usage echo is far below what was
    sent, and a periodic health note driven by HALO_CANARY_EVERY_N_CALLS."""
    SCENARIOS["r2cc"] = ScriptedTurns([
        _usage_chunks(2000),
    ])
    mock = MockUpstream().start()
    saved_env = {k: os.environ.get(k) for k in ("HALO_CANARY_EVERY_N_CALLS", "HALO_CANARY_EVERY_S")}
    os.environ["HALO_CANARY_EVERY_N_CALLS"] = "3"
    os.environ["HALO_CANARY_EVERY_S"] = "0"
    try:
        from halo_harness.agent.assemble import SessionContext
        from halo_harness.agent.loop import Session
        from halo_harness.model import ModelProfile, parse_model_ref
        from halo_harness.permissions import PermissionEngine
        from halo_harness.providers.stream import ProviderCreds

        cwd = Path(tempfile.mkdtemp(prefix="r2cc-"))
        os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="r2cc-home-")))
        session = Session(
            cwd=cwd, model_ref=parse_model_ref("or:mock/r2cc"), model_profile=ModelProfile(),
            creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
            state_dir=Path(tempfile.mkdtemp(prefix="r2cc-state-")), model_label="or:mock/r2cc",
            session_context=SessionContext(cwd=cwd, model_label="or:mock/r2cc", bare=True),
            openrouter_base_url=mock.base_url, max_turns=10,
            permission_engine=PermissionEngine(mode="auto", cwd=cwd),
            agents={}, routes={},
        )
        # Turn 1: a LONG prompt (est > 1000 tokens) with a usage echo far
        # below it -> the one-time truncation warning fires here.
        long_pad = "truncation canary filler line with several words in it. " * 120
        evs = list(session.turn(f"{long_pad}\nReply: pong"))
        notes = [e.data.get("text", "") for e in evs if e.kind == "notification"]
        ctx.check("the truncation suspect warning fired once",
                  sum("context truncation suspected" in t for t in notes) == 1)

        # Two more small turns -> 3 model calls total -> the periodic note.
        evs2 = list(session.turn("and again"))
        evs3 = list(session.turn("and once more"))
        notes_all = notes + [e.data.get("text", "") for e in evs2 + evs3 if e.kind == "notification"]
        ctx.check("the periodic health note fired by call count",
                  any(t.startswith("canary: 3 calls") for t in notes_all))
        ctx.check("the note reports the session model",
                  any("or:mock/r2cc" in t for t in notes_all if t.startswith("canary:")))
        ctx.check("no truncation warning repeat (one-time)",
                  sum("context truncation suspected" in t for t in notes_all) == 1)
        ctx.check("exactly 3 upstream requests -- the canary adds none",
                  len(mock.requests) == 3)
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
