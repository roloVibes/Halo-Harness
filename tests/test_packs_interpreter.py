"""tests.test_packs_interpreter -- a pack's hook and MCP server run with
Halo's own Python (Halo 3.2.0.0 R7, halo_harness/packs/interpreter.py; the
R6 open point): `${halo_python}` in a hooks.json entry (shell `command`
quoted, exec-form `args` plain) and in `.mcp.json` (`command`, `args`)
expands to `sys.executable`; every process the plugin-root channel starts
from a pack's folder gets Halo's package root first on PYTHONPATH, a plain
plugin folder neither; the shipped pack uses the placeholder, and its hook,
started the way a session starts it, imports `halo_harness.ext` and writes
its note into the pack's data folder (the test home's, never the real one).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import DOC_REVIEW, PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_the_placeholder_and_its_quoting(ctx: Ctx):
    from halo_harness.packs import interpreter as I
    entry = I.expand_hook({"type": "command", "command": "${halo_python} x.py", "args": ["${halo_python}", "y.py"], "timeout": 5})
    ctx.check(f"exec form: the plain path, got {entry['args']}", entry["args"] == [sys.executable, "y.py"] and entry["timeout"] == 5)
    ctx.check(f"shell form: quoted for the hook's shell, got {entry['command']!r}", entry["command"] == f"{I.shell_python()} x.py"
              and I.shell_python().strip("'\"").replace("/", os.sep).lower() == sys.executable.replace("/", os.sep).lower())
    if os.name == "nt":
        ctx.check("on Windows the shell path has forward slashes (Git Bash runs it)", "\\" not in I.shell_python())
    ctx.check("an entry without it is unchanged", I.expand_hook({"command": "echo hi"}) == {"command": "echo hi"})
    block = I.expand_hooks({"PostToolUse": [{"matcher": "Write", "hooks": [{"args": ["${halo_python}"]}]}], "Bad": "x"})
    ctx.check("a whole hooks block", block["PostToolUse"][0]["hooks"][0]["args"] == [sys.executable] and block["Bad"] == "x")
    d = Path(tempfile.mkdtemp(prefix="not-a-pack-"))
    ctx.check("a folder without pack.yaml gets no PYTHONPATH", I.pack_env(d, {"A": "1"}) == {"A": "1"})
    (d / "pack.yaml").write_text("id: x\n", encoding="utf-8")
    env = I.pack_env(d, {"PYTHONPATH": "elsewhere"})
    ctx.check(f"a pack's folder: Halo's package root first, the rest kept, got {env['PYTHONPATH']}",
              env["PYTHONPATH"].split(os.pathsep) == [I.package_root(), "elsewhere"])
    ctx.check("the package root holds halo_harness", (Path(I.package_root()) / "halo_harness" / "__init__.py").is_file())


@test
def test_the_shipped_pack_uses_it(ctx: Ctx):
    mcp = json.loads((DOC_REVIEW / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["lint"]
    hooks = json.loads((DOC_REVIEW / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["PostToolUse"][0]["hooks"][0]
    ctx.check(f"the lint server's command, got {mcp}", mcp["command"] == "${halo_python}")
    ctx.check(f"the hook's exec form, got {hooks}", hooks["args"][0] == "${halo_python}")
    doc = (Path(__file__).resolve().parent.parent / "docs" / "PACKS.md").read_text(encoding="utf-8")
    ctx.check("docs/PACKS.md explains it", "${halo_python}" in doc and "PYTHONPATH" in doc)


@test
def test_a_session_starts_them_with_halos_python(ctx: Ctx):
    from halo_harness.config.plugins import discover_plugin_mcp_servers
    from halo_harness.hooks import HookRunner, load_plugin_hooks, run_command_hook
    from halo_harness.packs import interpreter as I
    with PacksHome() as h:
        h.install(h.source(), enable=True, grants=["hooks", "mcp:lint"])
        root = h.packs / "doc-review"
        servers, notices = discover_plugin_mcp_servers(env=dict(os.environ), extra_roots=[str(root)])
        cfg = servers.get("plugin_doc-review_lint")
        ctx.check(f"the lint server: Halo's Python, the pack's script, got {cfg and (cfg.command, cfg.args)} {notices}",
                  cfg is not None and cfg.command == sys.executable and Path(cfg.args[0]) == root / "mcp" / "lint_server.py")
        ctx.check("its env puts Halo's package root first on PYTHONPATH",
                  cfg is not None and cfg.env.get("PYTHONPATH", "").split(os.pathsep)[0] == I.package_root())
        plain = Path(tempfile.mkdtemp(prefix="plain-plugin-"))
        (plain / ".mcp.json").write_text(json.dumps({"mcpServers": {"s": {"command": "${halo_python}", "args": []}}}), encoding="utf-8")
        other, n2 = discover_plugin_mcp_servers(env=dict(os.environ), extra_roots=[str(plain)])
        cfg2 = next((v for k, v in other.items() if k.endswith("_s")), None)  # the plain plugin's own server
        seen = (f"servers {sorted(other)} picked {(cfg2.command if cfg2 else None)!r} vs {sys.executable!r} "
                f"env {sorted((cfg2.env or {}) if cfg2 else [])} notices {n2[:2]}")
        ctx.check(f"a plain plugin: the placeholder expands, no PYTHONPATH added, got {seen}",
                  cfg2 is not None and cfg2.command == sys.executable and "PYTHONPATH" not in (cfg2.env or {}))
        hook = load_plugin_hooks(root)["PostToolUse"][0]
        ctx.check(f"the hook: Halo's Python, exec form, got {hook.args}", hook.args == [sys.executable, f"{root}/hooks/note.py"])
        runner = HookRunner({}, cwd=h.repo, session_id="s", transcript_path=None, effective_env=dict(os.environ))
        env = runner._env_for(hook)
        ctx.check("the hook's env: Halo's package root first on PYTHONPATH", env["PYTHONPATH"].split(os.pathsep)[0] == I.package_root())
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": "docs/guide.md"}}
        result = run_command_hook(hook, payload, cwd=h.repo, env=env)
        note = h.packs / ".data" / "doc-review" / "last-write.txt"
        ctx.check(f"it ran and imported halo_harness.ext: its note is in the test home's data folder, got {result}",
                  note.is_file() and note.read_text(encoding="utf-8").strip() == "docs/guide.md")


@test
def test_pythonpath_alone_lets_another_python_import_ext(ctx: Ctx):
    from halo_harness.packs import interpreter as I
    d = Path(tempfile.mkdtemp(prefix="pack-py-"))
    (d / "pack.yaml").write_text("id: x\n", encoding="utf-8")
    base = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    probe = [sys.executable, "-S", "-c", "import halo_harness.ext as e; print(e.API_VERSION)"]  # -S: no site-packages
    bare = subprocess.run(probe, cwd=str(d), env=base, capture_output=True, text=True, timeout=60)
    ctx.check("without it, a Python with no site-packages cannot import Halo", bare.returncode != 0)
    run = subprocess.run(probe, cwd=str(d), env=I.pack_env(d, base), capture_output=True, text=True, timeout=60)
    ctx.check(f"with the pack's env it can, got {run.returncode} {run.stdout!r} {run.stderr[-200:]!r}",
              run.returncode == 0 and run.stdout.strip() == "1.0")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
