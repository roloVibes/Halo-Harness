"""halo_harness.packs.interpreter -- the Python a pack's hook and MCP server
run with (Halo 3.2.0.0 R7; docs/PACKS.md "A pack's own Python"), and the
plugin root a hook's shell command sees (3.2.1.0 R4).

A pack's `.mcp.json` and `hooks/hooks.json` commands may name Halo's own
interpreter as `${halo_python}`; Halo expands it, when it starts them, to
`sys.executable` (the Python Halo runs in, where `halo_harness.ext` imports):

    .mcp.json        {"command": "${halo_python}", "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/lint_server.py"]}
    hooks/hooks.json {"type": "command", "command": "${halo_python} ${CLAUDE_PLUGIN_ROOT}/hooks/note.py"}

In an MCP server's `command` and `args` and a hook's exec-form `args` both
paths go in as they are; in a hook's shell `command` (run by Git Bash on
Windows, /bin/sh elsewhere) each goes in with forward slashes on Windows and
quoted for where it sits: bare, it is quoted when it holds a space or another
character the shell reads (`${halo_python}` is always quoted); inside the
command's own "..." or '...' it is escaped for those quotes instead. A hook
with `shell: powershell` gets the plugin root as it is (PowerShell keeps
backslashes). Every process the plugin-root channel starts from a pack's
folder also gets `PYTHONPATH` with Halo's package root first, so a pack's
script run by another `python` imports `halo_harness.ext` too. A folder that
is not a pack (no pack.yaml) gets neither.

    PLACEHOLDER / ROOT              "${halo_python}" / "${CLAUDE_PLUGIN_ROOT}"
    python_path()                   sys.executable
    shell_python()                  the same, quoted for a hook's shell command
    shell_path(path)                a path with forward slashes on Windows (as Git Bash reads it)
    fill_shell(command, values)     each placeholder in a shell command filled for the quotes it sits in
    expand_hook(entry, root)        one hooks.json entry with both placeholders expanded
    pack_env(root, env)             env with PYTHONPATH for a pack's folder (unchanged for any other)
"""

from __future__ import annotations

import os
import re
import shlex
import sys
from pathlib import Path

PLACEHOLDER = "${halo_python}"
NAME = "halo_python"
ROOT = "${CLAUDE_PLUGIN_ROOT}"


def python_path() -> str:
    return sys.executable or "python"


def shell_path(path: str) -> str:
    """`path` as a hook's shell reads it: forward slashes on Windows (Git Bash eats a backslash)."""
    return str(path).replace("\\", "/") if os.name == "nt" else str(path)


def shell_python() -> str:
    if os.name == "nt":
        return '"' + shell_path(python_path()) + '"'
    return shlex.quote(python_path())


def _inside(text: str, quote: str) -> str:
    if quote == "'":
        return text.replace("'", "'\\''")
    return re.sub(r'(["\\$`])', r"\\\1", text)


def fill_shell(command: str, values: dict) -> str:
    """`values` is {placeholder: (bare, path)}: a placeholder outside quotes becomes `bare`, one inside the
    command's "..." or '...' becomes `path` escaped for them. Quotes are read the way sh reads them."""
    out, quote, i = [], "", 0
    while i < len(command):
        hit = next((p for p in values if command.startswith(p, i)), None)
        if hit:
            bare, path = values[hit]
            out.append(_inside(path, quote) if quote else bare)
            i += len(hit)
            continue
        ch = command[i]
        if ch == "\\" and quote != "'" and i + 1 < len(command) and not any(command.startswith(p, i + 1) for p in values):
            out.append(command[i:i + 2])
            i += 2
            continue
        if ch in "'\"" and quote in ("", ch):
            quote = "" if quote else ch
        out.append(ch)
        i += 1
    return "".join(out)


def package_root() -> str:
    """The folder that holds the `halo_harness` package (a checkout's root, or a venv's site-packages)."""
    import halo_harness
    return str(Path(halo_harness.__file__).resolve().parent.parent)


def is_pack_root(root) -> bool:
    try:
        return bool(root) and (Path(root) / "pack.yaml").is_file()
    except OSError:
        return False


def expand_hook(entry: dict, root=None) -> dict:
    """A hooks.json command entry: `command` (shell text) gets each path filled for its quotes, `args` (exec
    form) the plain Python; `root` (the plugin's folder) fills `${CLAUDE_PLUGIN_ROOT}` in `command` only."""
    if not isinstance(entry, dict):
        return entry
    out = dict(entry)
    cmd = out.get("command")
    if isinstance(cmd, str) and (PLACEHOLDER in cmd or (root and ROOT in cmd)):
        if out.get("shell") == "powershell":
            cmd = cmd.replace(PLACEHOLDER, shell_python())
            out["command"] = cmd.replace(ROOT, str(root)) if root else cmd
        else:
            values = {PLACEHOLDER: (shell_python(), shell_path(python_path()))}
            if root:
                values[ROOT] = (shlex.quote(shell_path(root)), shell_path(root))
            out["command"] = fill_shell(cmd, values)
    if isinstance(out.get("args"), list):
        out["args"] = [a.replace(PLACEHOLDER, python_path()) if isinstance(a, str) else a for a in out["args"]]
    return out


def expand_hooks(hooks_block: dict, root=None) -> dict:
    """Every entry of a hooks.json `{event: [{matcher, hooks: [...]}]}` block through `expand_hook`."""
    out = {}
    for event, groups in (hooks_block or {}).items():
        if not isinstance(groups, list):
            out[event] = groups
            continue
        out[event] = [{**g, "hooks": [expand_hook(h, root) for h in g["hooks"]]}
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
