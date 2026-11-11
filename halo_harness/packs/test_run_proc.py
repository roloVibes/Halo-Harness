"""halo_harness.packs.test_run_proc -- `halo pack test`'s checks that start a process (Halo 3.3.12.0 R4): the entry
command against a fake session, each hook once with a sample event of its matcher, each MCP server's handshake, each
policy against two sample calls, each Setup check block, a bundle module's syntax. Every process is waited for (or
stopped at its time limit) before the next check; none outlives the check that started it. A part that needs the
network or a model is skipped with its line, and so is one whose program is not on this machine.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

SHELL_WORDS = ("echo", "printf", "true", "false", "test", "cd", "exit", "export", "sh", "bash", ":", "cat", "env")


def _env(r, extra=None) -> dict:
    from halo_harness.packs.interpreter import pack_env
    from halo_harness.providers.config import tool_child_env
    env = tool_child_env(dict(os.environ))
    env.update({"CLAUDE_PLUGIN_ROOT": str(r.root), "CLAUDE_PROJECT_DIR": str(r.project), "HALO_PACK_ID": r.pack.id,
                "HALO_PACK_TEST": "1", **(extra or {})})
    return pack_env(r.root, env)


def program_missing(word: str, root) -> str:
    """'' when `word` (a command's program) is here: Halo's Python, a file of the pack, a shell word, on PATH."""
    if not word or "${" in word or word in SHELL_WORDS or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word):
        return ""
    p = Path(word)
    if p.is_absolute() and p.exists() or (Path(root) / word).exists() or shutil.which(word):
        return ""
    return f"{word} is not on PATH here"


def _shell_program(command: str) -> str:
    try:
        words = shlex.split(command or "", posix=True)
    except ValueError:
        return ""
    words = [w for w in words if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w)]
    return words[0] if words else ""


def entry(r) -> None:
    if not r.wants("commands"):
        return
    rel = f"commands/{r.pack.id}.md"
    if not (r.root / rel).is_file():
        r.add("commands", rel, f"no entry command /{r.pack.id}", None, "halo pack new writes one: what the pack is, "
              "its commands, workflows and lineups")
        return
    from halo_harness.commands.registry import Registry
    from halo_harness.packs.scaffold.docs import parts
    cmd = Registry.discover(r.project, home=r.home, plugin_roots=[r.root]).resolve(f"/{r.pack.id}")
    facade = type("FakeSession", (), {"cwd": r.project, "session": None})()
    text = cmd.run("", facade) if cmd is not None and cmd.run else ""
    files = {p.relative_to(r.root).as_posix(): p.read_text(encoding="utf-8", errors="replace")
             for p in r.root.rglob("*") if p.is_file() and p.suffix in (".md", ".yaml")}
    names = [ref for what, ref, _ in parts(r.manifest, files) if what in ("command", "workflow", "lineup")]
    missing = [n for n in names if n not in text]
    r.add("commands", rel, f"/{r.pack.id} runs in a fake session and lists every command, workflow and lineup",
          cmd is not None and bool(text.strip()) and not missing,
          f"list {', '.join(missing)} in it" if missing else "commands/<id>.md is the entry command")


def _sample_event(r, event: str, matcher) -> dict:
    from halo_harness.hooks import build_payload
    words = [w for w in re.split(r"[,|]", str(matcher or "")) if re.match(r"^[A-Za-z0-9_-]+$", w)]
    tool = words[0] if words else "Write"
    target = r.project / "sample.txt"
    target.write_text("hello\nTODO: one sample line\n", encoding="utf-8")
    inputs = {"Write": {"file_path": str(target), "content": target.read_text(encoding="utf-8")},
              "Edit": {"file_path": str(target), "old_string": "hello", "new_string": "hello"},
              "Read": {"file_path": str(target)}, "Bash": {"command": "echo hello"}}
    extra = {}
    if "Tool" in event or event in ("PermissionRequest",):
        extra = {"tool_name": tool, "tool_input": inputs.get(tool, {}), "tool_response": {"ok": True}}
    elif event == "UserPromptSubmit":
        extra = {"prompt": "a sample prompt"}
    return build_payload(event, session_id="pack-test", transcript_path=r.home / "transcript.jsonl", cwd=r.project,
                         permission_mode="default", extra=extra)


def _hook_skip(r, h: dict) -> str:
    from halo_harness.packs.manifest_requires import gated_by
    kind = h.get("type", "command")
    if kind == "http":
        return "an http hook reaches the network; halo pack test never does"
    if kind in ("prompt", "agent"):
        return f"a {kind} hook asks a model; halo pack test makes no model call"
    if kind != "command":
        return f"a {kind} hook runs inside a session only"
    test = h.get("halo_test") if isinstance(h.get("halo_test"), dict) else {}
    if test.get("skip"):
        return str(test["skip"])
    argv = h.get("args") if isinstance(h.get("args"), list) else None
    words = [str(a) for a in argv] if argv else [_shell_program(str(h.get("command") or ""))]
    for w in words:
        rel = w.replace("${CLAUDE_PLUGIN_ROOT}", "").lstrip("/\\")
        for e, why in gated_by(r.manifest, rel):
            return f"{why} (pack.yaml requires {e.get('name')})"
    return program_missing(words[0] if words else "", r.root)


def hooks(r) -> None:
    from halo_harness.hooks import HookRunner, _substitute_plugin_root, normalize_hooks, run_command_hook
    from halo_harness.packs.interpreter import expand_hook
    path = r.root / "hooks" / "hooks.json"
    if not r.wants("hooks") or not path.is_file():
        return
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    block = raw.get("hooks", raw) if isinstance(raw, dict) else {}
    runner = HookRunner({}, cwd=r.project, session_id="pack-test", transcript_path=r.home / "t.jsonl",
                        effective_env=dict(os.environ))
    for event, groups in block.items() if isinstance(block, dict) else []:
        for g in groups if isinstance(groups, list) else []:
            for h in g.get("hooks") or [] if isinstance(g, dict) else []:
                what = f"{event} hook {' '.join(map(str, h.get('args') or [])) or h.get('command')}"
                skip = _hook_skip(r, h)
                if skip:
                    r.add("hooks", "hooks/hooks.json", f"{what}: skipped, {skip}", None)
                    continue
                entry = _substitute_plugin_root(expand_hook(h, str(r.root)), str(r.root))
                hook = normalize_hooks({event: [{"matcher": g.get("matcher"), "hooks": [entry]}]},
                                       default_source="plugin", plugin_root=str(r.root))[event][0]
                result = run_command_hook(hook, _sample_event(r, event, g.get("matcher")), cwd=r.project,
                                          env=runner._env_for(hook, event))
                want = int((h.get("halo_test") or {}).get("exit", 0)) if isinstance(h.get("halo_test"), dict) else 0
                out = result.stdout.strip()
                bad_json = out.startswith("{") and _not_json(out)
                tail = (result.stderr.strip().splitlines() or [""])[-1]
                r.add("hooks", "hooks/hooks.json", f"{what} runs once with a sample {event} event",
                      result.exit_code == want and not bad_json,
                      f"exit {result.exit_code} (want {want}){': ' + tail if tail else ''}" if result.exit_code != want
                      else "its stdout starts with { but is not JSON")


def _not_json(text: str) -> bool:
    try:
        json.loads(text)
        return False
    except ValueError:
        return True


def mcp(r) -> None:
    from halo_harness.config.plugins import _discover_one_plugin_root_mcp_servers
    from halo_harness.packs.manifest import mcp_servers
    from halo_harness.packs.manifest_requires import gated_by
    from halo_harness.packs.test_run_mcp import declared_tools, handshake
    servers = mcp_servers(r.root) if r.wants("mcp") or r.wants("integration") else {}
    resolved, notices = {}, []
    _discover_one_plugin_root_mcp_servers(r.pack.id, r.root, env=_env(r), resolved=resolved, notices=notices,
                                          cwd=r.project)
    for name, raw in sorted(servers.items()):
        cfg = next((c for k, c in resolved.items() if k.endswith(f"_{name}")), None)
        gate = gated_by(r.manifest, f"mcp:{name}")
        skip = ("a server reached by url is on the network; halo pack test never is" if isinstance(raw, dict)
                and raw.get("url") else f"{gate[0][1]} (pack.yaml requires {gate[0][0].get('name')})" if gate
                else program_missing(str((raw or {}).get("command") or ""), r.root))
        if skip:
            r.add("mcp", ".mcp.json", f"MCP server {name}: skipped, {skip}", None)
            continue
        tools, line = handshake(cfg, _env(r, cfg.env if cfg else None), r.project, r.timeout)
        r.add("mcp", ".mcp.json", f"MCP server {name} starts, answers initialize and tools/list ({len(tools)} tools), "
              "and stops", not line, line)
        want = declared_tools(r, name)
        missing = [t for t in want if t not in tools]
        if want:
            r.add("mcp", ".mcp.json", f"MCP server {name} has the tools the pack names ({', '.join(want)})",
                  not line and not missing, f"tools/list lacks {', '.join(missing)}")


def policy(r) -> None:
    from halo_harness.packs import policy as P
    from halo_harness.packs.manifest_policy import KNOWN_TOOLS
    for p in P.declared(r.pack) if r.wants("policy") else []:
        rel = next((a.replace(str(r.root), "").lstrip("/\\") for a in p.argv if str(r.root) in a), "pack.yaml")
        tool_in = next((t for t in p.tools if t != "*"), "Write")
        outside = next((t for t in ("Read", "Grep", "Glob", "Bash") + KNOWN_TOOLS if p.tools and t not in p.tools
                        and "*" not in p.tools), None)
        for tool in [tool_in] + ([outside] if outside else []):
            sample = {"file_path": str(r.project / "notes.txt"), "content": "a sample"} if tool != "Bash" else {"command": "ls"}
            req = P.request(p, tool, sample, cwd=r.project, session="pack-test", mode=(p.modes or (None,))[0])
            v = P.ask(p, req, budget_ms=int(r.timeout * 1000), keep=False, log=False)
            if not v.asked:
                r.add("policy", rel, f"policy {p.id}: a {tool} call is not asked (when.tools does not name it)", True)
            else:
                r.add("policy", rel, f"policy {p.id} answers a {tool} call in shape ({v.action}: {v.reason})",
                      not v.error, f"{v.error}: answer one JSON line {{id, verdict: allow|deny|ask, reason, rule}} "
                      f"within {int(r.timeout * 1000)} ms")


def setup(r) -> None:
    from halo_harness.packs.manifest_setup import setup_of
    from halo_harness.checks.pack import run_block
    from halo_harness.checks.run import CheckFailed
    ctx = type("Ctx", (), {"cwd": r.project, "state_dir": None})()
    for e in setup_of(r.manifest) if r.wants("setup") else []:
        if e.get("kind") != "check":
            r.add("setup", "pack.yaml", f"Setup block {e.get('id')} ({e.get('kind')}) reads clean", True)
            continue
        from halo_harness.packs.manifest_policy import script_rel  # 3.3.13.0 R3: a check a missing tool gates
        from halo_harness.packs.manifest_requires import gated_by
        gate = gated_by(r.manifest, script_rel(e.get("run"))[0])
        if gate:
            r.add("setup", "pack.yaml", f"Setup check {e.get('id')}: skipped, {gate[0][1]} (pack.yaml requires "
                  f"{gate[0][0].get('name')})", None)
            continue
        try:
            lines, ok = run_block(r.pack, e, ctx), True
        except CheckFailed as ex:
            lines, ok = list(ex.args[0] if ex.args else []), False
        r.add("setup", "pack.yaml", f"Setup check {e.get('id')} runs green", ok, "; ".join(map(str, lines)))


def es_module_lines(path: Path, timeout: float) -> "list[str]":
    """[] when `path` reads as an ES module exporting `mount`; `node --check` too when node is on PATH."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"export\s+(default\s+)?(async\s+)?function\s+mount\b|export\s+(const|let)\s+mount\b|"
                     r"export\s*\{[^}]*\bmount\b", text):
        return ["it does not export mount (export function mount(el, api) { ... })"]
    node = shutil.which("node")
    if not node:
        return []
    import tempfile
    with tempfile.TemporaryDirectory(prefix="halo-pack-test-") as d:
        copy = Path(d) / "module.mjs"
        copy.write_text(text, encoding="utf-8")
        try:
            done = subprocess.run([node, "--check", str(copy)], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return []
    err = [ln for ln in done.stderr.splitlines() if "Error" in ln]
    return [f"node --check: {err[0].strip() if err else 'exit ' + str(done.returncode)}"] if done.returncode else []
