"""tests.test_governor_gate -- Halo 2.0.5 round 4: THE GATE (the owner's
own acceptance test, from the round brief): six fake PROCESSES against a
mock upstream returning a 429 storm with Retry-After, all sharing ONE
governor state dir -- the rate is cut, the cooldown is set, the
priority-0 waiter still completes, and the failover lands on the
fallback host. Main makes TWO governed calls (the workers one each):
as the priority-0 front waiter it is granted every permit first, so
its first call rides into the storm; it then stands down until the
parent drops the go file (the workers have exited, the storm is fully
burnt) and its second call completes past the storm.

The storm server is a stdlib http.server: the first STORM_LEN POSTs get
429 + `Retry-After: 0`, everything after gets a 200. Each subprocess
drives the REAL choke point (`providers.http.governed_upstream`) with
its own role (process 0 runs as role "main", priority 0) against it,
sharing the parent's GOVERNOR_STATE_DIR so all six pace through one
bucket. Bounded: small cooldown_base/max_wait via a per-subprocess
config, and a hard 90 s communicate deadline -- on Windows every
governor pass pays a `tasklist` spawn per waiter (pid_alive), so the
wall time is host-bound; on Linux it is a few seconds.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

REPO_DIR = Path(__file__).resolve().parent.parent
STORM_LEN = 10

_DRIVER = r"""
import json, os, sys, time, http.client
sys.path.insert(0, os.environ["PYTHONPATH"])
from halo_harness.providers.http import governed_upstream

host, port, role, agent = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]

class R:
    def __init__(self, status, headers):
        self.status = status
        self.headers = headers
        self.resp = None
        self.conn = None
        self.body_bytes = None

def do_call():
    conn = http.client.HTTPConnection(host, port, timeout=10)
    conn.request("POST", "/api/v1/chat/completions", body=json.dumps({"model": "gate", "m": agent}),
                 headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    hdrs = {k.lower(): v for k, v in resp.getheaders()}
    status = resp.status
    resp.read()
    conn.close()
    return R(status, hdrs)

out = []
# The governor grants permits to the FRONT of the waiter queue first,
# and role "main" is priority 0 -- while main has an acquire pending,
# no worker is ever granted a permit. Main therefore rides its first
# call INTO the storm (max_retries 1: two 429s), then stands down (no
# acquire pending) until the parent drops the go file -- which it
# does once the five workers have EXITED, i.e. their ten attempts
# have burnt the whole storm -- and its SECOND call rides the
# fail-open half-open probe past the storm for a real 200. Bounded
# either way: the go poll gives up after 45 s.
calls = 2 if role == "main" else 1
for i in range(calls):
    if i:
        go = os.environ.get("GATE_GO_FILE", "")
        give_up = time.time() + 45.0
        while go and not os.path.exists(go) and time.time() < give_up:
            time.sleep(0.25)
    try:
        r = governed_upstream(host, do_call, {"agent": agent, "role": role})
        out.append(r.status)
    except Exception as e:
        out.append(f"ERR:{type(e).__name__}")
print(json.dumps(out))
"""


class _StormHandler(BaseHTTPRequestHandler):
    """429 + Retry-After: 0 for the first STORM_LEN POSTs, then 200."""
    served = {"n": 0}

    def do_POST(self):  # noqa: N802 (http.server's own casing)
        _StormHandler.served["n"] += 1
        n = _StormHandler.served["n"]
        body = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
        if n <= STORM_LEN:
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Retry-After", "0")
            self.send_header("Content-Length", "52")
            self.end_headers()
            self.wfile.write(b'{"error": {"message": "storm", "type": "rate_limit"}}')
        else:
            payload = json.dumps({"ok": True, "n": n}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def log_message(self, *a):
        pass


def _start_server() -> "tuple[ThreadingHTTPServer, int]":
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _StormHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, srv.server_address[1]


@test
def test_the_gate_six_processes_one_bucket(ctx: Ctx):
    from halo_harness.providers import governor, governor_state
    governor_state.reset_degraded_for_tests()
    gov_dir = Path(tempfile.mkdtemp(prefix="halo-gov-gate-"))
    old_gov = os.environ.get("GOVERNOR_STATE_DIR")
    old_halo = os.environ.get("HALO_GOVERNOR")
    os.environ["GOVERNOR_STATE_DIR"] = str(gov_dir)
    os.environ["HALO_GOVERNOR"] = "1"
    srv, port = _start_server()
    # the go file: dropped once the five workers have exited (their ten
    # attempts have burnt the whole storm), green-lighting main's second
    # call. Main is the priority-0 front waiter -- queued, it would be
    # granted every permit ahead of the workers and ride into the storm
    # forever, so it stands down until the storm is actually over.
    go_file = Path(tempfile.mkdtemp(prefix="halo-gov-gate-go-")) / "go"
    procs = []
    try:
        # six fake processes: process 0 runs as the main session (priority
        # 0); the rest are workers. All share ONE governor state dir.
        for i in range(6):
            role = "main" if i == 0 else "coder"
            env = {**os.environ,
                   "PYTHONPATH": str(REPO_DIR),
                   "BRIDGE_TEST_HOME": str(Path(tempfile.mkdtemp(prefix=f"halo-gate-p{i}-"))),
                   "GOVERNOR_STATE_DIR": str(gov_dir),
                   "HALO_GOVERNOR": "1",
                   "GATE_GO_FILE": str(go_file)}
            # per-process tuning: a short cooldown ladder + a short
            # fail-open horizon keeps the gate bounded (the shared err
            # counter climbs across six processes, so cooldown_base 0.2
            # with the 2^6 ladder cap tops out ~12.8 s) while still
            # exercising every path: pacing, priority, the in-flight
            # cap, the half-open probe, the retry ladder, recovery.
            # (config.json lives at <test home>/.halo/config.json --
            # bridge_home() nests .halo under BRIDGE_TEST_HOME.)
            cfg = {"governor": {"cooldown_base": 0.2, "backoff_mult": 0.5, "rate_rps": 4.0,
                                "burst": 4, "max_inflight": 3, "max_retries": 1,
                                "ramp_after": 2, "ramp_inc": 0.5, "max_wait": 2.5}}
            cfg_dir = Path(env["BRIDGE_TEST_HOME"]) / ".halo"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
            procs.append((i, role, subprocess.Popen(
                [sys.executable, "-c", _DRIVER, "127.0.0.1", str(port), role, f"agent-{i}"],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, cwd=str(REPO_DIR))))
        results = {}
        deadline = time.time() + 90
        # reap the five WORKERS first: when they have all exited, their
        # ten attempts (plus main's two) have served the whole storm --
        # then green-light main's second call past it.
        for i, role, p in procs[1:]:
            out, err = p.communicate(timeout=max(5, deadline - time.time()))
            results[i] = {"role": role, "rc": p.returncode, "out": out.strip(), "err": err.strip()[-300:]}
        go_file.write_text("go", encoding="utf-8")
        i, role, p = procs[0]
        out, err = p.communicate(timeout=max(5, deadline - time.time()))
        results[i] = {"role": role, "rc": p.returncode, "out": out.strip(), "err": err.strip()[-300:]}
        for i, r in results.items():
            ctx.check(f"process {i} (role {r['role']}) exited 0 (err: {r['err']!r})", r["rc"] == 0)
            try:
                r["codes"] = json.loads(r["out"])
            except ValueError:
                r["codes"] = None
                ctx.check(f"process {i} printed its result JSON, got {r['out']!r}", False)
        # the priority-0 waiter still completes: the main-role process saw
        # a 200 through the storm (its fail-open probe after max_wait).
        main_codes = results.get(0, {}).get("codes") or []
        ctx.check(f"the priority-0 (main) process completed a call past the storm, got {main_codes}",
                  200 in main_codes)
        # the storm actually stormed and then cleared
        served = _StormHandler.served["n"]
        ctx.check(f"the mock served a real storm then recovered ({served} requests)", served > STORM_LEN)
        # the shared bucket: rate cut below its ceiling
        st = governor.inspect("host:127.0.0.1")
        ctx.check("the shared bucket exists", st is not None)
        if st:
            ctx.check(f"rate cut below the ceiling, got {st['rate']}/{st['rate_ceiling']}",
                      st["rate"] < st["rate_ceiling"])
        # the log recorded the storm: overload verdicts from several agents
        calls = governor.recent_calls("host:127.0.0.1", limit=100)
        overloads = [c for c in calls if c.get("ok") is False]
        agents = {c.get("agent") for c in overloads}
        ctx.check(f"the bucket's log shows the 429 storm from several agents, got {sorted(a for a in agents if a)}",
                  len(overloads) >= 4 and len(agents) >= 3)
        ctx.check("the main-role calls are tagged priority 0 in the log",
                  any(c.get("role") == "main" for c in calls))

        # ---- failover: trip THIS host's circuit, pivot to a healthy one --
        p2 = {"rate_rps": 4.0, "burst": 4, "max_inflight": 2, "max_retries": 1,
              "cooldown_base": 0.4, "backoff_mult": 0.5, "ramp_after": 2, "ramp_inc": 0.5}
        for _ in range(3):
            h = governor.acquire("host:127.0.0.1", p2, agent="trip", role="worker", max_wait=6)
            governor.report(h, ok=False, status=429, retry_after=60, params=p2)
        from halo_harness.providers import gateway_routing
        # route "a" resolves to the SAME host the drivers hammered: the
        # Governor buckets by bare hostname (call_openai_chat keys on
        # parsed.hostname, portless), so the base_url here must be
        # portless too -- a port in it would netloc-match a bucket key
        # no driver ever wrote ("host:127.0.0.1:<port>") and the pivot
        # would silently never fire. The route is only used for host
        # resolution; nothing dials it.
        routes = {"a": {"provider": "openrouter", "base_url": "http://127.0.0.1/api/v1"},
                  "b": {"provider": "openai", "base_url": "http://localhost:9/api/v1"}}
        pick, health, pivoted = gateway_routing.choose(["or:stormed/model", "oai:healthy/model"], routes=routes)
        ctx.check(f"failover pivots off the stormed host, got {pick} ({health}, pivoted={pivoted})",
                  pick == "oai:healthy/model" and pivoted is True and health != "open")
        ctx.check("the storm host's health classifies as open",
                  governor.health("host:127.0.0.1") == "open")
    finally:
        srv.shutdown()
        srv.server_close()
        if old_gov is None:
            os.environ.pop("GOVERNOR_STATE_DIR", None)
        else:
            os.environ["GOVERNOR_STATE_DIR"] = old_gov
        if old_halo is not None:
            os.environ["HALO_GOVERNOR"] = old_halo
        else:
            os.environ.pop("HALO_GOVERNOR", None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
