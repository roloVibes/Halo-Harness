"""tests.test_host_service -- Halo 3.3.7.0 R1 deliverable 1: the process (host/service.py, host/state.py,
host_cli.py serve | status | stop). Over tests/helpers/host_rig.py's scratch homes:

1. it starts on 127.0.0.1:0, writes serve.json (pid, port, bind, tls fingerprint, started, grants file), `halo host
   status` prints one block (running since, port, peers paired, last request, what it watches), `halo host stop`
   writes the stop file and it ends (serve.json gone);
2. offline mode refuses it with the hub's FleetOffline line, `halo host serve` too; host.enabled false says so;
3. the steward's watch runs in it (`where="host"`): it tails a fixture server log and records its events; no model,
   and the rules only report (mode off);
4. the ledger forwarder pushes this machine's lines to a fake hub with no session open, and the host announces itself
   there (hub_state's `hosts`).
No model call, no real ssh, never a request beyond 127.0.0.1.
Run: python -m tests.test_host_service
"""
from __future__ import annotations

import io
import json
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_rig import PC, HostRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _cli(*argv) -> "tuple[int, str]":
    from halo_harness.host_cli import cmd_host
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(out):
        rc = cmd_host(list(argv))
    return rc, out.getvalue()


def _wait(fn, timeout: float = 8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.05)
    return fn()


@test
def test_it_starts_writes_serve_json_status_and_stops(ctx: Ctx):
    from halo_harness.host import state as S
    with HostRig(host_home=None) as rig:
        rig.start()
        info = S.read_info(rig.home)
        ctx.check(f"serve.json names the pid, port, bind, tls, started, grants file, got {info}", bool(info)
                  and info["port"] == rig.svc.port and info["bind"] == "127.0.0.1" and info["started"]
                  and info["grants_file"].endswith("peers.json") and "fingerprint" in info and "tls" in info)
        rc, text = _cli("status")
        ctx.check(f"status: one block, running since, port, no peers yet, watches pc, got {rc} {text!r}", rc == 0
                  and "running since" in text and f"port {rig.svc.port}" in text and "peers paired: 0" in text
                  and "watches: pc" in text and "last request: none yet" in text)
        rig.pair()
        rig.client().ping()
        rc, text = _cli("status", "--json")
        got = json.loads(text)
        ctx.check(f"after a pairing and a ping: one peer, the last request named, got {got}", got["peers"] == 1
                  and (got["last_request"] or {}).get("path") == "/host/v1/ping" and got["requests"] >= 2)
        rc, text = _cli("stop")
        ctx.check(f"stop: it ends and serve.json is gone, got {rc} {text!r}", rc == 0 and "stopped" in text
                  and S.read_info(rig.home) is None and rig.svc.stopping.is_set())
        rc, text = _cli("status")
        ctx.check(f"status after: not running, got {text!r}", "not running" in text)


@test
def test_offline_mode_refuses_it(ctx: Ctx):
    import os
    from halo_harness.fleet.hub import FleetOffline
    from halo_harness.host.service import HostService
    with HostRig(host_home=None) as rig:
        os.environ["HALO_OFFLINE"] = "1"
        try:
            try:
                HostService(rig.home, port=0, bind="127.0.0.1").start()
                raised = ""
            except FleetOffline as e:
                raised = str(e)
            ctx.check(f"start raises the hub's FleetOffline line, got {raised!r}", raised.startswith("offline mode is on"))
            rc, text = _cli("serve", "--foreground", "--port", "0")
            ctx.check(f"halo host serve says it in one line, got {rc} {text!r}", rc == 1 and "offline mode is on" in text
                      and len(text.strip().splitlines()) == 1)
        finally:
            os.environ.pop("HALO_OFFLINE", None)
        rig.set_peer(**{"host.enabled": False})
        rc, text = _cli("serve", "--foreground", "--port", "0")
        ctx.check(f"host.enabled false: one line naming the key, got {rc} {text!r}", rc == 1 and "host.enabled" in text)


@test
def test_the_steward_watch_runs_in_the_host(ctx: Ctx):
    from halo_harness.ollama_steward import job_state, server_log
    from halo_harness.ollama_steward.job import HOST_NO_MODEL, StewardJob
    from halo_harness.ollama_steward.server_events import read_events
    from halo_harness.providers.ollama import OllamaHost
    from tests.helpers.mock_ollama import MockUpstream
    mock = MockUpstream(tags_response={"models": []}, ps_response={"models": []}).start()
    box = OllamaHost(name="box", url=mock.base_url)
    jobs: list = []
    try:
        with HostRig(host_home=None, seed=False) as rig:
            log = rig.home / "fixture-server.log"
            log.write_text('time=2026-10-31T08:00:01.000Z level=WARN source=runner.go:1 msg="truncating input prompt" '
                           "limit=16386 prompt=41104 keep=4 new=16386\n", encoding="utf-8")

            def watch(sd, host, stop, on_event=None):
                server_log.watch(sd, host, stop, path=log, on_event=on_event, from_start=True, tail_s=0.1, poll_s=0.2)

            def make(home):
                job = StewardJob(home, host=box, where="host", watch=watch)
                jobs.append(job)
                return job if job.start()[0] else None
            rig.job = make
            rig.start()
            got = _wait(lambda: [e for e in read_events(rig.home, host="box") if e.get("kind") == "prompt-trimmed"])
            ctx.check(f"the watch tailed the fixture log into events, got {got}", bool(got))
            st = job_state.status(rig.home)
            ctx.check(f"one steward job, where host, got {st.get('where')} {st.get('running')}", st.get("where") == "host"
                      and st.get("running"))
            ctx.check("no model in the host", jobs[0].model() == (None, HOST_NO_MODEL))
            done = jobs[0].run_once()
            ctx.check(f"its rules only report (mode off), got {done.get('mode')} {done.get('model')}",
                      done.get("mode") == "off" and done.get("model") is None)
            rc, text = _cli("status")
            ctx.check(f"status says the watch runs here, got {text!r}", "the steward's watch runs here" in text)
    finally:
        mock.stop()


@test
def test_the_forwarder_pushes_to_a_hub_with_no_session_and_the_host_announces(ctx: Ctx):
    import tempfile
    from halo_harness.fleet import identity, ollama_share, relay, store
    from halo_harness.fleet.hub import HubServer
    from halo_harness.fleet.hub_hosts import listing
    from halo_harness.ollama_steward.ledger import read_calls, record_call
    saved = (ollama_share.FLUSH_S, ollama_share.CHECK_S)
    ollama_share.FLUSH_S, ollama_share.CHECK_S = 0.05, 0.0
    home_a = Path(tempfile.mkdtemp(prefix="hs_hub-")) / ".halo"
    home_a.mkdir(parents=True)
    (home_a / "config.json").write_text(json.dumps({"fleet": {"name": "alice@hub"}}), encoding="utf-8")
    hub = HubServer(home_a, port=0, bind="127.0.0.1", name="hub-a", tls_on=False, record=False,
                    local_view=lambda: None).start()
    try:
        with HostRig(host_home=None, seed=False) as rig:
            got = relay.join(hub.url("127.0.0.1"), hub.pairing.new_code(600)[0], identity.harness())
            key = got.pop("key")
            store.add_hub(got, key)
            record_call(rig.home, {"host": PC, "model": "qwen3.8:27b", "status": 200, "prompt_eval_count": 1200})
            rig.start()
            time.sleep(0.1)
            rig.svc.forward_tick()
            lines = _wait(lambda: [x for x in read_calls(home_a) if x.get("model") == "qwen3.8:27b"])
            ctx.check(f"the line reached the hub with from = this machine's name, no session open, got {lines}",
                      bool(lines) and lines[0].get("from") == "bob@peer")
            rows = listing(home_a)
            ctx.check(f"the host announced itself: port, fingerprint, serves, got {rows}", len(rows) == 1
                      and rows[0]["port"] == rig.svc.port and rows[0]["serves"][0]["port"] == 11434 and rows[0]["fresh"])
            ctx.check("the hub's merged view lists it", hub.state.view()["hosts"][0]["member"] == "bob@peer")
            rig.svc.forward_tick()
            ctx.check("a second pass sends nothing twice",
                      len([x for x in read_calls(home_a) if x.get("model") == "qwen3.8:27b"]) == 1)
            st = rig.svc.forward_state.get(got["url"]) or {}
            ctx.check(f"the forward state per hub, got {st}", st.get("sent") == 1 and not st.get("error"))
    finally:
        hub.stop()
        ollama_share.FLUSH_S, ollama_share.CHECK_S = saved
        import shutil
        shutil.rmtree(home_a.parent, ignore_errors=True)


@test
def test_serve_detaches_and_says_where(ctx: Ctx):
    """`halo host serve` without --foreground starts `halo host serve --foreground` detached (the spawn seam stands in
    for the child: it starts the service here) and returns once serve.json is written; a second serve says it runs."""
    from halo_harness import host_cli
    from halo_harness.host.service import HostService
    from tests.helpers.host_rig import readers
    seen: list = []

    class _Child:
        def poll(self):
            return None

    def spawn(argv):
        seen.append(argv)
        seen.append(HostService(rig.home, port=0, bind="127.0.0.1", readers=readers(), job=lambda h: None).start())
        return _Child()
    with HostRig(host_home=None) as rig:
        host_cli.SEAMS["spawn"] = spawn
        try:
            rc, text = _cli("serve", "--port", "0")
            ctx.check(f"the child's argv: halo host serve --foreground --port 0, got {seen[:1]}", seen
                      and seen[0][-5:] == ["host", "serve", "--foreground", "--port", "0"])
            ctx.check(f"it returns once serve.json is there, got {rc} {text!r}", rc == 0 and "runs in the background" in text)
            rc, text = _cli("serve")
            ctx.check(f"a second serve says it already runs, got {text!r}", rc == 0 and "already runs" in text)
            rc, text = _cli("stop")
            ctx.check(f"stop ends it, got {text!r}", rc == 0 and seen[1].stopping.is_set())
        finally:
            host_cli.SEAMS.clear()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
