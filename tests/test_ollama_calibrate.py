"""tests.test_ollama_calibrate -- Halo 2.0.3 round 5b item 1/2: the
`~/.halo/ollama-fit.json` store (learned caps + last-turn throughput) and
`run_calibration`'s stepping loop, against `tests/helpers/mock_ollama.
MockUpstream` -- never a real daemon, never a real model. Every test
scopes its own `BRIDGE_STATE_DIR` (never the real `~/.halo`).
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_ollama import SCENARIOS, MockUpstream

test, TESTS = new_registry()


def _fresh_state_dir(prefix: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix=prefix))
    os.environ["BRIDGE_STATE_DIR"] = str(d)
    return d


def _clear_state_dir_env() -> None:
    os.environ.pop("BRIDGE_STATE_DIR", None)


# ---- the ~/.halo/ollama-fit.json store --------------------------------

@test
def test_store_round_trip_record_and_lookup(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import lookup_learned_cap, record_calibration
    d = _fresh_state_dir("ol-fit-store-")
    try:
        record_calibration(d, host_url="http://h", model="m", digest="sha256:a", max_full_gpu_ctx=16384,
                            ollama_version="0.5.0")
        got = lookup_learned_cap(d, host_url="http://h", model="m")
        ctx.check(f"learned cap round-trips, got {got}", got == 16384)
    finally:
        _clear_state_dir_env()


@test
def test_store_has_calibration_entry_true_even_for_does_not_fit(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import has_calibration_entry, lookup_learned_cap, record_calibration
    d = _fresh_state_dir("ol-fit-store-nofit-")
    try:
        record_calibration(d, host_url="http://h", model="m", digest="sha256:a", max_full_gpu_ctx=None,
                            ollama_version="0.5.0")
        ctx.check("has_calibration_entry is True (a recorded fact, not a missing one)",
                  has_calibration_entry(d, host_url="http://h", model="m") is True)
        ctx.check("lookup_learned_cap is None (does-not-fit carries no usable cap)",
                  lookup_learned_cap(d, host_url="http://h", model="m") is None)
    finally:
        _clear_state_dir_env()


@test
def test_store_digest_mismatch_invalidates_the_cap(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import lookup_learned_cap, record_calibration
    d = _fresh_state_dir("ol-fit-store-digest-")
    try:
        record_calibration(d, host_url="http://h", model="m", digest="sha256:old", max_full_gpu_ctx=16384,
                            ollama_version="0.5.0")
        ctx.check("matching digest -> cap returned",
                  lookup_learned_cap(d, host_url="http://h", model="m", digest="sha256:old") == 16384)
        ctx.check("a DIFFERENT digest (re-pulled model) -> stale, None",
                  lookup_learned_cap(d, host_url="http://h", model="m", digest="sha256:new") is None)
        ctx.check("digest=None (the hot per-turn path) -> trusts it anyway",
                  lookup_learned_cap(d, host_url="http://h", model="m", digest=None) == 16384)
    finally:
        _clear_state_dir_env()


@test
def test_store_version_mismatch_invalidates_the_cap(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import lookup_learned_cap, record_calibration
    d = _fresh_state_dir("ol-fit-store-version-")
    try:
        record_calibration(d, host_url="http://h", model="m", digest="sha256:a", max_full_gpu_ctx=16384,
                            ollama_version="0.5.0")
        ctx.check("matching version -> cap returned",
                  lookup_learned_cap(d, host_url="http://h", model="m", ollama_version="0.5.0") == 16384)
        ctx.check("a DIFFERENT version (server upgraded) -> stale, None",
                  lookup_learned_cap(d, host_url="http://h", model="m", ollama_version="0.6.0") is None)
    finally:
        _clear_state_dir_env()


@test
def test_store_calibration_lookup_normalizes_tag_both_ways(ctx: Ctx):
    """Review fix pass (finding 9): `halo ollama calibrate qwen3:latest`
    and an `ol:qwen3` session must see each other's entry -- recorded
    under either spelling, found by the other."""
    from halo_harness.providers.ollama_calibrate import has_calibration_entry, lookup_learned_cap, record_calibration
    d = _fresh_state_dir("ol-fit-store-tagmatch-")
    try:
        record_calibration(d, host_url="http://h", model="qwen3:latest", digest="sha256:a", max_full_gpu_ctx=16384,
                            ollama_version="0.5.0")
        ctx.check("recorded under :latest, found by the bare name",
                  lookup_learned_cap(d, host_url="http://h", model="qwen3") == 16384)
        ctx.check("has_calibration_entry agrees for the bare name too",
                  has_calibration_entry(d, host_url="http://h", model="qwen3") is True)

        d2 = _fresh_state_dir("ol-fit-store-tagmatch-rev-")
        record_calibration(d2, host_url="http://h", model="qwen3", digest="sha256:a", max_full_gpu_ctx=8192,
                            ollama_version="0.5.0")
        ctx.check("recorded under the bare name, found by :latest",
                  lookup_learned_cap(d2, host_url="http://h", model="qwen3:latest") == 8192)
    finally:
        _clear_state_dir_env()


@test
def test_store_upsert_normalizes_tag_never_duplicates_across_spellings(ctx: Ctx):
    """The SAME upsert guarantee `test_store_upsert_overwrites_not_
    duplicates` pins for an identical model string, now also across an
    untagged/`:latest`-qualified spelling of the SAME model -- two
    separate `record_calibration` calls for "qwen3" then "qwen3:latest"
    must still settle on exactly one entry, never two that silently
    disagree with each other."""
    from halo_harness.providers.ollama_calibrate import load_fit_store, lookup_learned_cap, record_calibration
    d = _fresh_state_dir("ol-fit-store-tagmatch-upsert-")
    try:
        record_calibration(d, host_url="http://h", model="qwen3", digest="sha256:a", max_full_gpu_ctx=8192,
                            ollama_version="0.5.0")
        record_calibration(d, host_url="http://h", model="qwen3:latest", digest="sha256:b", max_full_gpu_ctx=16384,
                            ollama_version="0.6.0")
        entries = load_fit_store(d)["entries"]
        ctx.check(f"exactly one entry across both spellings, got {len(entries)}", len(entries) == 1)
        ctx.check(f"the latest measurement wins, got {lookup_learned_cap(d, host_url='http://h', model='qwen3')}",
                  lookup_learned_cap(d, host_url="http://h", model="qwen3") == 16384)
    finally:
        _clear_state_dir_env()


@test
def test_last_turn_throughput_normalizes_tag_both_ways(ctx: Ctx):
    """Review fix pass (finding 9): the SAME untagged/`:latest` cross-
    lookup, for the last-turn throughput record `halo ollama`'s panel
    reads back -- recorded under a session's own (often untagged) ref,
    found by the panel's own tagged catalog-row name, and vice versa."""
    from halo_harness.providers.ollama_calibrate import get_last_turn_throughput, record_last_turn_throughput
    d = _fresh_state_dir("ol-throughput-tagmatch-")
    try:
        record_last_turn_throughput(d, host_url="http://h", model="qwen3", tokens_per_second=30.0,
                                     prefill_seconds=0.5, offloaded=False)
        got = get_last_turn_throughput(d, host_url="http://h", model="qwen3:latest")
        ctx.check(f"recorded under the bare name, found by :latest, got {got}",
                  got is not None and got["tokens_per_second"] == 30.0)

        d2 = _fresh_state_dir("ol-throughput-tagmatch-rev-")
        record_last_turn_throughput(d2, host_url="http://h", model="qwen3:latest", tokens_per_second=41.0,
                                     prefill_seconds=1.2, offloaded=False)
        got2 = get_last_turn_throughput(d2, host_url="http://h", model="qwen3")
        ctx.check(f"recorded under :latest, found by the bare name, got {got2}",
                  got2 is not None and got2["tokens_per_second"] == 41.0)
    finally:
        _clear_state_dir_env()


@test
def test_store_upsert_overwrites_not_duplicates(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import load_fit_store, lookup_learned_cap, record_calibration
    d = _fresh_state_dir("ol-fit-store-upsert-")
    try:
        record_calibration(d, host_url="http://h", model="m", digest="sha256:a", max_full_gpu_ctx=8192,
                            ollama_version="0.5.0")
        record_calibration(d, host_url="http://h", model="m", digest="sha256:b", max_full_gpu_ctx=16384,
                            ollama_version="0.6.0")
        entries = load_fit_store(d)["entries"]
        ctx.check(f"exactly one entry for (host, model), got {len(entries)}", len(entries) == 1)
        ctx.check(f"the LATEST measurement wins, got {lookup_learned_cap(d, host_url='http://h', model='m')}",
                  lookup_learned_cap(d, host_url="http://h", model="m") == 16384)
    finally:
        _clear_state_dir_env()


@test
def test_has_calibration_entry_treats_a_stale_digest_or_version_as_absent(ctx: Ctx):
    """Review fix pass (finding 10): commit 9af8dac promised "re-measured
    ... when the model digest or Ollama version changes" -- the GATE
    itself (`has_calibration_entry`) never checked either one before this
    fix, so a re-pulled model or an upgraded server kept a stale entry
    looking "already calibrated" forever. Passing `digest`/`ollama_
    version` now makes a mismatch read as "no entry at all"; omitting
    them (every pre-fix caller) keeps the old "some entry exists, period"
    answer."""
    from halo_harness.providers.ollama_calibrate import has_calibration_entry, record_calibration
    d = _fresh_state_dir("ol-fit-store-gate-staleness-")
    try:
        record_calibration(d, host_url="http://h", model="m", digest="sha256:old", max_full_gpu_ctx=16384,
                            ollama_version="0.5.0")
        ctx.check("no digest/version given -> the old 'any entry' answer",
                  has_calibration_entry(d, host_url="http://h", model="m") is True)
        ctx.check("matching digest+version -> still calibrated",
                  has_calibration_entry(d, host_url="http://h", model="m", digest="sha256:old",
                                         ollama_version="0.5.0") is True)
        ctx.check("a re-pulled model (new digest) -> treated as absent, re-triggers calibration",
                  has_calibration_entry(d, host_url="http://h", model="m", digest="sha256:new",
                                         ollama_version="0.5.0") is False)
        ctx.check("an upgraded server (new version) -> treated as absent too",
                  has_calibration_entry(d, host_url="http://h", model="m", digest="sha256:old",
                                         ollama_version="0.6.0") is False)
    finally:
        _clear_state_dir_env()


@test
def test_store_missing_file_degrades_to_empty(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import has_calibration_entry, load_fit_store
    d = _fresh_state_dir("ol-fit-store-missing-")
    try:
        ctx.check("no file yet -> empty shape, never raises", load_fit_store(d)["entries"] == [])
        ctx.check("no entry -> False", has_calibration_entry(d, host_url="http://h", model="m") is False)
    finally:
        _clear_state_dir_env()


@test
def test_auto_calibrate_enabled_default_true_and_opt_out(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import auto_calibrate_enabled
    from halo_harness.theme import set_config_value
    d = _fresh_state_dir("ol-fit-autocal-config-")
    try:
        ctx.check("default True (nothing configured)", auto_calibrate_enabled() is True)
        set_config_value("ollama.auto_calibrate", False)
        ctx.check("explicit false opts out", auto_calibrate_enabled() is False)
        set_config_value("ollama.auto_calibrate", True)
        ctx.check("explicit true", auto_calibrate_enabled() is True)
    finally:
        _clear_state_dir_env()


_GB = 1024 ** 3


class _StepScenario:
    """A `/api/chat` scenario (keyed by model name in `mock.scenarios`)
    that, on each call, sets `mock.ps_response` to the NEXT scripted
    `/api/ps` entry BEFORE answering with a trivial one-line reply --
    simulates "loading at this candidate num_ctx produced this /api/ps
    snapshot" for `run_calibration`'s own stepping loop, entirely through
    `MockUpstream`'s public surface (never touching its private
    internals). `ps_steps[i]` is an entry dict (loaded) or `None` (the
    load failed / model not found); the LAST step repeats once exhausted."""

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


# ---- run_calibration's stepping loop (mock_ollama, never a real model) --

@test
def test_run_calibration_fits_on_the_first_try(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import run_calibration
    mock = MockUpstream().start()
    model = "qwen3-coder:30b"
    try:
        mock.scenarios[model] = _StepScenario(mock, [{"model": model, "size": 20 * _GB, "size_vram": 20 * _GB}])
        host = OllamaHost(name="mock", url=mock.base_url)
        result = run_calibration(host, model, start_ctx=16384)
        ctx.check(f"fits, got {result.outcome!r}", result.outcome == "fits")
        ctx.check(f"max_full_gpu_ctx == the starting candidate, got {result.max_full_gpu_ctx}",
                  result.max_full_gpu_ctx == 16384)
        ctx.check(f"exactly one step, got {result.steps}", result.steps == 1)
    finally:
        mock.stop()


@test
def test_run_calibration_fits_after_two_steps(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import run_calibration
    mock = MockUpstream().start()
    model = "qwen3-coder:30b"
    try:
        mock.scenarios[model] = _StepScenario(mock, [
            {"model": model, "size": 20 * _GB, "size_vram": 12 * _GB},   # partial at 16384
            {"model": model, "size": 20 * _GB, "size_vram": 20 * _GB},  # fully resident at 8192
        ])
        host = OllamaHost(name="mock", url=mock.base_url)
        result = run_calibration(host, model, start_ctx=16384)
        ctx.check(f"fits, got {result.outcome!r}", result.outcome == "fits")
        ctx.check(f"max_full_gpu_ctx halved once, got {result.max_full_gpu_ctx}", result.max_full_gpu_ctx == 8192)
        ctx.check(f"exactly two steps, got {result.steps}", result.steps == 2)
    finally:
        mock.stop()


@test
def test_run_calibration_never_fits_stops_at_floor(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import MIN_CALIBRATE_CTX, run_calibration
    mock = MockUpstream().start()
    model = "qwen3-coder:30b"
    try:
        # Every step reports partial offload -- 16384 -> 8192 -> 4096, then
        # stops (4096 is MIN_CALIBRATE_CTX; 2048 is never tried).
        mock.scenarios[model] = _StepScenario(mock, [{"model": model, "size": 40 * _GB, "size_vram": 2 * _GB}])
        host = OllamaHost(name="mock", url=mock.base_url)
        result = run_calibration(host, model, start_ctx=16384)
        ctx.check(f"does not fit, got {result.outcome!r}", result.outcome == "does_not_fit")
        ctx.check("max_full_gpu_ctx is None (no size fits)", result.max_full_gpu_ctx is None)
        ctx.check(f"stepped 16384 -> 8192 -> {MIN_CALIBRATE_CTX} == 3 steps, got {result.steps}", result.steps == 3)
    finally:
        mock.stop()


@test
def test_run_calibration_missing_entry_is_unknown_and_retried_at_the_same_size(ctx: Ctx):
    """Halo 3.2.3.0 R1: a step whose /api/ps entry is missing (`None` in
    `ps_steps`) is `unknown`, never "not resident": the SAME candidate is
    loaded once more with the budget doubled, and the model showing up
    there is the measurement (8192, not a halved 4096)."""
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import run_calibration
    mock = MockUpstream().start()
    model = "qwen3-coder:30b"
    try:
        mock.scenarios[model] = _StepScenario(mock, [None, {"model": model, "size": 1 * _GB, "size_vram": 1 * _GB}])
        host = OllamaHost(name="mock", url=mock.base_url)
        result = run_calibration(host, model, start_ctx=8192)
        ctx.check(f"fits on the second step once the model actually shows up, got {result.outcome!r}",
                  result.outcome == "fits")
        ctx.check(f"measured at the same candidate, got {result.max_full_gpu_ctx}", result.max_full_gpu_ctx == 8192)
        ctx.check(f"two loads (the retry), got {result.steps}", result.steps == 2)
    finally:
        mock.stop()


@test
def test_run_calibration_start_ctx_floored_to_power_of_two(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import run_calibration
    mock = MockUpstream().start()
    model = "qwen3-coder:30b"
    try:
        mock.scenarios[model] = _StepScenario(mock, [{"model": model, "size": 1 * _GB, "size_vram": 1 * _GB}])
        host = OllamaHost(name="mock", url=mock.base_url)
        result = run_calibration(host, model, start_ctx=20000)  # not a power of two
        ctx.check(f"floored to 16384 before the first load, got {result.max_full_gpu_ctx}",
                  result.max_full_gpu_ctx == 16384)
    finally:
        mock.stop()


@test
def test_run_calibration_unreachable_host_reports_unreachable_not_does_not_fit(ctx: Ctx):
    """Review fix pass (finding 8): a host that NEVER answers a single
    `/api/ps` probe across every step tried (connection refused -- same
    "nothing listens on this port" fixture tests/test_ollama_cli.py's own
    unreachable-host test uses) must report "unreachable", not "does_not_
    fit" -- the latter would be recorded PERMANENTLY even though nothing
    was ever actually measured."""
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import run_calibration
    host = OllamaHost(name="dead", url="http://127.0.0.1:1")  # nothing listens on port 1
    result = run_calibration(host, "some-model", start_ctx=8192, timeout=2.0)
    ctx.check(f"reports unreachable, not does_not_fit, got {result.outcome!r}", result.outcome == "unreachable")
    ctx.check("max_full_gpu_ctx is None (nothing was ever measured)", result.max_full_gpu_ctx is None)
    ctx.check("last_size is None too (no reading ever came back)", result.last_size is None)


# ---- run_auto_calibration (the end-to-end orchestration) ------------------

@test
def test_run_auto_calibration_records_and_returns_a_fits_notice(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import lookup_learned_cap, run_auto_calibration
    d = _fresh_state_dir("ol-autocal-fits-")
    mock = MockUpstream().start()
    model = "qwen3:30b"  # already in mock_ollama's own DEFAULT_TAGS/DEFAULT_SHOW
    try:
        mock.scenarios[model] = _StepScenario(mock, [{"model": model, "size": 1 * _GB, "size_vram": 1 * _GB}])
        host = OllamaHost(name="mock", url=mock.base_url)
        notice = run_auto_calibration(host, model, state_dir=d)
        ctx.check(f"a plain notice string, got {notice!r}", isinstance(notice, str) and len(notice) > 0)
        ctx.check(f"notice names the model, got {notice!r}", model in notice)
        got_cap = lookup_learned_cap(d, host_url=host.url, model=model)
        ctx.check(f"recorded to the store, got {got_cap}", isinstance(got_cap, int) and got_cap > 0)
    finally:
        mock.stop()
        _clear_state_dir_env()


@test
def test_run_auto_calibration_unknown_model_returns_none(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import run_auto_calibration
    d = _fresh_state_dir("ol-autocal-unknown-")
    mock = MockUpstream().start()
    try:
        host = OllamaHost(name="mock", url=mock.base_url)
        notice = run_auto_calibration(host, "not-in-the-catalog:1b", state_dir=d)
        ctx.check("None (never raises) for a model not in this host's catalog", notice is None)
    finally:
        mock.stop()
        _clear_state_dir_env()


@test
def test_run_auto_calibration_never_records_an_unreachable_outcome(ctx: Ctx):
    """Review fix pass (finding 8): when `run_calibration` reports
    "unreachable", `run_auto_calibration` must NOT call `record_
    calibration` at all -- `has_calibration_entry` staying False means a
    LATER attempt (a fresh `halo` run, or once the host wakes up) still
    gets to measure for real, instead of being permanently settled by a
    transient "couldn't reach it this time". `run_calibration` itself is
    monkeypatched to the fixed outcome -- engineering a real dual-
    reachability repro (catalog reachable, `/api/chat`+`/api/ps` not) is
    `test_run_calibration_unreachable_host_...`'s own job, not this
    one's; this test is about run_auto_calibration's OWN branch."""
    import halo_harness.providers.ollama_calibrate as calib_mod
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import CalibrationResult, has_calibration_entry, \
        run_auto_calibration
    d = _fresh_state_dir("ol-autocal-unreachable-")
    mock = MockUpstream().start()
    model = "qwen3:30b"  # already in mock_ollama's own DEFAULT_TAGS/DEFAULT_SHOW
    real_run_calibration = calib_mod.run_calibration
    calib_mod.run_calibration = lambda *a, **kw: CalibrationResult(
        outcome="unreachable", max_full_gpu_ctx=None, steps=3, last_size=None, last_size_vram=None)
    try:
        host = OllamaHost(name="mock", url=mock.base_url)
        notice = run_auto_calibration(host, model, state_dir=d)
        ctx.check(f"still returns a plain notice string, got {notice!r}", isinstance(notice, str) and notice)
        ctx.check("the notice does not claim the model does not fit", "does not fit" not in notice)
        ctx.check(f"NOTHING was recorded, got has_calibration_entry={has_calibration_entry(d, host_url=host.url, model=model)}",
                  has_calibration_entry(d, host_url=host.url, model=model) is False)
    finally:
        calib_mod.run_calibration = real_run_calibration
        mock.stop()
        _clear_state_dir_env()


# ---- last-turn throughput persistence --------------------------------

@test
def test_last_turn_throughput_round_trip(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import get_last_turn_throughput, record_last_turn_throughput
    d = _fresh_state_dir("ol-throughput-")
    try:
        record_last_turn_throughput(d, host_url="http://h", model="m", tokens_per_second=41.0,
                                     prefill_seconds=1.2, offloaded=False, output_tokens=120)
        got = get_last_turn_throughput(d, host_url="http://h", model="m")
        ctx.check(f"tokens_per_second round-trips, got {got}", got["tokens_per_second"] == 41.0)
        ctx.check(f"prefill_seconds round-trips, got {got}", got["prefill_seconds"] == 1.2)
        ctx.check(f"offloaded round-trips, got {got}", got["offloaded"] is False)
    finally:
        _clear_state_dir_env()


@test
def test_last_turn_throughput_unknown_pair_is_none(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import get_last_turn_throughput
    d = _fresh_state_dir("ol-throughput-missing-")
    try:
        ctx.check("never recorded -> None", get_last_turn_throughput(d, host_url="http://h", model="m") is None)
    finally:
        _clear_state_dir_env()


# ---- Session._maybe_auto_calibrate_ollama's own gating logic -------------

def _minimal_session(state_dir, mock):
    """The SAME minimal-Session construction tests/test_providers_ollama_
    session.py::test_ol_compaction_summary_uses_native_body already uses,
    just enough to call a Session method directly without a real turn.
    UNLIKE that test (which deliberately uses a state_dir separate from
    its own BRIDGE_TEST_HOME, since it never touches calibration), `self.
    state_dir` is passed in explicitly here and MUST equal whatever this
    test itself calls `record_calibration(...)`/`has_calibration_entry(
    ...)` against -- `_maybe_auto_calibrate_ollama` reads/writes through
    `self.state_dir`, matching the real CLI's own `state_dir = bridge_
    home()` (headless.py) exactly, including for a sub-agent Session
    (`agent/subagent.py`'s `_build_child_session` passes `parent.state_
    dir` straight through, never a different one)."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    cwd = Path(tempfile.mkdtemp(prefix="ol-autocal-cwd-"))
    session_ctx = SessionContext(cwd=cwd, model_label="ol:plain-text")
    return Session(
        cwd=cwd, model_ref=parse_model_ref("ol:plain-text"),
        model_profile=ModelProfile(context_tokens=10_000, max_output_tokens=1_000),
        creds=ProviderCreds(base_url=mock.base_url, api_key=""),
        state_dir=Path(state_dir), model_label="ol:plain-text",
        session_context=session_ctx, max_turns=10,
        permission_engine=PermissionEngine(mode="auto", cwd=cwd),
    )


def _build_turn_body(session, mock, model: str) -> dict:
    """One Ollama body built the way a turn builds it (`_build_ollama_body_for_ref`), the host on the mock."""
    import halo_harness.agent.loop as loop_mod
    from halo_harness.model import parse_model_ref
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.routing import Route
    real = loop_mod.resolve_ollama_host
    loop_mod.resolve_ollama_host = lambda name, env: OllamaHost(name="mock", url=mock.base_url)
    try:
        ref = parse_model_ref(f"ol:{model}")
        session.model_ref = ref
        route = Route(provider="ollama", upstream_model=model, dialect="ollama")
        return session._build_ollama_body_for_ref(
            ref=ref, route=route, profile=resolve_profile(route), system_text="sys",
            messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}], tools=[], tool_choice=None,
            effort=None, requested_max_tokens=256)
    finally:
        loop_mod.resolve_ollama_host = real


@test
def test_a_call_never_measures_the_model_whatever_the_flag_config_or_store_say(ctx: Ctx):
    """3.6.0.0 R8 (was four tests of the first-use auto-calibration's gates: the test flag, `ollama.auto_calibrate:
    false`, a fresh entry, a stale digest): no call measures a model any more. With the test flag OFF, the opt-out
    unset, no entry, and then a STALE-digest entry, building a turn's body sends no `/api/chat` at all -- the ladder
    of loads is `halo local measure` / Studio's Measure, when a person asks (tests/test_local_ollama_verbs.py pins
    its once-per-digest rule). The session has no measurement of its own left to call."""
    from halo_harness.agent.loop import Session
    from halo_harness.providers.ollama_calibrate import record_calibration
    d = _fresh_state_dir("ol-nomeasure-session-")
    mock = MockUpstream().start()
    old_flag = os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
    try:
        ctx.check("the session has no first-use measurement any more",
                  not hasattr(Session, "_maybe_auto_calibrate_ollama"))
        session = _minimal_session(d, mock)
        body = _build_turn_body(session, mock, "qwen3:30b")
        chats = [r for r in mock.requests if r["method"] == "POST" and r["path"].rstrip("/") == "/api/chat"]
        ctx.check(f"a body was built, and no load was sent to measure first, got {len(chats)}",
                  (body.get("options") or {}).get("num_ctx") and not chats)
        record_calibration(d, host_url=mock.base_url, model="qwen3:30b", digest="sha256:some-older-pull",
                           max_full_gpu_ctx=16384, ollama_version="0.1.0-mock")
        _build_turn_body(_minimal_session(d, mock), mock, "qwen3:30b")
        chats = [r for r in mock.requests if r["method"] == "POST" and r["path"].rstrip("/") == "/api/chat"]
        ctx.check(f"a stale digest is no reason to measure from a call either, got {len(chats)}", not chats)
    finally:
        if old_flag is not None:
            os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = old_flag
        mock.stop()
        _clear_state_dir_env()


# ---- Halo 3.2.3.0 R1: a measurement or unknown (mock load delays) --------

@test
def test_load_budget_s_scales_with_size_and_host(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import load_budget_s
    ctx.check(f"local 17 GB -> 20 + 68 = 88 s, got {load_budget_s(17, False)}", load_budget_s(17, False) == 88.0)
    ctx.check(f"remote 17 GB -> 40 + 102 = 142 s, got {load_budget_s(17, True)}", load_budget_s(17, True) == 142.0)
    ctx.check("unknown size -> 60 s", load_budget_s(None, True) == 60.0 and load_budget_s(None, False) == 60.0)
    ctx.check("a zero or bogus size -> 60 s", load_budget_s(0, False) == 60.0 and load_budget_s("x", True) == 60.0)


@test
def test_run_calibration_slow_load_is_unknown_then_inconclusive(ctx: Ctx):
    """A 2.5 s load against a 1 s budget: unknown, one retry with 2 s
    (still unknown), then `inconclusive` -- never a small `fits`."""
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import outcome_line, run_calibration
    mock = MockUpstream().start()
    model = "slow-model:17b"
    try:
        mock.load_delay_s[model] = 2.5
        host = OllamaHost(name="pc", url=mock.base_url)
        result = run_calibration(host, model, start_ctx=8192, budget_s=1.0, step_up=True)
        ctx.check(f"inconclusive, got {result.outcome!r}", result.outcome == "inconclusive")
        ctx.check("no cap", result.max_full_gpu_ctx is None)
        ctx.check(f"two loads: the step and its retry, got {result.steps}", result.steps == 2)
        ctx.check(f"the unknown candidate is named, got {result.unknown_ctx}", result.unknown_ctx == 8192)
        ctx.check(f"the budget is kept, got {result.budget_s}", result.budget_s == 1.0)
        chats = [r for r in mock.requests if r["path"].rstrip("/") == "/api/chat"]
        ctx.check(f"both loads at the same num_ctx, got {[c['body']['options']['num_ctx'] for c in chats]}",
                  [c["body"]["options"]["num_ctx"] for c in chats] == [8192, 8192])
        line = outcome_line(model, host.name, result, window=40960, source="trained")
        ctx.check(f"the line says inconclusive and the window, got {line!r}",
                  line.startswith(f"{model} on pc: inconclusive") and "the window stays at 40k (trained)" in line)
    finally:
        mock.stop()


@test
def test_run_auto_calibration_slow_load_records_nothing(ctx: Ctx):
    from halo_harness.providers import ollama_hw
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import (
        calibration_state, has_calibration_entry, lookup_learned_cap, run_auto_calibration,
    )
    d = _fresh_state_dir("ol-autocal-slow-")
    mock = MockUpstream().start()
    model = "qwen3:30b"
    try:
        ollama_hw.reset_local_gpu_cache()
        mock.load_delay_s[model] = 2.5
        host = OllamaHost(name="pc", url=mock.base_url)
        notice = run_auto_calibration(host, model, state_dir=d, timeout=1.0)
        ctx.check(f"one inconclusive line, got {notice!r}", isinstance(notice, str) and "inconclusive" in notice)
        ctx.check("no calibration entry", has_calibration_entry(d, host_url=host.url, model=model) is False)
        ctx.check("no learned cap", lookup_learned_cap(d, host_url=host.url, model=model) is None)
        ctx.check("halo ollama will say inconclusive",
                  calibration_state(d, host_url=host.url, model=model) == "inconclusive")
    finally:
        mock.stop()
        _clear_state_dir_env()


@test
def test_run_calibration_completed_load_lists_its_context_and_fits(ctx: Ctx):
    """A load that completes within the budget lists the candidate's own
    context_length: `fits`; stepping up stops at the first partial load
    and the midpoint is tried once; the line names both sizes."""
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import outcome_line, run_calibration
    mock = MockUpstream().start()
    model = "qwen3:30b"
    try:
        mock.load_delay_s[model] = 0.2
        mock.load_vram[model] = lambda n: (4 * _GB, 4 * _GB) if n <= 8192 else (5 * _GB, 4 * _GB)
        host = OllamaHost(name="pc", url=mock.base_url)
        result = run_calibration(host, model, start_ctx=8192, budget_s=5.0, step_up=True, trained_context=40960)
        ctx.check(f"fits at 8192, got {result.outcome} {result.max_full_gpu_ctx}",
                  result.outcome == "fits" and result.max_full_gpu_ctx == 8192)
        ctx.check(f"16384 then the midpoint 12288 measured offloaded, got {result.failed_ctx}",
                  result.failed_ctx == 12288)
        nums = [r["body"]["options"]["num_ctx"] for r in mock.requests if r["path"].rstrip("/") == "/api/chat"]
        ctx.check(f"loads 8192, 16384, 12288, got {nums}", nums == [8192, 16384, 12288])
        line = outcome_line(model, host.name, result)
        ctx.check(f"the one-line outcome, got {line!r}", line.startswith(f"{model} on pc: 8k fits, 12k does not ("))
    finally:
        mock.stop()


@test
def test_run_calibration_never_credits_a_late_larger_load(ctx: Ctx):
    """/api/ps lists the model at 65536 while the candidate was 32768 (a
    larger load landing late): unknown at 32768, retried, inconclusive."""
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import run_calibration
    mock = MockUpstream().start()
    model = "qwen3-coder:30b"
    try:
        mock.scenarios[model] = _StepScenario(mock, [{"model": model, "size": 20 * _GB, "size_vram": 20 * _GB,
                                                      "context_length": 65536}])
        host = OllamaHost(name="pc", url=mock.base_url)
        result = run_calibration(host, model, start_ctx=32768, budget_s=5.0)
        ctx.check(f"inconclusive, never fits at 32768, got {result.outcome} {result.max_full_gpu_ctx}",
                  result.outcome == "inconclusive" and result.max_full_gpu_ctx is None)
        ctx.check(f"two loads, got {result.steps}", result.steps == 2)
    finally:
        mock.stop()


def _no_gpu(ollama_hw):
    real = ollama_hw.get_local_gpu_memories
    ollama_hw.get_local_gpu_memories = lambda **kw: []
    return real


@test
def test_a_measurement_counts_the_cold_load_as_a_load_and_keeps_what_it_learned(ctx: Ctx):
    """3.6.0.0 R8 (was: the first-use measurement keeps running past a turn's wait and records later -- no turn
    waits on a measurement any more). The asked-for measurement (`run_auto_calibration`, no `timeout`): every load
    of this server is slower than a step's budget; the first step is the cold load and gets a load's own allowance
    (one load, no timeout and retry), and a later step that stays unknown ends the run with the safe window it
    measured RECORDED -- never `inconclusive` with nothing kept (the evidence's "measured all over again")."""
    from halo_harness.providers import ollama_calibrate as C
    from halo_harness.providers import ollama_hw
    from halo_harness.providers.ollama import OllamaHost, reset_catalog_cache
    d = _fresh_state_dir("ol-measure-slow-")
    mock = MockUpstream().start()
    model = "qwen3:30b"
    real = _no_gpu(ollama_hw)
    real_budget = C.load_budget_s
    C.load_budget_s = lambda size_gb, remote: 0.4
    try:
        reset_catalog_cache()
        mock.load_delay_s[model] = 1.0
        host = OllamaHost(name="pc", url=mock.base_url, max_ctx=65536)
        line = C.run_auto_calibration(host, model, state_dir=d)
        nums = [r["body"]["options"]["num_ctx"] for r in mock.requests if r["path"].rstrip("/") == "/api/chat"]
        ctx.check(f"the cold first load is one load at the start window, got {nums}", nums and nums.count(nums[0]) == 1)
        ctx.check(f"never above the host's max_ctx, got {nums}", max(nums) <= 65536)
        got = C.lookup_learned_cap(d, host_url=host.url, model=model)
        ctx.check(f"the safe window it measured is recorded, got {got} {line!r}",
                  got == 32768 and isinstance(line, str) and line.startswith(f"{model} on pc: 32k fits"))
    finally:
        C.load_budget_s = real_budget
        ollama_hw.get_local_gpu_memories = real
        mock.stop()
        _clear_state_dir_env()


@test
def test_a_recorded_cap_under_the_prompt_floor_is_raised_over_and_kept(ctx: Ctx):
    """3.6.0.0 R8 (was: discarded once so the model is measured again -- no call measures any more): a request
    above a recorded cap gets the window it needs (the prompt floor raises over the cap) and the cap stays."""
    from types import SimpleNamespace
    from halo_harness.agent.ollama_window import prepare_window
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import lookup_learned_cap, record_calibration
    d = _fresh_state_dir("ol-floor-kept-")
    mock = MockUpstream().start()
    try:
        session = _minimal_session(d, mock)
        host = OllamaHost(name="pc", url=mock.base_url)
        record_calibration(d, host_url=host.url, model="qwen3:30b", digest=None, max_full_gpu_ctx=4096,
                           ollama_version=None)
        decision = SimpleNamespace(learned_cap=4096, num_ctx=4096, source="learned cap", trained_context=40960,
                                   fit_estimate=None, host_max_ctx=None)
        ref = SimpleNamespace(model="qwen3:30b")
        kwargs = dict(host=host, ref=ref, decision=decision, base_num_ctx=4096, base_source="learned cap",
                      system_text="x" * 35000, messages=[], tools=[], auto_calibrate=True)
        estimate, _factor = prepare_window(session, **kwargs)
        ctx.check(f"the request is above the cap, got {estimate}", estimate > 4096)
        sent = session._ollama_window_state["sent"][(host.url, "qwen3:30b")]
        ctx.check(f"the window holds the request (the floor raised over the cap), got {sent}",
                  sent["num_ctx"] >= estimate and sent["source"] == "prompt floor")
        ctx.check("the cap is kept", lookup_learned_cap(d, host_url=host.url, model="qwen3:30b") == 4096)
        ctx.check("nothing was sent to the server", not [r for r in mock.requests if r["method"] == "POST"])
    finally:
        mock.stop()
        _clear_state_dir_env()


# ---- Halo 3.2.3.0 R1: all layers on the GPU + the headroom rule -----------

def _measured_23gb_card(n: int):
    """The owner's measurement, as placeholders: a 17 GB model on a 23 GB
    card -- 65,536 used 20.7 GB (safe), 98,304 used 22.1 GB (tight),
    131,072 spilled to the CPU."""
    gb = 1024 ** 3
    if n <= 65536:
        return int(20.7 * gb), int(20.7 * gb)
    if n <= 98304:
        return int(22.1 * gb), int(22.1 * gb)
    return int(26 * gb), int(22.5 * gb)


@test
def test_headroom_rule_records_the_safe_window_and_names_the_tight_one(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import outcome_line, run_calibration
    mock = MockUpstream().start()
    model = "qwen3:30b"
    try:
        mock.load_delay_s[model] = 0.05
        mock.load_vram[model] = _measured_23gb_card
        host = OllamaHost(name="pc", url=mock.base_url)
        result = run_calibration(host, model, start_ctx=65536, step_up=True, trained_context=131072, budget_s=5.0,
                                 gpu_total=23 * _GB, num_gpu=65)
        ctx.check(f"65536 recorded (the largest SAFE window), got {result.outcome} {result.max_full_gpu_ctx}",
                  result.outcome == "fits" and result.max_full_gpu_ctx == 65536)
        ctx.check(f"98304 tight, got {result.tight_ctx}", result.tight_ctx == 98304)
        ctx.check(f"131072 does not fit, got {result.failed_ctx}", result.failed_ctx == 131072)
        line = outcome_line(model, host.name, result)
        ctx.check(f"the line names both, got {line!r}",
                  line.startswith(f"{model} on pc: 65k safe, 98k tight (22.1 of 23 GB), 131k does not fit ("))
        chats = [r for r in mock.requests if r["path"].rstrip("/") == "/api/chat"]
        ctx.check(f"every load asks for all layers on the GPU, got {[c['body']['options'] for c in chats]}",
                  chats and all(c["body"]["options"].get("num_gpu") == 65 for c in chats))
        ctx.check(f"loads 65536, 131072, 98304, got {[c['body']['options']['num_ctx'] for c in chats]}",
                  [c["body"]["options"]["num_ctx"] for c in chats] == [65536, 131072, 98304])
    finally:
        mock.stop()


@test
def test_headroom_kind(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import headroom_kind
    gb = 1024 ** 3
    ctx.check("20.7 of 23 GB is safe (2.3 GB >= 8 %)", headroom_kind(int(20.7 * gb), 23 * gb) == "safe")
    ctx.check("22.1 of 23 GB is tight", headroom_kind(int(22.1 * gb), 23 * gb) == "tight")
    ctx.check("1.5 GB floor on a small card: 6.7 of 8 GB is tight", headroom_kind(int(6.7 * gb), 8 * gb) == "tight")
    ctx.check("unknown total -> safe", headroom_kind(int(22.1 * gb), None) == "safe")


@test
def test_halo_ollama_panel_shows_window_source_state_floor_speed_and_tight(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_calibrate import (
        record_calibration, record_last_turn_throughput, record_prompt_speed,
    )
    from halo_harness.providers.ollama_panel import analyze_host, format_host_analysis
    d = _fresh_state_dir("ol-panel-r1-")
    mock = MockUpstream().start()
    try:
        host = OllamaHost(name="pc", url=mock.base_url)
        record_calibration(d, host_url=host.url, model="qwen3:30b", digest="sha256:deadbeef1",
                           max_full_gpu_ctx=8192, ollama_version="0.1.0-mock", tight_ctx=16384,
                           tight_vram=int(22.1 * _GB), gpu_total=23 * _GB)
        record_prompt_speed(d, host_url=host.url, model="qwen3:30b", tok_s=2500.0)
        record_last_turn_throughput(d, host_url=host.url, model="qwen3:30b", tokens_per_second=40.0,
                                    prefill_seconds=4.4, offloaded=False, prompt_floor=11000)
        text = format_host_analysis(analyze_host(host, hw_runner=lambda argv, timeout: None, state_dir=d))
        row = next(line for line in text.splitlines() if line.strip().startswith("qwen3:30b:"))
        ctx.check(f"window raised by the floor, source word, calibrated, the floor, the speed; got {row!r}",
                  "window 16384 [prompt floor]" in row and "calibrated" in row
                  and "prompt floor 11k (last session)" in row and "reads ~2,500 tok/s" in row)
        ctx.check(f"the tight window is shown, got {text!r}", "16384 tight (22.1 of 23 GB)" in text)
        other = next(line for line in text.splitlines() if line.strip().startswith("gpt-oss:20b:"))
        ctx.check(f"an unmeasured model reads estimated, got {other!r}",
                  "estimated" in other and "prompt floor unknown" in other)
    finally:
        mock.stop()
        _clear_state_dir_env()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
