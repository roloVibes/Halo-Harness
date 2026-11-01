"""tests.test_host_servers -- Halo 3.3.8.0 R4 deliverables 6 and 7: peers see host-served local servers
(host/state.served_rows + server_rows, the join's and the announce's `servers`, fleet/hub_hosts, the hub's server
events: fleet/control_probes.read_events) and a server's change lands through the host
(ollama_steward/host_land.via_host -> the host's set_num_ctx on a Served server), verified in tok/s from the server
log's `timing` events (ollama_steward/verify_timing.py, host/verify.py). Over tests/helpers/host_act_rig.PeerRig: the
host is a real host/service.HostService on 127.0.0.1:0, its machine's llama-server a Server row with a log written by
hand (no llama-server runs); every address a 192.0.2.x placeholder or 127.0.0.1.
Run: python -m tests.test_host_servers
"""
from __future__ import annotations

import io
import shutil
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_act_rig import PeerRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MODEL = "qwen3-8b"
LOG = ("--- halo starts: /opt/llama/llama-server -m /models/Qwen3-8B-Q4_K_M.gguf --alias qwen3-8b --port 8095 -c 16384\n"
       "load_tensors: offloaded 37/37 layers to GPU\n"
       "slot         init: id  0 | task -1 | new slot n_ctx_slot = 16384\n"
       "main: model loaded\n"
       "srv  log_server_r: request: POST /v1/chat/completions 127.0.0.1 200\n")


class Rig:
    """A PeerRig whose host serves one llama-server (`coder-srv` on 127.0.0.1:8095, its log in a scratch folder) and
    whose peer names it `coder` at the host's placeholder address."""

    def __enter__(self):
        from halo_harness.ollama_steward.servers_hf import Server
        self.tmp = Path(tempfile.mkdtemp(prefix="hd_srv-"))
        self.log = self.tmp / "coder-srv.log"
        self.log.write_text(LOG, encoding="utf-8")
        self.srv = Server(name="coder-srv", url="http://127.0.0.1:8095/v1", runtime="llama-server", log=str(self.log))
        self.peer = PeerRig(servers=[self.srv]).__enter__()
        self.peer.rig.set_peer(**{"huggingface.local_servers": [
            {"name": "coder", "url": "http://192.0.2.10:8095/v1", "runtime": "llama-server"}]})
        from halo_harness.ollama_steward import servers_hf
        getattr(servers_hf, "_CACHE", {}).clear()
        return self

    def __exit__(self, *exc):
        try:
            self.peer.__exit__(*exc)
        finally:
            shutil.rmtree(self.tmp, ignore_errors=True)


def _timing(home, tok_s: float, n: int, at: float) -> None:
    from halo_harness.ollama_steward.server_events import record_events
    from halo_harness.ollama_steward.server_rules import event
    record_events(home, [event("timing", f"a reply at {tok_s} tok/s", "eval time = ...", at=at + i * 0.01, model=MODEL,
                               eval_tok_s=tok_s, eval_n=200, eval_ms=200 / tok_s * 1000) for i in range(n)],
                  host="coder-srv")


@test
def test_the_join_the_announce_and_the_hub_list_the_servers(ctx: Ctx):
    from halo_harness.fleet import hub_hosts
    from halo_harness.host import state as S
    with Rig() as r:
        want = {"name": "coder-srv", "port": 8095, "addr": "192.0.2.10", "kind": "server", "runtime": "llama-server",
                "pool": False}
        ctx.check(f"the join's `servers`: the host's local servers, got {r.peer.entry.get('servers')}",
                  r.peer.entry.get("servers") == [want] and [x["name"] for x in r.peer.entry["serves"]] == ["pc"])
        rows = S.served_rows("192.0.2.10", [r.peer.host], [r.srv])
        ctx.check(f"served_rows lists a host's local servers after its Ollama rows, got {rows}", rows[0]["name"] == "pc"
                  and rows[1] == want)
        home = Path(r.tmp) / "hub"
        got = hub_hosts.record(home, "h1", "pc-member", "192.0.2.10", {"host": True, "port": 7431, "serves": rows[:1],
                                                                       "servers": S.server_rows("192.0.2.10", [r.srv])})
        ctx.check(f"the hub keeps the announced servers, got {got['servers']}", got["servers"] == [
            {"name": "coder-srv", "port": 8095, "addr": "192.0.2.10", "runtime": "llama-server", "pool": False}]
                  and hub_hosts.listing(home)[0]["servers"] == got["servers"])


@test
def test_a_peer_reads_the_servers_log_through_the_host(ctx: Ctx):
    from halo_harness.local_log_cli import cmd_log
    with Rig():
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_log(["coder", "-n", "10"])
        out = buf.getvalue()
        ctx.check(f"halo local log coder reads through the host, got {rc} {out[:300]!r}", rc == 0
                  and "via host 127.0.0.1" in out and "new slot n_ctx_slot = 16384" in out)


@test
def test_a_servers_change_lands_through_the_host_and_is_verified_in_tok_s(ctx: Ctx):
    from halo_harness.host import verify
    from halo_harness.host.state import read_audit
    from halo_harness.ollama_steward import changes
    from halo_harness.ollama_steward.host_land import via_host
    from halo_harness.ollama_steward.ledger import append_lines
    from tests.helpers.steward_seed import line
    with Rig() as r:
        home = r.peer.home
        _timing(home, 40.0, 3, time.time() - 30)
        f = {"id": "window-small-c0de", "host": "coder", "model": MODEL, "key": f"coder|{MODEL}", "rule": "window-small",
             "finding": "qwen3-8b on coder (llama-server): the server's window 16,384 per slot is too small"}
        ch = {"field": "num_ctx", "from": None, "to": 16384, "why": "the server holds 16,384 per slot"}
        row = via_host(r.peer.peer, f, ch, mode_name="auto")
        ctx.check(f"landed through the host, got {row and row.get('say')!r}", row is not None and row["landed"]
                  and row["kind"] == "host-apply" and row["via"] == "host")
        n = r.peer.rig.audited(1)
        audit = [a for a in read_audit(home, limit=1000) if a.get("op") == "set_num_ctx"]
        ctx.check(f"the host's audit says so: set_num_ctx on coder-srv, landed, got {n} {audit[-1:]}", audit
                  and (audit[-1].get("params") or {}).get("host") == "coder-srv" and audit[-1].get("landed") is True)
        rows = [x for x in changes.read(home) if x.get("key") == f"coder-srv|{MODEL}"]
        fix = verify.last_on(home, f"coder-srv|{MODEL}") or {}
        ctx.check(f"the host's change row and its verify row (before: 40 tok/s from the log), got {fix.get('before')}",
                  rows and fix.get("verdict") == "verifying" and (fix.get("before") or {}).get("tok_s") == 40.0
                  and (fix["before"] or {}).get("tok_s_from") == "the server log's timing")
        _timing(home, 20.0, 5, time.time() + 1)
        append_lines(home, [line(host={"name": "coder-srv"}, model=MODEL, dialect="openai", eval_tok_s=None,
                                 ago=-2 - i * 0.01) for i in range(5)])
        closed = verify.tick(r.peer.svc, now=time.time() + 5)
        ctx.check(f"the verdict in tok/s from the server log, reverted, got {[c.get('line') for c in closed]}",
                  closed and closed[0]["verdict"] == "reverted"
                  and "40 -> 20 tok/s (the server log's timing)" in closed[0]["line"])


@test
def test_the_hub_gets_the_servers_events(ctx: Ctx):
    from halo_harness.fleet import control_probes
    from halo_harness.ollama_steward import server_log_hf, servers_hf
    from tests.helpers import pool_seed as P
    from tests.helpers.pool_rig import PoolHome
    with PoolHome() as h:
        P.seed(h.state, P.LOAD() + P.DEGRADED)
        s = next(x for x in servers_hf.roster(h.state) if x.name == "pool")
        server_log_hf.scan(h.state, s, from_start=True)
        control_probes._SENT.clear()
        got = control_probes.read_events(h.state)
        kinds = sorted({e["kind"] for e in got if e.get("host") == "pool"})
        ctx.check(f"the member pushes its local servers' events (the pool's RPC lines), got {kinds}",
                  "rpc-lost" in kinds and "load-result" in kinds and all(e.get("server") is True and e.get("port") == 8090
                                                                         for e in got if e.get("host") == "pool"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
