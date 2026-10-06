"""halo_harness.mcp.doctor_probe -- Halo 2.0.4 round 6 ("MCP connectivity
deep dive"), the bounded per-step PROBES: resolve the command (PATH, a
Windows .cmd/.bat/.ps1 shim's own interpreter, node/python/uv --version),
spawn + run the real stdio/http/sse handshake with a timeout (reusing
`mcp.manager`'s own proven connect machinery, never a second JSON-RPC
client), a bare TCP/TLS pre-check for http/sse/ws, diff the child
environment against the user's shell, and check the config entry's shape.
Every step returns one `ProbeStep` with its own evidence text, MASKED (no
key-shaped value ever appears) -- `doctor_deep.py` is the orchestrator that
strings these into one evidence block per server and hands it to a model.

No safety/refusal language, no new hard dependency (stdlib `socket`/`ssl`/
`subprocess` only); every probe here is bounded by a timeout and never
blocks the caller indefinitely.
"""

from __future__ import annotations

import os
import re
import socket
import ssl
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# ---- secret masking ---------------------------------------------------------
# A second, free-text-oriented cousin of `manager._looks_like_credential`
# (which only ever judges a bare VAR NAME) -- this one scrubs a VALUE found
# in captured stdout/stderr/evidence text, so a server whose crash message
# happened to echo back a key/token/header never lands in a printed
# evidence block, a persisted diagnosis record, or a model prompt.

_SECRET_VALUE_RE = re.compile(
    r"(?i)(authorization\s*:\s*)(\S+)"
    r"|(\b(?:api[_-]?key|token|secret|password|passwd)\b\s*[=:]\s*)(\S+)"
    r"|(\bbearer\s+)(\S+)"
)


def mask_secrets(text: Optional[str]) -> str:
    """Best-effort redaction of credential-SHAPED substrings in free text
    (never raises; `None`/empty -> `""`)."""
    if not text:
        return ""

    def _sub(m: "re.Match") -> str:
        for i in (1, 3, 5):
            if m.group(i):
                return m.group(i) + "***"
        return m.group(0)

    return _SECRET_VALUE_RE.sub(_sub, text)


def mask_url(url: Optional[str]) -> str:
    """scheme://host:port/path only -- drops userinfo, query string and
    fragment outright (never shown, not even masked) since those are the
    most likely place a token rides along on a remote MCP server's url."""
    if not url:
        return "?"
    try:
        p = urlparse(url)
    except ValueError:
        return "?"
    if not p.hostname:
        return "?"
    port = f":{p.port}" if p.port else ""
    return f"{p.scheme}://{p.hostname}{port}{p.path or ''}"


# ---- ProbeStep / ProbeResult -------------------------------------------------

@dataclass
class ProbeStep:
    name: str
    ok: bool
    elapsed_s: float
    detail: str

    def line(self) -> str:
        tag = "OK" if self.ok else "FAIL"
        return f"[{tag}] {self.name} ({self.elapsed_s:.2f}s): {mask_secrets(self.detail)}"


@dataclass
class ProbeResult:
    server: str
    steps: "list[ProbeStep]" = field(default_factory=list)

    @property
    def verdict(self) -> str:
        return "healthy" if self.steps and all(s.ok for s in self.steps) else "failed"

    @property
    def failing_step(self) -> Optional[str]:
        return next((s.name for s in self.steps if not s.ok), None)

    def primary_error_text(self) -> str:
        """The first failing step's own detail -- what `doctor_deep.
        failure_signature` fingerprints, and the headline of `evidence_
        text()`'s summary line. `""` when every step passed."""
        s = next((s for s in self.steps if not s.ok), None)
        return s.detail if s is not None else ""

    def evidence_text(self) -> str:
        lines = [f"=== MCP deep dive: {self.server} (verdict: {self.verdict}) ==="]
        lines.extend(s.line() for s in self.steps)
        return "\n".join(lines)


# ---- step 1: resolve the command / url --------------------------------------

_SHIM_INTERPRETER_RE = re.compile(
    r'["\']([A-Za-z]:[\\/][^"\']+?\.exe)["\']'
    r'|["\']?(/[^"\'\s]+/(?:python3?|node|uvx?))["\']?',
    re.IGNORECASE,
)
_VERSION_PROBE_PREFIXES = ("node", "python", "uv", "npx", "uvx")


def _command_basename(command: Optional[str]) -> str:
    if not command:
        return "?"
    base = re.split(r"[\\/]", command)[-1]
    for suffix in (".exe", ".cmd", ".bat", ".ps1"):
        if base.lower().endswith(suffix):
            return base[: -len(suffix)]
    return base


def inspect_shim(path: str) -> str:
    """A Windows `.cmd`/`.bat`/`.ps1` shim is a text file that execs a real
    interpreter somewhere else -- pure static text analysis (never run),
    so it's exercisable on any OS with a hand-built fixture file."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"could not read shim contents: {type(e).__name__}: {e}"
    m = _SHIM_INTERPRETER_RE.search(text)
    if not m:
        return "shim contents did not match a recognizable interpreter path"
    interp = next(g for g in m.groups() if g)
    exists = Path(interp).exists()
    return (f"shim points at: {interp} (exists)" if exists
            else f"shim points at: {interp} (MISSING -- this interpreter does not exist)")


def _bounded_version_probe(resolved: str, timeout_s: float = 3.0) -> Optional[str]:
    base = _command_basename(resolved).lower()
    if not any(base.startswith(p) for p in _VERSION_PROBE_PREFIXES):
        return None
    try:
        import subprocess
        proc = subprocess.run([resolved, "--version"], capture_output=True, text=True, timeout=timeout_s)
        out = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
        return f"{base} --version: {out[0]}" if out else f"{base} --version: (no output)"
    except Exception as e:
        return f"{base} --version failed: {type(e).__name__}: {e}"


def resolve_command_step(cfg) -> ProbeStep:
    """stdio only -- PATH lookup (or a literal path already given), a
    Windows shim's own interpreter, and a bounded `--version` probe of
    whatever actually resolved."""
    import shutil
    command = (cfg.command or "").strip()
    t0 = time.monotonic()
    if not command:
        return ProbeStep("resolve_command", False, time.monotonic() - t0,
                          "no command configured for a stdio server")
    resolved = shutil.which(command)
    if resolved is None and ("/" in command or "\\" in command):
        resolved = command if Path(command).exists() else None
    elapsed = time.monotonic() - t0
    if resolved is None:
        return ProbeStep("resolve_command", False, elapsed, f"{command!r} not found on PATH")
    lines = [f"resolved: {resolved}"]
    if resolved.lower().endswith((".cmd", ".bat", ".ps1")):
        lines.append(inspect_shim(resolved))
    version = _bounded_version_probe(resolved)
    if version:
        lines.append(version)
    return ProbeStep("resolve_command", True, elapsed, "; ".join(lines))


def resolve_url_step(cfg) -> ProbeStep:
    """http/sse/ws -- pure shape check, no network."""
    url = (cfg.url or "").strip()
    if not url:
        return ProbeStep("resolve_url", False, 0.0, f"no url configured for a {cfg.type} server")
    p = urlparse(url)
    if not p.scheme or not p.hostname:
        return ProbeStep("resolve_url", False, 0.0, f"could not parse a scheme/host out of {mask_url(url)}")
    return ProbeStep("resolve_url", True, 0.0, f"parsed: {mask_url(url)}")


# ---- step 2: port + TLS pre-check (http/sse/ws) ------------------------------

def port_and_tls_step(cfg, *, timeout_s: float = 3.0) -> ProbeStep:
    url = cfg.url or ""
    p = urlparse(url)
    host = p.hostname
    if not host:
        return ProbeStep("port_tls", False, 0.0, f"could not parse a host out of {mask_url(url)}")
    default_port = 443 if p.scheme in ("https", "wss") else 80
    port = p.port or default_port
    t0 = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout_s) as sock:
            elapsed = time.monotonic() - t0
            if p.scheme in ("https", "wss"):
                ctx = ssl.create_default_context()
                try:
                    with ctx.wrap_socket(sock, server_hostname=host) as tls_sock:
                        return ProbeStep("port_tls", True, elapsed,
                                          f"{host}:{port} open, TLS handshake ok ({tls_sock.version()})")
                except ssl.SSLError as e:
                    return ProbeStep("port_tls", False, time.monotonic() - t0,
                                      f"{host}:{port} open, TLS handshake failed: {type(e).__name__}: {e}")
                except OSError as e:
                    return ProbeStep("port_tls", False, time.monotonic() - t0,
                                      f"{host}:{port} open, TLS handshake failed: {type(e).__name__}: {e}")
            return ProbeStep("port_tls", True, elapsed, f"{host}:{port} open (plain {p.scheme})")
    except OSError as e:
        return ProbeStep("port_tls", False, time.monotonic() - t0, f"{host}:{port}: {type(e).__name__}: {e}")


# ---- step 3: the real spawn + handshake (stdio/http/sse/ws, via manager.py) -

def run_handshake(name: str, cfg, *, tool_env: dict, cwd, abort=None) -> "tuple[dict, float]":
    """The REAL connect, through a throwaway, single-server `McpManager`
    (never a second JSON-RPC client) -- bounded by the same
    `MCP_CONNECT_TIMEOUT_MS`/`MCP_TIMEOUT` knobs any ordinary connect uses.
    Returns a plain snapshot dict (captured BEFORE `close_all()`, which
    unconditionally flips `state` to "closed") and the wall-clock elapsed
    time: `{state, error, tool_count, tools_fetch_failed,
    tools_fetch_failed_error}`."""
    from halo_harness.mcp.manager import McpManager, mcp_timeout_s
    mgr = McpManager({name: cfg}, tool_env=tool_env, cwd=cwd)
    h = mgr.handles[name]
    t0 = time.monotonic()
    try:
        h.start(abort=abort)
    finally:
        snapshot = {
            "state": h.state, "error": h.error, "tool_count": len(h.tools),
            "tools_fetch_failed": h.tools_fetch_failed,
            "tools_fetch_failed_error": h.tools_fetch_failed_error,
        }
        elapsed = time.monotonic() - t0
        mgr.close_all(timeout=mcp_timeout_s() + 5.0)
    return snapshot, elapsed


def handshake_steps(name: str, cfg, *, tool_env: dict, cwd, abort=None) -> "list[ProbeStep]":
    from halo_harness.mcp.manager import tail_server_log
    snapshot, elapsed = run_handshake(name, cfg, tool_env=tool_env, cwd=cwd, abort=abort)
    state = snapshot["state"]
    if state == "connected" and not snapshot["tools_fetch_failed"]:
        return [ProbeStep("handshake", True, elapsed,
                           f"spawned, initialized, tools/list returned {snapshot['tool_count']} tool(s)")]
    if state == "connected" and snapshot["tools_fetch_failed"]:
        return [
            ProbeStep("handshake", True, elapsed, "spawned and initialized ok"),
            ProbeStep("tools_list", False, elapsed,
                      snapshot["tools_fetch_failed_error"] or "tools/list failed after a clean initialize"),
        ]
    # failed / needs_auth -- classify spawn-vs-handshake from the error text
    # (mcp_cli.failure_reason's own classification, reused rather than
    # re-derived) and fold in a masked tail of this server's own log
    # (stdio stderr + connect/transport errors -- manager._append_server_log
    # already writes both there).
    from halo_harness.mcp_cli import failure_reason
    reason = failure_reason({"state": state, "error": snapshot["error"],
                              "command": cfg.command, "url": cfg.url, "type": cfg.type})
    step_name = "spawn" if reason.lower().startswith("command not found on path") else "handshake"
    detail_bits = [snapshot["error"] or f"state={state}"]
    try:
        tail = [ln for ln in tail_server_log(name, max_lines=8) if ln.strip()]
    except Exception:
        tail = []
    if tail:
        # deliberately NOT `{name}.log` here (server_log_path(name).name) --
        # that would bake this server's own NAME into the exact text
        # `doctor_deep.failure_signature` fingerprints, so two differently-
        # named servers hitting the identical underlying problem (same
        # command, same stderr) would never share a signature and a
        # learned fix could never generalize past the one name it was
        # first learned on.
        detail_bits.append("log tail: " + " | ".join(tail[-5:]))
    return [ProbeStep(step_name, False, elapsed, "; ".join(detail_bits))]


# ---- step 4: env diff --------------------------------------------------------

def env_diff_step(cfg, *, tool_env: dict, shell_env: dict) -> ProbeStep:
    """Diffs the child env this server would actually run with against the
    user's own shell: missing PATH entries, and any `${VAR}`/bare env-var
    name the config mentions that isn't set anywhere -- every value stays
    masked (names only, via `manager.expand_config`'s own warnings list,
    never a real value read back out)."""
    from halo_harness.mcp.manager import expand_config
    lines: "list[str]" = []
    try:
        _expanded, warnings = expand_config(cfg, shell_env)
        lines.extend(warnings)
    except Exception as e:
        lines.append(f"could not check ${{VAR}} expansion: {type(e).__name__}: {e}")

    if cfg.type == "stdio":
        from halo_harness.mcp import stdio as stdio_mod
        try:
            child_env = stdio_mod.build_env(cfg.env, tool_env, cfg.cwd)
        except Exception as e:
            child_env = {}
            lines.append(f"could not build the child env to diff: {type(e).__name__}: {e}")
        child_path = {p for p in (child_env.get("PATH") or child_env.get("Path") or "").split(os.pathsep) if p}
        shell_path = {p for p in (shell_env.get("PATH") or shell_env.get("Path") or "").split(os.pathsep) if p}
        missing_path = sorted(shell_path - child_path)
        if missing_path:
            noun = "entry" if len(missing_path) == 1 else "entries"
            lines.append(f"{len(missing_path)} PATH {noun} in your shell but not in the child env "
                          f"(showing up to 5): {', '.join(missing_path[:5])}")
    ok = not lines
    return ProbeStep("env_diff", ok, 0.0, "; ".join(lines) if lines else "no PATH/env-var gaps found")


# ---- step 5: config shape ----------------------------------------------------

_KNOWN_KEYS = {
    "stdio": {"type", "command", "args", "env", "cwd", "timeout", "alwaysLoad", "mcpLazy"},
    "http": {"type", "url", "headers", "headersHelper", "oauth", "timeout", "alwaysLoad", "mcpLazy"},
    "sse": {"type", "url", "headers", "headersHelper", "oauth", "timeout", "alwaysLoad", "mcpLazy"},
}


def raw_entry_best_effort(name: str, cfg, cwd: Path) -> Optional[dict]:
    """Best-effort re-read of `name`'s on-disk entry for `config_shape_
    step` below -- never raises, `None` for a scope with no single file
    (managed/flag/dynamic/plugin) or on any read/parse failure."""
    import json
    try:
        if cfg.scope == "project":
            path = Path(cfg.source_path) if cfg.source_path else (Path(cwd) / ".mcp.json")
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            return (data.get("mcpServers") or {}).get(name)
        if cfg.scope in ("user", "local"):
            from halo_harness.config.paths import claude_json_path, normalize_cwd
            data = json.loads(claude_json_path().read_text(encoding="utf-8-sig"))
            if cfg.scope == "user":
                return (data.get("mcpServers") or {}).get(name)
            proj = (data.get("projects") or {}).get(normalize_cwd(cwd)) or {}
            return (proj.get("mcpServers") or {}).get(name)
    except Exception:
        return None
    return None


def config_shape_step(name: str, cfg, cwd: Path) -> ProbeStep:
    lines = [f"scope: {cfg.scope}" + (f" ({cfg.source_path})" if cfg.source_path else "")]
    problems: "list[str]" = []
    if cfg.type == "stdio" and not cfg.command:
        problems.append('a stdio entry needs "command"')
    if cfg.type in ("http", "sse") and not cfg.url:
        problems.append(f'a {cfg.type} entry needs "url"')
    raw_entry = raw_entry_best_effort(name, cfg, cwd)
    if raw_entry is not None:
        known = _KNOWN_KEYS.get(cfg.type, set())
        unknown = sorted(set(raw_entry) - known) if known else []
        if unknown:
            lines.append(f"unrecognized key(s) in this entry: {', '.join(unknown)}")
    else:
        lines.append("no single on-disk file for this scope to check (managed/flag/dynamic/plugin)")
    if problems:
        lines.append("MISSING: " + "; ".join(problems))
    ok = not problems
    return ProbeStep("config_shape", ok, 0.0, "; ".join(lines))


# ---- the whole probe ---------------------------------------------------------

def probe_server(name: str, cfg, *, tool_env: dict, cwd, abort=None) -> ProbeResult:
    """Deliverable 2: resolve -> spawn+handshake -> env diff -> config
    shape, in that order, each step bounded and evidenced. A disabled/
    pending-approval server is reported as a single step naming why,
    never attempted."""
    steps: "list[ProbeStep]" = []
    if getattr(cfg, "disabled_reason", None):
        steps.append(ProbeStep("config", False, 0.0, f"disabled: {cfg.disabled_reason}"))
        return ProbeResult(server=name, steps=steps)
    if getattr(cfg, "pending_approval", False):
        steps.append(ProbeStep("config", False, 0.0, "pending .mcp.json approval -- never connected"))
        return ProbeResult(server=name, steps=steps)

    if cfg.type == "stdio":
        steps.append(resolve_command_step(cfg))
    else:
        steps.append(resolve_url_step(cfg))
        steps.append(port_and_tls_step(cfg))

    steps.extend(handshake_steps(name, cfg, tool_env=tool_env, cwd=cwd, abort=abort))
    steps.append(env_diff_step(cfg, tool_env=tool_env, shell_env=os.environ))
    steps.append(config_shape_step(name, cfg, Path(cwd)))
    return ProbeResult(server=name, steps=steps)
