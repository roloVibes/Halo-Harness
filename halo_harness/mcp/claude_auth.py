"""halo_harness.mcp.claude_auth -- "is the installed `claude` logged in with
a claude.ai account?", the one question the claude.ai connectors bridge
asks before it discovers or bridges connectors (3.1.5.0 R1: moved here
from the removed `cc:` route's `providers/cc_models.py` and
`init_providers.claude_login_available`).

The answer comes from `claude auth status` (its JSON), never from Claude
Code's credentials file. A cache pair keeps every reader cheap: only
`refresh_cached_claude_auth_status` spawns anything (a startup worker, or
an explicit, bounded refresh); `cached_claude_auth_status` is a plain
lookup.

Test seam: `BRIDGE_TEST_CC_AUTH_STATUS` (a JSON object string, same shape
`claude auth status` prints) short-circuits the spawn -- set it to `""`
to simulate "resolvable binary, unparseable output" -> logged_in=False.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from halo_harness.mcp.claude_process import ClaudeCodeNotFoundError, claude_child_env, resolve_claude_launch_argv


@dataclass(frozen=True)
class ClaudeAuthStatus:
    logged_in: bool
    auth_method: Optional[str] = None
    email: Optional[str] = None
    subscription_type: Optional[str] = None
    version: Optional[str] = None
    raw: dict = field(default_factory=dict)
    # True ONLY on a `subprocess.TimeoutExpired` -- a timeout is not the
    # same as "not installed" (None) or "ran fine, not logged in".
    timed_out: bool = False


# `authMethod` values that mean "this is a claude.ai login" -- the only
# login the connectors bridge can discover claude.ai connectors through.
SUBSCRIPTION_AUTH_METHODS = frozenset({"claude.ai"})

# The synthetic `auth_method` used whenever `is_claude_gateway_driven()`
# says the installed `claude` is wired to a gateway: never a value
# `claude auth status` itself prints, so a reader can tell "never asked"
# from "asked and got another method", while still failing the
# SUBSCRIPTION_AUTH_METHODS check.
GATEWAY_AUTH_METHOD = "gateway"


def is_claude_gateway_driven(env: Optional[dict] = None) -> bool:
    """True when the installed `claude` is wired to a gateway (Databricks
    or otherwise) rather than a claude.ai login -- `ANTHROPIC_BASE_URL` /
    `ANTHROPIC_AUTH_TOKEN` (the shell env, or Claude Code's own settings.json
    `env` block) or a top-level `apiKeyHelper`. The answer is then known
    without spawning `claude auth status` at all (a gateway's own auth check
    can hang that spawn for its whole timeout).

    `env=None` checks bare `os.environ`, then Claude Code's settings chain
    (cheap disk reads only). A caller passing its own `env` gets only that
    dict checked (`apiKeyHelper` is never part of an env dict)."""
    e = env if env is not None else os.environ
    if e.get("ANTHROPIC_BASE_URL") or e.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    if env is not None:
        return False
    from pathlib import Path as _Path
    from halo_harness.config.settings import resolve_settings
    try:
        settings = resolve_settings(_Path.cwd())
    except Exception:
        return False
    if settings.env.get("ANTHROPIC_BASE_URL") or settings.env.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    return bool(settings.raw.get("apiKeyHelper"))


def claude_auth_status(*, timeout: float = 10.0, env: Optional[dict] = None) -> Optional[ClaudeAuthStatus]:
    """Runs `claude auth status` and parses its JSON. Returns None ONLY when
    the binary can't be found/run at all; a resolvable binary that reports
    (or prints something unparseable) `loggedIn: false` returns
    `ClaudeAuthStatus(logged_in=False, ...)`; a timeout returns
    `ClaudeAuthStatus(logged_in=False, timed_out=True)`.

    `env` defaults to `claude_child_env(os.environ)`, the same stripped env
    the connector calls run in, so an ambient ANTHROPIC_API_KEY never makes
    this report an `authMethod` the connector call would never see."""
    override = os.environ.get("BRIDGE_TEST_CC_AUTH_STATUS")
    if override is not None:
        return _parse_auth_status_json(override)
    try:
        argv = resolve_claude_launch_argv()
    except ClaudeCodeNotFoundError:
        return None
    if env is None:
        env = claude_child_env(dict(os.environ))
    from halo_harness.termtitle import reassert_after_claude_child
    try:
        proc = subprocess.run(argv + ["auth", "status"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        # A real `claude` child did start (the timeout kills it after
        # launch): re-assert halo's own terminal title.
        reassert_after_claude_child()
        return ClaudeAuthStatus(logged_in=False, timed_out=True)
    except OSError:
        return None
    reassert_after_claude_child()
    return _parse_auth_status_json(proc.stdout)


def _parse_auth_status_json(text: str) -> ClaudeAuthStatus:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        data = None
    if not isinstance(data, dict):
        return ClaudeAuthStatus(logged_in=False, raw={})
    return ClaudeAuthStatus(
        logged_in=bool(data.get("loggedIn")), auth_method=data.get("authMethod"),
        email=data.get("email"), subscription_type=data.get("subscriptionType"),
        version=data.get("claudeCodeVersion") or data.get("version"), raw=data,
    )


# ---- the cache ---------------------------------------------------------------
_AUTH_STATUS_CACHE_LOCK = threading.Lock()
_auth_status_cache: Optional[ClaudeAuthStatus] = None
_auth_status_cached_at: float = 0.0

# How long `cached_auth_status_is_stale()` considers a cached answer fresh
# (informational: a stale read still beats blocking on a fresh spawn).
CACHED_AUTH_STATUS_TTL_S = 30.0


def refresh_cached_claude_auth_status(*, timeout: float = 10.0) -> Optional[ClaudeAuthStatus]:
    """The ONLY function in this cache pair that may spawn `claude auth
    status` -- call it off the UI thread. `is_claude_gateway_driven()` is
    checked first: when true, a synthetic `ClaudeAuthStatus(logged_in=False,
    auth_method=GATEWAY_AUTH_METHOD)` is cached without spawning anything.
    Stores the result (even `None`, "claude not found") and returns it."""
    global _auth_status_cache, _auth_status_cached_at
    if is_claude_gateway_driven():
        status = ClaudeAuthStatus(logged_in=False, auth_method=GATEWAY_AUTH_METHOD)
    else:
        status = claude_auth_status(timeout=timeout)
    with _AUTH_STATUS_CACHE_LOCK:
        _auth_status_cache = status
        _auth_status_cached_at = time.monotonic()
    return status


def cached_claude_auth_status() -> Optional[ClaudeAuthStatus]:
    """Read-only, never spawns. `None` both before the first refresh has
    landed and for "claude not found" -- readers treat both as "no
    claude.ai login known". `BRIDGE_TEST_CC_AUTH_STATUS` bypasses the cache
    entirely so a test always sees its own current value."""
    if os.environ.get("BRIDGE_TEST_CC_AUTH_STATUS") is not None:
        return claude_auth_status()
    with _AUTH_STATUS_CACHE_LOCK:
        return _auth_status_cache


def cached_auth_status_is_stale(*, max_age: float = CACHED_AUTH_STATUS_TTL_S) -> bool:
    """True when nothing is cached yet, or the cached answer is older than
    `max_age`."""
    with _AUTH_STATUS_CACHE_LOCK:
        if _auth_status_cache is None:
            return True
        return (time.monotonic() - _auth_status_cached_at) >= max_age


def reset_cached_claude_auth_status() -> None:
    """Test seam: clear the cache between tests."""
    global _auth_status_cache, _auth_status_cached_at
    with _AUTH_STATUS_CACHE_LOCK:
        _auth_status_cache = None
        _auth_status_cached_at = 0.0


def claude_login_available() -> bool:
    """Cache-only: True when the cached status says a claude.ai login. A
    cache miss means "not detected yet" -- this never spawns anything."""
    status = cached_claude_auth_status()
    return bool(status and status.logged_in and status.auth_method in SUBSCRIPTION_AUTH_METHODS)
