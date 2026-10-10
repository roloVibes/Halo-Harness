"""tests.test_subscription_consent -- Halo 2.0.7 fix pass round 7b: the
cc:/cx: subscription-routes consent gate itself, plus the
`model.parse_model_ref` gate it feeds. See test_subscription_consent_
cli.py for the CLI/doctor/providers/lineup-fallback coverage (kept in a
separate file -- house rule: one file write/edit stays at or under 250
lines). No network, no real `claude`/`codex` binary.
"""
from __future__ import annotations

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
        d = Path(tempfile.mkdtemp(prefix="subs-consent-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["BRIDGE_ENV_FILE"] = str(d / "no-env-file")
        os.environ.pop("ANTHROPIC_API_KEY", None)
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
# subscription_consent.py itself.
# ---------------------------------------------------------------------------

@test
def test_fresh_config_is_not_accepted(ctx: Ctx):
    from halo_harness.subscription_consent import is_accepted, status_line
    with _Env():
        ctx.check("fresh config: not accepted", is_accepted() is False)
        ctx.check(f"status line, got {status_line()!r}", status_line() == "subscription routes: off (not accepted)")


@test
def test_accept_flips_config_with_date_and_version(ctx: Ctx):
    from halo_harness.subscription_consent import NOTICE_VERSION, is_accepted, record_acceptance
    with _Env():
        state = record_acceptance(now="2026-10-09T23:30:00Z")
        ctx.check(f"accepted True, got {state}", state["accepted"] is True)
        ctx.check(f"version recorded, got {state}", state["accepted_version"] == NOTICE_VERSION)
        ctx.check(f"date recorded, got {state}", state["accepted_at"] == "2026-10-09T23:30:00Z")
        ctx.check("is_accepted() now True", is_accepted() is True)


@test
def test_revoke_returns_to_off(ctx: Ctx):
    from halo_harness.subscription_consent import is_accepted, record_acceptance, revoke
    with _Env():
        record_acceptance()
        ctx.check("accepted first", is_accepted() is True)
        revoke()
        ctx.check("revoked -> off again", is_accepted() is False)


@test
def test_changed_notice_version_asks_again(ctx: Ctx):
    import halo_harness.subscription_consent as sc
    with _Env():
        sc.record_acceptance()
        ctx.check("accepted at the current version", sc.is_accepted() is True)
        real_version = sc.NOTICE_VERSION
        sc.NOTICE_VERSION = real_version + 1
        try:
            ctx.check("a version bump asks again (reads as not accepted)", sc.is_accepted() is False)
        finally:
            sc.NOTICE_VERSION = real_version


@test
def test_read_typed_acceptance_exact_phrase_only(ctx: Ctx):
    from halo_harness.subscription_consent import read_typed_acceptance
    ctx.check("exact phrase -> True", read_typed_acceptance(prompt=lambda _p: "I accept") is True)
    ctx.check("trailing whitespace tolerated", read_typed_acceptance(prompt=lambda _p: "  I accept  ") is True)
    ctx.check("anything else -> False", read_typed_acceptance(prompt=lambda _p: "sure") is False)
    ctx.check("empty -> False", read_typed_acceptance(prompt=lambda _p: "") is False)

    def _eof(_p):
        raise EOFError()

    ctx.check("non-interactive stdin (EOF) -> False, never raises", read_typed_acceptance(prompt=_eof) is False)


# ---------------------------------------------------------------------------
# model.parse_model_ref gate.
# ---------------------------------------------------------------------------

@test
def test_parse_model_ref_cc_refused_when_not_accepted(ctx: Ctx):
    import json
    from halo_harness.model import parse_model_ref
    from halo_harness.subscription_consent import SubscriptionConsentRequiredError
    with _Env():
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": True, "authMethod": "claude.ai"})
        raised = False
        try:
            parse_model_ref("cc:opus")
        except SubscriptionConsentRequiredError as e:
            raised = True
            ctx.check(f"names the route, got {e}", "available after acceptance" in str(e))
            ctx.check("carries the route", e.route == "cc")
        ctx.check("raised SubscriptionConsentRequiredError", raised)


@test
def test_parse_model_ref_cx_refused_when_not_accepted(ctx: Ctx):
    from halo_harness.model import parse_model_ref
    from halo_harness.subscription_consent import SubscriptionConsentRequiredError
    with _Env():
        raised = False
        try:
            parse_model_ref("cx:astra")
        except SubscriptionConsentRequiredError as e:
            raised = True
            ctx.check("carries the route", e.route == "cx")
        ctx.check("raised", raised)


@test
def test_bare_alias_routes_through_cc_and_is_gated_too(ctx: Ctx):
    import json
    from halo_harness.model import parse_model_ref
    from halo_harness.subscription_consent import SubscriptionConsentRequiredError
    with _Env():
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": True, "authMethod": "claude.ai"})
        raised = False
        try:
            parse_model_ref("opus")  # bare alias -> routes to cc: -> gated the same way
        except SubscriptionConsentRequiredError:
            raised = True
        ctx.check("bare alias is gated via the cc: route", raised)


@test
def test_cc_resolves_once_accepted_and_enabled(ctx: Ctx):
    import json
    from halo_harness.model import parse_model_ref
    from halo_harness.providers.enablement import enable
    from halo_harness.subscription_consent import record_acceptance
    with _Env():
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": True, "authMethod": "claude.ai"})
        record_acceptance()
        enable("claude_subscription")
        ref = parse_model_ref("cc:opus")
        ctx.check(f"resolves fine once accepted, got {ref}", ref.provider == "cc")


@test
def test_ant_route_never_gated(ctx: Ctx):
    """"Nothing else changes for API-key routes" -- ant: never consults
    the consent gate at all."""
    from halo_harness.model import parse_model_ref
    from halo_harness.providers.enablement import enable
    with _Env():
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-fake"
        enable("anthropic")
        ref = parse_model_ref("ant:opus")
        ctx.check(f"ant: resolves with no acceptance needed, got {ref}", ref.provider == "anthropic")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
