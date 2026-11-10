"""tests.test_studio_copilot -- the Copilot card of Setup -> Providers in the page (Halo 3.3.17.0 R2). Headless Chrome
through tests/helpers/studio_copilot.py (skipped without one) over a scratch home, the Copilot mock standing in for
Entra and Work IQ, the browser a stub that follows the redirect: no pop-up on load, the card and its scopes; the
tenant and app id saved; Sign in (the browser flow: "finish in the browser tab that opened", then signed in, the
refresh token in the env file and never in the page); Sign out; Sign in with no browser here (the device code, then
signed in); a row per fact with its ellipsis and tooltip, no horizontal scroll. No Microsoft endpoint, no model.

Run: python -m tests.test_studio_copilot
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_copilot", why="the Copilot card needs headless Chrome", cache=_RUN,
                      timeout=300, tail=600)


@test
def test_the_card_on_load(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"nothing pops up on load, got {got.get('popups')}", got.get("popups") == [False, False, 0])
    ctx.check(f"the eight provider cards are unchanged, got {got.get('provider_cards')}", got.get("provider_cards") == 8)
    ctx.check(f"not set up, got {got.get('status0')!r}", str(got.get("status0")).startswith("Copilot: not set up") and got.get("mark0") == "-")
    ctx.check(f"the scopes an admin consents to, got {got.get('scopes')!r}", got.get("scopes") == "https://workiq.svc.cloud.microsoft/.default")
    ctx.check("Register the app is closed until opened", got.get("register_open") is False)


@test
def test_the_tenant_and_app_id_are_saved(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"config.json has them, got {got.get('config')}", (got.get("config") or {}).get("tenant") == "pretend-tenant"
              and (got.get("config") or {}).get("client_id") == "00000000-0000-0000-0000-000000000000")
    ctx.check(f"the status names the tenant, not signed in, got {got.get('status1')!r}", "tenant: pretend-tenant" in str(got.get("status1"))
              and "not signed in" in str(got.get("status1")))


@test
def test_sign_in_in_the_browser_then_out(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"finish in the browser tab that opened, got {got.get('waiting_line')!r}",
              str(got.get("waiting_line")).startswith("Finish in the browser tab that opened"))
    ctx.check(f"then signed in, got {got.get('signed_mark')!r} {got.get('status2')!r}", got.get("signed_mark") == "signed in"
              and "signed in as someone@pretend-tenant.example" in str(got.get("status2")) and got.get("opened") == 1)
    ctx.check("the refresh token is in the env file and never in the page", got.get("env_has_refresh") is True and got.get("token_in_page") is False)
    ctx.check(f"Sign out: set up, not signed in, got {got.get('status3')!r}", "not signed in" in str(got.get("status3"))
              and "HALO_SECRET_COPILOT_REFRESH" in str(got.get("lines3")))


@test
def test_no_browser_here_shows_the_device_code(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the code and where to type it, got {got.get('device_line')!r}", "PRETEND1" in str(got.get("device_line"))
              and "devicelogin" in str(got.get("device_line")))
    ctx.check(f"then signed in, got {got.get('device_mark')!r}", got.get("device_mark") == "signed in")


@test
def test_a_row_per_fact(ctx: Ctx):
    got = _got(ctx)
    rows = got.get("rows") or []
    ctx.check(f"each status row: its text in its tooltip, one line, an ellipsis, got {rows}", rows and all(
        r == [True, "nowrap", "ellipsis", True] for r in rows))
    ctx.check("no horizontal scroll", got.get("hscroll") is False)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
