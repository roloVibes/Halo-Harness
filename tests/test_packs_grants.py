"""tests.test_packs_grants -- what each Studio grant's line says (Halo 3.3.14.0 R1, the November review's #4 and #34;
packs/grants.py WHAT, docs/EXTENSION_API.md):

1. `studio-script`: 3.4.1.2 (SERVERS-2): "runs this pack's code INSIDE Studio's page with Studio's own power: it can do
   what you can do in Studio, including starting sessions that run commands" (before: "a client scoped to this pack's
   own routes", which a page's own script is not held to);
2. `studio-routes`: "runs this pack's Python inside halo (Studio's server) with your rights, Halo's keys and Studio's
   token; turning it off takes effect at Studio's restart for work already started";
3. EXTENSION_API.md says the same, states `api.lib`'s scope and no longer says "Every call is the pack's own";
4. packs_routes.unload calls a routes module's own `unload()`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
SCRIPT = ("runs this pack's code INSIDE Studio's page with Studio's own power: it can do what you can do in Studio, "
          "including starting sessions that run commands")
ROUTES = ("runs this pack's Python inside halo (Studio's server) with your rights, Halo's keys and Studio's token; turning "
          "it off takes effect at Studio's restart for work already started")


@test
def test_the_studio_grant_lines(ctx: Ctx):
    from halo_harness.packs.grants import WHAT, what
    ctx.check(f"studio-script, got {WHAT['studio-script']!r}", WHAT["studio-script"] == SCRIPT and what("studio-script") == SCRIPT)
    ctx.check(f"studio-routes, got {WHAT['studio-routes']!r}", WHAT["studio-routes"] == ROUTES)


@test
def test_the_extension_api_says_the_same(ctx: Ctx):
    doc = " ".join((REPO / "docs" / "EXTENSION_API.md").read_text(encoding="utf-8").split())
    ctx.check("the studio-script line", SCRIPT in doc)
    ctx.check("the studio-routes line", ROUTES in doc)
    ctx.check("api.lib states its scope", "**The client's scope**" in doc and "this needs the owner's own page" in doc)
    ctx.check("no 'Every call is the pack's own' any more", "Every call is the pack's own" not in doc)
    ctx.check("the key, not the token, in a pack GET's URL", "the pack's key in `?k=`" in doc and "token in `?t=`" not in doc)


@test
def test_unload_calls_the_modules_own_hook(ctx: Ctx):
    import inspect
    from halo_harness.studio import packs_routes as PR
    src = inspect.getsource(PR.unload)
    ctx.check("unload looks for a module-level unload()", 'getattr((have or {}).get("module"), "unload", None)' in src
              and "hook()" in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
