"""tests.test_ollama_calibrate_step_up_5b2 -- Halo 2.0.3 round 5b part 2
(brief item 7, part 1 follow-ups): `run_calibration`'s own step-UP phase
(bounded by trained context and the hard cap, `--no-up` skips it) against
scripted `/api/ps` sequences, and the auto-calibrate notice actually
draining from the two secondary call sites (`call_small_model`,
`_run_compaction`) that part 1 left unflushed.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_ollama import MockUpstream, SCENARIOS

test, TESTS = new_registry()
_GB = 1024 ** 3


class _StepScenario:
    """Same shape as tests/test_ollama_calibrate.py's own helper -- each
    `/api/chat` call advances `mock.ps_response` to the next scripted
    `/api/ps` snapshot before answering trivially."""

    def __init__(self, mock: MockUpstream, ps_steps: list):
        self.mock = mock
        self.ps_steps = ps_steps
        self.calls = 0

    def __call__(self, handler, body) -> None:
        idx = min(self.calls, len(self.ps_steps) - 1)
        entry = self.ps_steps[idx]
        self.mock.ps_response = {"models": [entry]} if entry else {"models": []}
        self.calls += 1
        SCENARIOS["done-reason-stop"](handler, body)


# ---- step-up phase -------------------------------------------------------

@test
def test_steps_up_from_a_fitting_first_guess(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import run_calibration
    mock = MockUpstream().start()
    model = "qwen3-coder:30b"
    try:
        # Fits at 8192 (the starting candidate) AND at 16384 AND at 32768;
        # NOT fully resident at 65536 -- the true ceiling is 32768.
        mock.scenarios[model] = _StepScenario(mock, [
            {"model": model, "size": 10 * _GB, "size_vram": 10 * _GB},   # 8192: fits
            {"model": model, "size": 10 * _GB, "size_vram": 10 * _GB},   # 16384: fits
            {"model": model, "size": 10 * _GB, "size_vram": 10 * _GB},   # 32768: fits
            {"model": model, "size": 20 * _GB, "size_vram": 5 * _GB},    # 65536: does NOT fit
        ])
        host = OllamaHost(name="mock", url=mock.base_url)
        result = run_calibration(host, model, start_ctx=8192, step_up=True, hard_cap=131072)
        ctx.check(f"fits, got {result.outcome!r}", result.outcome == "fits")
        ctx.check(f"stepped UP to the true ceiling 32768, got {result.max_full_gpu_ctx}",
                  result.max_full_gpu_ctx == 32768)
        ctx.check(f"4 steps (8192, 16384, 32768, 65536-fails), got {result.steps}", result.steps == 4)
    finally:
        mock.stop()


@test
def test_no_up_skips_the_step_up_phase(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import run_calibration
    mock = MockUpstream().start()
    model = "qwen3-coder:30b"
    try:
        mock.scenarios[model] = _StepScenario(mock, [{"model": model, "size": 10 * _GB, "size_vram": 10 * _GB}])
        host = OllamaHost(name="mock", url=mock.base_url)
        result = run_calibration(host, model, start_ctx=8192, step_up=False, hard_cap=131072)
        ctx.check(f"stays at the first fitting guess, got {result.max_full_gpu_ctx}",
                  result.max_full_gpu_ctx == 8192)
        ctx.check(f"exactly one step (never tries 16384), got {result.steps}", result.steps == 1)
    finally:
        mock.stop()


@test
def test_step_up_bounded_by_trained_context(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import run_calibration
    mock = MockUpstream().start()
    model = "qwen3-coder:30b"
    try:
        # Would ALSO fit at 16384 if tried, but trained_context=8192 must
        # stop the up-phase from ever trying past the model's own window.
        mock.scenarios[model] = _StepScenario(mock, [{"model": model, "size": 10 * _GB, "size_vram": 10 * _GB}])
        host = OllamaHost(name="mock", url=mock.base_url)
        result = run_calibration(host, model, start_ctx=8192, step_up=True, trained_context=8192, hard_cap=131072)
        ctx.check(f"never probes past the trained context, got {result.max_full_gpu_ctx}",
                  result.max_full_gpu_ctx == 8192)
        ctx.check(f"exactly one step, got {result.steps}", result.steps == 1)
    finally:
        mock.stop()


@test
def test_step_up_bounded_by_hard_cap(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import run_calibration
    mock = MockUpstream().start()
    model = "qwen3-coder:30b"
    try:
        # Every candidate "fits" (tiny weights, huge VRAM) -- without a
        # hard cap this would double forever; hard_cap=16384 must stop it.
        mock.scenarios[model] = _StepScenario(mock, [{"model": model, "size": 1 * _GB, "size_vram": 100 * _GB}])
        host = OllamaHost(name="mock", url=mock.base_url)
        result = run_calibration(host, model, start_ctx=8192, step_up=True, hard_cap=16384)
        ctx.check(f"stops exactly at the hard cap, got {result.max_full_gpu_ctx}", result.max_full_gpu_ctx == 16384)
        ctx.check(f"two steps (8192, 16384 -- 32768 would exceed the cap, never tried), got {result.steps}",
                  result.steps == 2)
    finally:
        mock.stop()


@test
def test_auto_calibration_passes_trained_context_through(ctx: Ctx):
    """`run_auto_calibration` (the automatic trigger) now also steps up,
    bounded by this model's OWN trained context from the catalog --
    `qwen3:30b` is mock_ollama's own default fixture, trained context
    40960."""
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import lookup_learned_cap, run_auto_calibration
    d = Path(tempfile.mkdtemp(prefix="ol-autocal-stepup-"))
    mock = MockUpstream().start()
    model = "qwen3:30b"
    try:
        mock.scenarios[model] = _StepScenario(mock, [{"model": model, "size": 1 * _GB, "size_vram": 1 * _GB}])
        host = OllamaHost(name="mock", url=mock.base_url)
        os.environ["BRIDGE_STATE_DIR"] = str(d)
        notice = run_auto_calibration(host, model, state_dir=d)
        ctx.check(f"a plain notice, got {notice!r}", isinstance(notice, str))
        got_cap = lookup_learned_cap(d, host_url=host.url, model=model)
        # Tiny weights (1 GiB) + huge headroom means it steps up past the
        # 32768 starting guess but must still stop AT or before the
        # catalog's trained context (40960), never past it.
        ctx.check(f"stepped up, but never past the trained context (40960), got {got_cap}",
                  isinstance(got_cap, int) and 32768 <= got_cap <= 40960)
    finally:
        mock.stop()
        os.environ.pop("BRIDGE_STATE_DIR", None)


# ---- notice flush from the two secondary call sites ----------------------

def _minimal_session(state_dir, mock, *, model="plain-text"):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    cwd = Path(tempfile.mkdtemp(prefix="ol-notice-flush-cwd-"))
    session_ctx = SessionContext(cwd=cwd, model_label=f"ol:{model}")
    return Session(
        cwd=cwd, model_ref=parse_model_ref(f"ol:{model}"),
        model_profile=ModelProfile(context_tokens=10_000, max_output_tokens=1_000),
        creds=ProviderCreds(base_url=mock.base_url, api_key=""),
        state_dir=Path(state_dir), model_label=f"ol:{model}",
        session_context=session_ctx, max_turns=10,
        permission_engine=PermissionEngine(mode="auto", cwd=cwd),
    )


@test
def test_drain_pending_ollama_notices_pops_and_clears(ctx: Ctx):
    mock = MockUpstream().start()
    d = Path(tempfile.mkdtemp(prefix="ol-drain-"))
    try:
        session = _minimal_session(d, mock)
        session._pending_ollama_notices.append("notice A")
        session._pending_ollama_notices.append("notice B")
        drained = session._drain_pending_ollama_notices()
        ctx.check(f"both notices drained in order, got {drained!r}", drained == ["notice A", "notice B"])
        ctx.check("the queue is cleared", session._pending_ollama_notices == [])
        ctx.check("a second drain is empty (never shown twice)", session._drain_pending_ollama_notices() == [])
    finally:
        mock.stop()


@test
def test_call_small_model_drains_notices_via_log_not_return_value(ctx: Ctx):
    """`call_small_model` has no event stream to yield a `notification`
    through, and several of its callers (title text, /improve drafts, a
    hook's own decision text) must never have their return value polluted
    with an extra line -- the notice is drained (so it never sits queued
    forever) but surfaces via the logger, not the returned string."""
    mock = MockUpstream().start()
    d = Path(tempfile.mkdtemp(prefix="ol-smallmodel-notice-"))
    try:
        session = _minimal_session(d, mock)
        session._pending_ollama_notices.append("a calibration happened")
        reply = session.call_small_model(system_text="sys", user_text="say hi", model_ref=session.model_ref)
        ctx.check(f"the reply text is clean, got {reply!r}", "calibration" not in reply)
        ctx.check("the notice queue was drained by this call", session._pending_ollama_notices == [])
    finally:
        mock.stop()


@test
def test_run_compaction_yields_notification_for_a_pending_notice(ctx: Ctx):
    """`_run_compaction` IS a real event-yielding generator (unlike
    `call_small_model`) -- a notice queued before/during its own summary
    call must come out as an ordinary `notification` event, the same way
    `_step`'s own main-turn flush already does."""
    from tests.helpers.fake_home import build_fake_home
    mock = MockUpstream().start()
    fh = build_fake_home()
    try:
        session = _minimal_session(Path(tempfile.mkdtemp(prefix="ol-compact-notice-")), mock)
        filler = "x" * 400
        for i in range(60):
            session.log.append_user([{"type": "text", "text": f"question number {i} -- {filler}"}])
            session.log.append_assistant(content=[{"type": "text", "text": f"answer number {i}. {filler}"}],
                                          stop_reason="end_turn")
        session._pending_ollama_notices.append("calibrated during compaction")
        events_seen = list(session._run_compaction(1, trigger="manual"))
        notif = [e for e in events_seen if e.kind == "notification"]
        ctx.check(f"a notification event was yielded, got {[e.data for e in notif]!r}",
                  any(e.data.get("text") == "calibrated during compaction" for e in notif))
        ctx.check("the queue was drained", session._pending_ollama_notices == [])
    finally:
        mock.stop()


# ---- review fix pass finding 4: "remember a successful retry" consumed ---

@test
def test_build_ollama_body_for_ref_folds_in_a_remembered_retry(ctx: Ctx):
    """Review fix pass (finding 4), the read/consume half of "remember a
    successful retry for the rest of the session": once `providers.
    ollama.remember_ollama_retry_num_ctx` has recorded a bigger num_ctx
    for (host, model), `_build_ollama_body_for_ref` must fold it in as an
    extra learned_cap-like candidate for the NEXT turn, replacing the
    "nothing known" conservative default (finding 5) once there IS
    something known -- but (finding 6) still bounded by trained_context/
    hard_cap, and still beaten by a SMALLER live fit_estimate were one
    present (none is, here -- `fit_estimate=None` is the realistic case
    this mechanism helps most: no live GPU/`/api/ps` reading available
    this turn at all). Both `resolve_ollama_host` (so the method's own
    host lookup lands on the mock, not the real default) and `resolve_
    context_decision` (a FIXED decision, so the real OS-level GPU/
    catalog probing it would otherwise do -- covered elsewhere -- never
    makes this one non-deterministic) are monkeypatched for this test
    only."""
    import halo_harness.agent.loop as loop_mod
    import halo_harness.providers.ollama_hw as ollama_hw_mod
    from halo_harness.providers.ollama import OllamaHost, remember_ollama_retry_num_ctx, reset_remembered_ollama_retries
    from halo_harness.providers.ollama_hw import OllamaContextDecision
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.routing import Route
    reset_remembered_ollama_retries()
    mock = MockUpstream().start()
    d = Path(tempfile.mkdtemp(prefix="ol-remember-fold-"))
    model = "remember-fold-model"
    real_resolve_host = loop_mod.resolve_ollama_host
    real_resolve_decision = ollama_hw_mod.resolve_context_decision
    fixed_host = OllamaHost(name="mock", url=mock.base_url)
    loop_mod.resolve_ollama_host = lambda name, env: fixed_host
    ollama_hw_mod.resolve_context_decision = lambda model_ref, env=None, **kw: OllamaContextDecision(
        trained_context=40960, fit_estimate=None, num_ctx=32768, tools_max=16, catalog_prompt_tokens=0,
        learned_cap=None, remote=False)
    try:
        session = _minimal_session(d, mock, model=model)
        route = Route(provider="ollama", upstream_model=model, dialect="ollama")
        profile = resolve_profile(route)
        kwargs = dict(ref=session.model_ref, route=route, profile=profile, system_text="sys",
                      messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
                      tools=[], tool_choice=None, effort=None, requested_max_tokens=256)
        before = session._build_ollama_body_for_ref(**kwargs)
        before_ctx = (before.get("options") or {}).get("num_ctx")
        ctx.check(f"without a remembered retry, nothing known -> the conservative default (32768), got "
                  f"{before_ctx}", before_ctx == 32768)
        remember_ollama_retry_num_ctx(mock.base_url, model, 16384)
        after = session._build_ollama_body_for_ref(**kwargs)
        after_ctx = (after.get("options") or {}).get("num_ctx")
        ctx.check(f"a remembered retry (16384) now wins over the blanket conservative default, got {after_ctx}",
                  after_ctx == 16384)
        # A SECOND, oversized remembered value must still never exceed
        # the trained context (finding 6: a cap competes in the same
        # min(), it never bypasses trained_context/hard_cap).
        remember_ollama_retry_num_ctx(mock.base_url, model, 999_999)
        after2 = session._build_ollama_body_for_ref(**kwargs)
        after2_ctx = (after2.get("options") or {}).get("num_ctx")
        ctx.check(f"an oversized remembered value is still capped at the trained context (40960), got "
                  f"{after2_ctx}", after2_ctx == 40960)
    finally:
        loop_mod.resolve_ollama_host = real_resolve_host
        ollama_hw_mod.resolve_context_decision = real_resolve_decision
        mock.stop()


@test
def test_build_ollama_body_for_ref_sends_think_only_when_effort_is_explicit_this_session(ctx: Ctx):
    """Review fix pass (finding 16) -- the brief's own pinning case:
    `session.effort_source` simulates a CARRIED `last_effort` (source
    "last", persisted from an EARLIER session -- never an explicit
    choice made THIS session) vs an EXPLICIT `/effort` (source
    "session", the exact tag `commands.builtins._cmd_effort` sets on a
    live session). The model is thinking-capable throughout
    (`resolve_context_decision` is monkeypatched to say so, same seam
    `test_build_ollama_body_for_ref_folds_in_a_remembered_retry` above
    uses) -- only the effort's own provenance changes between the two
    calls, computed the SAME way the real `_derive_and_build` call site
    does (`self.effort_source in ("flag", "session")`)."""
    import halo_harness.agent.loop as loop_mod
    import halo_harness.providers.ollama_hw as ollama_hw_mod
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_hw import OllamaContextDecision
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.routing import Route
    mock = MockUpstream().start()
    d = Path(tempfile.mkdtemp(prefix="ol-think-explicit-"))
    model = "thinking-capable-model"
    real_resolve_host = loop_mod.resolve_ollama_host
    real_resolve_decision = ollama_hw_mod.resolve_context_decision
    fixed_host = OllamaHost(name="mock", url=mock.base_url)
    loop_mod.resolve_ollama_host = lambda name, env: fixed_host
    ollama_hw_mod.resolve_context_decision = lambda model_ref, env=None, **kw: OllamaContextDecision(
        trained_context=40960, fit_estimate=None, num_ctx=32768, tools_max=16, catalog_prompt_tokens=0,
        learned_cap=None, remote=False, supports_thinking=True)
    try:
        session = _minimal_session(d, mock, model=model)
        route = Route(provider="ollama", upstream_model=model, dialect="ollama")
        profile = resolve_profile(route)
        kwargs = dict(ref=session.model_ref, route=route, profile=profile, system_text="sys",
                      messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
                      tools=[], tool_choice=None, effort="high", requested_max_tokens=256)

        session.effort_source = "last"  # carried from an earlier session, nothing set THIS session
        carried = session._build_ollama_body_for_ref(
            **kwargs, effort_explicit=session.effort_source in ("flag", "session"))
        ctx.check(f"a carried effort with no explicit set this session sends no think, got "
                  f"{carried.get('think', 'OMITTED')!r}", "think" not in carried)

        session.effort_source = "session"  # an explicit /effort THIS session
        explicit = session._build_ollama_body_for_ref(
            **kwargs, effort_explicit=session.effort_source in ("flag", "session"))
        ctx.check(f"an explicit /effort on a thinking-capable model sends think, got "
                  f"{explicit.get('think', 'OMITTED')!r}", explicit.get("think") is True)
    finally:
        loop_mod.resolve_ollama_host = real_resolve_host
        ollama_hw_mod.resolve_context_decision = real_resolve_decision
        mock.stop()


# ---- review fix pass finding 8: abort/budget, never in call_small_model --

@test
def test_maybe_auto_calibrate_respects_abort_and_a_total_budget(ctx: Ctx):
    """Review fix pass (finding 8): the actual measurement runs in a
    background thread this method waits on only up to a bounded total
    budget, polling `self.abort` too -- the budget elapsing or Esc firing
    must stop the TURN from waiting any further (no abort hook reaches
    this deep into the HTTP layer to cut an in-flight request off mid-
    socket-read, so the background thread is left to finish -- or time
    out -- on its own; the dedupe flag is set regardless, so this
    process never re-attempts the same pair)."""
    import halo_harness.providers.ollama_calibrate as calib_mod
    from halo_harness.providers.ollama import OllamaHost
    mock = MockUpstream().start()
    d = Path(tempfile.mkdtemp(prefix="ol-autocal-abort-"))
    old_no_net = os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
    real_run_auto_calibration = calib_mod.run_auto_calibration
    started = threading.Event()
    release = threading.Event()

    def _slow_run_auto_calibration(host, model, *, state_dir, **kw):
        started.set()
        release.wait(timeout=5)  # held open until this test lets it go
        return "a notice this turn must never see"

    calib_mod.run_auto_calibration = _slow_run_auto_calibration
    try:
        host = OllamaHost(name="mock", url=mock.base_url)
        session = _minimal_session(d, mock)
        start = time.monotonic()
        session._maybe_auto_calibrate_ollama(host, "budget-model", budget_s=0.5)
        elapsed = time.monotonic() - start
        ctx.check(f"stopped waiting at the budget, not the slow calibration's own return, got {elapsed:.2f}s",
                  elapsed < 2.0)
        ctx.check("the background thread actually started", started.wait(timeout=1))
        ctx.check("no notice was queued for this turn (it never finished within the budget)",
                  session._pending_ollama_notices == [])
        ctx.check("the dedupe flag was still set (never re-attempted within this process)",
                  (host.url, "budget-model") in session._ollama_calibrate_attempted)

        session2 = _minimal_session(d, mock)
        session2.abort.set()
        start2 = time.monotonic()
        session2._maybe_auto_calibrate_ollama(host, "abort-model", budget_s=5.0)
        elapsed2 = time.monotonic() - start2
        ctx.check(f"an already-set abort stops the wait almost immediately, got {elapsed2:.2f}s", elapsed2 < 1.0)
    finally:
        release.set()
        calib_mod.run_auto_calibration = real_run_auto_calibration
        if old_no_net is not None:
            os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = old_no_net
        mock.stop()


# ---- review fix pass finding 14: the offloaded-turn notice + learned cap -

@test
def test_maybe_record_offload_learned_cap_records_and_notices(ctx: Ctx):
    """Review fix pass (finding 14): "on an offloaded /api/ps read after
    a turn, print the one sentence with the size that fit, and record it
    as a learned cap." `_record_last_known_offload` is seeded directly
    (the same real `/api/ps` read a full turn would have made -- pinned
    elsewhere, `tests/test_ollama_hw_5b.py`) so this test isolates the
    NEW post-turn behaviour itself: a real learned-cap record, and a
    notice naming `ollama.hosts[].max_ctx`, computed from the KV-bytes-
    per-token formula against the REAL size_vram this load got (never a
    live GPU probe)."""
    from halo_harness.providers import ollama_hw
    from halo_harness.providers.ollama_calibrate import lookup_learned_cap
    from halo_harness.theme import set_config_value
    model = "offload-cap-model"
    weight_bytes = 4 * _GB
    # KV bytes/token 131072 (f16; head_dim 4096/32=128; 2*32*8*128*2.0),
    # the SAME fixture tests/test_providers_ollama_hw.py's own
    # _QWEN_MODEL_INFO uses -- 256 MiB of KV headroom holds exactly 2048
    # tokens (256*1024*1024 / 131072 == 2048, already a power of two, so
    # the floor never rounds it down further).
    model_info = {"qwen3.block_count": 32, "qwen3.attention.head_count_kv": 8,
                  "qwen3.attention.head_count": 32, "qwen3.embedding_length": 4096}
    size_vram = weight_bytes + 256 * 1024 * 1024
    total_size = weight_bytes + 1 * _GB  # bigger than size_vram -- a genuine partial offload
    d = Path(tempfile.mkdtemp(prefix="ol-offload-cap-"))
    old_state_dir = os.environ.get("BRIDGE_STATE_DIR")
    os.environ["BRIDGE_STATE_DIR"] = str(d)  # set_config_value below must land here, never the real ~/.halo
    mock = MockUpstream().start()
    try:
        mock.tags_response = {"models": [{"name": model, "model": model, "size": weight_bytes,
                                           "digest": "sha256:offloadcap", "details": {"family": "qwen3"}}]}
        mock.show_responses = {model: {"modelfile": "", "parameters": "", "template": "",
                                        "capabilities": [], "details": {"family": "qwen3"},
                                        "model_info": model_info}}
        set_config_value("ollama.hosts", [{"name": "mock", "url": mock.base_url, "default": True}])
        session = _minimal_session(d, mock, model=model)
        ollama_hw._record_last_known_offload(mock.base_url, model, {"size": total_size, "size_vram": size_vram})
        session._maybe_record_offload_learned_cap(mock.base_url, model)
        got_cap = lookup_learned_cap(session.state_dir, host_url=mock.base_url, model=model)
        ctx.check(f"the learned cap was recorded from the real size_vram, got {got_cap}", got_cap == 2048)
        ctx.check(f"a notice was queued naming ollama.hosts[].max_ctx, got {session._pending_ollama_notices!r}",
                  any("ollama.hosts[].max_ctx" in n and "2048" in n for n in session._pending_ollama_notices))
    finally:
        ollama_hw._record_last_known_offload(mock.base_url, model, None)  # leave no cross-test cache residue
        mock.stop()
        if old_state_dir is None:
            os.environ.pop("BRIDGE_STATE_DIR", None)
        else:
            os.environ["BRIDGE_STATE_DIR"] = old_state_dir


@test
def test_maybe_record_offload_learned_cap_skips_when_kv_formula_inputs_are_missing(ctx: Ctx):
    """The graceful-degrade half of the SAME fix: a catalog row with no
    usable KV-formula fields (the ordinary case for a model the test
    suite hasn't fully fixtured) must record nothing and queue no
    notice, never raise."""
    from halo_harness.providers import ollama_hw
    from halo_harness.providers.ollama_calibrate import has_calibration_entry
    from halo_harness.theme import set_config_value
    model = "offload-nocap-model"
    d = Path(tempfile.mkdtemp(prefix="ol-offload-nocap-"))
    old_state_dir = os.environ.get("BRIDGE_STATE_DIR")
    os.environ["BRIDGE_STATE_DIR"] = str(d)
    mock = MockUpstream().start()
    try:
        mock.tags_response = {"models": [{"name": model, "model": model, "size": 4 * _GB,
                                           "digest": "sha256:x", "details": {}}]}
        mock.show_responses = {model: {"modelfile": "", "parameters": "", "template": "",
                                        "capabilities": [], "details": {}, "model_info": {}}}
        set_config_value("ollama.hosts", [{"name": "mock", "url": mock.base_url, "default": True}])
        session = _minimal_session(d, mock, model=model)
        ollama_hw._record_last_known_offload(mock.base_url, model, {"size": 5 * _GB, "size_vram": 4 * _GB})
        session._maybe_record_offload_learned_cap(mock.base_url, model)
        ctx.check("no notice queued", session._pending_ollama_notices == [])
        ctx.check("nothing recorded", has_calibration_entry(session.state_dir, host_url=mock.base_url,
                                                              model=model) is False)
    finally:
        ollama_hw._record_last_known_offload(mock.base_url, model, None)
        mock.stop()
        if old_state_dir is None:
            os.environ.pop("BRIDGE_STATE_DIR", None)
        else:
            os.environ["BRIDGE_STATE_DIR"] = old_state_dir


@test
def test_call_small_model_never_triggers_auto_calibration(ctx: Ctx):
    """Review fix pass (finding 8): `call_small_model` must never trigger
    auto-calibration at all -- its own `timeout_s` budget is meant to
    bound the small-model request itself, not a first-use calibration
    probe stacked underneath it. The dedupe set staying COMPLETELY EMPTY
    is the proof: `_maybe_auto_calibrate_ollama` adds its `(host.url,
    model)` key unconditionally, before any other gate, the moment it is
    CALLED at all (unlike test_maybe_auto_calibrate_respects_abort_and_a_
    total_budget just above, where a direct call DOES add one) -- so an
    empty set means the method was never reached from `call_small_model`,
    regardless of which host it would have resolved to."""
    mock = MockUpstream().start()
    d = Path(tempfile.mkdtemp(prefix="ol-smallmodel-nocalib-"))
    try:
        # "plain-text" (_minimal_session's own default) is a REAL scripted
        # mock_ollama.py scenario -- an arbitrary model name here gets a
        # 404 "unknown mock scenario" (an UNCAUGHT UpstreamError, since
        # call_small_model has no try/except around the stream it reads),
        # unrelated to what this test means to isolate.
        session = _minimal_session(d, mock)
        session.call_small_model(system_text="sys", user_text="say hi", model_ref=session.model_ref)
        ctx.check(f"auto-calibration was never even attempted, got {session._ollama_calibrate_attempted}",
                  session._ollama_calibrate_attempted == set())
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
