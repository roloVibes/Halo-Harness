"""tests.test_review3_g3c -- pins for the 3.0.2.0 review fix pass, round
G3-mcp-commands (part 3): manager/log behaviour.

  * item 68   an expanded tokenized url never shows in /mcp, `mcp list`,
              `mcp get` or the per-server log
  * item 70   reconnect-on-next-call / manual reconnect run under the
              per-server lock: a dead server is started once
  * item 141  connect failures on the parallel start path reach the
              per-server log
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.test_review3_g3b import PAT, _Home, _handle

ensure_default_provider_credentials()

test, TESTS = new_registry()


# ---- item 68: the expanded url never shows -----------------------------------

@test
def test_item68_tokenized_url_is_masked_everywhere(ctx: Ctx):
    from halo_harness import mcp_cli
    from halo_harness.mcp.client import McpLoop
    from halo_harness.mcp.errtext import scrub_error_text
    url = f"https://mcp.example.com/sse?token={PAT}"
    shown = mcp_cli.failure_reason({"state": "failed", "error": "ConnectionRefusedError: refused", "url": url})
    ctx.check(f"connection-refused row shows the masked url, got {shown!r}", PAT not in shown and "mcp.example.com/sse" in shown)
    text = f"HTTPStatusError: Client error '401 Unauthorized' for url '{url}' For more information check: x"
    ctx.check("scrubbed text has no token", PAT not in scrub_error_text(text) and "mcp.example.com/sse" in scrub_error_text(text))
    ctx.check("failure_reason scrubs a stored error too",
              PAT not in mcp_cli.failure_reason({"state": "failed", "error": text, "url": url}))
    with _Home():
        loop = McpLoop()
        h = _handle(url, "g3b-leak", loop)

        async def boom():
            raise RuntimeError(text)
        h._connect_once = boom
        try:
            h.start()
            from halo_harness.mcp.manager import tail_server_log
            log = "\n".join(tail_server_log("g3b-leak"))
            ctx.check(f"handle error is scrubbed, got {h.error!r}", PAT not in (h.error or "") and "mcp.example.com" in h.error)
            ctx.check("the per-server log is scrubbed", PAT not in log and "connect failed" in log)
        finally:
            h.close()
            loop.close()


# ---- item 70: reconnect under the per-server lock -----------------------------

@test
def test_item70_parallel_calls_on_a_dead_server_reconnect_once(ctx: Ctx):
    from halo_harness.mcp.manager import McpManager, McpServerConfig
    cfg = McpServerConfig(name="dead", type="stdio", command=sys.executable, args=["-c", "pass"], scope="user")
    mgr = McpManager({"dead": cfg}, tool_env=dict(os.environ))
    h = mgr.handles["dead"]
    starts, active, overlap = [], [0], [False]

    def fake_start(abort=None):
        active[0] += 1
        overlap[0] = overlap[0] or active[0] > 1
        starts.append(1)
        time.sleep(0.3)
        h.state = "connected"
        active[0] -= 1

    h.close = lambda timeout=None, abort=None: None
    h.start = fake_start
    h.call_tool = lambda tool, args, timeout=None, abort=None: "ok"
    h.state = "failed"
    h._reconnect_on_next_call = True
    h.backoff_due = lambda: True
    out = []
    ths = [threading.Thread(target=lambda: out.append(mgr.call("dead", "t", {}))) for _ in range(3)]
    try:
        [t.start() for t in ths]
        [t.join(10) for t in ths]
        ctx.check(f"start() ran exactly once for 3 parallel callers, got {len(starts)}", len(starts) == 1)
        ctx.check("starts never overlapped", overlap[0] is False)
        ctx.check(f"all callers got the tool result, got {out}", out == ["ok"] * 3)
        # a manual reconnect racing a call is serialized too
        starts.clear()
        ths = [threading.Thread(target=lambda: mgr.reconnect_manual("dead")) for _ in range(2)]
        [t.start() for t in ths]
        [t.join(10) for t in ths]
        ctx.check(f"manual reconnects never overlapped, got overlap={overlap[0]}", overlap[0] is False and len(starts) == 2)
    finally:
        mgr.close_all()


# ---- item 141: parallel-start failures reach the per-server log --------------

@test
def test_item141_parallel_start_failure_is_logged(ctx: Ctx):
    from halo_harness.mcp.manager import McpManager, McpServerConfig, tail_server_log
    with _Home():
        cfg = McpServerConfig(name="g3b-par", type="http", url=f"http://127.0.0.1:1/mcp?token={PAT}", scope="user")
        mgr = McpManager({"g3b-par": cfg}, tool_env=dict(os.environ))
        h = mgr.handles["g3b-par"]

        async def boom():
            raise ConnectionRefusedError(f"could not reach 127.0.0.1:1 for http://127.0.0.1:1/mcp?token={PAT}")
        h._connect_once = boom
        try:
            mgr.start_all()
            log = "\n".join(tail_server_log("g3b-par"))
            ctx.check(f"state failed, got {h.state!r}", h.state == "failed")
            ctx.check(f"`L` has the connect failure, got {log!r}", "connect failed (failed)" in log)
            ctx.check("and no token", PAT not in log and PAT not in (h.error or ""))
        finally:
            mgr.close_all()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
