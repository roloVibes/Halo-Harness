"""halo_harness.packs.interpreter -- the Python a pack's hook and MCP server
run with (Halo 3.2.0.0 R7; docs/PACKS.md "A pack's own Python").

A pack's `.mcp.json` and `hooks/hooks.json` commands may name Halo's own
interpreter as `${halo_python}`; Halo expands it, when it starts them, to
`sys.executable` (the Python Halo runs in, where `halo_harness.ext` imports):

    .mcp.json        {"command": "${halo_python}", "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/lint_server.py"]}
    hooks/hooks.json {"type": "command", "command": "${halo_python} ${CLAUDE_PLUGIN_ROOT}/hooks/note.py"}

In an MCP server's `command` and `args` and a hook's exec-form `args` the
path goes in as it is; in a hook's shell `command` it is quoted for the
shell the hook runs in (forward slashes on Windows, where Git Bash runs it).
Every process the plugin-root channel starts from a pack's folder also gets
`PYTHONPATH` with Halo's package root first, so a pack's script run by
another `python` imports `halo_harness.ext` too. A folder that is not a pack
(no pack.yaml) gets neither.

    PLACEHOLDER                     "${halo_python}"
    python_path()                   sys.executable
    shell_python()                  the same, quoted for a hook's shell command
    expand_hook(entry)              one hooks.json entry with the placeholder expanded
    pack_env(root, env)             env with PYTHONPATH for a pack's folder (unchanged for any other)
"""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

PLACEHOLDER = "${halo_python}"
NAME = "halo_python"


def python_path() -> str:
    return sys.executable or "python"


def shell_python() -> str:
    if os.name == "nt":
        return '"' + python_path().replace("\\", "/") + '"'
    return shlex.quote(python_path())


def package_root() -> str:
    """The folder that holds the `halo_harness` package (a checkout's root, or a venv's site-packages)."""
    import halo_harness
    return str(Path(halo_harness.__file__).resolve().parent.parent)


def is_pack_root(root) -> bool:
    try:
        return bool(root) and (Path(root) / "pack.yaml").is_file()
    except OSError:
        return False


def expand_hook(entry: dict) -> dict:
    """A hooks.json command entry: `command` (shell text) gets the quoted path, `args` (exec form) the plain one."""
    if not isinstance(entry, dict):
        return entry
    out = dict(entry)
    if isinstance(out.get("command"), str) and PLACEHOLDER in out["command"]:
        out["command"] = out["command"].replace(PLACEHOLDER, shell_python())
    if isinstance(out.get("args"), list):
        out["args"] = [a.replace(PLACEHOLDER, python_path()) if isinstance(a, str) else a for a in out["args"]]
    return out


def expand_hooks(hooks_block: dict) -> dict:
    """Every entry of a hooks.json `{event: [{matcher, hooks: [...]}]}` block through `expand_hook`."""
    out = {}
    for event, groups in (hooks_block or {}).items():
        if not isinstance(groups, list):
            out[event] = groups
            continue
        out[event] = [{**g, "hooks": [expand_hook(h) for h in g["hooks"]]}
                      if isinstance(g, dict) and isinstance(g.get("hooks"), list) else g for g in groups]
    return out


def pack_env(root, env: dict) -> dict:
    """`env` with Halo's package root first on PYTHONPATH when `root` is a pack's folder."""
    if not is_pack_root(root):
        return env
    out = dict(env)
    rest = out.get("PYTHONPATH") or os.environ.get("PYTHONPATH") or ""
    parts = [package_root()] + [p for p in rest.split(os.pathsep) if p and p != package_root()]
    out["PYTHONPATH"] = os.pathsep.join(parts)
    return out
