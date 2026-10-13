"""tests.test_review3_b2 -- pins for the 3.0.1.0 review fix pass, round
B-trust (part 2): review items 40, 65, 66 and 139.

  * item 40   `halo design doctor --probe` starts craft servers with the
              key-stripped tool env
  * item 65   `@path` / `@server:uri` mentions in an expanded command or
              skill body (and typed ones) honour the session's deny rules
  * item 66   a `.mcp.json` approval holds in the folder it was given in only
  * item 139  `halo mcp serve` runs its tools with the key-stripped env
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.test_review3_b import _Env

ensure_default_provider_credentials()

test, TESTS = new_registry()


def _engine(cwd: Path, deny=()):
    from halo_harness.permissions import PermissionEngine, parse_rule
    return PermissionEngine(deny_rules=[parse_rule(r, action="deny", base_dir=cwd) for r in deny], cwd=cwd)


# ---- item 40 ------------------------------------------------------------------

@test
def test_item40_probe_starts_servers_without_provider_keys(ctx: Ctx):
    from halo_harness.design import crafts_probe
    from halo_harness.mcp import manager as M
    seen = {}

    class _Handle:
        state, tools, error = "connected", [], None

        def start(self):
            pass

    class _FakeManager:
        def __init__(self, configs, *, tool_env, cwd):
            seen["env"] = tool_env
            self.handles = {name: _Handle() for name in configs}

        def close_all(self, timeout=None):
            pass

    real = M.McpManager
    M.McpManager = _FakeManager
    saved = os.environ.get("OPENROUTER_API_KEY")
    os.environ["OPENROUTER_API_KEY"] = "sk-or-r3b-probe"
    try:
        crafts_probe.probe_craft("photocraft", object())
    finally:
        M.McpManager = real
        if saved is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = saved
    env = seen.get("env") or {}
    ctx.check("the probed server's env has no provider key", "OPENROUTER_API_KEY" not in env
              and "ANTHROPIC_API_KEY" not in env)
    ctx.check("ordinary variables still reach it", "PATH" in env or "Path" in env)


# ---- item 65 ------------------------------------------------------------------

@test
def test_item65_command_body_mention_of_a_denied_file_is_not_read(ctx: Ctx):
    from halo_harness.commands.registry import AT_MENTION_DENIED_NOTE, read_at_mention_snapshots
    cwd = Path(tempfile.mkdtemp(prefix="r3b-at-")).resolve()
    (cwd / ".env").write_text("DB_PASSWORD=hunter2\n", encoding="utf-8")
    (cwd / "notes.txt").write_text("plain notes\n", encoding="utf-8")
    engine = _engine(cwd, deny=("Read(./.env)",))
    snaps = dict(read_at_mention_snapshots("Review @.env and @notes.txt", cwd=cwd, permission_engine=engine))
    joined = "\n".join(snaps.values())
    ctx.check("the denied file's content never appears", "hunter2" not in joined)
    ctx.check("a note says it was not attached", AT_MENTION_DENIED_NOTE in joined)
    ctx.check("an allowed file is still attached", "plain notes" in joined)
    open_snaps = dict(read_at_mention_snapshots("Review @notes.txt", cwd=cwd, permission_engine=_engine(cwd)))
    ctx.check("no deny rule: unchanged", "plain notes" in "\n".join(open_snaps.values()))


@test
def test_item65_headless_threads_the_session_engine(ctx: Ctx):
    from halo_harness.headless import _append_at_mention_snapshots
    cwd = Path(tempfile.mkdtemp(prefix="r3b-at-h-")).resolve()
    (cwd / ".env").write_text("TOKEN=abc123\n", encoding="utf-8")
    logged = []
    session = SimpleNamespace(log=SimpleNamespace(append_snapshot=lambda blocks, kind: logged.append(blocks)),
                              mcp_manager=None, permission_engine=_engine(cwd, deny=("Read(./.env)",)))
    _append_at_mention_snapshots(session, "look at @.env", cwd)
    text = json.dumps(logged)
    ctx.check(f"headless never attaches the denied file, got {text[:120]}", "abc123" not in text and logged)


@test
def test_item65_typed_prompt_mention_honours_read_deny(ctx: Ctx):
    from halo_harness.controller import Controller
    cwd = Path(tempfile.mkdtemp(prefix="r3b-at-t-")).resolve()
    (cwd / ".env").write_text("API=zzz999\n", encoding="utf-8")
    (cwd / "ok.txt").write_text("fine text\n", encoding="utf-8")
    queued = []
    session = SimpleNamespace(mcp_manager=None, permission_engine=_engine(cwd, deny=("Read(./.env)",)),
                              queue_log_write=lambda kind, data: queued.append(data))
    Controller.ingest_at_mentions(SimpleNamespace(session=session, cwd=cwd), "check @.env and @ok.txt")
    text = json.dumps(queued)
    ctx.check(f"the denied file is not attached, got {text[:160]}", "zzz999" not in text)
    ctx.check("the allowed one is", "fine text" in text)


@test
def test_item65_mcp_resource_of_a_denied_server_is_not_read(ctx: Ctx):
    from halo_harness.mcp.mentions import read_server_resource_snapshots
    reads = []

    class _Mgr:
        def resources(self):
            return [("docs", SimpleNamespace(uri="file:///a"))]

        def read_resource(self, server, uri):
            reads.append((server, uri))
            return SimpleNamespace(contents=[SimpleNamespace(text="PRIVATE")])

    cwd = Path(tempfile.mkdtemp(prefix="r3b-at-m-"))
    out = read_server_resource_snapshots("see @docs:file:///a", mcp_manager=_Mgr(),
                                         permission_engine=_engine(cwd, deny=("mcp__docs",)))
    ctx.check(f"no read happened, got {reads}", reads == [] and "PRIVATE" not in json.dumps(out))
    out = read_server_resource_snapshots("see @docs:file:///a", mcp_manager=_Mgr(), permission_engine=_engine(cwd))
    ctx.check("without a deny rule the resource is attached", "PRIVATE" in json.dumps(out))


# ---- item 66 ------------------------------------------------------------------

@test
def test_item66_approval_does_not_cover_another_folder(ctx: Ctx):
    from halo_harness import mcp_setup
    from halo_harness.mcp import manager as M
    with _Env() as e:
        entry = {"command": "./scripts/mcp-server.sh"}
        repos = []
        for name in ("repo-a", "repo-b"):
            d = e.home / name
            d.mkdir()
            (d / ".mcp.json").write_text(json.dumps({"mcpServers": {"srv": entry}}), encoding="utf-8")
            repos.append(d)
        mcp_setup.record_mcp_approval("srv", entry, cwd=repos[0])
        approvals = mcp_setup.load_mcp_approvals()
        a, _ = M.resolve_server_configs(cwd=repos[0], claude_json={}, print_mode=False, approvals=approvals)
        b, _ = M.resolve_server_configs(cwd=repos[1], claude_json={}, print_mode=False, approvals=approvals)
        ctx.check("approved where it was approved", a["srv"].pending_approval is False)
        ctx.check("the same bytes in another folder still ask", b["srv"].pending_approval is True)
        import hashlib
        old_key = hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()
        c, _ = M.resolve_server_configs(cwd=repos[1], claude_json={}, print_mode=False,
                                        approvals={old_key: {"name": "srv"}})
        ctx.check("an old content-only record approves nothing", c["srv"].pending_approval is True)
        ctx.check("reset forgets the folder's own approval",
                  mcp_setup.reset_project_approvals(repos[0] / ".mcp.json") == 1)


# ---- item 139 -----------------------------------------------------------------

@test
def test_item139_serve_tool_context_strips_provider_keys(ctx: Ctx):
    from halo_harness.mcp.serve import serve_tool_context
    saved = os.environ.get("OPENROUTER_API_KEY")
    os.environ["OPENROUTER_API_KEY"] = "sk-or-r3b-serve"
    try:
        tool_ctx = serve_tool_context(Path("."))
        explicit = serve_tool_context(Path("."), {"OPENROUTER_API_KEY": "x", "KEEP": "1"})
    finally:
        if saved is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = saved
    ctx.check("a None env becomes the stripped process env, never None",
              isinstance(tool_ctx.env, dict) and "OPENROUTER_API_KEY" not in tool_ctx.env)
    ctx.check("an explicit env is stripped too", explicit.env == {"KEEP": "1"})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
