"""tests.test_mcp_deferred_round -- Halo 2.0.6 round 10: MCP connects off
the TUI startup path.

build_manager(start=False) seeds every server's catalog from cache (zero
connections) and flags the manager deferred; the TUI's own background
worker completes the connects behind the paint
(Manager.complete_deferred_start). Print mode keeps the blocking start.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


class _FakeHandle:
    def __init__(self, state, lazy=False, tools=None):
        self.state = state
        self.config = type("C", (), {"lazy": lazy, "always_load": False})()
        self.tools = tools or []


class _FakeManager:
    """The manager surface complete_deferred_start touches, with recording."""

    def __init__(self, handles, lazy_names=()):
        self.handles = handles
        self._lazy_names = set(lazy_names)
        self.deferred_start = True
        self.calls = []

    def start_all(self):
        self.calls.append(("start_all",))
        for h in self.handles.values():
            if h.state == "pending" and True:
                h.state = "connected"

    def _start_targets_parallel(self, targets):
        self.calls.append(("parallel", [id(t) for t in targets]))
        for t in targets:
            t.state = "connected"


@test
def test_complete_deferred_start_connects_and_reports(ctx: Ctx):
    from halo_harness.mcp.manager import McpManager
    m = _FakeManager({
        "eager-pending": _FakeHandle("pending"),
        "eager-cached": _FakeHandle("cached"),
        "lazy-cached": _FakeHandle("cached", lazy=True),
        "already": _FakeHandle("connected"),
    }, lazy_names={"lazy-cached"})
    notes = []
    out = McpManager.complete_deferred_start(m, note_fn=notes.append)
    ctx.check(f"start_all ran and cleared the flag, got {m.calls[:1]}",
              m.calls and m.calls[0] == ("start_all",) and not m.deferred_start)
    ctx.check(f"the cached EAGER handle connected, got {m.handles['eager-cached'].state}",
              m.handles["eager-cached"].state == "connected")
    ctx.check(f"the pending EAGER handle connected too, got {m.handles['eager-pending'].state}",
              m.handles["eager-pending"].state == "connected")
    ctx.check(f"the LAZY handle is deliberately untouched, got {m.handles['lazy-cached'].state}",
              m.handles["lazy-cached"].state == "cached")
    ctx.check(f"the summary names both connects, got {out}",
              sorted(out["connected"]) == ["eager-cached", "eager-pending"] and not out["failed"])
    ctx.check(f"one note landed, got {notes}", len(notes) == 1 and "connected" in notes[0])


@test
def test_complete_deferred_start_is_idempotent_and_quiet(ctx: Ctx):
    from halo_harness.mcp.manager import McpManager
    m = _FakeManager({"a": _FakeHandle("connected")})
    m.deferred_start = False
    notes = []
    out = McpManager.complete_deferred_start(m, note_fn=notes.append)
    ctx.check("a non-deferred manager is a no-op", out == {"connected": [], "failed": []})
    ctx.check("nothing connected -> no note", notes == [])


@test
def test_build_manager_start_false_seeds_and_defers(ctx: Ctx):
    """The build side: start=False must create handles, seed from cache,
    and set deferred_start -- with ZERO connections. Driven against the
    real build_manager with a scratch config (one eager server, a warm
    cache written first) and a manager-start recorder."""
    import os
    from halo_harness.mcp import tools_cache
    from halo_harness.mcp_setup import build_manager

    home = Path(tempfile.mkdtemp(prefix="mcpdev-"))
    proj = home / "proj"
    proj.mkdir(parents=True)
    cfg_dir = home / ".halo"
    cfg_dir.mkdir()
    (cfg_dir / "config.json").write_text(json.dumps(
        {"mcpServers": {"eager": {"type": "stdio", "command": "python",
                                  "args": ["-c", "print('hi')"]}}}), encoding="utf-8")
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    try:
        # write a warm cache for the eager server so seeding has something
        from halo_harness.mcp.manager import resolve_server_configs
        configs, _ = resolve_server_configs(
            cwd=proj, claude_json={"mcpServers": {
                "eager": {"type": "stdio", "command": "python", "args": ["-c", "print('hi')"]}}})
        from halo_harness.mcp.tools_cache import CachedTool
        tools_cache.write_cache("eager", key=tools_cache.config_cache_key(configs["eager"]),
                                tools=[CachedTool(name="ping", description="pings",
                                                  input_schema={"type": "object"}, meta={})],
                                instructions=None)
        manager, notices = build_manager(
            cwd=proj, claude_json={"mcpServers": {
                "eager": {"type": "stdio", "command": "python", "args": ["-c", "print('hi')"]}}},
            start=False)
        h = manager.handles.get("eager")
        ctx.check(f"the eager handle exists, got {h}", h is not None)
        if h is not None:
            ctx.check(f"it is cache-seeded WITHOUT connecting, got state={h.state!r}",
                      h.state == "cached")
            names = [t.name for t in (h.tools or [])]
            ctx.check(f"its catalog came from the cache, got {names}", "ping" in names)
        ctx.check("the manager is flagged deferred for the app worker",
                  getattr(manager, "deferred_start", False) is True)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@test
def test_the_tui_wires_the_worker_and_print_mode_blocks(ctx: Ctx):
    """Structural pins: build_session passes start=bool(print_mode) so the
    TUI defers while -p blocks; and BridgeApp owns the worker method that
    on_mount schedules."""
    src = (Path(__file__).resolve().parent.parent / "halo_harness" / "headless.py") \
        .read_text(encoding="utf-8")
    ctx.check("build_session gates the blocking start on print_mode",
              "start=bool(print_mode), trusted=trusted" in src)
    app_src = (Path(__file__).resolve().parent.parent / "halo_harness" / "tui" / "app.py") \
        .read_text(encoding="utf-8")
    ctx.check("on_mount schedules the deferred-start worker",
              "_mcp_deferred_start_worker()" in app_src)
    ctx.check("the worker completes behind the paint on a thread",
              "complete_deferred_start" in app_src and "thread=True" in app_src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
