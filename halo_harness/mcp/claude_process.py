"""halo_harness.mcp.claude_process -- the installed `claude` binary as the
claude.ai connectors bridge spawns it (3.1.5.0 R1: moved here from the
removed `cc:` route's `providers/cc_models.py`, `agent/cc_process.py` and
`providers/config.cc_child_env`).

Three pieces:
- `resolve_claude_launch_argv` / `ClaudeCodeNotFoundError`: the argv prefix
  for `claude` (or a test's fake stand-in through HALO_CLAUDE_EXE).
- `claude_child_env`: the environment a `claude` child runs in -- the tool
  child env minus every ANTHROPIC_* / CLAUDE* variable, so the binary's own
  claude.ai login is what a connector call uses.
- `ClaudeCodeProcess`: one `claude -p` stream-json subprocess in its own
  process group, so an early kill reaches its whole tree.
"""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import threading
from collections import deque
from pathlib import Path
from typing import Optional


class ClaudeCodeNotFoundError(Exception):
    """No `claude` binary could be resolved (HALO_CLAUDE_EXE/legacy
    BRIDGE_CLAUDE_EXE unset, and none on PATH or at ~/.local/bin)."""


def resolve_claude_launch_argv() -> "list[str]":
    """argv PREFIX for launching the claude binary (or, in a test, a fake
    stand-in). `HALO_CLAUDE_EXE` (legacy `BRIDGE_CLAUDE_EXE`), when set, is
    shlex-split -- a deliberate difference from `mcp_setup.find_claude_exe()`'s
    single-path contract (used for --chrome): a test's fake claude is a
    Python script, which Windows' CreateProcess cannot exec directly, so a
    test points this at `"<python> <script>"` and gets a working argv prefix
    on every platform. posix=True (even on Windows) is the only mode that
    strips quotes; every path-bearing token must be double-quoted, since a
    bare unquoted backslash path is mangled in that mode. Falls back to
    `mcp_setup.find_claude_exe()` wrapped as a one-element list; raises
    ClaudeCodeNotFoundError (never returns None/[]) when nothing resolves."""
    from halo_harness.config.paths import env_compat
    env_val = env_compat("CLAUDE_EXE")
    if env_val:
        return shlex.split(env_val, posix=True)
    from halo_harness.mcp_setup import find_claude_exe
    exe = find_claude_exe()
    if not exe:
        raise ClaudeCodeNotFoundError(
            "claude executable not found (HALO_CLAUDE_EXE unset; looked on PATH and ~/.local/bin)"
        )
    return [exe]


def claude_child_env(env: dict, *, env_file_path: Optional[Path] = None) -> dict:
    """Everything `providers.config.tool_child_env` already strips PLUS
    every ANTHROPIC_* and CLAUDE* variable (CLAUDECODE, CLAUDE_CODE_*,
    CLAUDE_EFFORT, CLAUDE_PROJECT_DIR, ...), so the installed `claude`
    binary's own claude.ai login is always what it uses -- never an ambient
    ANTHROPIC_API_KEY/AUTH_TOKEN/BASE_URL this process happened to have, and
    never an outer Claude Code session's identity inherited by running
    nested inside one."""
    from halo_harness.providers.config import tool_child_env
    stripped = tool_child_env(env, env_file_path=env_file_path)
    return {k: v for k, v in stripped.items() if not k.startswith("CLAUDE") and not k.startswith("ANTHROPIC_")}


class ClaudeCodeProcess:
    """One `claude -p --input-format stream-json --output-format
    stream-json` subprocess, stdin held open. POSIX: its own process GROUP
    (`start_new_session=True`), so `interrupt`/`kill` reach every
    descendant with no orphans. Windows: a new process group
    (`CREATE_NEW_PROCESS_GROUP`) so `CTRL_BREAK_EVENT` can target it alone.
    utf-8 pipes, never the Windows console codepage (claude prints glyphs
    cp1252 cannot represent)."""

    def __init__(self, argv: list, *, cwd: "Path | str", env: Optional[dict] = None):
        self.argv = list(argv)
        popen_kwargs = dict(
            cwd=str(cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        if env is not None:
            popen_kwargs["env"] = dict(env)
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True
        self._proc = subprocess.Popen(argv, **popen_kwargs)
        self._stdin_lock = threading.Lock()
        self._stderr_buf: "deque[str]" = deque(maxlen=200)
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True,
                                                 name=f"claude-stderr-{self._proc.pid}")
        self._stderr_thread.start()

    def _drain_stderr(self) -> None:
        try:
            stream = self._proc.stderr
            if stream is None:
                return
            for line in stream:
                self._stderr_buf.append(line.rstrip("\n"))
        except (OSError, ValueError):
            pass

    @property
    def pid(self) -> int:
        return self._proc.pid

    @property
    def alive(self) -> bool:
        return self._proc.poll() is None

    def send_user_line(self, text: str) -> None:
        self.send_user_blocks([{"type": "text", "text": text}])

    def send_user_blocks(self, blocks: list) -> None:
        """`blocks` are Anthropic Messages API content blocks verbatim --
        claude's `--input-format stream-json` user content accepts the same
        shapes."""
        self._write_line(json.dumps({"type": "user", "message": {"role": "user", "content": blocks}},
                                     ensure_ascii=False))

    def _write_line(self, line: str) -> None:
        with self._stdin_lock:
            stdin = self._proc.stdin
            if stdin is None or stdin.closed:
                raise BrokenPipeError("claude subprocess stdin is closed")
            stdin.write(line + "\n")
            stdin.flush()

    def read_event(self) -> Optional[dict]:
        """One parsed stream-json line from stdout, or None on EOF. A
        blank or unparseable line is skipped, never raised."""
        stdout = self._proc.stdout
        if stdout is None:
            return None
        while True:
            line = stdout.readline()
            if line == "":
                return None
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

    def close_stdin(self) -> None:
        with self._stdin_lock:
            try:
                stdin = self._proc.stdin
                if stdin is not None and not stdin.closed:
                    stdin.close()
            except OSError:
                pass

    def _posix_signal_group(self, sig) -> None:
        """Signal the child's own process group (it was started with
        start_new_session), falling back to the bare pid if the child
        somehow shares this process's group -- never signal our own group."""
        pid = self._proc.pid
        try:
            pgid = os.getpgid(pid)
        except (ProcessLookupError, OSError):
            return
        if pgid != os.getpgid(0):
            os.killpg(pgid, sig)
        else:
            os.kill(pid, sig)

    def interrupt(self) -> None:
        """Process-GROUP stop, no orphans."""
        try:
            if os.name == "nt":
                self._proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self._posix_signal_group(signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass

    def kill(self) -> None:
        try:
            if os.name == "nt":
                self._proc.kill()
            else:
                self._posix_signal_group(signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass

    def wait(self, timeout: Optional[float] = None) -> Optional[int]:
        try:
            rc = self._proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None
        # A non-None rc means the `claude` child has exited -- the moment it
        # can no longer scribble the terminal title, so halo re-asserts its
        # own here (see halo_harness.termtitle).
        from halo_harness.termtitle import reassert_after_claude_child
        reassert_after_claude_child()
        return rc

    def stderr_tail(self, max_chars: int = 2000) -> str:
        text = "\n".join(self._stderr_buf)
        return text[-max_chars:]
