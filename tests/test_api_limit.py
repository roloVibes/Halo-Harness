"""tests.test_api_limit -- Halo 3.6.0.2 P4 batch 9: Studio's requests have a time limit (lib/apiLimit.ts, used by
lib/api.ts `request`), so a read that never ends cannot leave a door's drawer closed for good. Pure: node, every platform
(tests/helpers/node_ts.py). The browser half (a goal run's Open with its file read held: the drawer opens at once) is
tests/test_studio_doors.py.

1. every request has 30 s; a longer limit only for the routes named in LONG, each with its reason (a model, another
   machine, a download, a run starting, a pack's own route);
2. a request that never answers is given up at its limit: it rejects with "no answer in N s" (lib/api.ts prefixes the
   page's own words, "Studio server unreachable: ") and the request is aborted; one that answers in time is untouched.
Run: python -m tests.test_api_limit
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
LIMIT = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "lib" / "apiLimit.ts"
API = LIMIT.with_name("api.ts")


def node(body: str):
    from tests.helpers import node_ts
    js = f"const M = await import({json.dumps(LIMIT.resolve().as_uri())});\nconst out = {{}};\n{body}\nconsole.log(JSON.stringify(out));"
    return node_ts.run(js)


@test
def test_every_request_has_a_limit_and_the_long_ones_are_named(ctx: Ctx):
    got = node("""
const paths = ['orchestra/r-1/file', 'orchestra/r-1/events', 'live', 'crew/map/shop', 'builder', 'local/steward/chat',
               'local/host/gpu-box/pull', 'models/test', 'sessions/abc/command', 'packs/demo/x', '/api/orchestra/runs?x=1'];
out.limits = Object.fromEntries(paths.map((p) => [p, M.limitFor(p)]));
out.base = M.LIMIT_MS;
out.reasons = M.LONG.every(([re, why]) => re instanceof RegExp && typeof why === 'string' && why.length > 8);
""")
    lim = got.get("limits") or {}
    ctx.check(f"30 s by default, got {got.get('base')}", got.get("base") == 30000)
    short = ["orchestra/r-1/file", "orchestra/r-1/events", "live", "crew/map/shop", "/api/orchestra/runs?x=1"]
    ctx.check(f"a page's reads get 30 s, got {lim}", all(lim.get(p) == 30000 for p in short))
    long_ = ["builder", "local/steward/chat", "local/host/gpu-box/pull", "models/test", "sessions/abc/command", "packs/demo/x"]
    ctx.check(f"a route that waits on a model, a host or a pack gets the longer limit, got {lim}", all(lim.get(p, 0) > 30000 for p in long_))
    ctx.check("each long route says why", got.get("reasons") is True)
    src = API.read_text(encoding="utf-8")
    ctx.check("lib/api.ts request goes through the limit (within + limitFor)", "within(" in src and "limitFor(path)" in src)


@test
def test_a_read_that_never_answers_fails_at_its_limit(ctx: Ctx):
    got = node("""
let aborted = false;
const never = (signal) => new Promise(() => { signal.addEventListener('abort', () => { aborted = true; }); });
const t0 = Date.now();
try { await M.within(never, 60); out.got = 'answered'; } catch (e) { out.got = String(e.message); }
out.ms = Date.now() - t0;
out.aborted = aborted;
out.fast = await M.within(async () => 'ok', 60000);
""")
    ctx.check(f"it fails with the limit's words, got {got.get('got')!r}", str(got.get("got")).startswith("no answer in "))
    ctx.check(f"the request is aborted, got {got.get('aborted')}", got.get("aborted") is True)
    ctx.check(f"at the limit, not before, got {got.get('ms')} ms", (got.get("ms") or 0) >= 55)
    ctx.check(f"an answer in time is untouched, got {got.get('fast')!r}", got.get("fast") == "ok")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
