"""tests.test_host_api -- Halo 3.3.7.0 R1 deliverable 2: the host's signed API (host/http.py, host/routes_view.py,
host/answers.py, host/join.py) over tests/helpers/host_rig.py's fake host (a fixture card, catalog, tail and log
status; a fixture ledger, events and a profile in its home):

1. pairing through the six-word code: fleet.json's `hosts` entry {url, name, host_id, key_ref, fingerprint, serves,
   grants: [view]}; a spent code is refused;
2. every route's shape: card (the hardware card, its log status, other clients, the usable footprint, the audit),
   catalog?window= (a fit verdict per model, speed, measured, profile truth), profiles, events, tail, simulate,
   route, ping;
3. the signature: unsigned 401, a wrong key 401, an unknown peer 403, a replayed request 401;
4. the tail never carries a prompt body (and `n` is held to host.tail_max);
5. control / manage / admin answer 403 naming the grant and the command that gives it (3.3.7.0 R2);
6. one audit line per request {at, peer, path, ok, ms};
7. the live stream: a card frame first, an event frame when an event is recorded, the ping.
Run: python -m tests.test_host_api
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_rig import BIG, BODY, CODER, HostRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _err(fn):
    from halo_harness.ollama_steward.host_client import HostError
    try:
        fn()
    except HostError as e:
        return e.status, str(e)
    return 200, ""


@test
def test_pairing_stores_the_host_with_the_view_grant(ctx: Ctx):
    from halo_harness.fleet import identity, store
    from halo_harness.fleet.relay import HubError
    from halo_harness.host.join import join
    with HostRig() as rig:
        rig.start()
        e = rig.pair()
        ctx.check(f"the entry: url, host id, key ref, serves pc at the placeholder, grants view, got {e}",
                  e["url"] == rig.url() and e["host_id"] == rig.svc.identity["id"] and e["key_ref"].startswith("host-")
                  and e["serves"] == [{"name": "pc", "port": 11434, "addr": "192.0.2.10"}] and e["grants"] == ["view"])
        ctx.check("fleet.json keeps it under hosts, the hubs untouched", store.hosts()[0]["host_id"] == e["host_id"]
                  and store.hubs() == [])
        ctx.check("the peer's record on the host carries the view grant",
                  rig.svc.pairing.grants_of(identity.harness()["id"]) == ("view",))
        code = rig.svc.pairing.new_code(600)[0]
        join(f"127.0.0.1:{rig.svc.port}", code, identity.harness())
        try:
            join(f"127.0.0.1:{rig.svc.port}", code, identity.harness())
            refused = ""
        except HubError as ex:
            refused = str(ex)
        ctx.check(f"a spent code is refused with the host's own line, got {refused!r}", "halo host pair" in refused)


@test
def test_every_route_answers_its_shape(ctx: Ctx):
    with HostRig() as rig:
        rig.start()
        rig.pair()
        c = rig.client()
        ctx.check("the peer's pc entry finds the host", c is not None and c.addr == "127.0.0.1")
        ping = c.ping()
        ctx.check(f"ping: the host and this peer's grants, got {ping}", ping["host"]["host"] is True
                  and ping["you"]["grants"] == ["view"])
        card = c.card()
        row = card["hosts"][0]
        ctx.check(f"card: the hardware card, the log status, other clients, the footprint, got {list(row)}",
                  row["name"] == "pc" and row["port"] == 11434 and row["card"]["gpus"][0]["name"] == "a 24 GB card"
                  and row["log"]["state"] == "live" and row["other_clients"] == [{"from": "mac@lab", "calls": 1}]
                  and row["footprint"] == "22.0 GB usable")
        ctx.check(f"card: the host's start time and the audit count, got {card.get('host')} {card.get('audit')}",
                  card["host"]["started"] and card["audit"]["count"] >= 2)
        cat = c.catalog(32768)
        models = {m["model"]: m for m in cat["hosts"][0]["models"]}
        big = models.get(BIG) or {}
        ctx.check(f"catalog: a fit verdict at the asked window from the host's budget, got {big.get('fit')}",
                  cat["window"] == 32768 and big["fit"]["fits"] is True and big["fit"]["window"] == 32768
                  and isinstance(big["fit"]["need_bytes"], int) and big["fit"]["max_window"])
        ctx.check(f"catalog: the profile verified there, the others expected, got {big.get('profile')}",
                  big["profile"]["truth"] == "verified" and big["profile"]["digest"] == "sha256:0b27"
                  and models[CODER]["profile"]["truth"] == "expected" and "measured" in big and "speed" in big)
        tight = c.catalog(131072)["hosts"][0]["models"]
        ctx.check("a large window turns the verdict", next(m for m in tight if m["model"] == BIG)["fit"]["fits"] is False)
        prof = c.profiles()["profiles"]
        ctx.check(f"profiles: digest, version, probe set, date, no evidence, got {prof}", len(prof) == 1
                  and prof[0]["digest"] == "sha256:0b27" and prof[0]["ollama_version"] == "0.40.6"
                  and prof[0]["probe_set"] == "battery-3" and prof[0]["probed_at"] and "evidence" not in prof[0])
        evs = c.events()["events"]
        ctx.check(f"events: the classified ones, got {[e['kind'] for e in evs]}",
                  {"prompt-trimmed", "load-result"} <= {e["kind"] for e in evs} and all(e["port"] == 11434 for e in evs))
        ctx.check("events?kind= filters", [e["kind"] for e in c.events(kind="load-result")["events"]] == ["load-result"])
        sim = c.simulate({"model": "qwen3:8b", "window": 32768})
        ctx.check(f"simulate: a model not pulled, from the library snapshot, got {sim}", sim["fits"] is True
                  and sim["installed"] is False and "library snapshot" in sim["row_source"] and sim["need_bytes"])
        big_sim = c.simulate({"size_gb": 60, "window": 32768})
        ctx.check(f"simulate: a size only, an estimate that does not fit, got {big_sim}", big_sim["fits"] is False
                  and "estimate" in big_sim["row_source"])
        kv = c.simulate({"model": BIG, "window": 49152, "kv": "q8_0"})
        f16 = c.simulate({"model": BIG, "window": 49152})
        ctx.check(f"simulate: kv q8_0 needs less than f16, got {kv['need_bytes']} {f16['need_bytes']}",
                  kv["kv"] == "q8_0" and kv["need_bytes"] < f16["need_bytes"])
        r = c.route({"model": CODER, "window": 32768})
        ctx.check(f"route: fits, not now (1.2 GB free), evicts the 27B, got {r}", r["fits"] is True and r["now"] is False
                  and r["evicts"] == [BIG] and r["warm"] is False and "once" in r["verdict"])
        w = c.route({"model": BIG, "window": 16384})
        ctx.check(f"route: loaded at 32k already: warm and now, got {w['verdict']!r}", w["warm"] and w["now"])
        t = c.route({"model": BIG, "window": 16384, "vision": True})
        ctx.check(f"route: its profile says no vision, got {t['verdict']!r}", t["capable"] is False and t["fits"] is False)


@test
def test_the_signature_check(ctx: Ctx):
    import http.client
    from halo_harness.fleet import protocol
    from halo_harness.ollama_steward.host_client import HostClient
    with HostRig(tls_on=False) as rig:
        rig.start()
        e = rig.pair()
        c = rig.client()
        conn = http.client.HTTPConnection("127.0.0.1", rig.svc.port, timeout=5)
        conn.request("GET", "/host/v1/card")
        ctx.check("unsigned: 401", conn.getresponse().status == 401)
        bad = HostClient(e, b"\x01" * 32, c.member)
        ctx.check(f"a wrong key: 401, got {_err(bad.card)}", _err(lambda: bad.card(fresh=True))[0] == 401)
        stranger = HostClient(e, c.key, "f" * 32)
        status, text = _err(lambda: stranger.card(fresh=True))
        ctx.check(f"an unknown peer: 403, got {status} {text!r}", status == 403 and "not a peer of this host" in text)
        headers = protocol.sign_headers(c.key, "GET", "/host/v1/ping", c.member)
        for want in (200, 401):
            conn = http.client.HTTPConnection("127.0.0.1", rig.svc.port, timeout=5)
            conn.request("GET", "/host/v1/ping", headers=headers)
            got = conn.getresponse().status
            ctx.check(f"the same signed request twice: {want} (replayed), got {got}", got == want)
        conn = http.client.HTTPConnection("127.0.0.1", rig.svc.port, timeout=5)
        conn.request("GET", "/fleet/v1/ping")
        ctx.check("only /host/v1 is served", conn.getresponse().status == 404)


@test
def test_the_tail_never_carries_a_prompt_body(ctx: Ctx):
    with HostRig() as rig:
        rig.start()
        rig.pair()
        got = rig.client().tail(400)
        text = "\n".join(got["lines"])
        ctx.check(f"the size lines stay, the body line is replaced by its size, got {got['lines']}",
                  "prompt=41104" in text and "the secret plan" not in text and f"({len(BODY):,} characters)" in text)
        rig.set_peer()
        (rig.home / "config.json").write_text('{"fleet": {"name": "pc-host"}, "host": {"tail_max": 2}}', encoding="utf-8")
        from halo_harness.fleet import identity
        identity.forget_cache()
        ctx.check("n is held to host.tail_max", rig.client().tail(400)["n"] == 2)


@test
def test_control_manage_admin_answer_403_naming_the_grant(ctx: Ctx):
    with HostRig() as rig:  # 3.3.7.0 R2: the ops behind each prefix (tests.test_host_ops); a view peer is refused
        rig.start()
        rig.pair()
        c = rig.client()
        for grant, op in (("control", "warm"), ("manage", "pull"), ("admin", "raw")):
            status, text = _err(lambda: c._call("POST", f"{grant}/{op}", {"v": 1, "params": {"model": BIG}}))
            ctx.check(f"{grant}: 403 naming the grant and the command that gives it, got {status} {text!r}", status == 403
                      and f"`{grant}` grant" in text and f"halo host grant bob@peer {grant}" in text
                      and len(text.splitlines()) == 1)


@test
def test_one_audit_line_per_request(ctx: Ctx):
    from halo_harness.host.state import read_audit
    with HostRig() as rig:
        rig.start()
        rig.pair()
        c = rig.client()
        before = len(read_audit(rig.home))
        c.card(fresh=True)
        _err(lambda: c._call("POST", "admin/run", {"v": 1}))
        rig.audited(before + 2)  # the line lands after the reply: wait for the server thread
        rows = read_audit(rig.home)[before:]
        ctx.check(f"two requests, two lines {{at, peer, path, ok, ms}}, got {rows}", len(rows) == 2
                  and set(rows[0]) == {"at", "peer", "path", "ok", "ms"} and rows[0]["path"] == "/host/v1/card"
                  and rows[0]["ok"] is True and rows[1]["ok"] is False and rows[0]["peer"] == "bob@peer")


@test
def test_the_live_stream(ctx: Ctx):
    from halo_harness.fleet import protocol
    from halo_harness.host import stream as H  # 3.3.7.0 R2: the stream moved out of host/http.py
    from halo_harness.ollama_steward.server_events import record_events
    from tests.helpers.steward_seed import event
    saved = (H.STREAM_EVENT_S, protocol.PING_S)
    H.STREAM_EVENT_S, protocol.PING_S = 0.2, 0.5
    try:
        with HostRig() as rig:
            rig.start()
            rig.pair()
            s = rig.client().stream()
            frames: list = []
            end = time.monotonic() + 3
            while time.monotonic() < end and not frames:
                frames += s.read(0.25)
            ctx.check(f"a card frame first, got {[f.get('type') for f in frames]}", frames and frames[0]["type"] == "card")
            record_events(rig.home, [event("cpu-spill", model=BIG, ago=0)], host="pc")
            end = time.monotonic() + 5
            while time.monotonic() < end and not any(f.get("type") == "event" for f in frames):
                frames += s.read(0.25)
            got = [f["data"]["kind"] for f in frames if f.get("type") == "event"]
            ctx.check(f"an event frame for the new event, got {got}", "cpu-spill" in got)
            raw = s._buf
            s.sock.settimeout(1.0)
            time.sleep(0.7)
            raw += s.sock.recv(65536)
            ctx.check("the ping comment", b": ping" in raw)
            s.close()
    finally:
        H.STREAM_EVENT_S, protocol.PING_S = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
