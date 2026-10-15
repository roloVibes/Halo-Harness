"""tests.test_fleet_mission_files -- Halo 3.0.6.0 "Fleet Missions" round R7:
the mission folder over the signed fleet protocol (fleet/mission_files.py,
the hub port's `POST /fleet/v1/mission_files`). Two homes on loopback
(tests/helpers/fleet_hub_rig.py): the member B pulls what its part may read
(MISSION.md, its brief, inputs/, never another part's brief), puts its
artifacts and hand-back, and is refused a path with `..`, another part's
files, a file over fleet.mission.max_file_mb, a mission it has no part in,
and an unsigned request.

Run: python -m tests.test_fleet_mission_files
"""
from __future__ import annotations

import base64
import http.client
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _mission(home, member: str, hub: str) -> str:
    """A planned mission in the hub's home: part 1 on the member, part 2 on the hub."""
    from halo_harness.fleet import mission as M
    from halo_harness.fleet import mission_plan as P
    from halo_harness.fleet import mission_store as S
    mid = M.new_id()
    doc = M.new_doc(mid=mid, goal="Scan and book", hub={"id": hub, "name": "alice@hub"})
    S.create(home, doc)
    parts = [{"id": "1", "title": "scan", "brief": "scan it", "kind": "files", "harness": member, "harness_name": "bob@member",
              "claims": ["artifacts/1/**"], "depends_on": [], "outputs": []},
             {"id": "2", "title": "book", "brief": "book it", "kind": "files", "harness": hub, "harness_name": "alice@hub",
              "claims": ["artifacts/2/**"], "depends_on": ["1"], "outputs": []}]
    plan = {"v": 1, "mission": mid, "parts": parts, "merge_order": [], "notes": []}
    P._commit(home, mid, plan, "test", "seeded")
    S.write_text(S.folder(home, mid), "inputs/targets.txt", "198.51.100.0/24\n")
    S.write_text(S.folder(home, mid), "artifacts/2/secret.txt", "the hub's own part\n")
    return mid


@test
def test_the_folder_round_trips_and_stays_confined(ctx: Ctx):
    from halo_harness.fleet import mission_store as S
    from halo_harness.fleet import store
    from halo_harness.fleet.mission_files import HubFiles
    from halo_harness.fleet.relay import HubError
    from tests.helpers.fleet_hub_rig import HubRig
    with HubRig(tls_on=False) as rig:  # plain HTTP: the unsigned request below is read, not dropped by TLS
        (rig.home_a / "config.json").write_text(json.dumps({"fleet": {"name": "alice@hub", "mission": {"max_file_mb": 0.01}}}),
                                                encoding="utf-8")
        from halo_harness.fleet import identity
        identity.forget_cache()
        rig.join()
        mid = _mission(rig.home_a, rig.b_id, rig.a_id)
        files = HubFiles(store.hubs()[0])
        listed = sorted(f["path"] for f in files.call("list", mid)["files"])
        ctx.check(f"list: what part 1 may read, got {listed}", listed == ["MISSION.md", "claims.json", "inputs/targets.txt",
                                                                          "parts/1/brief.md"])
        dest = Path(tempfile.mkdtemp(prefix="mirror-"))
        got = files.pull(mid, dest)
        ctx.check("pull mirrors them byte for byte", sorted(got) == listed and (dest / "parts" / "1" / "brief.md").read_bytes()
                  == (S.folder(rig.home_a, mid) / "parts" / "1" / "brief.md").read_bytes())
        (dest / "artifacts" / "1").mkdir(parents=True)
        (dest / "artifacts" / "1" / "scan.xml").write_text("<nmaprun/>", encoding="utf-8")
        (dest / "parts" / "1" / "handback.md").write_text("scanned", encoding="utf-8")
        sent, skipped = files.push(mid, dest, ["artifacts/1/scan.xml", "parts/1/handback.md"])
        ctx.check("push puts the artifact and the hand-back on the hub", sent == ["artifacts/1/scan.xml", "parts/1/handback.md"]
                  and (S.folder(rig.home_a, mid) / "artifacts" / "1" / "scan.xml").read_text(encoding="utf-8") == "<nmaprun/>")
        ctx.check("every put is in the mission log", len(S.read_log(rig.home_a, mid, ("file_put",))) == 2)

        def refused(op: str, **fields) -> int:
            try:
                files.call(op, mid, **fields)
                return 200
            except HubError as e:
                return e.status
        b64 = base64.b64encode(b"x").decode("ascii")
        ctx.check("get another part's brief: 403", refused("get", path="parts/2/brief.md") == 403)
        ctx.check("get another part's artifact: 403", refused("get", path="artifacts/2/secret.txt") == 403)
        ctx.check("put another part's hand-back: 403", refused("put", path="parts/2/handback.md", data_b64=b64) == 403)
        ctx.check("put MISSION.md: 403", refused("put", path="MISSION.md", data_b64=b64) == 403)
        ctx.check("a path with ..: 400", refused("put", path="artifacts/1/../../mission.json", data_b64=b64) == 400)
        ctx.check("an absolute path: 400", refused("get", path="C:/Windows/win.ini") == 400 and refused("get", path="/etc/hosts") == 400)
        big = base64.b64encode(b"x" * 20000).decode("ascii")
        ctx.check("a file over fleet.mission.max_file_mb: 413", refused("put", path="artifacts/1/big.bin", data_b64=big) == 413)
        ctx.check("bad base64: 400", refused("put", path="artifacts/1/x", data_b64="!!") == 400)
        ctx.check("a missing file: 404", refused("get", path="inputs/none.txt") == 404)
        other = _mission(rig.home_a, "c" * 16, rig.a_id)
        try:
            files.call("list", other)
            code = 200
        except HubError as e:
            code = e.status
        ctx.check(f"a mission it has no part in: 403, got {code}", code == 403)
        conn = http.client.HTTPConnection("127.0.0.1", rig.hub.port, timeout=10)
        conn.request("POST", "/fleet/v1/mission_files", body=json.dumps({"v": 1, "op": "list", "mission": mid}).encode("utf-8"),
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        ctx.check(f"an unsigned request: 401, got {resp.status}", resp.status == 401)
        conn.close()
        files.close()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet mission files tests"))
