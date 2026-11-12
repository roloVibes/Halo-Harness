"""tests.test_studio_owner_probe -- a pack's page script cannot lift the owner proof (Halo 3.4.1.2, the 2026-11-12
review's SERVERS-4 and PACKS-2), in headless Chrome through tests/helpers/studio_owner_probe.py (skipped without
Chrome), with the fixture pack tests/fixtures/packs/owner-probe as the attacker:

1. SERVERS-4: the bundle opens Studio's page in a window on a user gesture and polls it for the salt: none (the window
   is a script's), and that page says it can look but not change things;
2. PACKS-2: with Map.prototype.get, Promise.prototype.then, Headers and fetch-init getters patched, the shell's own
   owner write (the theme menu) still works, and the bundle catches no proof;
3. every forged `pack/owner-probe/grant` (each salt and caught value, and none) is 403, and the pack keeps its grant.
Run: python -m tests.test_studio_owner_probe
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
    return driver_got(ctx, "tests.helpers.studio_owner_probe", why="the probes need headless Chrome", cache=_RUN, timeout=300)


@test
def test_servers_4_a_window_a_script_opens_gets_no_salt(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the window opened, got {got}", got.get("opened") is True)
    ctx.check(f"no salt reached it, got {got.get('salts')}", got.get("salts") == 0)
    ctx.check(f"it says it can look but not change things, or its opener is cut off from it, got {got.get('view_only')} "
              f"{got.get('severed')}", got.get("view_only") is True or got.get("severed") is True)


@test
def test_packs_2_patched_intrinsics_catch_no_proof_and_the_shell_still_writes(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the shell's own owner write worked while patched, got {got.get('shell_theme')!r}", got.get("shell_theme") == "midnight")
    ctx.check(f"the bundle caught no proof, got {got.get('stolen')}", got.get("stolen") == 0)


@test
def test_every_forgery_is_refused_and_the_grant_stays(ctx: Ctx):
    got = _got(ctx)
    forged = got.get("forged") or []
    ctx.check(f"every forged owner write is 403, got {forged}", forged and all(s == 403 for s in forged))
    ctx.check(f"the pack keeps studio-script, got {got.get('granted_after')}", got.get("granted_after") == ["studio-script"])


@test
def test_the_browsers_reload_keeps_the_owners_page_a_scripts_does_not(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"F5 (the browser's reload): still the owner's page, got {got.get('browser_reload_view_only')}",
              got.get("browser_reload_view_only") is False)
    ctx.check(f"location.reload() from a script: VIEW ONLY, got {got.get('script_reload_view_only')}",
              got.get("script_reload_view_only") is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
