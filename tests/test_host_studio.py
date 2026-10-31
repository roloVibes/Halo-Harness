"""tests.test_host_studio -- Halo 3.3.7.0 R1 deliverable 4, the Python half: Studio and the CLI see the host, over
tests/helpers/host_rig.py's fake host (the Chrome half is tests/test_studio_hosts_host.py):

1. GET local/hosts: pc's card carries the `host` block (addr, started, last seen, the audit count) and controls
   `via: "host"`; a host that stops answering says so in the block;
2. `halo local hosts` lists the rung each host is read through and the host line;
3. `halo host status --peer pc-host` prints the paired host's block (running since, its audit, its servers);
4. a member's samples and a discovered server at a host's address get the block too (the member/discovered groups).
Run: python -m tests.test_host_studio
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_rig import HostRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _hosts(rig) -> list:
    from halo_harness.studio.api import Request, dispatch
    code, got = dispatch(Request(method="GET", path="local/hosts", query={}, body={}, cwd=Path(rig.root_p),
                                 state_dir=rig.peer, server=None))
    return got["hosts"] if code == 200 else []


@test
def test_the_hosts_card_carries_the_host_block(ctx: Ctx):
    from halo_harness.ollama_steward import host_client
    with HostRig() as rig:
        rig.start()
        rig.pair()
        pc = next(h for h in _hosts(rig) if h["name"] == "pc")
        b = pc.get("host") or {}
        ctx.check(f"served by halo host at its address, running since, last seen, the audit count, got {b}",
                  b.get("addr") == "127.0.0.1" and b.get("started") and b.get("last_seen") and b.get("audit_count", 0) >= 1
                  and b.get("name") == "pc-host" and not b.get("error"))
        ctx.check(f"controls via host, not from here without the grant, got {pc['controls']}", pc["controls"]["via"] == "host"
                  and pc["controls"]["ok"] is False and "need `control`" in pc["controls"]["why"])
        ctx.check(f"its log line reads through the host, got {pc.get('log')}", (pc.get("log") or {}).get("rung") == "host")
        rig.svc.stop()
        rig.svc = None
        host_client.reset()
        from halo_harness.studio import ollama_hosts_view as V
        V.reset_cache()
        pc = next(h for h in _hosts(rig) if h["name"] == "pc")
        ctx.check(f"a host that stopped: the block says it did not answer, got {pc.get('host')}",
                  "did not answer" in (pc.get("host") or {}).get("error", ""))


@test
def test_halo_local_hosts_lists_the_rung(ctx: Ctx):
    from halo_harness.local_tab_cli import hosts_lines
    with HostRig() as rig:
        rig.start()
        rig.pair()
        lines = hosts_lines(rig.peer)
        text = "\n".join(lines)
        ctx.check(f"pc: read through host, served by halo host, its audit, got {text!r}",
                  "read through: host (via host 127.0.0.1" in text and "served by halo host at 127.0.0.1" in text
                  and "in its audit" in text)


@test
def test_halo_host_status_peer(ctx: Ctx):
    from halo_harness.host_cli import cmd_host
    with HostRig() as rig:
        rig.start()
        rig.pair()
        for argv, want in ((["status", "--peer", "pc-host"], "running since"), (["status", "--peer", "pc-host", "--json"], "")):
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(out):
                rc = cmd_host(argv)
            text = out.getvalue()
            if want:
                ctx.check(f"the paired host's block, got {rc} {text!r}", rc == 0 and want in text and "pc (port 11434)" in text
                          and "22.0 GB usable" in text)
            else:
                got = json.loads(text)
                ctx.check(f"--json: the host, its audit, its servers, got {list(got)}", got["host"]["host"] is True
                          and got["hosts"][0]["name"] == "pc" and got["audit"]["count"] >= 1)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            rc = cmd_host(["status", "--peer", "nobody"])
        ctx.check(f"an unknown peer: one line, got {rc} {out.getvalue()!r}", rc == 1 and "no paired host" in out.getvalue())


@test
def test_member_and_discovered_rows_get_the_block(ctx: Ctx):
    from halo_harness.ollama_steward import resources
    from halo_harness.studio import local_hosts_view as L
    with HostRig() as rig:
        rig.start()
        rig.pair()
        resources.STORE.add({"host": "pc-lan", "url": "http://192.0.2.10:11434", "t": 1.0, "from": "mac@lab",
                             "holders": [], "sources": {}})
        try:
            rows = L._members(set(), None)
            ctx.check(f"a member's host at the host's address gets the block, got {[(r['name'], r.get('host')) for r in rows]}",
                      any(r["name"] == "pc-lan" and (r.get("host") or {}).get("addr") == "127.0.0.1" for r in rows))
        finally:
            resources.STORE.clear()
        from types import SimpleNamespace
        from halo_harness.studio import setup_discover_jobs as J
        saved = J.found
        J.found = lambda: [SimpleNamespace(name="found", url="http://192.0.2.10:11434", configured=False, version="0.40.6",
                                           models=["qwen3.8:27b"], where="lan")]
        try:
            rows = L._discovered(set())
            ctx.check(f"a discovered server there gets it too, got {[r.get('host') for r in rows]}",
                      rows and (rows[0].get("host") or {}).get("addr") == "127.0.0.1")
        finally:
            J.found = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
