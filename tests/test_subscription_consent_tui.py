"""tests.test_subscription_consent_tui -- Halo 2.0.7 fix pass round 7b:
the `/model`/picker-facing surfaces of the cc:/cx: subscription-routes
consent gate -- `Controller.list_models()`'s rows, the `/subscriptions`
and `/providers` builtins, and the TUI's own `_apply_model` opening the
notice instead of erroring on a gated ref. No network, no real binary,
no live Textual app (a fake stand-in records what would have happened).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_ENV_FILE", "BRIDGE_TEST_CC_AUTH_STATUS",
          "BRIDGE_TEST_CODEX_LOGIN_STATUS", "ANTHROPIC_API_KEY")


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _VARS}
        d = Path(tempfile.mkdtemp(prefix="subs-consent-tui-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["BRIDGE_ENV_FILE"] = str(d / "no-env-file")
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.state_dir = d / ".halo"
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class _FakeModelRef:
    raw = "dbx:databricks-deepseek-v4-1-flash"
    provider = "databricks"


class _FakeModelProfile:
    context_tokens = 128000
    max_output_tokens = 8192


class _FakeSession:
    model_ref = _FakeModelRef()
    model_profile = _FakeModelProfile()


@test
def test_picker_rows_show_hint_not_models_when_detected_but_not_accepted(ctx: Ctx):
    from halo_harness.controller import Controller
    from halo_harness.providers.cc_models import refresh_cached_claude_auth_status
    from halo_harness.providers.enablement import enable
    with _Env() as env:
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": True, "authMethod": "claude.ai"})
        refresh_cached_claude_auth_status()
        enable("claude_subscription")  # enabled, but consent is still off
        ctrl = Controller(session=_FakeSession(), cwd=Path.cwd(), state_dir=env.state_dir, routes={})
        rows = ctrl.list_models()
        cc_refs = [m.get("ref") for m in rows if isinstance(m.get("ref"), str) and m["ref"].startswith("cc:")]
        ctx.check(f"no selectable cc: rows while not accepted, got {cc_refs}", cc_refs == [])
        hints = [m["hint"] for m in rows if "hint" in m]
        ctx.check(f"a hint says available after acceptance, got {hints}",
                  any("available after acceptance" in h for h in hints))


@test
def test_picker_rows_show_cc_models_once_accepted(ctx: Ctx):
    from halo_harness.controller import Controller
    from halo_harness.providers.cc_models import refresh_cached_claude_auth_status
    from halo_harness.providers.enablement import enable
    from halo_harness.subscription_consent import record_acceptance
    with _Env() as env:
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": True, "authMethod": "claude.ai"})
        refresh_cached_claude_auth_status()
        enable("claude_subscription")
        record_acceptance()
        ctrl = Controller(session=_FakeSession(), cwd=Path.cwd(), state_dir=env.state_dir, routes={})
        cc_refs = [m.get("ref") for m in ctrl.list_models()
                   if isinstance(m.get("ref"), str) and m["ref"].startswith("cc:")]
        ctx.check(f"cc: rows now present, got {len(cc_refs)}", len(cc_refs) > 0)


@test
def test_slash_subscriptions_builtin_registered(ctx: Ctx):
    from halo_harness.commands.builtins import _BUILTIN_SPECS, HeadlessFacade
    with _Env():
        ctx.check("'subscriptions' is a registered builtin", "subscriptions" in _BUILTIN_SPECS)
        _kind, _desc, _hint, run = _BUILTIN_SPECS["subscriptions"]
        result = run("status", HeadlessFacade(cwd=Path.cwd()))
        ctx.check(f"headless status mentions off, got {result!r}", "off (not accepted)" in result)


@test
def test_apply_model_opens_notice_instead_of_setting_when_gated(ctx: Ctx):
    """`tui/slash.py::_apply_model` must probe-parse the ref FIRST and push
    the notice screen instead of calling `Controller.set_model` at all when
    the ref is gated -- pinned with a fake app that records every call."""
    from halo_harness.tui import slash as slash_mod

    calls: "list[str]" = []

    class _FakeController:
        routes = {}

        def set_model(self, ref):
            calls.append(f"set_model:{ref}")
            return None

    class _FakeApp:
        controller = _FakeController()

        def push_screen(self, screen, callback):
            calls.append(f"push_screen:{type(screen).__name__}")

        def notify(self, *a, **k):
            calls.append("notify")

    with _Env():
        slash_mod._apply_model(_FakeApp(), "cc:opus")
        ctx.check(f"opened the notice screen, got {calls}",
                  any(c.startswith("push_screen:SubscriptionNoticeScreen") for c in calls))
        ctx.check(f"never called set_model, got {calls}", not any(c.startswith("set_model:") for c in calls))


@test
def test_apply_model_calls_set_model_normally_when_not_gated(ctx: Ctx):
    from halo_harness.tui import slash as slash_mod

    calls: "list[str]" = []

    class _FakeController:
        routes = {}

        def set_model(self, ref):
            calls.append(f"set_model:{ref}")
            return None

    class _FakeApp:
        controller = _FakeController()
        cwd = Path.cwd()

        def push_screen(self, screen, callback):
            calls.append("push_screen")

        def notify(self, *a, **k):
            calls.append("notify")

    with _Env():
        slash_mod._apply_model(_FakeApp(), "or:deepseek/deepseek-v3.2")
        ctx.check(f"set_model called normally, got {calls}", any(c.startswith("set_model:") for c in calls))
        ctx.check(f"no notice screen opened, got {calls}", not any(c.startswith("push_screen") for c in calls))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
