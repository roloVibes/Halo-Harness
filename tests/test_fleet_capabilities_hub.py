"""tests.test_fleet_capabilities_hub -- Halo 3.0.6.0 "Fleet Missions" round
R6 over two Halo homes (tests/helpers/fleet_hub_rig.py): the member's
announce carries its catalog's summary and hash, the hub asks for the full
catalog once per hash with the read-only `capabilities` fleet command and
announces it as a `fleet` frame; `GET /api/fleet/capabilities` lists both
harnesses (the hub's own from its cache) and `GET /api/fleet/who` ranks the
member that has gridcraft first; a refresh moves the hash and emits the
frame, for the member and for the hub's own harness.

Run: python -m tests.test_fleet_capabilities_hub
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _caps_frames(rig, hid: str) -> list:
    return [f for f in rig.seen("fleet", harness=hid) if (f.get("data") or {}).get("action") == "capabilities"]


def _setup(rig):
    """The hub's own catalog seeded; the member's gathered from its config + a gridcraft tool cache."""
    from halo_harness.config.paths import bridge_home
    from tests.helpers.fleet_caps_seed import hub_catalog, mcp_setup, seed
    from tests.helpers.fleet_hub_rig import wait_for
    seed(rig.home_a, hub_catalog(rig.hub.state.identity))
    fake = {"type": "stdio", "command": sys.executable, "args": ["-m", "tests.helpers.fake_mcp_server"]}
    mcp_setup(rig.root_b, bridge_home(), {"gridcraft": fake},
              {"gridcraft": [("write_range", "Write values and formulas into a spreadsheet range")]})
    rig.set_b(**{"fleet.tags": ["linux"]})
    rig.join()
    rig.session()
    return wait_for(lambda: rig.hub.state.caps.catalogs.get(rig.b_id), 20.0)


@test
def test_the_members_catalog_reaches_the_hub_once_per_hash(ctx: Ctx):
    from tests.helpers.fleet_hub_rig import HubRig, wait_for
    with HubRig() as rig:
        cat = _setup(rig)
        ctx.check("the member's catalog reached the hub", bool(cat))
        cat = cat or {}
        grid = next((s for s in cat.get("mcp") or [] if s.get("name") == "gridcraft"), {})
        ctx.check(f"with gridcraft and its tool, got {grid}", [t["name"] for t in grid.get("tools") or []] == ["write_range"])
        m = rig.member() or {}
        ctx.check(f"the member's row carries its summary and hash, got {m.get('capabilities_summary')!r}",
                  m.get("capabilities_hash") == cat.get("hash") and "1 MCP server (1 tools)" in str(m.get("capabilities_summary")))
        time.sleep(3.0)  # six more announces at 0.5 s
        asks = [f for f in rig.hub.state.caps.fetches if f[0] == rig.b_id]
        ctx.check(f"the hub asked once for that hash, got {asks}", len(asks) == 1)
        ctx.check("a fleet frame said the member's catalog changed", bool(wait_for(lambda: _caps_frames(rig, rig.b_id), 5.0)))
        status, body = rig.api("GET", "fleet/capabilities")
        rows = {r["harness"]: r for r in body.get("harnesses") or []}
        ctx.check(f"the route lists both harnesses, got {status} {sorted(rows)}", status == 200 and set(rows) == {rig.a_id, rig.b_id})
        a = rows.get(rig.a_id) or {}
        ctx.check(f"the hub's own from its cache, with chips, got {a.get('chips')}", a.get("local") is True
                  and (a.get("catalog") or {}).get("tags") == ["studio", "gpu"] and a.get("chips")[:2] == ["studio", "gpu"])
        ctx.check("no full local path in the route's JSON", rig.root_a not in json.dumps(body) and rig.root_b not in json.dumps(body))
        status, one = rig.api("GET", "fleet/capabilities?harness=bob@member")
        ctx.check("?harness= picks one by name", status == 200 and [r["harness"] for r in one["harnesses"]] == [rig.b_id])
        ctx.check("an unknown harness is 404", rig.api("GET", "fleet/capabilities?harness=nobody")[0] == 404)
        status, who = rig.api("GET", "fleet/who?q=gridcraft")
        res = who.get("results") or []
        ctx.check(f"who gridcraft ranks the member first, got {status} {[r['name'] for r in res]}",
                  status == 200 and res and res[0]["harness"] == rig.b_id and res[0]["matches"][0]["kind"] in ("mcp_tool", "craft_app"))
        status, who = rig.api("GET", "fleet/who?q=4090")
        ctx.check("who 4090 ranks the hub first", status == 200 and who["results"][0]["harness"] == rig.a_id)
        ctx.check("a query with no words is 422", rig.api("GET", "fleet/who?q=the")[0] == 422)


@test
def test_refresh_updates_the_hash_and_emits_the_frame(ctx: Ctx):
    from halo_harness.fleet import identity
    from tests.helpers.fleet_hub_rig import HubRig, wait_for
    with HubRig() as rig:
        cat = _setup(rig) or {}
        before = len(_caps_frames(rig, rig.b_id))
        rig.set_b(**{"fleet.tags": ["linux", "night-shift"]})
        status, body = rig.api("GET", f"fleet/capabilities?harness={rig.b_id}&refresh=1", timeout=60.0)
        row = (body.get("harnesses") or [{}])[0]
        ctx.check(f"refresh asks the member now: a new hash with the new tag, got {status} {row.get('hash')} vs {cat.get('hash')}",
                  status == 200 and row.get("hash") != cat.get("hash") and "night-shift" in (row.get("catalog") or {}).get("tags", []))
        ctx.check("and the frame says so", bool(wait_for(lambda: len(_caps_frames(rig, rig.b_id)) > before, 5.0)))
        old = (rig.hub.state.caps.local() or {}).get("hash")
        (rig.home_a / "config.json").write_text(json.dumps({"fleet": {"name": "alice@hub", "tags": ["hub-box"]}}), encoding="utf-8")
        identity.forget_cache()
        status, body = rig.api("GET", "fleet/capabilities?harness=local&refresh=1", timeout=60.0)
        row = (body.get("harnesses") or [{}])[0]
        ctx.check(f"refresh=1 regathers the hub's own harness, got {status} {row.get('chips')}",
                  status == 200 and row.get("hash") != old and row.get("chips", [""])[0] == "hub-box")
        ctx.check("with a frame for the hub's own id", bool(wait_for(lambda: _caps_frames(rig, rig.a_id), 5.0)))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet capabilities hub tests"))
