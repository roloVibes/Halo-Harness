"""tests.test_fleet_hub_security -- Halo 3.0.5.0 "Fleet" round R2: what the
hub and the relay refuse, and what never blocks a session.

* a wrong pairing code is refused; one code admits one harness;
* a signed request replayed, stale, unsigned or with a bad signature is
  refused; a down doc (a command) that is not the hub's, out of order or
  stale is ignored by the relay (protocol.verify_down);
* `kick` disconnects B: its relay stops (fleet.json says kicked), the view
  drops it, its signed requests get 403 `kicked`;
* the hub down never slows B: a session opens and its turn completes.
"""
from __future__ import annotations

import http.client
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fleet_hub_rig import HubRig, wait_for
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


@test
def test_a_wrong_code_is_refused_and_a_code_admits_one_harness(ctx: Ctx):
    from halo_harness.fleet import identity, relay
    with HubRig() as rig:
        code = rig.hub.pairing.new_code(600)[0]
        wrong = " ".join(reversed(code.split()))
        if wrong == code:
            wrong = "acorn " * 5 + "zebra"
        try:
            relay.join(rig.url(), wrong, identity.harness())
            ctx.check("a wrong code must not join", False)
        except relay.HubError as e:
            ctx.check(f"a wrong code is refused (403), got {e.status} {e}", e.status == 403 and "not accepted" in str(e))
        ctx.check("no member was added", rig.hub.pairing.members() == {})
        ctx.check("the right code still works afterwards", relay.join(rig.url(), code, identity.harness())["hub_id"] == rig.a_id)
        try:
            relay.join(rig.url(), code, {**identity.harness(), "id": "0123456789abcdef"})
            ctx.check("a spent code must not admit a second harness", False)
        except relay.HubError as e:
            ctx.check(f"one code admits one harness: the second join is refused, got {e.status}", e.status == 403)
        try:
            relay.join(rig.url(), rig.hub.pairing.new_code(600)[0], {**identity.harness(), "id": rig.a_id})
            ctx.check("the hub's own harness must not join itself", False)
        except relay.HubError as e:
            ctx.check(f"the hub's own harness is already its member (409), got {e.status}", e.status == 409)
        try:
            relay.join(rig.url(), "only three words", identity.harness())
            ctx.check("a malformed code fails before any request", False)
        except ValueError as e:
            ctx.check(f"a malformed code is a usage error, got {e}", "6 words" in str(e))


def _post(port: int, path: str, body: bytes, headers: dict):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("POST", path, body=body, headers={**headers, "Content-Type": "application/json"})
        resp = conn.getresponse()
        return resp.status, resp.read().decode("utf-8")
    finally:
        conn.close()


@test
def test_replayed_stale_unsigned_and_forged_requests_are_refused(ctx: Ctx):
    from halo_harness.fleet import protocol, store
    with HubRig(tls_on=False) as rig:
        entry = rig.join()
        key, port, path = store.key_for(entry), rig.hub.port, "/fleet/v1/announce"
        body = protocol.encode(protocol.doc(link="feedfacefeedface", harness={"name": "bob@member"}, sessions=[]))
        signed = protocol.sign_headers(key, "POST", path, rig.b_id, body)
        status, _ = _post(port, path, body, signed)
        ctx.check(f"a signed announce is accepted, got {status}", status == 200)
        status, text = _post(port, path, body, signed)
        ctx.check(f"the same request replayed is refused, got {status} {text}", status == 401 and "replayed" in text)
        old = protocol.sign_headers(key, "POST", path, rig.b_id, body, now=time.time() - 600)
        status, text = _post(port, path, body, old)
        ctx.check(f"a stale request is refused, got {status} {text}", status == 401 and "stale" in text)
        status, text = _post(port, path, body + b" ", protocol.sign_headers(key, "POST", path, rig.b_id, body))
        ctx.check(f"a body that does not match its signature is refused, got {status}", status == 401 and "bad signature" in text)
        status, text = _post(port, path, body, protocol.sign_headers(b"x" * 32, "POST", path, rig.b_id, body))
        ctx.check(f"another key's signature is refused, got {status}", status == 401 and "bad signature" in text)
        status, text = _post(port, path, body, {})
        ctx.check(f"an unsigned request is refused, got {status}", status == 401 and "unsigned" in text)
        doc = protocol.sign_down(key, rig.b_id, "lnk", {"type": "command", "seq": 5, "ts": time.time(), "cmd": "agent_stop"})
        ctx.check("the hub's own down doc verifies", protocol.verify_down(key, rig.b_id, "lnk", doc, 4) == "")
        ctx.check("a down doc with a changed field is ignored",
                  protocol.verify_down(key, rig.b_id, "lnk", {**doc, "cmd": "shutdown"}, 4) == "bad signature")
        ctx.check("a down doc for another link is ignored", protocol.verify_down(key, rig.b_id, "other", doc, 4) == "bad signature")
        ctx.check("a down doc seen before (its seq) is ignored", protocol.verify_down(key, rig.b_id, "lnk", doc, 5) == "replayed")
        stale = protocol.sign_down(key, rig.b_id, "lnk", {"type": "command", "seq": 9, "ts": time.time() - 999})
        ctx.check("a stale down doc is ignored", protocol.verify_down(key, rig.b_id, "lnk", stale, 4) == "stale")


@test
def test_kick_disconnects_b(ctx: Ctx):
    from halo_harness.fleet import store
    from halo_harness.fleet.cli_more import _ping
    with HubRig() as rig:
        rig.join()
        _controller, act = rig.session()
        wait_for(lambda: rig.member_session(act.session_id))
        # 15 s, not 5: under the full suite's load the relay's first connect has taken over 6 s
        ctx.check("B is connected first", wait_for(lambda: getattr(rig.relay(), "state", None) == "connected", 15))
        hits = rig.hub.pairing.find("bob@member")
        ctx.check("the member is found by name", len(hits) == 1)
        rig.hub.pairing.remove(hits[0]["id"], kicked=True)
        ctx.check("B's relay hears the kick and stops", wait_for(lambda: rig.relay().state == "kicked", 8))
        ctx.check("B's fleet.json marks the hub kicked", store.hubs()[0]["state"] == "kicked")
        ctx.check("the hub's view no longer lists B", wait_for(lambda: rig.member() is None, 5))
        ctx.check("a `fleet` frame said B left", any(f["data"].get("action") == "leave" for f in rig.seen("fleet", harness=rig.b_id)))
        got = _ping({**store.hubs()[0], "state": "joined"})
        ctx.check(f"B's signed requests are refused as kicked, got {got}", got.get("reachable") is False and got.get("kicked") is True)


@test
def test_the_hub_down_never_slows_b(ctx: Ctx):
    with HubRig() as rig:
        rig.join()
        rig.hub.stop()
        t0 = time.monotonic()
        controller, act = rig.session()
        opened = time.monotonic() - t0
        ctx.check(f"a session opens at once with its hub down, took {opened:.2f}s", act is not None and opened < 1.5)
        t0 = time.monotonic()
        controller.submit("work while the hub is away")
        done = wait_for(lambda: controller.session.turn_count >= 1 and not controller.session.busy, 10)
        took = time.monotonic() - t0
        ctx.check(f"its turn completes, took {took:.2f}s", bool(done) and took < 3.0)
        ctx.check("the relay keeps retrying in the background", wait_for(lambda: rig.relay() is not None
                  and rig.relay().state in ("retrying", "starting"), 5))


@test
def test_offline_mode_refuses_serve_and_stops_the_relay(ctx: Ctx):
    import os
    from halo_harness.fleet import identity, relay
    from halo_harness.fleet.cli import cmd_serve
    from halo_harness.fleet.hub import FleetOffline, HubServer
    with HubRig() as rig:
        rig.join()
        os.environ["HALO_OFFLINE"] = "1"
        try:
            try:
                HubServer(rig.home_a, port=0, bind="127.0.0.1").start()
                ctx.check("serve must not start offline", False)
            except FleetOffline as e:
                ctx.check(f"offline: the hub refuses to start, got {e}", "offline mode is on" in str(e))
            ctx.check("offline: `halo fleet serve` exits 1", cmd_serve(["--bind", "127.0.0.1", "--port", "0"]) == 1)
            try:
                relay.join(rig.url(), rig.hub.pairing.new_code(600)[0], identity.harness())
                ctx.check("a join must not connect offline", False)
            except relay.HubError as e:
                ctx.check(f"offline: a join says why before any socket, got {e}", "offline mode is on" in str(e))
            _controller, act = rig.session()
            ctx.check("offline: a session still opens", act is not None)
            time.sleep(1.0)
            ctx.check("offline: no relay starts and the hub never hears of the session",
                      rig.relay() is None and rig.member_session(act.session_id) is None)
        finally:
            os.environ.pop("HALO_OFFLINE", None)
        from halo_harness.fleet import relay_runtime
        relay_runtime._sync()
        ctx.check("back online: the relay starts and announces the session",
                  wait_for(lambda: rig.member_session(act.session_id), 8))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
