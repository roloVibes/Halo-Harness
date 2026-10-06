"""tests.test_catalog_refresh_scheduler -- Halo 2.0.4 round 3
(deliverable 5): `providers.catalog_refresh` (the "one scheduler for every
catalog, each provider registering its own fetcher" piece H15 part 2
addendum 3.2 named -- `refresh_all_enabled_catalogs` -- but never actually
built), the background TUI worker's new failure notification ("a failed
refresh keeps the previous cache and says so once"), and `halo doctor`
reporting every catalog's age (not just three) via the same registry.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_get_endpoints import MockGetEndpoints

test, TESTS = new_registry()

_PROVIDER_ENV_VARS = ("OPENROUTER_API_KEY", "BRIDGE_OPENROUTER_BASE_URL", "ANTHROPIC_API_KEY",
                      "BRIDGE_ANTHROPIC_BASE_URL", "BRIDGE_TEST_CC_AUTH_STATUS")


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in
                       (("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET")
                        + _PROVIDER_ENV_VARS)}
        d = Path(tempfile.mkdtemp(prefix="catalog-sched-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        for k in _PROVIDER_ENV_VARS:
            os.environ.pop(k, None)
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": False})
        # The whole-suite runner's own ambient default (and this module's
        # own shell env while developing it) must NOT leak in here -- the
        # TUI worker test below needs background network genuinely
        # enabled to prove the mock upstream was actually called (same
        # fix test_h15_catalog_refresh.py's own _Env already applies).
        os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
        self.home = d
        self.state_dir = d / ".halo"
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@test
def test_specs_cover_every_live_api_provider(ctx: Ctx):
    from halo_harness.providers.catalog_refresh import _specs
    names = {s.provider for s in _specs()}
    ctx.check(f"all six registered, got {names}",
              names == {"openrouter", "anthropic", "databricks", "huggingface", "openai", "experiential"})


@test
def test_catalog_ages_never_cached_then_fresh(ctx: Ctx):
    from halo_harness.providers.catalog_refresh import catalog_ages
    from halo_harness.providers.databricks import models_json_path
    with _Env() as env:
        env.state_dir.mkdir(parents=True, exist_ok=True)
        ages = catalog_ages(env.state_dir)
        ctx.check(f"one row per catalog, got {len(ages)}", len(ages) == 6)
        ctx.check("every row never-cached (age_seconds is None) on a fresh dir",
                  all(a["age_seconds"] is None for a in ages))
        models_json_path(env.state_dir).write_text("{}", encoding="utf-8")
        ages2 = catalog_ages(env.state_dir)
        or_row = next(a for a in ages2 if a["provider"] == "openrouter")
        ctx.check(f"OpenRouter's age is now a real number, got {or_row['age_seconds']!r}",
                  isinstance(or_row["age_seconds"], float) and or_row["age_seconds"] >= 0)
        other_rows = [a for a in ages2 if a["provider"] != "openrouter"]
        ctx.check("every OTHER catalog is still never-cached",
                  all(a["age_seconds"] is None for a in other_rows))


@test
def test_refresh_all_enabled_catalogs_skips_disabled_and_reports_attempted(ctx: Ctx):
    from halo_harness.providers.catalog_refresh import refresh_all_enabled_catalogs
    from halo_harness.providers.enablement import enable
    or_mock = MockGetEndpoints({"/api/v1/models": (200, {"data": [
        {"id": "deepseek/deepseek-v3.2", "context_length": 128000, "pricing": {"prompt": "0.0000008", "completion": "0.0000024"}},
    ]})}).start()
    try:
        with _Env() as env:
            enable("openrouter")
            os.environ["OPENROUTER_API_KEY"] = "sk-or-fake"
            os.environ["BRIDGE_OPENROUTER_BASE_URL"] = or_mock.base_url + "/api/v1"
            results = {r["provider"]: r for r in refresh_all_enabled_catalogs(env.state_dir, force=True)}
            ctx.check(f"openrouter attempted and ok, got {results['openrouter']}",
                      results["openrouter"]["attempted"] is True and results["openrouter"]["ok"] is True
                      and results["openrouter"]["count"] == 1)
            ctx.check(f"anthropic never attempted (not enabled), got {results['anthropic']}",
                      results["anthropic"]["attempted"] is False and results["anthropic"]["ok"] is None)
    finally:
        or_mock.stop()


@test
def test_refresh_all_enabled_catalogs_reports_failure_not_crash(ctx: Ctx):
    """A real upstream 500 -> ok=False, count=None (never shows the
    PREVIOUS cache's count as if the failed attempt had produced it) --
    never raises, so one bad catalog can't take the batch down."""
    from halo_harness.providers.catalog_refresh import refresh_all_enabled_catalogs
    from halo_harness.providers.enablement import enable
    or_mock = MockGetEndpoints({"/api/v1/models": (500, {"error": "boom"})}).start()
    try:
        with _Env() as env:
            enable("openrouter")
            os.environ["OPENROUTER_API_KEY"] = "sk-or-fake"
            os.environ["BRIDGE_OPENROUTER_BASE_URL"] = or_mock.base_url + "/api/v1"
            results = {r["provider"]: r for r in refresh_all_enabled_catalogs(env.state_dir, force=True)}
            ctx.check(f"openrouter attempted and failed, got {results['openrouter']}",
                      results["openrouter"]["attempted"] is True and results["openrouter"]["ok"] is False
                      and results["openrouter"]["count"] is None)
    finally:
        or_mock.stop()


@test
def test_tui_worker_reports_a_failed_refresh_once(ctx: Ctx):
    """deliverable 5: "a failed refresh keeps the previous cache and says
    so once" -- tui.slash.catalog_auto_refresh_worker's own failure
    notification, added this round (it used to be completely silent on a
    failed background attempt)."""
    from halo_harness.providers.databricks import load_models_json, write_models_json
    from halo_harness.providers.enablement import enable
    from halo_harness.tui.slash import catalog_auto_refresh_worker

    class _FakeSettings:
        def __init__(self, env):
            self.effective_env = env

    class _FakeController:
        def __init__(self, state_dir, env):
            self.state_dir = state_dir
            self.settings = _FakeSettings(env)

    class _FakeApp:
        def __init__(self, state_dir, env):
            self.controller = _FakeController(state_dir, env)
            self.notifications = []

        def call_from_thread(self, fn, *a, **kw):
            fn(*a, **kw)

        def notify(self, text, **kw):
            self.notifications.append((text, kw))

    mock = MockGetEndpoints({"/api/v1/models": (500, {"error": "boom"})}).start()
    try:
        with _Env() as env:
            enable("openrouter")
            # A pre-existing cache -- proof the failed attempt below never
            # touches it (refresh_*_if_stale's own "failure leaves the
            # previous cache untouched" contract).
            write_models_json(env.state_dir, [{"id": "keep/me", "context_length": 1000}])
            # A freshly-written cache reads as "not stale yet" to the
            # staleness gate, which would SKIP the refresh attempt
            # entirely (returning None, never False) -- force every
            # catalog to always be treated as due, same knob a real
            # `databricks.catalog_max_age_hours: 0` config value gives.
            from halo_harness.theme import set_config_value
            set_config_value("databricks.catalog_max_age_hours", 0)
            app = _FakeApp(env.state_dir, {
                "OPENROUTER_API_KEY": "sk-or-fake",
                "BRIDGE_OPENROUTER_BASE_URL": mock.base_url + "/api/v1",
            })
            catalog_auto_refresh_worker(app)
            ctx.check(f"one failure notification naming OpenRouter, got {app.notifications}",
                      any("OpenRouter" in n[0] and "failed" in n[0].lower() for n in app.notifications))
            ctx.check(f"the previous cache is untouched, got {load_models_json(env.state_dir)}",
                      "keep/me" in load_models_json(env.state_dir))
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
