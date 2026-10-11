"""tests.test_remote_print_mode -- Halo 2.0.9 round 2: print mode (`halo -p`,
which `--bg` re-runs) opens the same control socket behind config
`remote.enabled`. `PrintModeHandle` is unit-tested against the scripted
session; one end-to-end test drives a real `halo -p --input-format
stream-json` child (mock upstream) over its socket. The loopback+token half
runs on Windows, the Unix-socket half on POSIX -- the child picks the
transport, the test reads the endpoint (and token) from the registry.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fake_home import build_fake_home
from tests.helpers.fake_remote_session import FakeRegistry, FakeSession
from tests.helpers.mock_openai import MockUpstream
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()


class _Queue:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


@test
def test_print_handle_surface(ctx: Ctx):
    from halo_harness import events
    from halo_harness.remote.handle import HandleError
    from halo_harness.remote.print_handle import PrintModeHandle
    s = FakeSession()
    q = _Queue()
    h = PrintModeHandle(s, Path("."), input_queue=q, registry=FakeRegistry(), facade=object())
    h.attach()
    sub = h.subscribe()
    stream = [events.message_start(turn=1), events.text_delta("ab", turn=1), events.text_delta("cd", turn=1),
              events.message_end(turn=1), events.turn_done(turn=1)]
    seen = list(h.tee(iter(stream)))
    ctx.check("tee yields every event unchanged for the sink", [e.kind for e in seen] == [e.kind for e in stream])
    frames = []
    while True:
        f = sub.get(0.2)
        if f is None:
            break
        frames.append(f)
    ctx.check("the hub got a copy: message_start, ONE text_chunk 'abcd', message_end, turn_done",
              [f["event"] for f in frames] == ["message_start", "text_chunk", "message_end", "turn_done"]
              and frames[1]["data"]["text"] == "abcd")
    ctx.check("idle submit feeds the stream-json input queue", h.submit("next turn") == {"steered": False, "queued": True}
              and q.items == [{"text": "next turn", "images": None}])
    s._busy.set()
    ctx.check("busy submit is a steer", h.submit("change course")["steered"] is True and s.steered == ["change course"])
    s._busy.clear()
    ctx.check("mode write + status published", h.set_mode("auto")["mode"] == "auto" and s.permission_engine.mode == "auto")
    ctx.check("status carries kind=print and the pending map", h.status()["kind"] == "print" and "pending" in h.status())
    ctx.check("interrupt sets abort", h.interrupt()["interrupted"] and s.abort.is_set())
    ctx.check("slash goes through the command registry", h.run_slash("cost", "x") == "ran /cost x")
    ctx.check("unknown slash is reported", "Unknown command" in h.run_slash("boom"))
    s.log.add("user", "q1")
    ctx.check("tail renders the log as Markdown", "## User" in h.tail(3) and "q1" in h.tail(3))
    for bad in (lambda: h.set_mode("nope"), lambda: h.set_effort("enormous"), lambda: h.answer_permission("p", "maybe")):
        try:
            bad()
            raised = False
        except HandleError:
            raised = True
        ctx.check("bad input raises HandleError", raised)
    one_shot = PrintModeHandle(s, Path("."))
    try:
        one_shot.submit("more")
        err = ""
    except HandleError as e:
        err = str(e)
    ctx.check("a single-prompt run has no input queue and says so", "stream-json" in err)
    h.detach()


def _wait_entry(home: Path, timeout: float = 25.0):
    path = home / ".halo" / "run" / "sessions.json"
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            rows = json.loads(path.read_text("utf-8")).get("sessions") or []
        except (OSError, ValueError):
            rows = []
        if rows:
            return rows[0]
        time.sleep(0.1)
    return None


@test
def test_halo_dash_p_serves_its_control_socket(ctx: Ctx):
    from halo_harness.remote import client as rclient
    fh = build_fake_home()
    home = Path(fh["home"])
    cfg = home / ".halo" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"remote": {"enabled": True}}), encoding="utf-8")
    mock = MockUpstream().start()
    env = dict(os.environ)
    env.pop("BRIDGE_STATE_DIR", None)
    for k in [k for k in env if k.startswith("HALO_")]:
        env.pop(k, None)
    env.update({"BRIDGE_TEST_HOME": str(home), "BRIDGE_OPENROUTER_BASE_URL": mock.base_url,
                "OPENROUTER_API_KEY": "test-key", "PYTHONPATH": str(REPO_DIR), "BRIDGE_TEST_NO_BACKGROUND_NET": "1"})
    proc = subprocess.Popen(
        [sys.executable, "-m", "halo_harness", "-p", "--model", "or:mock/model", "--cwd", str(fh["proj"]),
         "--input-format", "stream-json", "--output-format", "stream-json"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=str(REPO_DIR), text=True)
    client = None
    try:
        entry = _wait_entry(home)
        ctx.check("the print-mode run registered itself", entry is not None)
        endpoint = entry["endpoint"]
        ctx.check("endpoint matches the platform transport",
                  endpoint.startswith("tcp:127.0.0.1:") if os.name == "nt" else endpoint.startswith("unix:"))
        client = rclient.ControlClient(endpoint, rclient.default_token_for(entry))
        st = client.call("status")["result"]
        ctx.check("status says kind=print with this session's id", st["kind"] == "print" and st["session_id"] == entry["session_id"])
        client.call("subscribe")
        r = client.call("submit", text="drive this turn over the socket")
        ctx.check("submit queued as the next turn", r["ok"] and r["result"]["queued"] is True)
        done = client.wait_event("turn_done", 25)
        ctx.check("the feed delivered the turn's events", done is not None)
        ctx.check("a turn driven by the socket reached the mock upstream", len(mock.requests) >= 1)
        ctx.check("tail shows the socket-driven turn", "pong" in client.call("tail", n=4)["result"]["markdown"])
        ctx.check("mode over the socket", client.call("mode", mode="plan")["result"]["mode"] == "plan")
        client.close()
        client = None
        out, err = proc.communicate(timeout=30)  # closes stdin itself (EOF ends the run)
        ctx.check(f"child exits 0 once stdin closes, got {proc.returncode} {err[-300:]!r}", proc.returncode == 0)
        ctx.check("the sink still printed the turn's result line (the tee did not eat events)",
                  any(json.loads(l).get("type") == "result" for l in out.splitlines() if l.startswith("{")))
        ctx.check("endpoint refuses after the run ends", not rclient.probe(endpoint))
        ctx.check("registry entry removed on exit", _wait_entry(home, 0.5) is None)
    finally:
        if client is not None:
            client.close()
        try:
            proc.kill()
        except Exception:
            pass
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
