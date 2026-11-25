"""tests.test_ollama_estimate_fit_5b -- Halo 2.0.3 round 5b: the three
new inputs wired INTO `providers.ollama_hw.estimate_fit_for_host` itself
(not just the pure functions they call) -- `ollama.hosts[].kv_cache_type`,
multi-GPU (several cards probed locally), and `ollama.hosts[].ssh` for a
remote host. Against `tests/helpers/mock_ollama.MockUpstream` with
injected `runner`s only -- never a real OS tool, never a real ssh binary.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_ollama import MockUpstream

test, TESTS = new_registry()

_QWEN_MODEL_INFO = {"qwen3.block_count": 32, "qwen3.attention.head_count_kv": 8,
                    "qwen3.attention.head_count": 32, "qwen3.embedding_length": 4096}  # 131072 B/tok at f16


def _catalog_for(model: str, *, size: int) -> dict:
    return {"models": [{"model": model, "name": model, "size": size, "model_info": _QWEN_MODEL_INFO}]}


def _reset():
    from halo_harness.providers import ollama_hw
    ollama_hw.reset_local_gpu_cache()
    ollama_hw.reset_ssh_gpu_cache()


# ---- kv_cache_type hint -----------------------------------------------

@test
def test_estimate_fit_for_host_uses_kv_cache_type_hint(ctx: Ctx):
    """A q4_0 host fits a MUCH larger context than an f16 host with the
    EXACT same free memory/weight size -- the hint must actually change
    the bytes-per-token constant `estimate_fit_for_host` uses, not just
    exist on the dataclass."""
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_hw import estimate_fit_for_host
    mock = MockUpstream(ps_response={"models": []}).start()
    _reset()
    try:
        catalog = _catalog_for("qwen3:30b", size=1 * 1024**3)

        def runner(argv, timeout):
            return "20480, 0, 20480, X\n"  # 20 GiB free, one card
        host_f16 = OllamaHost(name="mock", url=mock.base_url)
        host_q4 = OllamaHost(name="mock", url=mock.base_url, kv_cache_type="q4_0")
        fit_f16 = estimate_fit_for_host(host_f16, "qwen3:30b", catalog, runner=runner)
        _reset()
        fit_q4 = estimate_fit_for_host(host_q4, "qwen3:30b", catalog, runner=runner)
        ctx.check(f"q4_0 fits a bigger context than f16 with identical memory, got f16={fit_f16} q4_0={fit_q4}",
                  isinstance(fit_f16, int) and isinstance(fit_q4, int) and fit_q4 > fit_f16)
    finally:
        mock.stop()
        _reset()


# ---- multi-GPU wiring --------------------------------------------------

@test
def test_estimate_fit_for_host_multi_gpu_sums_not_minimum(ctx: Ctx):
    """Two cards probed locally -- the SAME "never the minimum" property
    `test_ollama_fit_5b.py` already pins for the pure formula, now
    through the real `estimate_fit_for_host` entry point a request
    actually uses."""
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_hw import estimate_fit_for_host
    from halo_harness.providers.ollama_fit import WEIGHTS_DO_NOT_FIT
    mock = MockUpstream(ps_response={"models": []}).start()
    _reset()
    try:
        # 3.3.4.0 R3: 14 GiB, not 15 -- the fit now also keeps Ollama's
        # 457 MiB minimum free per card and counts the compute buffer.
        weight_bytes = 14 * 1024**3
        catalog = _catalog_for("qwen3:30b", size=weight_bytes)

        def runner(argv, timeout):
            return "20480, 0, 20480, Card A\n1, 0, 1, Card B\n"  # 20 GiB + ~1 MiB
        host = OllamaHost(name="mock", url=mock.base_url)
        got = estimate_fit_for_host(host, "qwen3:30b", catalog, runner=runner)
        ctx.check(f"sums both cards -> a real fit, not WEIGHTS_DO_NOT_FIT, got {got!r}", got is not None
                  and got is not WEIGHTS_DO_NOT_FIT)
    finally:
        mock.stop()
        _reset()


@test
def test_estimate_fit_for_host_multi_gpu_reclaimable_counts_once(ctx: Ctx):
    """Another loaded model's reclaimable `size_vram` still counts toward
    the TOTAL across every card -- not lost, not double-counted."""
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_hw import estimate_fit_for_host
    from tests.helpers.mock_ollama import partial_offload_ps_entry
    other_vram = 10 * 1024**3
    mock = MockUpstream(ps_response={"models": [
        partial_offload_ps_entry("other-model", size=other_vram, size_vram=other_vram, context_length=8192),
    ]}).start()
    _reset()
    try:
        # 3.3.4.0 R3: 14 GiB, not 15 -- the fit now also keeps Ollama's
        # 457 MiB minimum free per card and counts the compute buffer.
        weight_bytes = 14 * 1024**3
        catalog = _catalog_for("qwen3:30b", size=weight_bytes)

        def runner(argv, timeout):
            return "6144, 0, 6144, Card A\n1, 0, 1, Card B\n"  # only ~6 GiB free alone
        host = OllamaHost(name="mock", url=mock.base_url)
        got = estimate_fit_for_host(host, "qwen3:30b", catalog, runner=runner)
        ctx.check(f"6 GiB + 10 GiB reclaimable >= 14 GiB weight -- fits, got {got!r}",
                  isinstance(got, int) and got > 0)
    finally:
        mock.stop()
        _reset()


# ---- optional ssh GPU read for a remote host --------------------------

@test
def test_estimate_fit_for_host_remote_with_ssh_uses_the_ssh_probe(ctx: Ctx):
    """`host.url` must be a NON-loopback hostname for `is_local_host` to
    take the remote branch at all -- following `test_providers_ollama_hw.
    py::test_estimate_fit_for_host_remote_path_unchanged`'s own pattern,
    `providers.ollama.fetch_ps` is monkeypatched directly (`.example`
    never resolves, so a real request would just time out instead of
    proving anything) rather than spinning a loopback mock server, which
    `is_local_host` would misclassify as local."""
    import halo_harness.providers.ollama as ollama_mod
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_hw import estimate_fit_for_host
    _reset()
    old_fetch_ps = ollama_mod.fetch_ps
    ollama_mod.fetch_ps = lambda h, **kw: {"models": []}  # nothing loaded remotely
    try:
        catalog = _catalog_for("qwen3:30b", size=4 * 1024**3)
        host = OllamaHost(name="remote", url="http://gpu-box.example:11434", ssh="user@gpu-box")

        def runner(argv, timeout):
            return "20480, 0, 20480, Remote GPU\n"
        got = estimate_fit_for_host(host, "qwen3:30b", catalog, runner=runner)
        ctx.check(f"a real fit via the ssh probe, got {got!r}", isinstance(got, int) and got > 0)
    finally:
        ollama_mod.fetch_ps = old_fetch_ps
        _reset()


@test
def test_estimate_fit_for_host_remote_without_ssh_unchanged(ctx: Ctx):
    """No `ssh:` configured -- a remote host with nothing loaded still
    gets `None` (never an OS-level read), unchanged from before round 5b."""
    import halo_harness.providers.ollama as ollama_mod
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_hw import estimate_fit_for_host
    old_fetch_ps = ollama_mod.fetch_ps
    ollama_mod.fetch_ps = lambda h, **kw: {"models": []}
    try:
        catalog = _catalog_for("qwen3:30b", size=4 * 1024**3)
        host = OllamaHost(name="remote", url="http://gpu-box.example:11434")  # no ssh
        got = estimate_fit_for_host(host, "qwen3:30b", catalog,
                                     runner=lambda argv, timeout: "20480, 0, 20480, X\n")
        ctx.check(f"None -- the runner is never even consulted for a plain remote host, got {got!r}", got is None)
    finally:
        ollama_mod.fetch_ps = old_fetch_ps


# ---- 3.6.0.20 E2: an observation of this model bounds a too-low estimate from below ------------------------------

_E2_MODEL, _E2_DIGEST = "example-model:30b", "sha256:e2digest"
_E2_INFO = {"examplemoe.block_count": 48, "examplemoe.attention.head_count_kv": 4,  # an invented 30B shape
            "examplemoe.attention.key_length": 128, "examplemoe.attention.value_length": 128,
            "examplemoe.embedding_length": 2048, "examplemoe.context_length": 131072}


def _e2_decide(free_bytes: int, prepare, *, panel: bool = False) -> tuple:
    """(the decision, the prompt floor's ceiling) for `_E2_MODEL` on a mock host, the card reading injected
    (`free_bytes`), a scratch state dir that `prepare(state_dir, host_url)` fills first. `panel`: the panel's
    (window, source) for that model in place of the ceiling."""
    import os
    import tempfile
    from halo_harness.model import parse_model_ref
    from halo_harness.providers import ollama_hw
    from halo_harness.providers.ollama import reset_catalog_cache, reset_ollama_version_cache
    from halo_harness.providers.ollama_prompt import window_for
    mock = MockUpstream(ps_response={"models": []}).start()
    mock.tags_response = {"models": [{"name": _E2_MODEL, "model": _E2_MODEL, "size": 17_000_000_000,
                                       "digest": _E2_DIGEST, "details": {}}]}
    mock.show_responses = {_E2_MODEL: {"modelfile": "", "parameters": "", "template": "", "details": {},
                                       "capabilities": ["completion", "tools"], "model_info": _E2_INFO}}
    d = tempfile.mkdtemp(prefix="ol-e2-floor-")
    old_dir, old_cards = os.environ.get("BRIDGE_STATE_DIR"), ollama_hw.get_local_gpu_memories
    os.environ["BRIDGE_STATE_DIR"] = d
    card = [ollama_hw.GpuMemory(vendor="nvidia", name="a 24 GB card", total_bytes=24_000_000_000,
                                free_bytes=free_bytes)]
    ollama_hw.get_local_gpu_memories = lambda **_kw: card
    _reset()
    reset_catalog_cache()
    reset_ollama_version_cache()
    try:
        prepare(d, mock.base_url)
        decision = ollama_hw.resolve_context_decision(parse_model_ref(f"ol:{_E2_MODEL}"), {"OLLAMA_HOST": mock.base_url})
        if panel:  # what `halo ollama`, `/ollama` and Studio's Models list print for the same model
            from halo_harness.providers.ollama import OllamaHost
            from halo_harness.providers.ollama_panel import analyze_host
            _reset()
            rows = analyze_host(OllamaHost(name="gpu-box", url=mock.base_url), state_dir=d, force=True).catalog_fits
            row = next(r for r in rows if r.name == _E2_MODEL)
            return decision, (row.what_fits, row.source)
        return decision, window_for(120_000, decision).ceiling
    finally:
        ollama_hw.get_local_gpu_memories = old_cards
        if old_dir is None:
            os.environ.pop("BRIDGE_STATE_DIR", None)
        else:
            os.environ["BRIDGE_STATE_DIR"] = old_dir
        _reset()
        reset_catalog_cache()
        reset_ollama_version_cache()
        mock.stop()


def _measured(tight_vram):
    def prepare(d, url):
        from halo_harness.providers.ollama_calibrate import record_calibration
        record_calibration(d, host_url=url, model=_E2_MODEL, digest=_E2_DIGEST, max_full_gpu_ctx=32768,
                           ollama_version="0.1.0-mock", tight_ctx=65536 if tight_vram else None,
                           tight_vram=tight_vram, gpu_total=24_000_000_000)
    return prepare


@test
def test_a_measured_cap_is_a_floor_of_the_estimate_while_the_card_has_the_room_it_had(ctx: Ctx):
    nothing, _c = _e2_decide(19_500_000_000, lambda d, url: None)
    est = nothing.fit_estimate
    ctx.check(f"the estimate alone is below the measured 32,768 (made too low on purpose), got {est}",
              isinstance(est, int) and est < 32768 and nothing.source == "fit estimate")
    room, ceiling = _e2_decide(19_500_000_000, _measured(19_200_000_000))
    ctx.check(f"the card has the measurement's room: 32,768 'learned cap', got {room.num_ctx} {room.source!r}",
              room.num_ctx == 32768 and room.source == "learned cap")
    ctx.check(f"the prompt floor may raise to it too: ceiling 32,768, got {ceiling}", ceiling == 32768)
    busy, ceiling = _e2_decide(18_500_000_000, _measured(19_200_000_000))
    ctx.check(f"the card is busier than when measured: the estimate wins, got {busy.num_ctx} {busy.source!r}",
              busy.num_ctx < 32768 and busy.source == "fit estimate" and ceiling == busy.num_ctx)
    old, _c = _e2_decide(19_500_000_000, _measured(None))
    ctx.check(f"a measurement with no tight_vram gives no floor, got {old.num_ctx}", old.num_ctx < 32768)


def _today(url) -> dict:
    """The server a load is seen under today: the mock's version and the fit settings the estimate reads for it."""
    from halo_harness.providers import ollama_hw
    from halo_harness.providers.ollama import OllamaHost
    return ollama_hw.load_server(OllamaHost(name="gpu-box", url=url), "0.1.0-mock")


def _seen(size, *, keep_size=True, digest=_E2_DIGEST, server=None, then=None):
    """`server(today) -> dict | None`: the server the load was seen under (today's when not given; None: a record
    written before 3.6.0.21); `then`: a later load `(num_ctx, size)` seen under today's server."""
    def prepare(d, url):
        from halo_harness.agent.ollama_window_truth import _key, _update, record_truth
        today = _today(url)
        record_truth(d, url, _E2_MODEL, num_ctx=65536, size=size, size_vram=size, digest=digest,
                     server=server(today) if server else today)
        if not keep_size:  # a record written before 3.6.0.20
            _update(d, "window_truth", _key(url, _E2_MODEL), lambda old: {k: v for k, v in old.items()
                                                                         if k != "fits_size"})
        if then:
            record_truth(d, url, _E2_MODEL, num_ctx=then[0], size=then[1], size_vram=then[1], digest=digest,
                         server=today)
    return prepare


@test
def test_a_load_seen_wholly_on_the_card_is_a_floor_while_the_card_has_its_size(ctx: Ctx):
    seen, ceiling = _e2_decide(19_500_000_000, _seen(19_200_000_000))
    ctx.check(f"a load seen at 65,536 on the card: 65,536 'seen to fit', got {seen.num_ctx} {seen.source!r}",
              seen.num_ctx == 65536 and seen.source == "seen to fit" and ceiling == 65536)
    busy, _c = _e2_decide(18_500_000_000, _seen(19_200_000_000))
    ctx.check(f"less room than that load took: the estimate wins, got {busy.num_ctx}", busy.num_ctx < 32768)
    old, _c = _e2_decide(19_500_000_000, _seen(19_200_000_000, keep_size=False))
    ctx.check(f"a record without the load's size gives no floor, got {old.num_ctx}", old.num_ctx < 32768)
    other, _c = _e2_decide(19_500_000_000, _seen(19_200_000_000, digest="sha256:another"))
    ctx.check(f"a load of another digest gives no floor, got {other.num_ctx}", other.num_ctx < 32768)


@test
def test_a_load_seen_under_another_server_version_or_other_fit_settings_gives_no_floor(ctx: Ctx):
    """3.6.0.21 R1: a load seen wholly on the card is a floor only under the server version and the fit settings
    (the cache type's bytes per element, the parallel count) it was seen under; a record without them (3.6.0.20)
    gives none, and the next load rewrites it."""
    cases = (("another server version", lambda t: {**t, "version": "0.0.9-older"}),
             ("another cache type", lambda t: {**t, "kv_bytes_per_elem": t["kv_bytes_per_elem"] / 2}),
             ("another parallel count", lambda t: {**t, "parallel": t["parallel"] + 1}),
             ("a record from 3.6.0.20 (no server kept)", lambda t: None))
    for label, server in cases:
        got, ceiling = _e2_decide(19_500_000_000, _seen(19_200_000_000, server=server))
        ctx.check(f"{label}: no floor, got {got.num_ctx} {got.source!r}",
                  got.num_ctx < 32768 and got.source == "fit estimate" and ceiling == got.num_ctx)
    again, _c = _e2_decide(19_500_000_000, _seen(19_200_000_000, server=lambda t: {**t, "version": "0.0.9-older"},
                                                  then=(49152, 18_000_000_000)))
    ctx.check(f"the next load under today's server rewrites it: 49,152 'seen to fit', got {again.num_ctx} "
              f"{again.source!r}", again.num_ctx == 49152 and again.source == "seen to fit")


@test
def test_a_measured_cap_taken_under_other_fit_settings_is_not_used(ctx: Ctx):
    """3.6.0.21 R1: the measured cap is keyed on the fit settings as it is on the version: a measurement taken under
    another cache type or parallel count is not this server's; one that kept none (before 3.6.0.21) still is."""
    def measured(change):
        def prepare(d, url):
            from halo_harness.providers.ollama_calibrate import record_calibration
            today = _today(url)
            settings = {k: v for k, v in today.items() if k != "version"}
            record_calibration(d, host_url=url, model=_E2_MODEL, digest=_E2_DIGEST, max_full_gpu_ctx=32768,
                               ollama_version="0.1.0-mock", tight_ctx=65536, tight_vram=19_200_000_000,
                               gpu_total=24_000_000_000, fit_settings=change(settings))
        return prepare
    same, _c = _e2_decide(19_500_000_000, measured(lambda s: s))
    ctx.check(f"under today's settings: 32,768 'learned cap', got {same.num_ctx} {same.source!r}",
              same.num_ctx == 32768 and same.source == "learned cap")
    for label, change in (("another cache type", lambda s: {**s, "kv_bytes_per_elem": s["kv_bytes_per_elem"] / 2}),
                          ("another parallel count", lambda s: {**s, "parallel": s["parallel"] + 1})):
        other, _c = _e2_decide(19_500_000_000, measured(change))
        ctx.check(f"{label}: neither a cap nor a floor, got {other.num_ctx} {other.source!r} "
                  f"(learned {other.learned_cap})", other.num_ctx < 32768 and other.learned_cap is None)


@test
def test_the_panel_says_the_window_the_session_decides_after_an_observation(ctx: Ctx):
    """3.6.0.20 E2 after the check: `halo ollama`, `/ollama` and Studio's Models list print the window a session
    is sent, the observation's floor included (they ran their own resolve on the raw estimate and said 32,768
    'memory' while the session asked for 65,536)."""
    cases = (("measured", 19_500_000_000, _measured(19_200_000_000)), ("seen", 19_500_000_000, _seen(19_200_000_000)),
             ("busy, measured", 18_500_000_000, _measured(19_200_000_000)),
             ("busy, seen", 18_500_000_000, _seen(19_200_000_000)), ("nothing", 19_500_000_000, lambda d, url: None))
    for label, free, prepare in cases:
        decision, (window, source) = _e2_decide(free, prepare, panel=True)
        ctx.check(f"{label}: the panel says the session's {decision.num_ctx} {decision.source!r}, "
                  f"got {window} {source!r}", window == decision.num_ctx and source == decision.source)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
