"""tests.test_model_enumeration -- Halo 2.0.4 round 4 (deliverable 1):
`halo_harness.providers.model_enumeration`, the module `Controller.
list_models()` now delegates to (`build_model_rows`) and the roles
wizard's own post-keys-step live probe (`enumerate_live`) calls before
handing its result to that SAME row builder -- "do not duplicate the
picker's data source; share it."
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_get_endpoints import MockGetEndpoints

test, TESTS = new_registry()

_PROVIDER_ENV_VARS = ("OPENROUTER_API_KEY", "BRIDGE_OPENROUTER_BASE_URL", "ANTHROPIC_API_KEY",
                      "BRIDGE_ANTHROPIC_BASE_URL", "OPENAI_API_KEY", "BRIDGE_OPENAI_BASE_URL",
                      "DATABRICKS_HOST", "DATABRICKS_TOKEN", "HF_TOKEN", "EXPLABS_API_KEY",
                      "BRIDGE_TEST_CC_AUTH_STATUS", "BRIDGE_TEST_CODEX_LOGIN_STATUS", "OLLAMA_HOST",
                      "OLLAMA_API_KEY")

_OR_MODELS_BODY = {"data": [
    {"id": "deepseek/deepseek-v4.1-flash", "context_length": 128000,
     "pricing": {"prompt": "0.0000008", "completion": "0.0000024"}},
]}


class _Env:
    """Same snapshot/restore + scratch-home convention every other
    provider test module's own `_Env` uses (see test_ant_enumeration.py) --
    the real `~/.halo` is never touched, and `BRIDGE_TEST_NO_BACKGROUND_
    NET` is explicitly cleared so a test that WANTS a real (loopback-only)
    probe isn't silently short-circuited by the whole-suite runner's own
    ambient default."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in
                       (("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET")
                        + _PROVIDER_ENV_VARS)}
        d = Path(tempfile.mkdtemp(prefix="model-enum-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        for k in _PROVIDER_ENV_VARS:
            os.environ.pop(k, None)
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": False})
        # Never let `_claude_probe`/`_codex_probe` spawn a REAL `claude`/
        # `codex` subprocess on a build host that happens to have either
        # one actually logged in -- both test seams return instantly.
        os.environ["BRIDGE_TEST_CODEX_LOGIN_STATUS"] = "Not logged in"
        # `resolve_ollama_hosts` synthesizes a BARE default host (OLLAMA_
        # HOST, else 127.0.0.1:11434) whenever `ollama.hosts` config is
        # empty/absent -- on a real dev box with Ollama actually running
        # (this build host, confirmed live), `_local_probe` would
        # otherwise reach a REAL local daemon and its REAL installed
        # models. `http://127.0.0.1:1` is this codebase's own existing
        # convention for "deliberately unreachable" (tests/test_local_
        # models.py's own `_Env`) -- deterministic, no real daemon
        # involved, same as every other provider left unconfigured here.
        os.environ["OLLAMA_HOST"] = "http://127.0.0.1:1"
        # Catalog refresh (the OpenRouter/OpenAI mock-server calls below)
        # is NOT gated by this flag -- only local/Ollama auto-detection's
        # own real socket probes are (`providers.local_models`'s own
        # docstring) -- kept SET (unlike the whole-suite runner clearing
        # it for a test that specifically wants to PROVE background net
        # fires) so this file's own build_model_rows calls skip that
        # unrelated, slow, real-port-scanning tail end.
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        self.home = d
        self.state_dir = d / ".halo"
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _fake_controller(state_dir):
    from halo_harness.controller import Controller

    class _FakeModelRef:
        raw = ""
        provider = "openrouter"

    class _FakeModelProfile:
        context_tokens = None
        max_output_tokens = None

    class _FakeSession:
        model_ref = _FakeModelRef()
        model_profile = _FakeModelProfile()

    return Controller(session=_FakeSession(), cwd=Path.cwd(), state_dir=state_dir, routes={})


@test
def test_controller_list_models_matches_build_model_rows_directly(ctx: Ctx):
    """`Controller.list_models()` is now a thin wrapper -- calling
    `build_model_rows` with the SAME state_dir/env/routes must produce
    byte-identical rows (modulo the synthesized "current model" row,
    which only `Controller.list_models()` ever inserts)."""
    from halo_harness.providers.enablement import enable
    from halo_harness.providers.model_enumeration import build_model_rows
    mock = MockGetEndpoints({"/api/v1/models": (200, _OR_MODELS_BODY)}).start()
    try:
        with _Env() as env:
            enable("openrouter")
            os.environ["OPENROUTER_API_KEY"] = "sk-or-fake"
            os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url + "/api/v1"
            from halo_harness.providers.databricks import refresh_openrouter_catalog_if_stale
            refresh_openrouter_catalog_if_stale(env.state_dir, force=True)

            ctrl = _fake_controller(env.state_dir)
            via_controller = ctrl.list_models()
            via_function = build_model_rows(env.state_dir, env=None, routes={})
            ctx.check(f"same row count (no current-row insertion either side here), got "
                      f"{len(via_controller)} vs {len(via_function)}", len(via_controller) == len(via_function))
            ctx.check(f"same refs, got {[m.get('ref') for m in via_function]}",
                      [m.get("ref") for m in via_controller] == [m.get("ref") for m in via_function])
    finally:
        mock.stop()


@test
def test_enumerate_live_reports_cached_not_configured_and_not_reachable(ctx: Ctx):
    """Three provider outcomes in one pass, deterministically (no real
    DNS/TCP timing relied on): OpenRouter reachable with real data,
    OpenAI "configured" but its own mock returns a 500 (-> "not
    reachable"), everything else genuinely unconfigured (-> "not
    configured"). `progress_cb` fires once per provider; the merged
    result at the end is built by `build_model_rows` (the OpenRouter
    model shows up in it)."""
    from halo_harness.providers.enablement import enable
    from halo_harness.providers.model_enumeration import enumerate_live
    or_mock = MockGetEndpoints({"/api/v1/models": (200, _OR_MODELS_BODY)}).start()
    oai_mock = MockGetEndpoints({"/v1/models": (500, {"error": "boom"})}).start()
    try:
        with _Env() as env:
            enable("openrouter")
            enable("openai")
            os.environ["OPENROUTER_API_KEY"] = "sk-or-fake"
            os.environ["BRIDGE_OPENROUTER_BASE_URL"] = or_mock.base_url + "/api/v1"
            os.environ["OPENAI_API_KEY"] = "sk-oai-fake"
            os.environ["BRIDGE_OPENAI_BASE_URL"] = oai_mock.base_url + "/v1"

            progress: "dict[str, str]" = {}

            def _cb(label, status):
                progress[label] = status

            rows = enumerate_live(env.state_dir, env=dict(os.environ), progress_cb=_cb, timeout_s=15.0)

            or_label = next(lbl for lbl in progress if lbl.startswith("OpenRouter"))
            oai_label = next(lbl for lbl in progress if lbl.startswith("OpenAI"))
            ant_label = next(lbl for lbl in progress if lbl.startswith("Anthropic"))
            ctx.check(f"OpenRouter reported cached, got {progress[or_label]!r}",
                      "cached" in progress[or_label])
            ctx.check(f"OpenAI's 500 reported not reachable, got {progress[oai_label]!r}",
                      progress[oai_label] == "not reachable")
            ctx.check(f"Anthropic (never configured) reported not configured, got {progress[ant_label]!r}",
                      progress[ant_label] == "not configured")
            ctx.check(f"local/claude/codex each got their own progress line too, got {sorted(progress)}",
                      any("Ollama" in lbl for lbl in progress) and any("Claude" in lbl for lbl in progress)
                      and any("Codex" in lbl for lbl in progress))
            ctx.check(f"the merged result still carries OpenRouter's real row, got "
                      f"{[m.get('ref') for m in rows]}", "or:deepseek/deepseek-v4.1-flash" in
                      [m.get("ref") for m in rows])
    finally:
        or_mock.stop()
        oai_mock.stop()


@test
def test_enumerate_live_env_overlay_never_mutates_os_environ(ctx: Ctx):
    """"never written to disk, never written to os.environ" -- an env
    dict passed in (simulating the wizard's own "typed but not yet
    saved" overlay) must never leak into the real process environment,
    before OR after the call."""
    from halo_harness.providers.model_enumeration import enumerate_live
    with _Env() as env:
        overlay = dict(os.environ)
        overlay["OPENROUTER_API_KEY"] = "sk-typed-not-saved"
        ctx.check("OPENROUTER_API_KEY absent from the REAL environ before the call",
                  "OPENROUTER_API_KEY" not in os.environ)
        enumerate_live(env.state_dir, env=overlay, progress_cb=lambda *_: None, timeout_s=15.0)
        ctx.check("still absent from the real environ after the call (never leaked)",
                  "OPENROUTER_API_KEY" not in os.environ)


@test
def test_enumerate_live_is_bounded_by_timeout_s_not_the_slowest_job(ctx: Ctx):
    """Belt-and-suspenders bound on top of each provider's own HTTP
    connect timeout (deliverable 1: "never blocks the step") -- pinned
    deterministically by substituting one deliberately slow fake job for
    the real provider list, never by relying on real network timing."""
    import halo_harness.providers.model_enumeration as me

    def _fake_jobs(state_dir, env):
        return [("Slow", lambda: (time.sleep(5.0), "unreachable in practice")[1]),
                ("Fast", lambda: "ok")]

    original = me._enumeration_jobs
    me._enumeration_jobs = _fake_jobs
    try:
        with _Env() as env:
            # This test replaces the provider job list entirely -- `_Env`'s
            # own `BRIDGE_TEST_NO_BACKGROUND_NET=1` (set unconditionally,
            # see its own comment) already keeps `build_model_rows`'s
            # trailing `build_local_view` call from running a real,
            # UNBOUNDED-by-`timeout_s` local port scan here -- this test
            # measures ONLY the bounded job-wait loop this round added.
            progress: "dict[str, str]" = {}
            t0 = time.monotonic()
            rows = me.enumerate_live(env.state_dir, env={}, progress_cb=lambda l, s: progress.__setitem__(l, s),
                                      timeout_s=0.4)
            elapsed = time.monotonic() - t0
            ctx.check(f"returned near the 0.4s bound, not after the slow job's own 5s, got {elapsed:.2f}s",
                      elapsed < 3.0)
            ctx.check(f"the slow job is reported timed out, got {progress.get('Slow')!r}",
                      progress.get("Slow") == "not reachable (timed out)")
            ctx.check(f"the fast job still answered normally, got {progress.get('Fast')!r}",
                      progress.get("Fast") == "ok")
            ctx.check("build_model_rows still ran at the end (a real list came back)", isinstance(rows, list))
    finally:
        me._enumeration_jobs = original


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
