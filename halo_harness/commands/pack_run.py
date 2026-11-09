"""halo_harness.commands.pack_run -- a pack's command that runs a program of the pack instead of prompting the model
(Halo 3.3.13.0 R3; docs/EXTENSION_API.md "Skills, commands, hooks and MCP").

A pack's `commands/<name>.md` whose frontmatter says `run:` (exec form, the substitutions hooks use) is a command the
session runs itself, with no model call: `/<pack>:<name> <words>` (and the entry command `/<pack>`) starts the program
in the pack's folder with the words after it as its arguments, and its output is the command's answer in the
transcript (stdout; with an exit other than 0, the last stderr lines and the code too).

    ---
    description: "Signal: the bridge's state, pairing and the phones"
    argument-hint: "[status | pair | unpair <n> | ...]"
    run: ["${halo_python}", "${CLAUDE_PLUGIN_ROOT}/halo_signal/ctl.py"]
    ---
    The body is what the command says when the program cannot run (shown, never sent to the model).

The program gets the environment a pack hook gets (Halo's provider keys left out) plus CLAUDE_PLUGIN_ROOT,
CLAUDE_PROJECT_DIR (the session's folder), HALO_PACK_ID and HALO_COMMAND; it is stopped after TIMEOUT_S. A folder
that is not a pack (a plain Claude plugin) keeps the prompt form: `run:` is read only in a pack's folder.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

TIMEOUT_S = 120
MAX_CHARS = 20000


def run_of(fm: dict, root: Path):
    """The frontmatter's `run` when `root` is a pack's folder and it names a command of the pack; else None."""
    from halo_harness.packs.interpreter import is_pack_root
    from halo_harness.packs.manifest_policy import script_rel
    run = fm.get("run") if isinstance(fm, dict) else None
    if run is None or not is_pack_root(root):
        return None
    _rel, why = script_rel(run)
    return None if why else run


def _words(args_text: str) -> "list[str]":
    try:
        return shlex.split(args_text or "", posix=True)
    except ValueError:
        return (args_text or "").split()


def make_run(root: Path, run, name: str, body: str):
    def _run(args_text: str, facade) -> str:
        from halo_harness.packs.interpreter import pack_env
        from halo_harness.packs.manifest_policy import run_argv
        from halo_harness.providers.config import tool_child_env
        cwd = str(getattr(facade, "cwd", "") or os.getcwd())
        env = tool_child_env(dict(os.environ))
        env.update({"CLAUDE_PLUGIN_ROOT": str(root), "CLAUDE_PROJECT_DIR": cwd, "HALO_PACK_ID": root.name,
                    "HALO_COMMAND": name})
        argv = run_argv({"run": run}, root) + _words(args_text)
        try:
            r = subprocess.run(argv, cwd=str(root), env=pack_env(root, env), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=TIMEOUT_S, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return f"/{name}: no answer in {TIMEOUT_S} s; it was stopped"
        except OSError as e:
            return f"/{name}: it did not start ({type(e).__name__}: {e})\n{body.strip()}".rstrip()
        out = (r.stdout or "").rstrip()
        if r.returncode != 0:
            err = [ln for ln in (r.stderr or "").splitlines() if ln.strip()][-8:]
            out = "\n".join([out] + err + [f"(/{name} exit {r.returncode})"]).strip()
        return (out or f"/{name}: done")[:MAX_CHARS]
    return _run
