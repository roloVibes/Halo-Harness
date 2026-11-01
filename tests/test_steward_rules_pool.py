"""tests.test_steward_rules_pool -- Halo 3.3.8.0 R4 deliverable 2: the steward's pool findings
(ollama_steward/rules_pool.py; server_context_hf's devices; server_rules_hf's `rpc-lost`) from the controller's log
fixtures (tests/helpers/pool_seed.py: written from llama.cpp's source wording, no live log), read by R2's server-log
reader under the server name `pool`:

1. the load block: one `layers` pair per device (estimated from the buffers; counted from the assigned lines when
   they are there), the per-device buffers on the load-result; a healthy pool has no pool finding;
2. pool-spill: worker2 holds less than its split and 4 layers stayed on the CPU -- one line, keyed pool|<model>, the
   generic cpu-spill of the group dropped;
3. pool-degraded: "degraded (worker2 down)", the same word and the same lines as local_pool/degrade;
4. pool-rtt: replies far under the reference, more than the round trips explain; the link the OS read speaks first;
5. `halo ollama steward findings` prints them; the host's findings (host/findings.host_findings) carry them.
Run: python -m tests.test_steward_rules_pool
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import pool_seed as P  # noqa: E402
from tests.helpers.pool_rig import PoolHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
QWEN = "qwen3-next-80b-a3b-q4km"


def _scan(state) -> list:
    from halo_harness.ollama_steward import server_log_hf, servers_hf
    servers_hf._CACHE.clear() if hasattr(servers_hf, "_CACHE") else None
    s = next((x for x in servers_hf.roster(state) if x.name == "pool"), None)
    assert s is not None, [x.name for x in servers_hf.roster(state)]
    return server_log_hf.scan(state, s, from_start=True)[0]


def _pool_findings(state) -> list:
    from halo_harness.ollama_steward.rules import findings
    return [f for f in findings(state) if f["host"] == "pool"]


@test
def test_the_load_block_and_a_healthy_pool(ctx: Ctx):
    with PoolHome() as h:
        P.seed(h.state, P.LOAD() + P.HEALTHY_TIMING)
        P.card(h.state, 11.2)
        evs = _scan(h.state)
        ld = next(e for e in evs if e["kind"] == "load-result")["data"]
        ctx.check(f"one layers pair per device, estimated from the buffers, got {ld.get('device_layers')}",
                  ld["device_layers"] == [["RPC[192.0.2.11:50052]", 21], ["RPC[192.0.2.12:50052]", 21], ["CUDA0", 8]]
                  and ld["layers_from"] == "estimated from the buffers" and (ld["offloaded"], ld["layers"]) == (49, 49))
        devs = {d["device"]: d for d in ld["devices"]}
        ctx.check(f"the per-device buffers, got {devs}", devs["RPC[192.0.2.12:50052]"]["model_mib"] == 19783.12
                  and devs["RPC[192.0.2.12:50052]"]["kv_mib"] == 1344.0 and devs["CUDA0"]["free_mib"] == 11010
                  and devs["CPU_Mapped"]["model_mib"] == 315.3)
        ctx.check(f"a healthy pool: no pool finding, got {_pool_findings(h.state)}", _pool_findings(h.state) == [])
    with PoolHome() as h:
        lines = P.LOAD().replace("load_tensors: offloaded 49/49", "\n".join(
            [f"load_tensors: layer {i:3d} assigned to device {'RPC[192.0.2.11:50052]' if i < 22 else 'CUDA0'}, is_swa = 0"
             for i in range(30)]) + "\nload_tensors: offloaded 49/49")
        P.seed(h.state, lines)
        ld = next(e for e in _scan(h.state) if e["kind"] == "load-result")["data"]
        ctx.check(f"counted from the assigned lines, got {ld['device_layers']}", ld["device_layers"] ==
                  [["RPC[192.0.2.11:50052]", 22], ["CUDA0", 8]] and ld["layers_from"] == "the assigned lines")


@test
def test_pool_spill(ctx: Ctx):
    with PoolHome() as h:
        P.seed(h.state, P.LOAD(mib=(19783.12, 9000.0, 7536.43), offloaded="45/49", cpu_mib=4200.0))
        _scan(h.state)
        got = _pool_findings(h.state)
        ctx.check(f"one pool-spill, the generic cpu-spill dropped, got {[f['rule'] for f in got]}",
                  [f["rule"] for f in got] == ["pool-spill"])
        f = got[0]
        ctx.check(f"keyed pool|<model>, worker2 and the CPU layers in one line, got {f['finding']!r}",
                  f["key"] == f"pool|{QWEN}" and f["server"] == "pool" and f["pool"] is True and "\n" not in f["finding"]
                  and "worker2 holds 8.8 GB of the weights, 25% against its 0.42 split" in f["finding"]
                  and "4 of 49 layers stayed on the controller's CPU (offloaded 45/49)" in f["finding"]
                  and "worker1" not in f["finding"].split(" -- ")[0])


@test
def test_pool_degraded_agrees_with_the_status(ctx: Ctx):
    from halo_harness.local_pool.degrade import rpc_failures
    with PoolHome() as h:
        log = P.seed(h.state, P.LOAD() + P.HEALTHY_TIMING + P.DEGRADED)
        evs = _scan(h.state)
        lost = [e for e in evs if e["kind"] == "rpc-lost"]
        ctx.check(f"two rpc-lost events (the connect, the abort), got {[e['say'] for e in lost]}", len(lost) == 2
                  and lost[0]["data"]["addr"] == "192.0.2.12:50052" and lost[1]["data"]["death"] is True)
        got = [f for f in _pool_findings(h.state) if f["rule"] == "pool-degraded"]
        ctx.check(f"pool-degraded: degraded (worker2 down), failed once, never retried, got {got}", len(got) == 1
                  and got[0]["severity"] == "error" and "on the pool: degraded (worker2 down) -- an RPC backend was lost "
                  "mid-generation (2 lines" in got[0]["finding"] and "the request failed once and is not retried"
                  in got[0]["finding"])
        text = log.read_text(encoding="utf-8").splitlines()
        ctx.check(f"local_pool/degrade reads exactly those lines, got {rpc_failures(text)}",
                  rpc_failures(text) == [e["evidence"].strip() for e in lost])


@test
def test_pool_rtt_and_where_they_show(ctx: Ctx):
    from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
    with PoolHome() as h:
        P.seed(h.state, P.LOAD() + P.SLOW)
        _scan(h.state)
        ctx.check("no pool speed card: no pool-rtt (nothing says how fast this pool should be)",
                  not [f for f in _pool_findings(h.state) if f["rule"] == "pool-rtt"])
        P.card(h.state, 11.2)
        got = [f for f in _pool_findings(h.state) if f["rule"] == "pool-rtt"]
        ctx.check(f"pool-rtt from the probe's RTT, got {got and got[0]['finding']!r}", len(got) == 1
                  and "replies at 5.0 tok/s (200 ms a token) against 11.2 (89 ms, its own bench card)"
                  in got[0]["finding"] and "worker1 0.4 ms RTT (the probe)" in got[0]["finding"]
                  and "slower than its link explains" in got[0]["finding"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_ollama_steward(["findings"])
        ctx.check(f"halo ollama steward findings prints it, got {buf.getvalue()[:300]!r}",
                  "pool qwen3-next-80b-a3b-q4km: " in buf.getvalue() and "replies at 5.0 tok/s" in buf.getvalue())
        from halo_harness.host.findings import host_findings
        from halo_harness.ollama_steward.servers_hf import roster
        view = SimpleNamespace(home=h.state, hosts=lambda: [SimpleNamespace(name="pc", url="http://127.0.0.1:9")],
                               host_card=lambda _h: {}, host_catalog=lambda _h: [],
                               servers=lambda: [s for s in roster(h.state) if s.name == "pool"])
        hf = [f for f in host_findings(view) if f["host"] == "pool"]
        ctx.check(f"the host's findings carry it with its port, got {[(f['rule'], f['port']) for f in hf]}",
                  [(f["rule"], f["port"]) for f in hf] == [("pool-rtt", 8090)])
    with PoolHome() as h:
        P.seed(h.state, P.LOAD() + P.SLOW, link="2.5 GbE")
        P.card(h.state, 11.2)
        _scan(h.state)
        got = [f for f in _pool_findings(h.state) if f["rule"] == "pool-rtt"]
        ctx.check(f"the link the OS read speaks first, got {got and got[0]['finding']!r}", len(got) == 1
                  and "worker1 2.5 GbE (the OS)" in got[0]["finding"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
