"""tests.test_fleet_hub -- Halo 3.0.5.0 "Fleet" round R2: the hub and the join,
two Halo homes on one machine (tests/helpers/fleet_hub_rig.py). Home A runs
the hub inside an in-process Studio; home B joins with a pair code and its
session shows on A's `GET /api/fleet` with its agent tree; B's frames reach
A's live feed with `harness: <B>` as far as B's share level allows (status:
rows and trees only; events: no text; full: the text too); the version chip
flips when B reports another version; the hub port serves nothing but the
fleet protocol.
"""
from __future__ import annotations

import http.client
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fleet_hub_rig import HubRig, wait_for
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


@test
def test_b_joins_a_and_its_session_shows_with_the_agent_tree(ctx: Ctx):
    with HubRig() as rig:
        entry = rig.join()
        ctx.check(f"B stored the hub in fleet.json, got {entry}", entry["url"] == rig.url() and entry["hub_id"] == rig.a_id
                  and entry["member_name"] == "bob@member" and entry["state"] == "joined")
        from halo_harness.fleet import store
        ctx.check("the pair key is on disk under B's fleet/keys, never in fleet.json",
                  store.key_for(entry) is not None and "key" not in entry and "key_hex" not in str(store.load()))
        controller, act = rig.session()
        sid = act.session_id
        row = wait_for(lambda: rig.member_session(sid))
        ctx.check(f"B's session is on the hub's view, got {row}", row is not None and row["kind"] == "tui")
        ctx.check("with its agent tree (the main agent first)", row and row["agents"][0]["agent_id"] == "main")
        ctx.check("and no endpoint, token or full path", row and "endpoint" not in row and "token" not in row
                  and row["cwd"] == Path(rig.root_b).name and "transcript" not in row["agents"][0])
        status, view = rig.api("GET", "fleet")
        ids = [h["id"] for h in view.get("harnesses") or []] if status == 200 else []
        ctx.check(f"GET /api/fleet lists both harnesses, A first (local), got {status} {ids}",
                  ids == [rig.a_id, rig.b_id] and view["harnesses"][0]["local"] is True)
        b = view["harnesses"][1] if len(ids) == 2 else {}
        ctx.check(f"B is online with its share and control levels, got {b}", b.get("online") is True
                  and b.get("share") == "events" and b.get("allow_control") == "ask" and b.get("name") == "bob@member"
                  and b.get("version_mismatch") is False and isinstance(b.get("cost_today"), (int, float)))
        ctx.check("B's session is in the API's row too", any(s["session_id"] == sid for s in b.get("sessions") or []))
        hub = view.get("hub") or {}
        ctx.check(f"the hub block says it serves, got {hub}", hub.get("serving") is True and hub.get("members") == 1
                  and hub.get("online") == 1 and hub.get("name") == "hub-a" and hub.get("port") == rig.hub.port)
        ctx.check("a `fleet` frame said B joined and came online", rig.seen("fleet", harness=rig.b_id)
                  and any(f["data"].get("action") == "online" for f in rig.seen("fleet", harness=rig.b_id)))
        ctx.check("A's own sessions frame carries the harness id", any(f.get("harness") for f in rig.seen("sessions")))


def _turn(controller, n: int) -> None:
    controller.submit(f"hello number {n}")
    wait_for(lambda: controller.session.turn_count >= n and not controller.session.busy)


@test
def test_frames_reach_a_feed_as_far_as_b_shares(ctx: Ctx):
    with HubRig() as rig:
        rig.set_b(**{"fleet.share": "status"})
        rig.join()
        controller, act = rig.session()
        sid = act.session_id
        wait_for(lambda: rig.member_session(sid))
        _turn(controller, 1)
        from halo_harness.agent.agent_registry import tree_for
        tree = tree_for(controller.session)
        tree.update(tree.root_id, current="Bash: ls", last_text="a line the owner wrote")
        wait_for(lambda: rig.seen("agent_state", harness=rig.b_id), 5)
        ctx.check("share status: agent_state frames arrive with harness B and the session id",
                  any(f["session_id"] == sid for f in rig.seen("agent_state", harness=rig.b_id)))
        ctx.check("share status: no user_message, no turn_done, no text", not rig.seen("user_message", harness=rig.b_id)
                  and not rig.seen("turn_done", harness=rig.b_id) and not rig.seen("text_chunk", harness=rig.b_id))
        ctx.check("share status: an agent row carries no last_text",
                  all("last_text" not in a for a in (rig.member_session(sid) or {}).get("agents", [])))
        rig.set_b(**{"fleet.share": "events"})
        rig.poke()
        wait_for(lambda: (rig.member() or {}).get("share") == "events", 5)
        _turn(controller, 2)
        got = wait_for(lambda: rig.seen("turn_done", harness=rig.b_id, session_id=sid), 5)
        ctx.check("share events: B's turn frames reach A's feed with harness B", bool(got)
                  and rig.seen("user_message", harness=rig.b_id, session_id=sid))
        ctx.check("share events: still no text chunk", not rig.seen("text_chunk", harness=rig.b_id))
        rig.set_b(**{"fleet.share": "full"})
        rig.poke()
        wait_for(lambda: (rig.member() or {}).get("share") == "full", 5)
        _turn(controller, 3)
        chunks = wait_for(lambda: rig.seen("text_chunk", harness=rig.b_id, session_id=sid), 8)
        ctx.check(f"share full: the text stream arrives, got {len(chunks or [])}",
                  bool(chunks) and "fake" in "".join(f["data"]["text"] for f in chunks))


@test
def test_the_version_chip_flips_when_b_reports_another_version(ctx: Ctx):
    import halo_harness
    with HubRig() as rig:
        rig.join()
        _controller, act = rig.session()
        wait_for(lambda: rig.member_session(act.session_id))
        ctx.check("same version: no mismatch", (rig.member() or {}).get("version_mismatch") is False)
        real = halo_harness.__version__
        try:
            halo_harness.__version__ = "0.0.1.0"
            rig.poke()
            flipped = wait_for(lambda: (rig.member() or {}).get("version_mismatch") is True, 5)
            ctx.check("B on another version: version_mismatch is true", bool(flipped)
                      and rig.member()["version"] == "0.0.1.0")
            from halo_harness.fleet.pairing import HubPairing
            ctx.check("the hub remembers the version B reported", HubPairing(rig.home_a).member(rig.b_id)["version"] == "0.0.1.0")
        finally:
            halo_harness.__version__ = real
        rig.poke()
        ctx.check("back on the hub's version: the chip clears",
                  wait_for(lambda: (rig.member() or {}).get("version_mismatch") is False, 5))


@test
def test_the_hub_port_serves_only_the_fleet_protocol(ctx: Ctx):
    with HubRig(tls_on=False) as rig:
        conn = http.client.HTTPConnection("127.0.0.1", rig.hub.port, timeout=5)
        try:
            conn.request("GET", "/api/fleet", headers={"Authorization": "Bearer " + rig.server.token})
            resp = conn.getresponse()
            body = resp.read().decode("utf-8")
        finally:
            conn.close()
        ctx.check(f"Studio's API is not on the hub port, got {resp.status} {body[:80]}",
                  resp.status == 404 and "only the Halo fleet protocol" in body)
        conn = http.client.HTTPConnection("127.0.0.1", rig.hub.port, timeout=5)
        try:
            conn.request("GET", "/fleet/v1/local/state")
            resp = conn.getresponse()
            resp.read()
        finally:
            conn.close()
        ctx.check(f"the hub's local view needs its own admin token, got {resp.status}", resp.status == 403)
        status, _ = rig.api("GET", "sessions")
        ctx.check("Studio's loopback API still answers on its own port", status == 200)


@test
def test_tls_hub_pins_its_fingerprint(ctx: Ctx):
    from halo_harness.fleet import tls
    if not tls.available():
        ctx.check("skipped: cryptography is not installed here (the hub would be HMAC-only)", True)
        return
    with HubRig() as rig:
        ctx.check("the hub serves TLS with a fingerprint", rig.url().startswith("https://") and len(rig.hub.fingerprint) == 64)
        entry = rig.join()
        ctx.check("the joiner pinned the hub's fingerprint", entry["tls"] is True and entry["fingerprint"] == rig.hub.fingerprint)
        from halo_harness.fleet import identity, relay
        try:
            relay.join(rig.url(), rig.hub.pairing.new_code(600)[0], identity.harness(), fingerprint="ab" * 32)
            ctx.check("a join insisting on another fingerprint must fail", False)
        except relay.HubError as e:
            ctx.check(f"a join insisting on another fingerprint fails, got {e}", "certificate changed" in str(e))


@test
def test_serve_starts_the_hub_inside_a_running_studio(ctx: Ctx):
    import contextlib
    import io
    import json
    import os
    import tempfile
    import threading
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    os.environ.pop("BRIDGE_STATE_DIR", None)
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="fleet-studio-")
    from halo_harness.fleet.identity import home
    from halo_harness.fleet.pairing import hub_dir
    from halo_harness.studio.server import start_server, studio_info_path
    state = home()
    state.mkdir(parents=True, exist_ok=True)
    server = start_server(port=0, cwd=state, state_dir=state)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        studio_info_path(state).write_text(json.dumps({"pid": os.getpid(), "port": server.server_address[1],
                                                       "token": server.token}), encoding="utf-8")
        from halo_harness.fleet.cli import cmd_serve
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_serve(["--bind", "127.0.0.1", "--port", "0", "--no-tls", "--json"])
        got = json.loads(out.getvalue() or "{}")
        ctx.check(f"`halo fleet serve` with Studio running starts the hub inside it, got {rc} {got}", rc == 0
                  and got.get("in_studio") is True and got.get("tls") is False and server.fleet_hub is not None)
        ctx.check("the running hub records where it is (serve.json)", (hub_dir(state) / "serve.json").is_file())
        from halo_harness.studio.launch import api_call
        status, view = api_call(state, "GET", "fleet")
        ctx.check(f"GET /api/fleet: serving, this harness alone, got {view.get('hub')}", status == 200
                  and view["hub"]["serving"] is True and len(view["harnesses"]) == 1 and view["harnesses"][0]["local"])
        status, again = api_call(state, "POST", "fleet/hub", {"action": "start"})
        ctx.check("a second start says it already runs", status == 200 and again.get("already") is True)
        status, _ = api_call(state, "POST", "fleet/hub", {"action": "stop"})
        status, view = api_call(state, "GET", "fleet")
        ctx.check("stopped: the view says it is not serving and serve.json is gone", view["hub"]["serving"] is False
                  and server.fleet_hub is None and not (hub_dir(state) / "serve.json").exists())
    finally:
        server.shutdown()
        server.server_close()
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
