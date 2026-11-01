"""tests.test_pool_act_api -- Halo 3.3.8.0 R3 deliverable 10, the API half: Local -> Pool's acting routes
(studio/pool_act_api.py through studio/pool_api.dispatch_pool), over tests/helpers/pool_run_rig.RunRig; no model call,
never a request beyond 127.0.0.1:

1. GET local/pool/run: stopped; GET local/pool/preflight?model=: the checks, green, the cli; an unknown model is 404;
   GET local/pool/members no longer carries a "not yet" line;
2. POST local/pool/warm: 202 at once (busy), the run then says how it went -- running, the members' claims and
   leases, the Warm's lines; a second Warm inside 10 min is a 409 with the minutes; a pool this Studio did not warm is
   adopted (its claims renewed by this process);
3. POST local/pool/stop: the lines (stopped, released, the pivot back); POST local/pool/rpc: a member's rpc-server.
Run: python -m tests.test_pool_act_api
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_run_rig import QWEN, RunRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _wait_run(rig, done, timeout: float = 60.0) -> dict:
    end = time.monotonic() + timeout
    while True:
        _st, got = rig.studio("GET", "local/pool/run")
        if done(got) or time.monotonic() > end:
            return got
        time.sleep(0.2)


@test
def test_run_and_preflight(ctx: Ctx):
    with RunRig() as rig:
        st, got = rig.studio("GET", "local/pool/run")
        ctx.check(f"stopped, got {st} {got.get('line')!r}", st == 200 and got["state"] == "stopped"
                  and got["cli"] == "halo pool status")
        st, pf = rig.studio("GET", "local/pool/preflight", query={"model": QWEN})
        ctx.check(f"the preflight: green, eight checks, the cli, got {st} {pf.get('line')!r}", st == 200 and pf["ok"]
                  and len(pf["checks"]) == 8 and pf["cli"] == f"halo pool preflight {QWEN}" and "rows" not in pf)
        st, pf = rig.studio("GET", "local/pool/preflight", query={"model": QWEN, "allow_wifi": "1"})
        ctx.check(f"the Wi-Fi switch reaches it, got {pf.get('allow_wifi')} {pf.get('cli')}", st == 200
                  and pf["allow_wifi"] is True and pf["cli"].endswith("--allow-wifi"))
        st, got = rig.studio("GET", "local/pool/preflight", query={"model": "nosuch"})
        ctx.check(f"an unknown model: 404, got {st}", st == 404 and "is not in the pool catalog" in got["error"])
        st, got = rig.studio("GET", "local/pool/members")
        ctx.check("members: no 'not yet' line any more", st == 200 and "not_yet" not in got)


@test
def test_warm_then_stop(ctx: Ctx):
    with RunRig() as rig:
        st, got = rig.studio("POST", "local/pool/warm", body={"model": QWEN})
        ctx.check(f"warm: 202 at once, busy, the cli, got {st} {got}", st == 202 and got["busy"] is True
                  and got["cli"] == f"halo local serve --pool {QWEN}")
        run = _wait_run(rig, lambda g: g.get("warm", {}).get("busy") is False)
        ctx.check(f"the run says how it went: running, got {run.get('line')!r} {run['warm'].get('lines', [])[-2:]}",
                  run["state"] == "running" and run["warm"]["ok"] is True and any(
                      ln.startswith("the pool serves Qwen3-Next") for ln in run["warm"]["lines"]))
        names = {m["name"]: m for m in run["members"]}
        ctx.check(f"each member's claim and lease, got {names}", sorted(names) == ["me", "pc"]
                  and names["pc"]["alive"] is True and names["pc"]["claim"]["live"] is True
                  and "lease" in names["pc"]["claim"]["line"])
        st, again = rig.studio("POST", "local/pool/warm", body={"model": QWEN})
        ctx.check(f"a second Warm inside 10 min: 409 with the minutes, got {st} {again}", st == 409
                  and again["error"].startswith("one pool change per 10 min"))
        from halo_harness.local_sched import lease
        lease.reset()
        rig.studio("GET", "local/pool/run")
        ctx.check(f"a pool this Studio does not hold is adopted, got {lease.held()}", lease.held() == [f"pool:{QWEN}"])
        st, done = rig.studio("POST", "local/pool/stop")
        ctx.check(f"stop: the lines, got {st} {done.get('lines')}", st == 200 and done["lines"][0].startswith(
            "stopped the pool's llama-server") and any(ln.startswith("pivot: pool -> qwen3.8:27b on pc")
                                                       for ln in done["lines"]) and done["cli"] == "halo pool stop")
        st, got = rig.studio("GET", "local/pool/run")
        ctx.check(f"stopped again, got {got['state']}", got["state"] == "stopped")


@test
def test_a_members_rpc_server(ctx: Ctx):
    with RunRig() as rig:
        st, got = rig.studio("POST", "local/pool/rpc", body={"member": "pc", "to": "on"})
        ctx.check(f"pc's rpc-server on through its host, got {st} {got.get('say')!r}", st == 200
                  and "rpc-server runs on 192.0.2.10" in got["say"] and got["cli"] == "halo pool rpc pc on")
        st, got = rig.studio("POST", "local/pool/rpc", body={"member": "pc", "to": "status"})
        ctx.check(f"status, got {got.get('status')}", st == 200 and got["status"]["running"] is True)
        st, got = rig.studio("POST", "local/pool/rpc", body={"member": "nobody", "to": "on"})
        ctx.check(f"an unknown member: 422, got {st}", st == 422)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
