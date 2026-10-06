"""tests.test_balances -- Halo 2.0.4 round 3 (deliverable 2): the one
shared balances surface -- `providers.balances` (the cached fetch/
persist core), `halo balances` (CLI), `/balances` (headless), and the
status bar's generic per-provider chip (`tui/widgets/statusbar.py`'s
`set_provider_balance`/`_active_balance`).
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_get_endpoints import MockGetEndpoints

test, TESTS = new_registry()

_PROVIDER_ENV_VARS = ("OPENROUTER_API_KEY", "BRIDGE_OPENROUTER_BASE_URL", "OPENROUTER_MANAGEMENT_KEY",
                      "EXPLABS_API_KEY", "BRIDGE_EXPLABS_BASE_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_ADMIN_KEY",
                      "BRIDGE_ANTHROPIC_BASE_URL", "BRIDGE_TEST_CC_AUTH_STATUS")


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in (("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR") + _PROVIDER_ENV_VARS)}
        d = Path(tempfile.mkdtemp(prefix="balances-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        for k in _PROVIDER_ENV_VARS:
            os.environ.pop(k, None)
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": False})
        self.home = d
        self.state_dir = d / ".halo"
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# providers.balances core.
# ---------------------------------------------------------------------------

@test
def test_databricks_is_always_not_offered(ctx: Ctx):
    """2.0.3-brief part B item 5: explicitly excluded by the owner (DBU
    billing is on the workspace side) -- never a fetch, regardless of
    enablement."""
    from halo_harness.providers.balances import refresh_all_balances
    from halo_harness.providers.enablement import enable
    with _Env() as env:
        enable("databricks")
        result = refresh_all_balances(env.state_dir, env={})
        ctx.check(f"databricks is not_offered, got {result['databricks']}",
                  result["databricks"]["status"] == "not_offered")
        ctx.check("names DBU billing as the reason", "DBU" in result["databricks"]["note"])


@test
def test_everything_not_configured_when_nothing_is_set(ctx: Ctx):
    from halo_harness.providers.balances import refresh_all_balances
    with _Env() as env:
        result = refresh_all_balances(env.state_dir, env={})
        for name in ("openrouter", "experiential", "anthropic", "databricks"):
            ctx.check(f"{name} is not_offered with nothing configured, got {result[name]}",
                      result[name]["status"] == "not_offered")


@test
def test_openrouter_success_flows_through_and_persists(ctx: Ctx):
    from halo_harness.providers.balances import cached_balances, refresh_all_balances
    from halo_harness.providers.enablement import enable
    from halo_harness.providers.openrouter_account import reset_cached_openrouter_balance
    mock = MockGetEndpoints({"/key": (200, {"data": {"label": "my-key", "limit": 20.0, "limit_remaining": 12.4,
                                                        "usage": 7.6, "is_free_tier": False}})}).start()
    try:
        with _Env() as env:
            reset_cached_openrouter_balance()
            enable("openrouter")
            os.environ["OPENROUTER_API_KEY"] = "sk-or-fake"
            os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
            os.environ["BRIDGE_TEST_OPENROUTER_HOST_OVERRIDE"] = "1"
            result = refresh_all_balances(env.state_dir, env=dict(os.environ))
            ctx.check(f"openrouter ok with the real reading, got {result['openrouter']}",
                      result["openrouter"]["status"] == "ok" and result["openrouter"]["amount"] == 12.4)
            persisted = cached_balances(env.state_dir)
            ctx.check(f"persisted to balances.json, got {persisted.get('openrouter')}",
                      persisted.get("openrouter", {}).get("amount") == 12.4)
    finally:
        mock.stop()
        os.environ.pop("BRIDGE_TEST_OPENROUTER_HOST_OVERRIDE", None)
        reset_cached_openrouter_balance()


@test
def test_anthropic_not_offered_without_admin_key_offered_with_one(ctx: Ctx):
    """2.0.3-brief part B item 2: no balance endpoint for a plain key;
    with ANTHROPIC_ADMIN_KEY, the organisation cost report."""
    from halo_harness.providers.balances import refresh_all_balances
    with _Env() as env:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-fake"
        result = refresh_all_balances(env.state_dir, env=dict(os.environ))
        ctx.check(f"no admin key -> not_offered, got {result['anthropic']}", result["anthropic"]["status"] == "not_offered")

        mock = MockGetEndpoints({"/v1/organizations/cost_report": (200, {"data": [
            {"results": [{"amount": {"value": "1.50"}}, {"amount": {"value": 2.25}}]},
        ]})}).start()
        try:
            os.environ["ANTHROPIC_ADMIN_KEY"] = "sk-ant-admin-fake"
            os.environ["BRIDGE_ANTHROPIC_BASE_URL"] = mock.base_url
            result2 = refresh_all_balances(env.state_dir, env=dict(os.environ))
            ctx.check(f"admin key present -> ok with summed spend, got {result2['anthropic']}",
                      result2["anthropic"]["status"] == "ok" and abs(result2["anthropic"]["amount"] - 3.75) < 1e-9)
        finally:
            mock.stop()


@test
def test_format_balances_table_lists_every_provider_in_order(ctx: Ctx):
    from halo_harness.providers.balances import format_balances_table
    from halo_harness.providers.enablement import PROVIDER_NAMES
    lines = format_balances_table({})
    ctx.check(f"one line per registered provider, got {len(lines)}", len(lines) == len(PROVIDER_NAMES))
    ctx.check("every line says not fetched/not offered, never a crash",
              all(("not fetched" in l or "not offered" in l) for l in lines))


# ---------------------------------------------------------------------------
# CLI + headless slash command.
# ---------------------------------------------------------------------------

@test
def test_cmd_balances_bare_never_touches_network(ctx: Ctx):
    from halo_harness.balances_cli import cmd_balances
    with _Env():
        os.environ["OPENROUTER_API_KEY"] = "sk-or-fake"
        os.environ["BRIDGE_OPENROUTER_BASE_URL"] = "https://unresolvable.invalid.example"
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_balances([])
        ctx.check(f"exit 0, no hang, got {rc}", rc == 0)
        ctx.check(f"OpenRouter line present, got {buf.getvalue()!r}", "OpenRouter" in buf.getvalue())


@test
def test_cmd_balances_refresh_populates_the_cache(ctx: Ctx):
    from halo_harness.balances_cli import cmd_balances
    from halo_harness.providers.enablement import enable
    from halo_harness.providers.openrouter_account import reset_cached_openrouter_balance
    mock = MockGetEndpoints({"/key": (200, {"data": {"label": "k", "limit": None, "limit_remaining": None,
                                                        "usage": 1.23, "is_free_tier": True}})}).start()
    try:
        with _Env():
            reset_cached_openrouter_balance()
            enable("openrouter")
            os.environ["OPENROUTER_API_KEY"] = "sk-or-fake"
            os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
            os.environ["BRIDGE_TEST_OPENROUTER_HOST_OVERRIDE"] = "1"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cmd_balances(["--refresh"])
            ctx.check(f"exit 0, got {rc}", rc == 0)
            ctx.check(f"shows the usage-based figure, got {buf.getvalue()!r}", "$1.23 used" in buf.getvalue())
    finally:
        mock.stop()
        os.environ.pop("BRIDGE_TEST_OPENROUTER_HOST_OVERRIDE", None)
        reset_cached_openrouter_balance()


@test
def test_slash_balances_matches_the_cli(ctx: Ctx):
    from halo_harness.commands.builtins import HeadlessFacade, _cmd_balances
    with _Env() as env:
        facade = HeadlessFacade(cwd=env.home)
        text = _cmd_balances("", facade)
        ctx.check(f"a line per provider, got {text!r}", text.count("\n") >= 5)
        ctx.check("Databricks always not_offered here too", "Databricks" in text and "not offered" in text)


# ---------------------------------------------------------------------------
# Status bar: the generic per-provider chip, active-provider preference.
# ---------------------------------------------------------------------------

@test
def test_status_bar_prefers_the_active_providers_balance_falls_back_to_openrouter(ctx: Ctx):
    """A real StatusBar needs a mounted Textual App for `.update()` to
    work at all (same `_run_in_mounted_app` convention every existing
    OpenRouter-chip test in tests/test_h15_openrouter_balance.py already
    uses) -- a bare `StatusBar()` with no app raises NoActiveAppError."""
    import asyncio
    from pathlib import Path as _Path
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp

    async def body():
        fake = FakeController()
        app = BridgeApp(fake, cwd=str(_Path(__file__).resolve().parent.parent))
        async with app.run_test(size=(240, 40)):
            bar = app.status_bar
            # Only OpenRouter populated -- every pre-round-3 box's own
            # shape -- must render exactly as before regardless of the
            # active model.
            bar.model = "xp:space-bunny-alpha"
            bar.set_or_balance("OR $12.40 left")
            text, _ = bar._active_balance()
            ctx.check(f"falls back to OpenRouter when the active provider has nothing of its own, got {text!r}",
                      text == "OR $12.40 left")
            # Now Experiential ALSO has its own reading -- the active
            # provider (xp:) must win over the OpenRouter fallback.
            bar.set_provider_balance("experiential", "XP $5.00 left")
            text2, _ = bar._active_balance()
            ctx.check(f"the ACTIVE provider's own reading wins, got {text2!r}", text2 == "XP $5.00 left")
            # Switching the active model back to openrouter shows
            # OpenRouter's own reading again, unaffected by experiential's.
            bar.model = "or:deepseek/x"
            text3, _ = bar._active_balance()
            ctx.check(f"switching models switches the chip, got {text3!r}", text3 == "OR $12.40 left")
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
