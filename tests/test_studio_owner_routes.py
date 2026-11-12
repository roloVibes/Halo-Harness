"""tests.test_studio_owner_routes -- every write needs the owner's own page (Halo 3.4.1.2, the 2026-11-12 review's
SERVERS-1 and SERVERS-2; studio/owner_proof.py, docs/STUDIO-shell.md "The owner's page and a pack's key"), over a real
server:

1. SERVERS-2: every POST / PUT / PATCH / DELETE route the code answers (tests/helpers/studio_write_routes.py harvests
   them all: the route tables, the dispatch functions' literals and patterns, the shipped fleet pack's routes) is
   classified in tests/fixtures/studio_write_routes.txt, and each `owner` one answers 403 NEEDS_OWNER with the token
   alone. A route the code adds fails here until someone classifies it.
2. SERVERS-2: the reviewer's chain -- a bio with a shell hook, a lineup, its apply, shutdown -- is refused with the
   token alone and nothing is written; a running pack's own routes are not owner routes, a made-up pack id's are.
3. SERVERS-1 (the general gate): a write that types into a session or answers its cards needs the proof wherever it is
   routed (the enumeration above covers every core route, the `fleet/...` ones among them); the core handlers that end
   in a control-socket call or change what runs (a session's command, a new session, bio and lineup writes and apply)
   are `owner_only` themselves.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_studio import PackStudio  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "studio_write_routes.txt"


def _classified() -> dict:
    out = {}
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            cls, key = line.split(" ", 1)
            out[key] = cls
    return out


@test
def test_servers_2_every_write_route_is_classified_and_owner_routes_refuse_the_token_alone(ctx: Ctx):
    from halo_harness.studio.owner_proof import NEEDS_OWNER
    from tests.helpers.studio_write_routes import harvest
    rows, known = harvest(), _classified()
    keys = {r["key"] for r in rows}
    ctx.check(f"the harvest found the routes (got {len(rows)})", len(rows) >= 150)
    new = sorted(keys - set(known))
    ctx.check(f"every write route is classified in {FIXTURE.name}: add these as owner or pack: {new}", not new)
    gone = sorted(set(known) - keys)
    ctx.check(f"no classified route is gone (remove these from {FIXTURE.name}): {gone}", not gone)
    with PackStudio() as s:
        bad = []
        for r in rows:
            if known.get(r["key"]) != "owner":
                continue
            for method in (("POST", "PUT", "PATCH", "DELETE") if r["method"] == "*" else (r["method"],)):
                status, got, _h = s.call(method, r["path"], {}, owner=False)
                if status != 403 or got.get("error") != NEEDS_OWNER:
                    bad.append(f"{method} {r['path']} -> {status}")
        ctx.check(f"every owner route is 403 NEEDS_OWNER with the token alone, these were not: {bad[:12]}", not bad)
        ctx.check("Studio still answers after all that (shutdown was refused too)", s.call("GET", "state", owner=False)[0] == 200)


@test
def test_servers_2_the_reviewers_chain_is_refused_and_writes_nothing(ctx: Ctx):
    from halo_harness.studio.owner_proof import NEEDS_OWNER
    with PackStudio() as s:
        hook = {"raw": {"hooks": {"on_start": [{"command": "echo pwned > pwned.txt"}]}}}
        steps = [("PUT", "bio/evil", hook), ("POST", "bio", {"name": "evil2"}), ("POST", "lineup", {"name": "evilteam"}),
                 ("PUT", "lineup/evilteam", {"raw": {"agents": []}}), ("POST", "lineup/standard/apply", {}),
                 ("DELETE", "bio/x", None), ("POST", "shutdown", {}), ("POST", "sessions/s-1/command", {"cmd": "submit", "text": "hi"})]
        for method, path, body in steps:
            status, got, _h = s.call(method, path, body, owner=False)
            ctx.check(f"{method} {path} with the token alone: 403, got {status} {got}", status == 403 and got.get("error") == NEEDS_OWNER)
        agents = s.state / "agents"
        ctx.check("no bio was written", not (agents / "evil.yaml").exists() and not (agents / "evil2.yaml").exists())
        ctx.check("no lineup was written", not (s.state / "teams" / "evilteam.yaml").exists())
        ctx.check("Studio still runs", s.call("GET", "state", owner=False)[0] == 200)
        s.install_pack("routes-pack", grants=["studio-routes"])
        status, got, _h = s.call("POST", "packs/routes-pack/r/ping", {}, owner=False)
        ctx.check(f"a running pack's own route takes the token alone, got {status} {got}", status == 200 and got.get("method") == "POST")
        status, got, _h = s.call("POST", "packs/nopack/r/ping", {}, owner=False)
        ctx.check(f"a made-up pack id is not a pack's route: 403, got {status}", status == 403 and got.get("error") == NEEDS_OWNER)
        status, _got, _h = s.call("PUT", "layout/routes-pack:canvas", {"positions": {}}, owner=False)
        ctx.check(f"a running pack's own layout takes the token alone, got {status}", status == 200)
        status, got, _h = s.call("PUT", "layout/standard", {"positions": {}}, owner=False)
        ctx.check(f"a lineup's layout is the owner's, got {status}", status == 403)
        status, got, _h = s.call("PUT", "bio/mine", {"raw": {"description": "mine"}})
        ctx.check(f"the shell's own call (with the proof) still writes a bio, got {status} {got.get('error')}", status == 200)


@test
def test_servers_1_the_handlers_are_owner_only_themselves(ctx: Ctx):
    from halo_harness.studio import api, sessions_api
    from halo_harness.studio.api import Request
    from halo_harness.studio.owner_proof import NEEDS_OWNER
    wanted = {"sessions/x/command", "sessions/new", "lineup", "lineup/x", "lineup/x/apply", "bio", "bio/x"}
    routes = list(api.ROUTES) + list(sessions_api.ROUTES)
    gated = {(m, p) for m, p, fn in routes if getattr(fn, "owner_only", False)}
    import re
    for path in sorted(wanted):
        hits = [(m, p) for m, p, _fn in routes if m != "GET" and re.match(p, path)]
        ctx.check(f"{path}: every write handler is owner_only, got {hits} vs gated", hits and all(h in gated for h in hits))
    req = Request(method="POST", path="sessions/x/command", query={}, body={"cmd": "pause"}, cwd=Path("."), state_dir=Path("."))
    fn = next(fn for m, p, fn in sessions_api.ROUTES if m == "POST" and p.endswith("/command$") and "agents" not in p)
    ctx.check("a Request without the proof is refused by the handler itself", fn(req) == (403, {"error": NEEDS_OWNER}))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
