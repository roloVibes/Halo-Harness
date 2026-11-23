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


REPO_DIR = Path(__file__).resolve().parent.parent
_F2_ENV = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "OLLAMA_HOST", "HALO_NO_UPDATER")


def _f2_home(*, servers=True):
    """A scratch home whose claude.json names three fake stdio servers ("fake"
    eager, "fake2" with the server's "alwaysLoad", "lazy" lazy as servers are
    by default) and NO tools cache, so a terminal session builds its catalog
    before any of them has connected."""
    import os
    from tests.helpers.fake_home import build_fake_home
    fh = build_fake_home()
    spec = {"type": "stdio", "command": sys.executable, "args": ["-m", "tests.helpers.fake_mcp_server"],
            "cwd": str(REPO_DIR)}
    cfg = {"mcpServers": {"fake": dict(spec, mcpLazy=False), "fake2": dict(spec, alwaysLoad=True),
                          "lazy": dict(spec)}} if servers else {}
    (fh["home"] / ".claude.json").write_text(json.dumps(cfg), encoding="utf-8")
    saved = {k: os.environ.get(k) for k in _F2_ENV}
    os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
    os.environ.pop("BRIDGE_STATE_DIR", None)
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"
    os.environ["HALO_NO_UPDATER"] = "1"
    return fh, saved


def _f2_restore(saved):
    import os
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _f2_controller(fh, extra=()):
    from halo_harness.cli import _build_parser
    from halo_harness.tui.bootstrap import build_controller
    args = _build_parser().parse_args(["--cwd", str(fh["proj"]), "--model", "or:mock/model", *extra])
    controller, _registry, _facade = build_controller(args)
    return controller


def _f2_late_connect(controller):
    """What the terminal app's worker runs once the first catalog is built."""
    manager = controller.session.mcp_manager
    out = manager.complete_deferred_start()
    take = getattr(controller, "take_connected_servers", None)
    if callable(take):
        take(out["connected"])
    return out


def _f2_helper(controller, agent_id, spec=None):
    from halo_harness.agent.subagent import _build_child_session
    from halo_harness.config.agents_md import AgentSpec
    spec = spec or AgentSpec(name="general-purpose", description="general purpose sub-agent", tools=None,
                             disallowed_tools=["Agent", "Task"], body="You are a helpful sub-agent.")
    child, _meta = _build_child_session(runtime=controller.session.agent_runtime, spec=spec, agent_id=agent_id,
                                        model_override=None, parent_tool_use_id="t")
    return child


def _f2_close(controller):
    manager = getattr(getattr(controller, "session", None), "mcp_manager", None) if controller else None
    if manager is not None:
        manager.close_all()


@test
def test_a_server_that_connects_after_the_first_catalog_reaches_main_and_a_helper(ctx: Ctx):
    """3.6.0.15 F2: on a fresh home a terminal session builds its catalog
    before its MCP servers connect; the late servers' tools must enter that
    catalog (deferred, the alwaysLoad ones loaded at once) and a helper
    built after that gets its own catalog over its parent's deferred tools."""
    fh, saved = _f2_home()
    controller = None
    try:
        controller = _f2_controller(fh)
        catalog = controller.session.session_catalog
        ctx.check("the session has a catalog", catalog is not None)
        before = set(catalog.names) | set(catalog.deferred)
        ctx.check(f"before the deferred start no server tool is known, got {sorted(before)}",
                  not any(n.startswith("mcp__fake") for n in before))
        out = _f2_late_connect(controller)
        ctx.check(f"both servers connected late, got {out}", sorted(out["connected"]) == ["fake", "fake2"])
        found, deferred = catalog.search("select:mcp__fake__echo")
        ctx.check(f"main finds the plain server's tool in its pool, got {[d['name'] for d in found]} {deferred}",
                  [d["name"] for d in found] == ["mcp__fake__echo"] and deferred == ["mcp__fake__echo"])
        ctx.check(f"the alwaysLoad server's tool is loaded in main, got {catalog.names}",
                  "mcp__fake2__echo" in catalog.names and catalog.registry.get("mcp__fake2__echo") is not None)
        ctx.check(f"a tool's alwaysLoad meta loads it in main, got {catalog.names}",
                  "mcp__fake__always_load_tool" in catalog.names)
        child = _f2_helper(controller, "f2late1")
        ctx.check(f"the helper has the alwaysLoad tool, got {child.tool_registry.names()}",
                  child.tool_registry.get("mcp__fake2__echo") is not None)
        cc = child.session_catalog
        ctx.check("the helper has its own catalog", cc is not None and cc is not catalog)
        if cc is not None:
            ctx.check("the helper has ToolSearch", child.tool_registry.get("ToolSearch") is not None)
            c_found, c_def = cc.search("select:mcp__fake__echo")
            ctx.check(f"the helper's ToolSearch finds the deferred tool, got {c_def}", c_def == ["mcp__fake__echo"])
            ctx.check(f"the helper loads it, got {cc.load(c_def)}", "mcp__fake__echo" in cc.names)
            ctx.check("loading in the helper never grows main's catalog",
                      "mcp__fake__echo" not in catalog.names and "mcp__fake__echo" in catalog.deferred)
        ctx.check(f"main's ToolSearch loads it too, got {catalog.load(['mcp__fake__echo'])}",
                  "mcp__fake__echo" in catalog.names and catalog.registry.get("mcp__fake__echo") is not None)
        if cc is not None:
            cc.ensure_lazy_discovered()
            ctx.check(f"the helper's ToolSearch starts a lazy server and finds its tool, got "
                      f"{cc.search('select:mcp__lazy__echo')[1]}", cc.search("select:mcp__lazy__echo")[1] == ["mcp__lazy__echo"])
        catalog.ensure_lazy_discovered()
        ctx.check(f"main finds the lazy server's tool after a helper started it, got "
                  f"{catalog.search('select:mcp__lazy__echo')[1]}",
                  catalog.search("select:mcp__lazy__echo")[1] == ["mcp__lazy__echo"])
    finally:
        _f2_close(controller)
        _f2_restore(saved)


@test
def test_a_late_server_keeps_every_deny_and_a_helpers_tools_line(ctx: Ctx):
    """3.6.0.15 F2: the late connect passes the build's own filter (a deny
    holds), and a helper's `tools:` still narrows what it gets."""
    from halo_harness.config.agents_md import AgentSpec
    fh, saved = _f2_home()
    controller = None
    try:
        controller = _f2_controller(fh, ["--disallowedTools", "mcp__fake__echo"])
        catalog = controller.session.session_catalog
        _f2_late_connect(controller)
        known = set(catalog.names) | set(catalog.deferred)
        ctx.check(f"the denied tool never enters the pool, got {sorted(n for n in known if 'fake__' in n)}",
                  "mcp__fake__echo" not in known)
        ctx.check(f"the other tools did, got {sorted(known)}", "mcp__fake__slow_tool" in known)
        narrow = _f2_helper(controller, "f2late2", AgentSpec(name="narrow", description="d", tools=["Read"]))
        nc = narrow.session_catalog
        ctx.check(f"a `tools: Read` helper has no MCP tool, got {narrow.tool_registry.names()}",
                  narrow.tool_registry.names() == ["Read"]
                  and (nc is None or not nc.deferred))
        wide = _f2_helper(controller, "f2late3",
                          AgentSpec(name="wide", description="d", tools=["Read", "mcp__fake__*"]))
        wc = wide.session_catalog
        pool = sorted(wc.deferred) if wc is not None else []
        ctx.check(f"`tools: Read, mcp__fake__*` gets that server only, never the denied tool, got {pool}",
                  "mcp__fake__slow_tool" in pool and "mcp__fake__echo" not in pool
                  and not any(n.startswith("mcp__fake2") for n in pool))
    finally:
        _f2_close(controller)
        _f2_restore(saved)


@test
def test_a_session_with_no_mcp_server_builds_its_helpers_as_before(ctx: Ctx):
    """3.6.0.15 F2: with no MCP server configured (the session still has a
    catalog, with an empty pool) a helper is built exactly as 3.6.0.14 built
    it: no catalog of its own, its parent's tools filtered by the spec, in
    the same order."""
    fh, saved = _f2_home(servers=False)
    controller = None
    try:
        controller = _f2_controller(fh, ["--strict-mcp-config"])
        parent = controller.session
        ctx.check("the parent has no MCP server", not getattr(parent.mcp_manager, "handles", None))
        child = _f2_helper(controller, "f2none")
        from halo_harness.config.agents_md import AgentSpec
        spec = AgentSpec(name="general-purpose", description="general purpose sub-agent", tools=None,
                         disallowed_tools=["Agent", "Task"], body="You are a helpful sub-agent.")
        names = parent.session_catalog.names if parent.session_catalog is not None else parent.tool_registry.names()
        want = parent.tool_registry.filtered(spec.resolved_tools(names)).names()
        ctx.check("the helper has no catalog", child.session_catalog is None)
        ctx.check(f"the helper's tools, in order, are 3.6.0.14's, got {child.tool_registry.names()} want {want}",
                  child.tool_registry.names() == want)
    finally:
        _f2_close(controller)
        _f2_restore(saved)


def _f13_search(child, query):
    """The helper's own ToolSearch, as its loop runs it."""
    from halo_harness.tools.base import ToolContext
    tool = child.tool_registry.get("ToolSearch")
    tctx = ToolContext(cwd=REPO_DIR, registry=child.tool_registry, catalog=child.session_catalog)
    return tool.run({"query": query}, tctx), tctx


@test
def test_a_helper_built_before_a_server_connects_finds_its_tools_later(ctx: Ctx):
    """3.6.0.15 F13: a helper that started BEFORE an MCP server connected
    finds that server's tools with its own ToolSearch: it looks at what its
    parent's catalog holds NOW, within its own limits; nothing is pushed into
    its tool list, and its parent's catalog never changes by it."""
    from halo_harness.config.agents_md import AgentSpec
    fh, saved = _f2_home()
    controller = None
    try:
        controller = _f2_controller(fh, ["--disallowedTools", "mcp__fake__slow_tool"])
        catalog = controller.session.session_catalog
        child = _f2_helper(controller, "f13early")
        narrow = _f2_helper(controller, "f13narrow", AgentSpec(name="narrow", description="d", tools=["Read"]))
        cc = child.session_catalog
        ctx.check("the early helper has its own catalog", cc is not None and cc is not catalog)
        held = set(child.tool_registry.names()) | (set(cc.names) | set(cc.deferred) if cc is not None else set())
        ctx.check(f"before the deferred start the helper holds no server tool, got {sorted(held)}",
                  not any(n.startswith("mcp__") for n in held))
        out = _f2_late_connect(controller)
        ctx.check(f"both servers connected late, got {out}", sorted(out["connected"]) == ["fake", "fake2"])
        p_names, p_pool = list(catalog.names), sorted(catalog.deferred)
        p_reg = catalog.registry.names()
        c_names = child.tool_registry.names()
        ctx.check(f"the late alwaysLoad tool is not pushed into the running helper, got {c_names}",
                  not any(n.startswith("mcp__") for n in c_names))
        if cc is None:
            return
        result, tctx = _f13_search(child, "select:mcp__fake__echo")
        text = json.dumps(result.content) if isinstance(result.content, list) else str(result.content)
        ctx.check(f"the helper's ToolSearch finds and loads the late server's tool, got {text[:200]}",
                  "not found" not in text and child.tool_registry.get("mcp__fake__echo") is not None)
        echo = child.tool_registry.get("mcp__fake__echo")
        if echo is not None:
            called = echo.run({"text": "f13-hello"}, tctx)
            ctx.check(f"the call runs, got {called.content!r}",
                      not called.is_error and "f13-hello" in str(called.content))
        result, _ = _f13_search(child, "select:mcp__fake2__echo")
        ctx.check("the alwaysLoad server's tool is found the same way",
                  child.tool_registry.get("mcp__fake2__echo") is not None)
        result, _ = _f13_search(child, "select:mcp__fake__slow_tool")
        ctx.check(f"a deny rule still holds, got {str(result.content)[:200]}",
                  child.tool_registry.get("mcp__fake__slow_tool") is None
                  and "mcp__fake__slow_tool" not in cc.deferred)
        nc = narrow.session_catalog
        if nc is not None:
            nc.search("select:mcp__fake__echo")
        ctx.check(f"a `tools: Read` helper still finds nothing, got {narrow.tool_registry.names()}",
                  narrow.tool_registry.names() == ["Read"] and (nc is None or not nc.deferred))
        ctx.check(f"the parent's catalog is exactly what it was, got {catalog.names} {sorted(catalog.deferred)}",
                  catalog.names == p_names and sorted(catalog.deferred) == p_pool
                  and catalog.registry.names() == p_reg)
    finally:
        _f2_close(controller)
        _f2_restore(saved)


@test
def test_the_tui_worker_hands_the_connected_servers_to_the_catalog(ctx: Ctx):
    app_src = (REPO_DIR / "halo_harness" / "tui" / "app.py").read_text(encoding="utf-8")
    ctx.check("the worker hands what connected to the controller",
              "take_connected_servers" in app_src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
