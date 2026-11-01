"""tests.test_rpc_probe -- Halo 3.3.8.0 R1 deliverable 4: the RPC-port probe (providers/rpc_probe.py) and the scan
(local_pool/scan.py), with a plain TCP listener on 127.0.0.1:0 standing in for rpc-server; the network layer of the
sweep is faked (SEAMS["sweep"], SEAMS["own"]), so no real network is ever swept and nothing leaves 127.0.0.1:

1. a listener answers: alive, an RTT in ms, the line; a closed port: no answer, one line;
2. past 10 ms a connect is "Wi-Fi?" (the connect's time faked);
3. the test flag asks only 127.0.0.1 (no name lookup, no connect beyond loopback); offline mode refuses a public name
   with the offline line before any socket;
4. the sweep: off in tests without its seam (one note); with it, this machine's /24 and the RPC port, each responder
   probed; a bad pool.scan_subnets entry is one note; offline mode turns it off;
5. `scan`: the members probed too, scan.json written, a responder that is a member says so, the member rows' RTT word.
Run: python -m tests.test_rpc_probe
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_rig import PoolHome, free_port, rpc_listener  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_a_listener_answers_a_closed_port_does_not(ctx: Ctx):
    from halo_harness.providers.rpc_probe import probe
    with PoolHome(), rpc_listener() as port:
        r = probe("127.0.0.1", port)
        ctx.check(f"alive, an RTT under 10 ms, the line, got {r}", r["alive"] and isinstance(r["rtt_ms"], float)
                  and 0 <= r["rtt_ms"] < 10 and not r["wifi_suspect"] and r["line"].startswith(f"127.0.0.1:{port} answers in "))
        closed = free_port()
        r = probe("127.0.0.1", closed, tries=1, timeout=0.5)
        ctx.check(f"a closed port: no answer, one line, got {r}", not r["alive"] and r["rtt_ms"] is None
                  and r["line"].startswith(f"127.0.0.1:{closed}: no answer (") and r["error"])


@test
def test_past_10_ms_is_wifi_suspect(ctx: Ctx):
    from halo_harness.providers import rpc_probe as P
    saved = P._connect_ms
    P._connect_ms = lambda addr, family, timeout, exact=False: (True, 12.4, "")
    try:
        with PoolHome():
            r = P.probe("127.0.0.1", 50052)
    finally:
        P._connect_ms = saved
    ctx.check(f"12.4 ms: Wi-Fi?, got {r}", r["alive"] and r["rtt_ms"] == 12.4 and r["wifi_suspect"]
              and r["line"] == "127.0.0.1:50052 answers in 12 ms -- Wi-Fi?")


@test
def test_the_test_flag_and_offline_mode(ctx: Ctx):
    from halo_harness.providers import rpc_probe as P
    with PoolHome():
        r = P.probe("worker1.local", 50052)
        ctx.check(f"the test flag: a LAN name is not asked, got {r}", not r["alive"] and "not asked in tests" in r["error"])
        os.environ["HALO_OFFLINE"] = "1"
        try:
            r = P.probe("example.com", 50052)
            ctx.check(f"offline: a public name refused with the offline line, got {r['error']!r}",
                      not r["alive"] and "offline" in r["error"].lower())
            got = P.sweep(50052)
            P.SEAMS["sweep"] = lambda networks, ports, deadline: []
            got2 = P.sweep(50052)
        finally:
            os.environ.pop("HALO_OFFLINE", None)
        ctx.check(f"offline: the sweep is off, got {got['notes']} {got2['notes']}", got2["notes"] == [P.OFFLINE_NOTE]
                  and got["notes"] == [P.TEST_NOTE])


@test
def test_the_sweep_over_a_faked_network(ctx: Ctx):
    from halo_harness.providers import rpc_probe as P
    with PoolHome(), rpc_listener() as port:
        got = P.sweep(port)
        ctx.check(f"no seam in tests: off, one note, got {got}", got["candidates"] == [] and got["notes"] == [P.TEST_NOTE])
        asked = []

        def fake(networks, ports, deadline):
            asked.append(([str(n) for n in networks], tuple(ports)))
            return [("127.0.0.1", port)]
        P.SEAMS.update(sweep=fake, own=lambda: "192.0.2.5")
        got = P.sweep(port, subnets=["not-a-cidr"])
        ctx.check(f"this machine's /24 on the RPC port, got {asked}", asked == [(["192.0.2.0/24"], (port,))])
        ctx.check(f"the responder probed, got {got['candidates']}", len(got["candidates"]) == 1 and got["candidates"][0]["alive"]
                  and got["networks"] == ["192.0.2.0/24"])
        ctx.check(f"a bad subnet: one note under its own key, got {got['notes']}",
                  got["notes"] == ["pool.scan_subnets: 'not-a-cidr' is not a CIDR -- skipped"])


@test
def test_scan_probes_the_members_and_keeps_the_answer(ctx: Ctx):
    from halo_harness.local_pool import members as M
    from halo_harness.local_pool.budget import budgets
    from halo_harness.local_pool.scan import last, scan
    from halo_harness.providers import rpc_probe as P
    with PoolHome() as h, rpc_listener() as port:
        M.add("w1", f"127.0.0.1:{port}", vram_gb=24, state_dir=h.state)
        M.add("w2", "worker2.local", vram_gb=24, state_dir=h.state)
        P.SEAMS.update(sweep=lambda networks, ports, deadline: [("127.0.0.1", port)], own=lambda: "192.0.2.5")
        got = scan(port=port, state_dir=h.state)
        ctx.check(f"the responder is the member w1, got {got['candidates']}", got["candidates"][0]["member"] == "w1")
        mem = {m["name"]: m for m in got["members"]}
        ctx.check(f"w1 answers, w2 is not asked in tests, got {mem}", mem["w1"]["alive"] and not mem["w2"]["alive"])
        ctx.check(f"the line, got {got['line']!r}", got["line"] == f"1 rpc-server port answered on :{port} across "
                  "192.0.2.0/24; 1 of 2 members answer")
        ctx.check("scan.json keeps it", last(h.state).get("line") == got["line"])
        rows = {r["name"]: r for r in budgets(state_dir=h.state)}
        ctx.check(f"the member rows carry the RTT word, got {rows['w1']['rtt_word']!r} {rows['w2']['rtt_word']!r}",
                  rows["w1"]["rtt_word"].endswith("ms") and rows["w2"]["rtt_word"].startswith(f"no answer on :50052"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
