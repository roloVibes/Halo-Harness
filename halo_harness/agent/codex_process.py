"""halo_harness.agent.codex_process -- Halo 2.0.3 round 5i part 2: the
`codex exec` subprocess wrapper + argv builder for the `cx:` route.

Architecturally simpler than `agent.cc_process`/`ClaudeCodeProcess`: Codex
has no stdin-streaming protocol (CODEX-RESEARCH.md section 7) -- each Halo
turn is ONE bounded `codex exec [resume <id>] --json -` invocation that runs
to completion and exits, never a long-held process fed one stdin line per
turn. `CodexExecProcess` therefore has no `send_user_line`; pass-B fix
(review finding 4, critical): the WHOLE prompt (preamble, carried
conversation, user text, steer) always rides on stdin instead, written
ONCE via `send_prompt` with the pipe closed right behind it (`codex exec
... -`/`codex exec resume <id> ... -`, both confirmed in their own
`--help`), never on argv -- argv is visible to any local user via
`/proc/<pid>/cmdline` on POSIX, and on Windows the resolved launcher is
often an npm `.cmd` shim that hands argv to cmd.exe for a SECOND, unwanted
parse pass (a quoted `&` truncates the command there, `%VAR%` expands, and
the practical length ceiling is a few KB -- see `resolve_codex_launch_
argv`'s own shim-bypass fix in providers/codex_models.py). The whole
lifecycle is start/send_prompt/read-stdout-lines/wait.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import Optional

from halo_harness.providers.codex_models import resolve_codex_launch_argv

# CODEX-RESEARCH.md section 3: Halo's permission-mode -> (approval_policy,
# sandbox_mode) mapping. Pass-B finding 11 (major): keyed on
# `permissions.PermissionEngine`'s own six real mode names (its own
# docstring: "mode is one of default|acceptEdits|plan|auto|dontAsk|
# bypassPermissions") -- `normalize_permission_mode` only ever maps
# "manual" to "default" before a mode reaches this table, so the OLD
# "bypass"/"manual" keys here never matched a real `.mode` value at all:
# EVERY mode but "auto" fell through to this `.get`'s own "default" row,
# including `bypassPermissions` (`--dangerously-skip-permissions`),
# `dontAsk`, `acceptEdits` and `plan` -- the documented "manual ->
# untrusted/read-only" row was unreachable code.
#   - auto/bypassPermissions: never asks, full access (both mean "allow
#     everything" per permissions.py's own module docstring; Codex has no
#     separate concept for the one difference between them, which deny
#     rules govern only on HALO's own tool dispatch).
#   - default/acceptEdits: Codex's own approval system decides when to
#     interrupt (its coarser sandbox has no separate "ask about edits
#     specifically" the way Halo's own engine does); edits stay confined
#     to the workspace.
#   - dontAsk: never asks (dontAsk's whole point is that an ask never
#     reaches the user), confined to the workspace.
#   - plan: never asks AND read-only -- plan mode never writes at all, so
#     this is also the one row that sidesteps the research's own
#     unconfirmed "an approval request `codex exec` cannot answer" risk
#     by construction (a blocked write just fails, nothing to approve).
_PERMISSION_MODE_TO_CODEX = {
    "auto": ("never", "danger-full-access"),
    "bypassPermissions": ("never", "danger-full-access"),
    "default": ("on-request", "workspace-write"),
    "acceptEdits": ("on-request", "workspace-write"),
    "dontAsk": ("never", "workspace-write"),
    "plan": ("never", "read-only"),
    # Legacy alias: `codex_runtime.py`'s one-shot `cx:` call still passes
    # the literal string "bypass" (pre-engine-name; finding 31, a
    # different, unassigned finding, covers fixing THAT call site) --
    # kept mapped to the same row `auto`/`bypassPermissions` get, so
    # removing the old dead "manual"/"bypass" keys from this table's
    # PRIMARY set doesn't silently change that one caller's behaviour.
    "bypass": ("never", "danger-full-access"),
}


def codex_approval_and_sandbox(permission_mode: str) -> "tuple[str, str]":
    return _PERMISSION_MODE_TO_CODEX.get(permission_mode, _PERMISSION_MODE_TO_CODEX["default"])


# Pass-B finding 13 (major): CODEX-RESEARCH.md section 8 (learn.chatgpt.com/
# docs/config-file/config-reference, confirmed): `model_reasoning_effort`
# accepts exactly low/medium/high/xhigh/max/ultra. Halo's own harness-wide
# `--effort`/`/effort` vocabulary (`providers.profiles.EFFORT_LEVELS`) is
# low/medium/high/xhigh/max -- the SAME five names (a `cx:` route has no
# `model_table.json`/vendored-catalog row of its own, so `resolve_profile`
# falls through to this exact generic set for it, same reasoning the
# "ollama"/"openai-responses" branches already give for why no row lookup
# applies here either) -- so no renaming table is needed, only a allowlist
# narrow enough to never forward a stray value Codex has never heard of
# (`none`/`minimal`, valid on other dialects, are never actually reachable
# here once `clamp_effort` has already narrowed them, but this stays a
# hard allowlist rather than trusting that invariant blindly). `ultra`
# itself is accepted too, even though nothing in Halo ever sends it today,
# since Codex's own set simply has one more rung than Halo's.
_CODEX_REASONING_EFFORT_VALUES = frozenset({"low", "medium", "high", "xhigh", "max", "ultra"})


def codex_reasoning_effort(effort: Optional[str]) -> Optional[str]:
    """`None`/empty (no `--effort`/`/effort` set at all) -> `None`, meaning
    "omit `model_reasoning_effort` entirely" -- Codex then uses its own
    config.toml/default, the same "omitting a field takes the provider's
    own default" contract every other route's effort handling follows. A
    value outside Codex's own accepted set also -> `None`, defensively,
    rather than forwarding something `codex exec` would reject outright."""
    if not effort:
        return None
    return effort if effort in _CODEX_REASONING_EFFORT_VALUES else None


def _repo_root_for_pythonpath() -> str:
    import halo_harness
    return str(Path(halo_harness.__file__).resolve().parent.parent)


def _toml_array_literal(values: "list[str]") -> str:
    return "[" + ", ".join(json.dumps(v) for v in values) + "]"


def build_mcp_override_args(bridge_env_keys: "list[str]") -> "list[str]":
    """One `-c mcp_servers.halo.<field>=<value>` flag per field (CODEX-
    RESEARCH.md section 4) -- the Codex counterpart of `cc_process.
    build_mcp_config`'s inline `--mcp-config` JSON, pointing at the SAME
    `python -m halo_harness.ccbridge` child + `ToolBridgeServer` `cc:`
    already uses.

    Privacy (matches `cc_process.build_mcp_config`'s own H11b finding 16):
    `bridge_env_keys` is a list of VARIABLE NAMES ONLY (the socket path var
    on posix, host/port/TOKEN vars on Windows -- `ToolBridgeServer.
    child_env()`'s own keys), never their VALUES -- those go straight into
    the `codex exec` SUBPROCESS's own environment instead (`turn_body_cx`'s
    `env=` on `CodexExecProcess`, which the MCP child then simply inherits),
    exactly like `cc:` folds `bridge.child_env()` into the claude
    subprocess's env rather than spelling it out in `--mcp-config`'s own
    JSON. `mcp_servers.<id>.env_vars` ("Variables to forward", confirmed
    shape in CODEX-RESEARCH.md section 4) is Codex's own documented
    mechanism for "forward these NAMES from my own env down to the MCP
    child" -- using it means the bridge's per-session token never appears
    in `-c ...=<value>` text at all, so it never shows up in a process
    listing (`Win32_Process.CommandLine`/`ps`) the way a baked-in value
    would."""
    args = [
        "-c", f"mcp_servers.halo.command={json.dumps(sys.executable)}",
        "-c", f"mcp_servers.halo.args={_toml_array_literal(['-m', 'halo_harness.ccbridge'])}",
        "-c", f"mcp_servers.halo.env_vars={_toml_array_literal(['PYTHONPATH'] + list(bridge_env_keys))}",
    ]
    return args


def cx_subprocess_env(base_env: dict, bridge_env: dict) -> dict:
    """The actual env dict for the `codex exec` subprocess itself (never
    for a `-c` override -- see `build_mcp_override_args`'s own docstring):
    `base_env` (the session's stripped child env, `providers.config.
    cc_child_env`) plus `PYTHONPATH` (repo root, so the MCP child can
    `import halo_harness`) plus every `bridge_env` key/value
    (`ToolBridgeServer.child_env()`), which `mcp_servers.halo.env_vars`
    then forwards by name down to that child."""
    env = dict(base_env)
    existing_pp = env.get("PYTHONPATH", "")
    repo_root = _repo_root_for_pythonpath()
    env["PYTHONPATH"] = os.pathsep.join([repo_root, existing_pp]) if existing_pp else repo_root
    env.update({str(k): str(v) for k, v in bridge_env.items()})
    return env


def build_cx_argv(*, model: str, prompt: str, resume_id: Optional[str], permission_mode: str,
                   mcp_override_args: "list[str]", ephemeral: bool = False,
                   image_paths: Optional[list] = None, prompt_via_stdin: bool = False,
                   effort: Optional[str] = None) -> list:
    """`resume_id=None` -> a fresh `codex exec ...`; otherwise `codex exec
    resume <id> ...`. `--skip-git-repo-check` always (a Halo session cwd
    need not be a git repo). `--ephemeral` only for the stateless one-shot
    small-model call (mirrors `--no-session-persistence` on `cc:`) --
    `turn_body_cx`'s own multi-turn flow never sets it, so Codex keeps a
    resumable session on disk.

    Pass-B finding 3 (critical): the sandbox is ALWAYS passed as `-c
    sandbox_mode=<mode>`, for a fresh `exec` AND a `resume` alike --
    `codex exec resume` has no `-s/--sandbox` option at all (confirmed:
    `codex exec resume -s read-only --help` -> "error: unexpected
    argument '-s' found"; `-c sandbox_mode=...` parses on both
    subcommands), so a session's SECOND and later turns -- every one of
    them a `resume` -- used to fail at argument parsing before the model
    ever saw anything.

    Pass-B finding 4 (critical): `prompt_via_stdin=True` (set by `codex_
    turn.py`'s real turn path only -- left False, its original default,
    for `codex_runtime.one_shot_cx_call`'s plain `subprocess.run` call,
    which is out of this fix's scope; see that function's own docstring)
    ends the argv with the bare positional `-` instead of the prompt text
    itself. The caller is then responsible for writing `prompt` to the
    child's own stdin (`CodexExecProcess.send_prompt`) -- see this
    module's own docstring for why argv is never where a prompt belongs.

    Pass-B finding 13 (major): `effort` (Halo's `--effort`/`/effort`,
    already clamped to the harness-wide set by the time a `cx:` session
    carries one) rides as its own `-c model_reasoning_effort=<value>` on
    EVERY invocation, a fresh `exec` and a `resume` alike -- same "both
    values on every call" shape `approval_policy`/`sandbox_mode` already
    use just above. `None` (unset, or a value `codex_reasoning_effort`
    doesn't recognize) omits the flag entirely, same as every other
    route's own "omit means take the provider's own default" contract."""
    approval_policy, sandbox_mode = codex_approval_and_sandbox(permission_mode)
    argv = resolve_codex_launch_argv() + ["exec"]
    if resume_id:
        argv += ["resume", resume_id]
    argv += [
        "--json", "--skip-git-repo-check", "-m", model,
        "-c", f"approval_policy={approval_policy}", "-c", f"sandbox_mode={sandbox_mode}",
    ]
    mapped_effort = codex_reasoning_effort(effort)
    if mapped_effort:
        argv += ["-c", f"model_reasoning_effort={mapped_effort}"]
    argv += mcp_override_args
    if ephemeral:
        argv.append("--ephemeral")
    for path in (image_paths or []):
        argv += ["-i", str(path)]
    argv.append("-" if prompt_via_stdin else prompt)
    return argv


def _kill_process_tree(proc: "subprocess.Popen") -> None:
    """Pass-B finding 14 (major): a bounded one-shot codex call's own
    timeout watchdog. `proc.kill()` alone (all `subprocess.run`'s own
    `timeout=` ever does internally) only reaches the ONE process this
    handle names -- on Windows that is often the resolved launcher
    (cmd.exe running the npm `.cmd` shim, or the `node` process), never
    whatever it goes on to spawn beneath it, so `communicate()` then
    blocks on a still-running grandchild that still holds the stdout/
    stderr pipes open, past any timeout this function was ever given.
    Verified: `subprocess.run([<.cmd shim whose child sleeps 8s>],
    capture_output=True, timeout=2)` returned after 8.1s, not 2s.
    `taskkill /T /F` (Windows: terminates the named process AND every
    process it started) / `killpg` (POSIX: every process in the group
    `start_new_session=True` below put every descendant into) reach the
    whole tree instead."""
    import contextlib
    if os.name == "nt":
        with contextlib.suppress(Exception):
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                            capture_output=True, timeout=10)
    else:
        with contextlib.suppress(ProcessLookupError, OSError):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    with contextlib.suppress(Exception):
        proc.kill()  # belt-and-suspenders: the handle itself, in case the tree-kill above missed it


def run_bounded_codex_subprocess(argv: "list[str]", *, timeout: float, env: Optional[dict] = None,
                                  cwd: Optional[str] = None) -> "subprocess.CompletedProcess":
    """Pass-B finding 14 (major): the shared replacement for a bare
    `subprocess.run(argv, capture_output=True, timeout=...)` call against
    the `codex` binary -- `one_shot_cx_call` (60s), `codex_login_status`
    (10s, run synchronously by `_preflight_cx` on a session's first `cx:`
    turn), `halo models --cx --refresh`'s per-alias pings (30s) and
    `installed_codex_version`'s `--version` check (10s) all used to call
    `subprocess.run` directly, whose own timeout isn't enough -- see
    `_kill_process_tree`'s own docstring for why. `stdin=DEVNULL`: every
    one of these is a one-shot call with no prompt of its own to write on
    stdin, and the OLD plain `subprocess.run` calls inherited Halo's own
    stdin unchanged -- under `--input-format stream-json` that let a
    `codex` child read and consume queued input meant for Halo itself.
    Own process group (`start_new_session=True`/`CREATE_NEW_PROCESS_
    GROUP`, the exact isolation `CodexExecProcess.__init__` already uses)
    so the watchdog has a whole tree to reach in the first place.

    Raises `subprocess.TimeoutExpired` on a timeout and `OSError` if the
    process never starts at all -- the exact two exceptions `subprocess.
    run` itself raises, so every existing caller's own `except` clause
    needed no change beyond the call site itself."""
    popen_kwargs = dict(
        cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )
    if env is not None:
        popen_kwargs["env"] = dict(env)
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    proc = subprocess.Popen(argv, **popen_kwargs)  # OSError propagates untouched, same as subprocess.run
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        # Drain whatever the now-dying tree still has buffered so THIS
        # process is fully reaped (no zombie) -- bounded by its own short
        # grace period since the tree-kill above should make this quick.
        # A second TimeoutExpired here is swallowed, not re-raised: the
        # ORIGINAL timeout (re-raised by the bare `raise` below) is what
        # every existing caller's `except subprocess.TimeoutExpired`
        # already expects to see.
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        raise
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)


class CodexExecProcess:
    """One `codex exec` invocation -- started, read to completion (or
    interrupted), then discarded; a fresh instance is created per Halo turn
    (see `agent/codex_turn.py::turn_body_cx`). POSIX: its own process group
    (`start_new_session=True`) so `interrupt`/`kill` reach every descendant
    (the MCP child it spawns for `mcp_servers.halo` included) with no
    orphans, mirroring `agent.cc_process.ClaudeCodeProcess` exactly."""

    def __init__(self, argv: list, *, cwd: "Path | str", env: Optional[dict] = None):
        self.argv = list(argv)
        # pass-B finding 4 (critical): PIPE, not DEVNULL -- the prompt now
        # always rides on stdin (`build_cx_argv`'s trailing `-`), written
        # once by `send_prompt` below right after this constructor returns.
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
        self._stderr_buf: "deque[str]" = deque(maxlen=200)
        import threading
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True,
                                                 name=f"cx-stderr-{self._proc.pid}")
        self._stderr_thread.start()

    def send_prompt(self, text: str) -> None:
        """Pass-B finding 4 (critical): writes the WHOLE turn prompt to
        this process's stdin in one call and closes the pipe right behind
        it -- `codex exec ... -`/`codex exec resume <id> ... -` (this
        process's own argv, built by `build_cx_argv(prompt_via_stdin=
        True)`) reads stdin to EOF before doing anything else (CODEX-
        RESEARCH.md section 7; no stdin-streaming protocol the way `cc:`'s
        long-held claude process has, so unlike `ClaudeCodeProcess.send_
        user_line` there is no held-open pipe fed one line per turn -- one
        write, one close, per process, matching this class's own
        one-shot-per-turn lifecycle). The caller (`codex_turn.py`) calls
        this AFTER its own stdout-reader thread is already running, so a
        prompt too large for the OS pipe buffer to hold in one go can
        never deadlock against an unread stdout. A closed/broken pipe
        (the process already exited before this ever ran) is swallowed
        here, same as `ClaudeCodeProcess.send_user_line`'s own stance --
        the EOF/exit-code handling downstream is what actually reports a
        startup failure to the user, not this method."""
        stdin = self._proc.stdin
        if stdin is None:
            return
        try:
            stdin.write(text)
            stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass
        finally:
            try:
                stdin.close()
            except (OSError, ValueError):
                pass

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

    def read_event(self) -> Optional[dict]:
        """One parsed JSONL line from stdout, or None on EOF. A blank or
        unparseable line is skipped, never raised -- same contract as
        `ClaudeCodeProcess.read_event`."""
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

    def _posix_signal_group(self, sig) -> None:
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
        from halo_harness.termtitle import reassert_after_claude_child
        reassert_after_claude_child()
        return rc

    def stderr_tail(self, max_chars: int = 2000) -> str:
        text = "\n".join(self._stderr_buf)
        return text[-max_chars:]
