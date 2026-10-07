"""halo_harness.providers.http -- low-level upstream HTTP plumbing: proxy
selection, connection opening (TLS/CA bundle/proxy tunnel), the OpenAI-chat
and Databricks-chat POST calls, and the raw Databricks Claude passthrough
relay (proxy_anthropic/count_tokens/reader thread). Moved out of bridge.py
unchanged in the H0 package split; see wip/SIGNATURES.md part4 and the M4/M5
sections.

NOTE on the http.py <-> databricks.py cycle: call_databricks_chat (here)
needs databricks.py's route-candidate/body/cache helpers, and databricks.py's
probe_databricks_endpoints/probe_openrouter_models need this module's
open_upstream/UpstreamConnectError. Both directions are only used INSIDE
function bodies (never at class/module scope), so the cross-imports are
deferred (done locally inside the functions that need them) to avoid a
circular import at module-load time -- see databricks.py's matching note.

Halo 2.0.5 round 4: this module is also the Governor's ONE choke point --
every remote model request (call_openai_chat, call_ollama_chat, the
Databricks posts, call_anthropic_native) goes through
`governed_upstream()`, which paces per gateway host, reports the outcome
to the shared bucket, and owns the 429/overload retry ladder for
governed routes (the agent loop's own ladder stops retrying those).
`cc:`/`cx:` drive a CLI child, not HTTP: not governed.
"""

from __future__ import annotations

import http.client
import ipaddress
import json
import logging
import os
import socket
import ssl
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from halo_harness.providers.config import dump_debug, jdumps
from halo_harness.providers.errors import upstream_error_text

log = logging.getLogger("bridge")

# 1.0.1 hotfix 2: the connect timeout `open_upstream` uses whenever a caller
# doesn't pass its own -- ALSO the wall-clock cap `_bounded_connect` enforces
# around the whole connect phase (DNS + TCP handshake), so a black-holed/
# unresponsive resolver can never again take the ~64s the owner measured
# against an unresolvable `*.cloud.databricks.com` host regardless of what
# the OS resolver's own retry/timeout policy would otherwise do. Applies
# uniformly to every caller (ordinary turns, `-p`, the TUI, `init`'s pong,
# `models --refresh`, `doctor`) since they all funnel through `open_upstream`.
DEFAULT_CONNECT_TIMEOUT_S = 8


class UpstreamConnectError(Exception):
    """Any failure during the CONNECT phase (DNS/name resolution, connection
    refused, no route to host, a TLS handshake failure, or our own bounded-
    connect timeout) -- never a failure after bytes were actually
    exchanged. `host` (1.0.1 hotfix 2), when known, is the real upstream
    hostname this attempt was for, so a caller can build a message that
    NAMES it without re-parsing a URL itself."""

    def __init__(self, message: str, host: "str | None" = None):
        super().__init__(message)
        self.host = host


# The fixed lead-in `format_connect_error` (below) always uses -- checked
# for verbatim (`is_connect_failure_message`) by `agent/loop.py`'s own retry
# ladder so it can tell "we never even connected" apart from a genuine
# upstream 5xx WITHOUT changing either wire mapper's own status/err_type/
# message shape (`providers.databricks.databricks_unreachable_response`/
# `providers.errors.map_upstream_error` both stay byte-for-byte unchanged --
# `bridge.py`'s legacy proxy path, and its own pinned test_bridge.py
# assertion ending in "(are you on the VPN? Databricks is whitelisted)",
# both keep relying on that). Whichever wire mapper re-wraps this
# exception's message, the marker survives as a substring either way.
CONNECT_FAILURE_MARKER = "cannot resolve/reach"


def is_connect_failure_message(message: "str | None") -> bool:
    return CONNECT_FAILURE_MARKER in (message or "")


# Halo 2.0.3 round 5e: enforced offline mode. `OFFLINE_REFUSAL_MARKER` is a
# SEPARATE marker from `CONNECT_FAILURE_MARKER` above -- an offline refusal
# is a deliberate, user-chosen network policy, never a DNS/VPN failure, so
# it must never pick up `format_connect_error`'s "check the machine's
# network, DNS or VPN" wording (which would misdescribe a plain, intentional
# refusal as if something were broken) or Databricks' own "(are you on the
# VPN? Databricks is whitelisted)" suffix (`providers.stream._run_phase1_
# attempts` checks `is_offline_refusal_message` before ever reaching that
# branch -- see its own comment). `is_offline_refusal_message` is checked
# everywhere `is_connect_failure_message` already is (agent/loop.py's `_step`
# retry ladder, providers/stream.py's three phase-1 retry loops) so a
# refusal is exactly as terminal as a genuine connect failure -- never
# retried, never counted toward a fallback-model exhaustion ladder (a
# deliberate policy block cannot be fixed by trying again).
OFFLINE_REFUSAL_MARKER = "offline mode: not connecting to"


def format_offline_refusal(host: "str | None") -> str:
    """The one plain sentence an offline refusal ever uses, naming the
    host -- "offline mode: not connecting to <host>". No safety/refusal
    framing ("blocked", "not allowed") anywhere in it: offline mode is a
    user-chosen network policy, described plainly, same as every other
    behaviour in this codebase."""
    named = host or "the upstream host"
    return f"{OFFLINE_REFUSAL_MARKER} {named}"


def is_offline_refusal_message(message: "str | None") -> bool:
    return OFFLINE_REFUSAL_MARKER in (message or "")


class OfflineBlocked(UpstreamConnectError):
    """Raised by `_check_offline_allowed` (below) -- a `UpstreamConnectError`
    subclass so every existing `except UpstreamConnectError` catch (doctor's
    probes, catalog fetchers, every phase-1 retry loop) keeps working with
    no changes of its own; callers that care specifically about an offline
    refusal (vs. a real connect failure) use `is_offline_refusal_message`."""

    def __init__(self, host: "str | None"):
        super().__init__(format_offline_refusal(host), host=host)


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "0.0.0.0", "[::1]"})


def _is_loopback_host(host: "str | None") -> bool:
    return (host or "").strip().lower().rstrip(".") in _LOOPBACK_HOSTS


def _is_private_ip_literal(host: "str | None") -> bool:
    """True only when `host` is already written as a literal IP address
    inside a private/loopback/link-local/ULA range -- NEVER a DNS lookup
    (a hostname that merely RESOLVES to a private address, e.g. via a
    hosts-file entry or split-horizon DNS, is not "local" by this check --
    doing a live resolution here to find out would itself be a network
    step, which computing the offline allow-list must never be). Halo
    2.0.3 fix pass C-1 (review finding 1): `ipaddress.ip_address(...).
    is_private` already covers every RFC1918 range, loopback, link-local
    (169.254.0.0/16/fe80::/10) and IPv6 ULA (fc00::/7) in one check -- the
    exact "private/link-local literals" the finding's fix text names."""
    candidate = (host or "").strip()
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    if not candidate:
        return False
    try:
        return ipaddress.ip_address(candidate).is_private
    except ValueError:
        return False


def _is_local_hostname(host: "str | None") -> bool:
    """True for loopback, a bare single-label name (`gpubox`, no dot --
    never a publicly routable hostname), or an `.local` mDNS name. Halo
    2.0.3 fix pass C-1 (review finding 1): one of the three ways a
    configured entry's host counts as "local" with no explicit marker
    needed -- a literal cloud hostname (`ollama.com`, any other public
    name a user pasted into `ollama.hosts`/`huggingface.local_servers`)
    has a dot and isn't `.local`, so it never matches this."""
    name = (host or "").strip().lower().rstrip(".")
    if not name:
        return False
    if name in _LOOPBACK_HOSTS:
        return True
    if name.endswith(".local"):
        return True
    return "." not in name


def allowlisted_local_hosts() -> "set[str]":
    """Every hostname `network.offline` lets through besides loopback --
    lowercased. Three sources, each read-only/local (no network call of its
    own, so computing the allow-list itself is always safe under offline
    mode): every `ollama.hosts` entry (`providers.ollama.resolve_ollama_
    hosts` -- a LAN Ollama box the user explicitly configured), every
    `huggingface.local_servers` entry (`providers.huggingface.resolve_
    huggingface_local_servers` -- the same "one GPU box, several laptops"
    manual entries round 5's own brief introduced), and every managed-
    runtime registry entry (`providers.local_runtime.load_registry` --
    `~/.halo/run/local-servers.json`; always `127.0.0.1` by construction
    today, included anyway so the allow-list stays correct if that ever
    changes).

    Halo 2.0.3 fix pass C-1 (review finding 1, critical): an entry's host
    is only added when it is ACTUALLY local -- a private/loopback/link-
    local/ULA IP literal (`_is_private_ip_literal`), a bare single-label
    or `.local` name (`_is_local_hostname`), or the entry itself carries
    an explicit `offline_ok: true` marker the user set. Before this fix
    every configured entry's hostname was added unconditionally, so an
    Ollama Cloud host (`https://ollama.com`, keyed by `api_key`) or any
    other public hostname a user pasted into `ollama.hosts`/`huggingface.
    local_servers` was allow-listed right along with a real LAN box --
    `--offline`/`/offline on` then kept sending `ol:`/`hf:local` turns
    (prompts, file contents, tool results) to that public host while the
    status bar still showed "offline". A literal cloud hostname never
    passes any of the three checks, so it is correctly refused the same
    way any other remote host is under offline mode.

    Deferred imports throughout: this module is the lowest layer in the
    provider tree (loaded before config/provider modules exist), the same
    reason every cross-module import elsewhere in this file is also done
    lazily, inside the function body. Never raises -- any one source's
    own failure (a malformed config.json, an unreadable registry file)
    just contributes nothing, the other sources still apply."""
    hosts: "set[str]" = set()

    def _consider(url: "str | None", *, offline_ok: bool = False) -> None:
        hostname = urllib.parse.urlparse(url or "").hostname
        if not hostname:
            return
        lowered = hostname.lower()
        if offline_ok or _is_private_ip_literal(lowered) or _is_local_hostname(lowered):
            hosts.add(lowered)

    try:
        from halo_harness.providers.ollama import resolve_ollama_hosts
        for h in resolve_ollama_hosts():
            _consider(h.url, offline_ok=bool(getattr(h, "offline_ok", False)))
    except Exception:
        pass
    try:
        from halo_harness.providers.huggingface import resolve_huggingface_local_servers
        for s in resolve_huggingface_local_servers():
            _consider(s.url, offline_ok=bool(getattr(s, "offline_ok", False)))
    except Exception:
        pass
    try:
        from halo_harness.providers.config import default_state_dir
        from halo_harness.providers.local_runtime import load_registry
        for entry in load_registry(default_state_dir()):
            base_url = entry.get("base_url") if isinstance(entry, dict) else None
            _consider(base_url)
    except Exception:
        pass
    return hosts


def offline_mode_enabled() -> bool:
    """`network.offline` -- `HALO_OFFLINE=1`/`HALO_OFFLINE=0` (set for the
    CURRENT PROCESS ONLY by `--offline`, never persisted -- `cli.py`'s own
    flag handler) wins over the persisted `~/.halo/config.json` value
    (`/offline on|off`, via `theme.set_config_value`), same "env overrides
    the persisted file" convention `config.paths.env_compat` already uses
    everywhere else in this codebase. Deferred import, same reason as
    `allowlisted_local_hosts`. Never raises -- a malformed config.json
    degrades to "offline mode is off", never a crash on every network call
    in the tree."""
    env_override = os.environ.get("HALO_OFFLINE")
    if env_override == "1":
        return True
    if env_override == "0":
        return False
    try:
        from halo_harness.theme import get_config_value
        return bool(get_config_value("network.offline", default=False))
    except Exception:
        return False


def _check_offline_allowed(host: "str | None") -> None:
    """The ONE gate `open_upstream`/`urlopen_tls` (below) both call before
    ever resolving DNS or opening a socket. A no-op whenever offline mode
    is off (the overwhelmingly common case) or `host` is loopback or
    allow-listed; raises `OfflineBlocked` otherwise."""
    if not offline_mode_enabled():
        return
    if _is_loopback_host(host):
        return
    if (host or "").strip().lower() in allowlisted_local_hosts():
        return
    raise OfflineBlocked(host)


def default_tls_context() -> ssl.SSLContext:
    """1.0.1 hotfix 11: the ONE TLS context every HTTPS connection this
    harness makes is built through -- `open_upstream` and `urlopen_tls`
    (below) both call this, so neither has its own, possibly-diverging
    verification policy.

    Starts from `ssl.create_default_context()` (real CA verification, no
    behavior change there), then clears `VERIFY_X509_STRICT` when the
    running Python's `ssl` module has it at all (added in 3.13, where
    `create_default_context()` turns it ON by default -- 3.11/3.12 never
    had it, so this is a no-op there). Verified live: a real corporate
    TLS-inspection proxy's re-signing CA certificate carries a non-critical
    `basicConstraints` extension, which every major HTTP client (curl,
    browsers, Node, and Python itself before 3.13) accepts -- only
    `X509_STRICT` rejects it (`CERTIFICATE_VERIFY_FAILED: basic constraints
    of CA cert not marked critical`), so a 3.13 halo was the ONLY
    thing failing at a work box every other tool on the same network
    already worked from (the Databricks endpoint itself is exempted from
    that same proxy's inspection, which is why a live pong there kept
    working while `models.dev`/OpenRouter did not). This does not weaken
    certificate-chain or hostname verification -- both stay fully on.

    Then applies the SAME `NODE_EXTRA_CA_CERTS`/`REQUESTS_CA_BUNDLE`/
    `HALO_CA_BUNDLE` (legacy `BRIDGE_CA_BUNDLE`, still honoured) custom-CA-
    bundle loading `open_upstream` already had (first one present that
    loads successfully wins; a load failure is logged and the next
    candidate is tried, never a hard failure -- the context still has the
    system trust store either way)."""
    from halo_harness.config.paths import env_compat
    ctx = ssl.create_default_context()
    strict_flag = getattr(ssl, "VERIFY_X509_STRICT", 0)
    if strict_flag:
        ctx.verify_flags &= ~strict_flag
    ca_candidates = [os.environ.get("NODE_EXTRA_CA_CERTS"), os.environ.get("REQUESTS_CA_BUNDLE"),
                     env_compat("CA_BUNDLE")]
    for ca_path in ca_candidates:
        if ca_path:
            try:
                ctx.load_verify_locations(ca_path)
                break
            except Exception:
                log.warning(f"Failed to load CA bundle from {ca_path}", exc_info=True)
    return ctx


class _OfflineAwareRedirectHandler(urllib.request.HTTPRedirectHandler):
    """urllib's own `HTTPRedirectHandler`, with `_check_offline_allowed`
    re-run against each hop's new `Location` BEFORE following it. Halo
    2.0.3 fix pass C-1 (review finding 21): `urlopen_tls` only ever gated
    the FIRST url -- `build_opener` then adds urllib's own default
    redirect handler underneath it (since no `HTTPRedirectHandler`
    instance/subclass was passed), which follows any `Location` header
    with no gate of its own, so a loopback or allow-listed URL that
    answers with a 3xx could bounce an offline call to an arbitrary host.
    Only the GATE is added here -- `redirect_request`'s own 3xx/method/
    redirect-loop handling is entirely the parent implementation's;
    raising here (before it ever builds the new request) simply stops a
    disallowed hop from being followed at all, the same as a plain
    `OfflineBlocked` from the FIRST request would."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_offline_allowed(urllib.parse.urlparse(newurl).hostname)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def urlopen_tls(req, timeout=None):
    """`urllib.request.urlopen`, but through `default_tls_context()` instead
    of `urllib`'s own bare default context -- every one-shot HTTPS GET this
    harness makes outside `open_upstream`'s own http.client-based path
    (currently: hooks.py's webhook helpers, linux_fixes.py's rg-release
    lookup/download, team_config.py's `--team <url>` fetch, tools/
    websearch.py, update.py's GitHub check, providers/local_runtime_
    fetch.py's llama.cpp release fetch) goes through this so all of them
    share the SAME VERIFY_X509_STRICT/custom-CA-bundle policy `open_upstream`
    uses, instead of quietly using a stricter/different one of urllib's own.

    Halo 2.0.3 round 5e: also the second half of the offline-mode choke
    point -- `_check_offline_allowed` runs here BEFORE anything is opened,
    exactly like `open_upstream` below, so every caller of this function is
    covered by `--offline`/`/offline on` with no change of its own. `req`
    is either a `urllib.request.Request` (`.full_url`) or a bare URL string
    (`team_config.py`'s own caller passes one directly) -- both `urlopen`
    itself and this wrapper accept either shape, so the host extraction
    must too; a string with neither attribute falls back to itself."""
    host = None
    try:
        full_url = req.full_url if hasattr(req, "full_url") else req
        host = urllib.parse.urlparse(full_url).hostname
    except Exception:
        pass
    _check_offline_allowed(host)
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=default_tls_context()),
                                          _OfflineAwareRedirectHandler())
    return opener.open(req, timeout=timeout)


def format_connect_error(host: "str | None", detail) -> str:
    """The ONE canonical wording for a connect-phase failure (hotfix 2's
    rule: "the error message names the host and says 'cannot resolve/reach
    <host> -- check the machine's network, DNS or VPN'") -- used for every
    provider (Databricks, OpenRouter, a direct Anthropic call, models.dev)
    so none of them invent their own variant. `detail` is the low-level
    exception (or any str-able detail) that actually triggered it, kept in
    parentheses for anyone debugging the underlying OS error; never part of
    the required phrase itself so `is_connect_failure_message` is never at
    the mercy of one platform's own errno text."""
    named = host or "the upstream host"
    return f"{CONNECT_FAILURE_MARKER} {named} -- check the machine's network, DNS or VPN ({detail})"


def format_post_connect_error(host: "str | None", detail) -> str:
    """1.0.1 fixpass finding 2: wording for a failure AFTER open_upstream()
    already handed back a connected socket -- i.e. `conn.request()`/
    `conn.getresponse()` raised (a dropped keep-alive, a server-side RST
    mid-response, the 300s idle-timeout waiting for headers), never
    `open_upstream()`/`_bounded_connect` itself. Deliberately WITHOUT
    CONNECT_FAILURE_MARKER: this is not a DNS/routing/VPN problem (the
    connection WAS established), so `is_connect_failure_message` must not
    mistake it for one and make `agent/loop.py` skip its normal retry
    ladder -- a load balancer dropping one keep-alive while the upstream
    queues the request should retry like any other transient 5xx, not die
    after phase 1's own single immediate reconnect attempt. Still wrapped
    in `UpstreamConnectError` (same type a real connect failure raises) so
    `_run_phase1_attempts`/`_run_phase1_anthropic`'s existing "retry once
    immediately, then map to a plain 502" handling is unchanged -- only the
    wording (and therefore `is_connect_failure_message`'s verdict) differs."""
    named = host or "the upstream host"
    return f"upstream connection to {named} was interrupted ({detail})"


def _bounded_connect(conn, timeout_s: float, host: str) -> None:
    """Runs `conn.connect()` (which performs `getaddrinfo` THEN the TCP/TLS
    handshake) on a background thread and waits at most `timeout_s`
    wall-clock seconds for it. A per-socket `timeout=` (what `conn` was
    already constructed with) only ever bounds the handshake -- `getaddrinfo`
    itself takes no timeout argument at the stdlib level, so a slow/
    unresponsive/black-holed DNS resolver can otherwise block for far longer
    than any `connect_timeout` implies (verified: ~64s against an
    unresolvable `*.cloud.databricks.com` host). On expiry, the background
    thread is ABANDONED, never killed (Python cannot forcibly cancel a
    blocking C call) -- same "abandoned, not stopped" caveat as every other
    abort-aware wait in this codebase (see tui/dialogs/mcp_status.py) -- and
    this call raises UpstreamConnectError immediately either way, so the
    caller never actually waits on it past `timeout_s`.

    2.0.1 finding 18: an abandoned connect that later succeeds (or fails
    PART way through -- e.g. the TCP handshake lands but a slow TLS
    handshake is what actually blew the budget, leaving `conn.sock` set to
    a raw, un-wrapped socket) used to leak that socket forever -- nobody
    else ever gets a reference to `conn` once this function has already
    raised and moved on. `_target` itself closes `conn` the moment it
    finishes IF this function already gave up on it (`abandoned` below),
    whether that finish was a success or a late failure -- `HTTPConnection.
    close()` is a safe no-op when `.sock` is None."""
    outcome: list = []
    done = threading.Event()
    abandoned = threading.Event()

    def _target() -> None:
        try:
            conn.connect()
        except BaseException as e:  # noqa: BLE001 -- relayed to the waiter, never swallowed
            outcome.append(e)
        finally:
            done.set()
        if abandoned.is_set():
            try:
                conn.close()
            except Exception:
                pass

    t = threading.Thread(target=_target, daemon=True, name="rolo-connect")
    t.start()
    if not done.wait(timeout_s):
        abandoned.set()
        raise UpstreamConnectError(
            format_connect_error(host, f"timed out after {timeout_s:.0f}s connecting -- "
                                        f"likely a DNS lookup that never returned"),
            host=host)
    if outcome:
        e = outcome[0]
        raise UpstreamConnectError(format_connect_error(host, e), host=host) from e


def pick_proxy(host: str) -> str | None:
    """Return proxy URL from env if host not bypassed, else None.

    Halo 2.0.3 fix pass C-1 (review finding 2): a loopback target, or a
    target already on the offline allow-list (`allowlisted_local_hosts`),
    is NEVER proxied -- checked FIRST, before `NO_PROXY`/`proxy_bypass_
    environment`'s own verdict, and unconditionally (this is a plain
    correctness fix, not only an offline-mode one: routing a loopback or
    LAN box's own traffic out to a remote HTTPS_PROXY/HTTP_PROXY host is
    never correct, offline mode on or not). Before this fix nothing
    exempted loopback/allow-listed hosts at all, so under offline mode a
    loopback or LAN `ol:`/`hf:local` request -- prompt body included --
    went to whatever HTTPS_PROXY/HTTP_PROXY named, same as it would have
    for any other host."""
    if _is_loopback_host(host):
        return None
    try:
        if (host or "").strip().lower() in allowlisted_local_hosts():
            return None
    except Exception:
        pass
    # Check bypass first
    if urllib.request.proxy_bypass_environment(host):
        return None

    # Check environment variables in order
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        proxy = os.environ.get(var)
        if proxy:
            return proxy
    return None


def open_upstream(host: str, port: int, tls: bool, connect_timeout: int = DEFAULT_CONNECT_TIMEOUT_S,
                   on_connect=None) -> http.client.HTTPConnection | http.client.HTTPSConnection:
    """Open HTTP(S) connection to upstream, respecting proxy and TLS
    settings. `on_connect` (must-do 5), when given, is called with the
    live `conn` object right after `connect()` succeeds -- BEFORE the
    caller sends the request or blocks in `getresponse()` -- so a caller
    that wants to interrupt a phase-1 call mid-flight (a genuinely
    blocking operation with no other hook point) can hand the socket to an
    abort watcher immediately, rather than only after the whole call
    returns. Exceptions from `on_connect` are swallowed (never let a
    watcher-registration bug break a real upstream call).

    1.0.1 hotfix 2: `connect_timeout` now bounds the WHOLE connect phase
    (DNS + TCP/TLS handshake), via `_bounded_connect`, not just the
    handshake -- and raises `UpstreamConnectError` (naming `host`) directly
    on either a timeout or an immediate failure (gaierror/refused/
    unreachable/...), rather than leaving a raw socket exception for every
    caller to catch and reformat itself.

    Halo 2.0.3 round 5e: `_check_offline_allowed(host)` runs FIRST, before
    `pick_proxy`/DNS/anything else -- this is the one HTTP choke point
    `call_openai_chat`/`call_ollama_chat`/`_dbx_post`/`proxy_anthropic` (and
    therefore every OpenAI-chat, Ollama native, Databricks, and Anthropic-
    passthrough request this harness makes) all funnel through, so offline
    enforcement lives here exactly once."""
    _check_offline_allowed(host)
    proxy_url = pick_proxy(host)
    # Halo 2.0.3 fix pass C-1 (review finding 2): defense in depth -- the
    # real socket peer whenever a proxy IS used is the PROXY host, never
    # `host` itself, so offline mode must gate that too. `pick_proxy`
    # above already returns None for any loopback/allow-listed `host`
    # (the ordinary case under offline, since `_check_offline_allowed`
    # just refused anything else), so this only ever fires if a FUTURE
    # change to `pick_proxy`'s own logic ever let a proxy through for an
    # offline-allowed host again.
    if proxy_url is not None:
        _check_offline_allowed(urllib.parse.urlparse(proxy_url).hostname)

    # 1.0.1 hotfix 11: built through default_tls_context() (VERIFY_X509_
    # STRICT cleared when present, same custom-CA-bundle env loading) --
    # never ssl.create_default_context() directly here anymore.
    ssl_context = default_tls_context() if tls else None

    # Determine connection parameters
    if proxy_url:
        proxy_parts = urllib.parse.urlparse(proxy_url)
        proxy_host = proxy_parts.hostname
        proxy_port = proxy_parts.port or (443 if proxy_parts.scheme == "https" else 80)
        
        if tls:
            # HTTPS via proxy tunnel
            conn = http.client.HTTPSConnection(
                proxy_host, proxy_port, timeout=connect_timeout, context=ssl_context
            )
            conn.set_tunnel(host, port)
        else:
            # HTTP via proxy
            conn = http.client.HTTPConnection(proxy_host, proxy_port, timeout=connect_timeout)
    else:
        # Direct connection
        if tls:
            conn = http.client.HTTPSConnection(
                host, port, timeout=connect_timeout, context=ssl_context
            )
        else:
            conn = http.client.HTTPConnection(host, port, timeout=connect_timeout)
    
    # Connect with timeout, then set idle timeout. Bounded (hotfix 2): a
    # hung/black-holed DNS resolution is capped at connect_timeout wall-clock
    # seconds, never the OS resolver's own (much longer) retry policy.
    _bounded_connect(conn, connect_timeout, host)
    if conn.sock:
        conn.sock.settimeout(300)  # 5 minutes idle timeout
    if on_connect is not None:
        try:
            on_connect(conn)
        except Exception:
            pass

    return conn


@dataclass
class UpstreamResult:
    """Result of an upstream HTTP call."""
    status: int
    headers: dict[str, str]
    resp: http.client.HTTPResponse | None
    conn: http.client.HTTPConnection | http.client.HTTPSConnection | None
    # Already-read raw response bytes when the producer had to consume `resp`
    # itself (e.g. call_databricks_chat peeking at a 400 body to look for a
    # max_tokens-limit wording before deciding whether to retry) -- None
    # means "resp has not been read yet, read it yourself".
    body_bytes: bytes | None = None


def governor_params_for_host(host: "str | None") -> "dict | None":
    """The Governor tuning for one gateway host: `governor.*` from
    config.json layered with `governor.hosts.<netloc>` per-host
    overrides, or None when the Governor is off (`governor.enabled`,
    default on; `HALO_GOVERNOR=0` forces off -- the test suite's default
    -- and `HALO_GOVERNOR=1` forces on, overriding config). Never
    raises.

    2.0.5 release-review nit 9: only an explicit YES spelling
    ("1"/"true"/"yes"/"on", case-insensitive) FORCES on; only an
    explicit NO spelling ("0"/"false"/"no"/"off") forces off. Any OTHER
    non-empty value -- a typo like "of", arbitrary text, an empty
    string -- is IGNORED and config decides, so a stray value can never
    silently switch every governed call on."""
    try:
        import os as _os
        from halo_harness.theme import get_config_value
        env_flag = (_os.environ.get("HALO_GOVERNOR") or "").strip().lower()
        if env_flag:
            if env_flag in ("0", "false", "no", "off"):
                return None
            if env_flag not in ("1", "true", "yes", "on"):
                env_flag = ""  # unrecognized: ignored, config decides
        if not env_flag:
            if not get_config_value("governor.enabled", default=True):
                return None
        cfg = get_config_value("governor", default={}) or {}
        if not isinstance(cfg, dict):
            cfg = {}
        hosts = cfg.get("hosts") or {}
        host_over = hosts.get((host or "").lower(), {}) if isinstance(hosts, dict) else {}
        merged = {k: v for k, v in cfg.items() if k not in ("enabled", "hosts")}
        if isinstance(host_over, dict):
            merged.update(host_over)
        return merged
    except Exception:
        return {}


def governed_upstream(host: "str | None", do_call, ctx: "dict | None" = None,
                      post_connect_error=None):
    """2.0.5 round 4: run ONE remote request through the Governor (the
    single choke point every model call in this module funnels through).

    `do_call()` must build and send the request and return an
    UpstreamResult (status known, resp unread). Pacing, the in-flight
    cap, priority fairness and overload reporting (honouring
    Retry-After) live here for every governed route; the transparent
    429/overload RETRY LADDER runs only for HARNESS calls (a non-None
    ctx -- agent/loop.py's own ladder steps aside for those): an
    overload response is read (bounded), reported, and the request
    RETRIED once the bucket's cooldown elapses, up to `max_retries` --
    then the last overload UpstreamResult is returned for the caller to
    surface. The PROXY (ctx=None) is a relay: its overload responses
    pass through single-shot exactly as before, still counted against
    the shared bucket (pacing and AIMD apply; only the retry is
    skipped -- the proxy's client asked once and gets the upstream's
    own answer, never a silently-retried one).

    A success returns the ORIGINAL UpstreamResult with the live `resp`
    untouched (streaming works exactly as before; the permit releases
    when headers arrive -- the gateway has accepted the request, which
    is what its rate limiter actually counts). Timeouts report with
    `timeout_signal` (two in a row cut the rate, one is a blip); other
    transport errors release NEUTRALLY and propagate; `abort` (the
    turn's abort event, threaded via ctx) interrupts a waiting acquire.

    ctx (None = the proxy's default): {agent, role, session, model,
    priority, abort}. `governor.enabled` false, a missing host, or the
    Governor import failing degrades to a plain `do_call()`.
    `post_connect_error(exc)` (each call site passes its own formatter)
    wraps a post-connect failure into the SAME UpstreamConnectError the
    ungoverned path raised, after the Governor has recorded the outcome
    -- the suite pins those wordings, and the governor must see the raw
    timeout identity first (two in a row count as overload).
    """
    params = governor_params_for_host(host)
    if params is None or not host:
        return do_call()
    from halo_harness.providers import governor
    from halo_harness.providers import governor_state as _gs
    key = "host:" + host.lower()
    # `c`, never a reassignment of `ctx`: "ctx is None" IS the proxy-vs-
    # harness distinction (the proxy relays, the harness retries) -- an
    # earlier `ctx = ctx or {}` here silently turned every proxy call
    # into a retrying harness call (found live by test_bridge's scripted
    # mock scenarios serving the NEXT row's status).
    c = ctx or {}
    gparams = governor.params_for({"name": host}, params)

    def _lock_contended(e) -> None:
        # 2.0.5 release-review finding 4: a LockFailed (the cross-process
        # lock unavailable past its timeout) must never escape the choke
        # point -- no call_* caller handles that type. governor_state's
        # own docstring promised one warning + the degraded flag + an
        # in-process fallthrough for that call; `warn_once` sets the flag,
        # `is_degraded()`/doctor report it.
        _gs.warn_once(f"governor: cross-process lock contended ({e}); "
                      "running this call ungoverned, in-process limiting only")

    def _report(*a, **k):
        try:
            return governor.report(*a, **k)
        except _gs.LockFailed as e:
            _lock_contended(e)
            return {}

    attempt = 0
    while True:
        try:
            h = governor.acquire(key, gparams, agent=c.get("agent", "system"),
                                 role=c.get("role", "main"), abort=c.get("abort"),
                                 explicit_priority=c.get("priority"),
                                 session=c.get("session"), model=c.get("model"))
        except _gs.LockFailed as e:
            _lock_contended(e)
            return do_call()
        try:
            result = do_call()
        except (TimeoutError, socket.timeout) as e:
            _report(h, ok=None, status=None, params=gparams, timeout_signal=True)
            if post_connect_error is not None:
                raise post_connect_error(e) from e
            raise
        except governor.GovernorAborted:
            raise
        except Exception as e:
            _report(h, ok=None, params=gparams)  # neutral: not evidence about load
            if post_connect_error is not None:
                raise post_connect_error(e) from e
            raise
        status = result.status
        if status == 500:
            # REVIEW item 6: 500 is neutral unless the body says overloaded.
            # 2.0.5 release-review finding 5: read(2048) truncated -- the
            # peeked bytes become `body_bytes`, which stream.py/the wire
            # mapper treat as the WHOLE body, so a long provider error
            # page was cut at 2 KB. 64 KB bounded read, still one read.
            try:
                peek = result.resp.read(65536) if result.resp is not None else b""
                result.body_bytes = peek or result.body_bytes
            except Exception:
                peek = b""
            body_text = (peek or b"").decode("utf-8", "replace")
        else:
            body_text = ""
        overloaded = governor.is_overload_status(status, statuses=gparams.get("overload_statuses")) or \
            (status == 500 and governor.is_overload_body(body_text))
        retry_after = governor.retry_after_seconds(result.headers, cap=gparams.get("retry_after_cap", 120.0)) \
            if overloaded else None
        telem = _report(h, ok=not overloaded, status=status, retry_after=retry_after, params=gparams)
        on_event = c.get("on_event")
        if telem.get("event") and on_event is not None:
            on_event(telem)
        if not overloaded:
            return result
        # the proxy (ctx=None) relays single-shot: counted against the
        # bucket, never silently retried -- only the harness retries.
        if ctx is None:
            return result
        attempt += 1
        if attempt > int(gparams.get("max_retries", 5)):
            return result  # the caller surfaces the last overload
        # 2.0.5 release-review finding 1: drain and close the overload
        # response BEFORE the retry, and ONLY here -- every call_* opens
        # ONE http.client connection outside `_send` and `_send` re-
        # `request()`s it, so an unread `getresponse()` makes the next
        # `conn.request()` raise ResponseNotReady (wrapped by call_* as a
        # marker-less UpstreamConnectError the loop then retries as a 502)
        # or corrupts the next parse. Never on the return paths: a success
        # (and the proxy's single-shot overload) must leave `resp`
        # untouched for streaming.
        try:
            result.resp.read()
            result.resp.close()
        except Exception:
            pass
        # loop: acquire() waits out the cooldown just set


def call_openai_chat(base_url: str, api_key: str, body: dict, extra_headers: dict, state_dir: Path,
                      on_connect=None, governor_ctx: "dict | None" = None) -> UpstreamResult:
    """POST to OpenAI-compatible chat completions endpoint (through the
    Governor's choke point -- `governed_upstream`)."""
    # Normalize base_url
    if base_url.endswith("/"):
        base_url = base_url.rstrip("/")
    
    # Parse URL to get host/port/tls
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    tls = parsed.scheme == "https"
    
    # Prepare request
    path = parsed.path + "/chat/completions"
    if not path.startswith("/"):
        path = "/" + path
    
    body_bytes = jdumps(body)
    dump_debug(state_dir, "upstream-request", body)
    
    # Build headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept-Encoding": "identity",
        "HTTP-Referer": "https://github.com/rolo/claude-bridge",
        "X-Title": "claude-bridge",
        "Content-Length": str(len(body_bytes)),
    }
    # Merge extra_headers on top (overriding defaults)
    headers.update(extra_headers)
    
    # 1.0.1 fixpass finding 2: two SEPARATE try/excepts, not one wrapping
    # both phases -- a failure opening the connection is still a genuine
    # connect failure (format_connect_error, the marker kept) even when
    # open_upstream itself raises a raw OSError (a test double, or any
    # future caller that doesn't go through _bounded_connect's own
    # UpstreamConnectError); only a failure from conn.request()/
    # getresponse() -- AFTER the connection is already open -- gets the
    # marker-free wording (format_post_connect_error).
    try:
        conn = open_upstream(host, port, tls, on_connect=on_connect)
    except (OSError, socket.timeout, ssl.SSLError, http.client.HTTPException) as e:
        raise UpstreamConnectError(format_connect_error(host, e), host=host) from e

    def _send() -> UpstreamResult:
        conn.request("POST", path, body=body_bytes, headers=headers)
        resp = conn.getresponse()
        resp_headers = {k.lower(): v for k, v in resp.getheaders()}
        return UpstreamResult(status=resp.status, headers=resp_headers, resp=resp, conn=conn)

    def _post_connect_err(e) -> Exception:
        return UpstreamConnectError(format_post_connect_error(host, e), host=host)

    return governed_upstream(host, _send, governor_ctx, post_connect_error=_post_connect_err)


def call_openai_responses(base_url: str, api_key: str, body: dict, extra_headers: dict, state_dir: Path,
                           on_connect=None, governor_ctx: "dict | None" = None) -> UpstreamResult:
    """POST to the OpenAI Responses endpoint (`<base_url>/responses`) --
    Halo 2.0.3 round 5i part 1, the `openai-responses` dialect's own
    sibling of `call_openai_chat` just above: same headers/connect/retry
    shape, only the path differs (`docs/harness/OPENAI-RESEARCH.md`
    section 1 confirms the request is an ordinary POST, same as chat
    completions)."""
    if base_url.endswith("/"):
        base_url = base_url.rstrip("/")
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    tls = parsed.scheme == "https"
    path = parsed.path + "/responses"
    if not path.startswith("/"):
        path = "/" + path

    body_bytes = jdumps(body)
    dump_debug(state_dir, "upstream-request", body)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept-Encoding": "identity",
        "Content-Length": str(len(body_bytes)),
    }
    headers.update(extra_headers)

    try:
        conn = open_upstream(host, port, tls, on_connect=on_connect)
    except (OSError, socket.timeout, ssl.SSLError, http.client.HTTPException) as e:
        raise UpstreamConnectError(format_connect_error(host, e), host=host) from e

    def _send() -> UpstreamResult:
        conn.request("POST", path, body=body_bytes, headers=headers)
        resp = conn.getresponse()
        resp_headers = {k.lower(): v for k, v in resp.getheaders()}
        return UpstreamResult(status=resp.status, headers=resp_headers, resp=resp, conn=conn)

    def _post_connect_err(e) -> Exception:
        return UpstreamConnectError(format_post_connect_error(host, e), host=host)

    return governed_upstream(host, _send, governor_ctx, post_connect_error=_post_connect_err)


def call_ollama_chat(base_url: str, api_key: "str | None", body: dict, extra_headers: dict, state_dir: Path,
                     on_connect=None, governor_ctx: "dict | None" = None) -> UpstreamResult:
    """POST to Ollama's native `/api/chat` (Halo 2.0.3 round 2) -- local,
    LAN, or Ollama Cloud, all through this one function: only `base_url`
    and whether `api_key` is set (an unauthenticated local/LAN host passes
    `None`; a cloud host's own `api_key` becomes `Authorization: Bearer
    <api_key>`, research doc Q7) ever differ. No `Accept-Encoding: identity`
    override here -- `/api/chat`'s NDJSON stream is already line-delimited
    JSON with no gzip framing to fight, unlike the SSE dialects' own
    override (kept there for a different reason: an intermediary that
    buffers a whole gzip frame before forwarding it would break SSE's
    "flush every line" requirement)."""
    if base_url.endswith("/"):
        base_url = base_url.rstrip("/")
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    tls = parsed.scheme == "https"
    path = parsed.path.rstrip("/") + "/api/chat"
    if not path.startswith("/"):
        path = "/" + path

    body_bytes = jdumps(body)
    dump_debug(state_dir, "upstream-request", body)

    headers = {"Content-Type": "application/json", "Content-Length": str(len(body_bytes))}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    headers.update(extra_headers)

    try:
        conn = open_upstream(host, port, tls, on_connect=on_connect)
    except (OSError, socket.timeout, ssl.SSLError, http.client.HTTPException) as e:
        raise UpstreamConnectError(format_connect_error(host, e), host=host) from e

    def _send() -> UpstreamResult:
        conn.request("POST", path, body=body_bytes, headers=headers)
        resp = conn.getresponse()
        resp_headers = {k.lower(): v for k, v in resp.getheaders()}
        return UpstreamResult(status=resp.status, headers=resp_headers, resp=resp, conn=conn)

    def _post_connect_err(e) -> Exception:
        return UpstreamConnectError(format_post_connect_error(host, e), host=host)

    return governed_upstream(host, _send, governor_ctx, post_connect_error=_post_connect_err)


def _dbx_post(base_url: str, path: str, api_key: str, req_body: dict, extra_headers: dict, state_dir,
              on_connect=None, governor_ctx: "dict | None" = None):
    """POST to a Databricks endpoint, returning (resp, conn) or raising UpstreamConnectError."""
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    tls = parsed.scheme == "https"
    path = parsed.path.rstrip("/") + path
    body_bytes = jdumps(req_body)
    dump_debug(state_dir, "upstream-request", req_body)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept-Encoding": "identity",
        "Content-Length": str(len(body_bytes)),
    }
    headers.update(extra_headers)
    # 1.0.1 fixpass finding 2: see call_openai_chat's matching comment --
    # open_upstream's own failure keeps the marker; only a post-connect
    # conn.request()/getresponse() failure gets the marker-free wording.
    try:
        conn = open_upstream(host, port, tls, on_connect=on_connect)
    except (OSError, socket.timeout, ssl.SSLError, http.client.HTTPException) as e:
        raise UpstreamConnectError(format_connect_error(host, e), host=host) from e

    class _RespResult(UpstreamResult):
        """_dbx_post returns (resp, conn), not UpstreamResult -- a tiny
        adapter lets it share the governed_upstream choke point."""

        def __init__(self, resp, conn):
            super().__init__(status=resp.status,
                             headers={k.lower(): v for k, v in resp.getheaders()},
                             resp=resp, conn=conn)

    def _send():
        conn.request("POST", path, body=body_bytes, headers=headers)
        resp = conn.getresponse()
        return _RespResult(resp, conn)

    def _post_connect_err(e) -> Exception:
        return UpstreamConnectError(format_post_connect_error(host, e), host=host)

    result = governed_upstream(host, _send, governor_ctx, post_connect_error=_post_connect_err)
    return result.resp, result.conn


def call_databricks_chat(base_url: str, api_key: str, body: dict, extra_headers: dict, state_dir, model: str,
                          on_connect=None, governor_ctx: "dict | None" = None) -> UpstreamResult:
    """POST an OpenAI-chat body to a Databricks route, trying the cached/
    candidate paths with 404 fallback and a max_tokens-limit clamp-retry.
    H14 scope D: candidates (path, whether the body needs "model", and
    WHICH string to put there) come from `providers.dbx_routing.
    chat_route_candidates` -- the discovered `~/.halo/dbx-endpoints.
    json` cache's family/api_types RULES-table order when `model` (the
    endpoint/model name) is in it, else today's static order unchanged."""
    # Deferred import: breaks the http.py <-> databricks.py module cycle
    # (see this module's docstring). By the time this function is actually
    # CALLED, both modules have finished initializing, so a plain `from`
    # import here behaves exactly like a top-level one.
    from halo_harness.providers.databricks import (
        build_databricks_body,
        parse_databricks_max_tokens_limit,
        dbx_cache_get_route,
        dbx_cache_set_route,
        dbx_cache_set_max_tokens_limit,
    )
    from halo_harness.providers.dbx_routing import RouteCandidate, chat_route_candidates
    candidates = chat_route_candidates(model, state_dir)
    if not candidates:
        # Defensive only -- callers (model.py's own ModelRef construction,
        # work_matrix.py's own probe loop) already refuse/skip a known
        # non-chat endpoint before ever reaching here, so this is normally
        # unreachable; never crash on an unpack of an empty `chosen` if it
        # somehow is (a direct/future call site that skips that check).
        candidates = [RouteCandidate(key="invocations", path=f"/serving-endpoints/{model}/invocations",
                                      include_model=False, model_value=None)]
    cached_idx = dbx_cache_get_route(model, state_dir)
    if cached_idx is not None and 0 <= cached_idx < len(candidates):
        order = [(cached_idx, candidates[cached_idx])]
        order += [(i, cand) for i, cand in enumerate(candidates) if i != cached_idx]
    else:
        order = list(enumerate(candidates))

    chosen = None  # (orig_idx, candidate, resp, conn)
    for pos, (orig_idx, candidate) in enumerate(order):
        req_body = build_databricks_body(body, candidate.include_model, candidate.model_value)
        resp, conn = _dbx_post(base_url, candidate.path, api_key, req_body, extra_headers, state_dir,
                                on_connect=on_connect, governor_ctx=governor_ctx)
        if resp.status == 404 and pos != len(order) - 1:
            resp.read()
            continue
        chosen = (orig_idx, candidate, resp, conn)
        break

    orig_idx, candidate, resp, conn = chosen
    dbx_cache_set_route(model, orig_idx, state_dir)
    headers = {k.lower(): v for k, v in resp.getheaders()}

    if resp.status == 400:
        raw = resp.read()
        try:
            err_obj = json.loads(raw.decode("utf-8", "replace")) if raw else {}
        except (json.JSONDecodeError, ValueError):
            err_obj = {"error": {"message": raw.decode("utf-8", "replace")}}
        # finding 2/6: Databricks' own shape is {"error_code":...,"message":...}
        # -- no nested "error" object at all -- and a bare {"error":"boom"}
        # used to crash the old ad hoc ".get('error') or {}).get('message')"
        # extraction with AttributeError.
        err_msg = upstream_error_text(err_obj)
        limit = parse_databricks_max_tokens_limit(err_msg)
        if limit is not None and isinstance(body.get("max_tokens"), int) and body["max_tokens"] > limit:
            # Done with the first attempt's connection -- close it before opening a second one.
            try:
                resp.close()
                conn.close()
            except Exception:
                pass
            retry_body = dict(body)
            retry_body["max_tokens"] = limit
            req_body = build_databricks_body(retry_body, candidate.include_model, candidate.model_value)
            resp2, conn2 = _dbx_post(base_url, candidate.path, api_key, req_body, extra_headers, state_dir,
                                      on_connect=on_connect, governor_ctx=governor_ctx)
            dbx_cache_set_max_tokens_limit(model, limit, state_dir)
            headers2 = {k.lower(): v for k, v in resp2.getheaders()}
            return UpstreamResult(status=resp2.status, headers=headers2, resp=resp2, conn=conn2, body_bytes=None)
        return UpstreamResult(status=400, headers=headers, resp=resp, conn=conn, body_bytes=raw)

    return UpstreamResult(status=resp.status, headers=headers, resp=resp, conn=conn, body_bytes=None)




def proxy_anthropic(base_url: str, api_key: str, body: dict, extra_headers: dict, state_dir, path: str = "/v1/messages",
                     query_suffix: str = "?beta=true", on_connect=None,
                     governor_ctx: "dict | None" = None) -> UpstreamResult:
    """POST an already-shaped Anthropic-format body straight through to a
    native Claude endpoint; raw relay, no dialect translation. Originally
    Databricks-only (hence the hardcoded `?beta=true`, kept as the default
    so every existing caller is byte-for-byte unaffected); H5 scope C's
    `call_anthropic_native` (below) reuses this SAME function for BOTH
    Databricks' Claude passthrough (`query_suffix` left at its default) and
    a direct `ant:` call to api.anthropic.com (`query_suffix=""` -- a real
    Anthropic endpoint has no use for Databricks' own gateway flag)."""
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    tls = parsed.scheme == "https"
    request_path = parsed.path.rstrip("/") + path + query_suffix
    body_bytes = jdumps(body)
    dump_debug(state_dir, "upstream-request", body)
    headers = {
        "Content-Type": "application/json",
        "Accept-Encoding": "identity",
        "Content-Length": str(len(body_bytes)),
    }
    headers.update(extra_headers)
    # 1.0.1 fixpass finding 2: see call_openai_chat's matching comment --
    # open_upstream's own failure keeps the marker; only a post-connect
    # conn.request()/getresponse() failure gets the marker-free wording.
    try:
        conn = open_upstream(host, port, tls, on_connect=on_connect)
    except (OSError, socket.timeout, ssl.SSLError, http.client.HTTPException) as e:
        raise UpstreamConnectError(format_connect_error(host, e), host=host) from e

    def _send() -> UpstreamResult:
        conn.request("POST", request_path, body=body_bytes, headers=headers)
        resp = conn.getresponse()
        resp_headers = {k.lower(): v for k, v in resp.getheaders()}
        return UpstreamResult(status=resp.status, headers=resp_headers, resp=resp, conn=conn, body_bytes=None)

    def _post_connect_err(e) -> Exception:
        return UpstreamConnectError(format_post_connect_error(host, e), host=host)

    return governed_upstream(host, _send, governor_ctx, post_connect_error=_post_connect_err)


def call_anthropic_native(base_url: str, api_key: str, body: dict, extra_headers: dict, state_dir,
                           route_provider: str, on_connect=None,
                           governor_ctx: "dict | None" = None) -> UpstreamResult:
    """H5 scope C: the ONE call site `stream.stream_anthropic_completion`
    uses for every native-Anthropic-dialect route. `route_provider` picks
    the host-specific bits `proxy_anthropic` itself stays agnostic of:
      - "anthropic" (`ant:`): `x-api-key`, `anthropic-version`, no
        Databricks gateway query flag.
      - "databricks" (`dbx:databricks-claude-*`/`dbx:system.ai.claude-*`):
        `Authorization: Bearer <token>`, `x-databricks-use-coding-agent-
        mode: true` (both already merged into `extra_headers` by the
        caller, same as the OpenAI-dialect Databricks path), Databricks'
        own `?beta=true` gateway flag on the primary path, and a 404
        fallback to the endpoint's OWN by-name invocations path -- see the
        V2b fix note below.
      - "experiential" (`xp:claude-*`, Halo 2.0.4 round 2): `x-api-key`,
        same as "anthropic" -- the gateway accepts it on `/v1/messages`
        "matching Anthropic SDK behavior" (research doc section 2) -- but
        `base_url` already carries the gateway's `/v1` path segment
        (`ExpConfig.base_url`), unlike api.anthropic.com's bare root, so
        the path passed to `proxy_anthropic` is `/messages` alone (that
        plus `base_url`'s own `/v1` gives the correct `/v1/messages`,
        never a doubled `/v1/v1/messages`); no Databricks gateway query
        flag."""
    if route_provider == "anthropic":
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        headers.update(extra_headers)
        return proxy_anthropic(base_url, api_key, body, headers, state_dir,
                                path="/v1/messages", query_suffix="", on_connect=on_connect)
    if route_provider == "experiential":
        headers = {"x-api-key": api_key}
        headers.update(extra_headers)
        return proxy_anthropic(base_url, api_key, body, headers, state_dir,
                                path="/messages", query_suffix="", on_connect=on_connect)
    # finding 16 (major, h4-h5-h3c review): the databricks branch never
    # added `Authorization: Bearer <token>` -- this docstring (and
    # headless.py's own extra_headers construction) CLAIMED it was
    # "already merged into extra_headers by the caller", but `build_session`
    # only ever adds `x-databricks-use-coding-agent-mode` there; every
    # Databricks Claude passthrough call (`dbx:databricks-claude-*`/
    # `dbx:system.ai.claude-*`) went out with no auth at all and 401/403'd.
    # `proxy_anthropic` itself never uses its own `api_key` parameter for
    # anything (it just relays whatever `headers` it's given), so the
    # header has to be added HERE, same as the "anthropic" branch above
    # does for `x-api-key`.
    headers = {"Authorization": f"Bearer {api_key}"}
    headers.update(extra_headers)
    # databricks: try the ai-gateway path first, fall back on a 404 to the
    # endpoint's OWN by-name invocations path -- `/serving-endpoints/<name>/
    # invocations`, the SAME universal last-resort candidate `docs/
    # DATABRICKS.md`'s routing table and `chat_route_candidates` (the
    # openai-chat dialect's own route table) already use for every family.
    # V2b fix (flagged during V2a): this used to hardcode the LITERAL,
    # non-existent endpoint name "anthropic" here
    # (`/serving-endpoints/anthropic/v1/messages`) -- no real workspace has
    # a serving endpoint actually named "anthropic"; the real name is
    # always `body["model"]` (`build_anthropic_request_body` always sets
    # it to `route.upstream_model`), same field `call_databricks_chat`
    # already reads for the identical purpose on the openai-chat side. No
    # query suffix on the fallback -- a plain invocations call never uses
    # Databricks' `?beta=true` AI-gateway flag (see `call_databricks_chat`/
    # `_dbx_post`, which never appends one either).
    endpoint_name = body.get("model") or ""
    fallback_path = f"/serving-endpoints/{endpoint_name}/invocations"
    for path, query_suffix in (("/ai-gateway/anthropic/v1/messages", "?beta=true"), (fallback_path, "")):
        result = proxy_anthropic(base_url, api_key, body, headers, state_dir, governor_ctx=governor_ctx,
                                  path=path, query_suffix=query_suffix, on_connect=on_connect)
        if result.status != 404:
            return result
        try:
            if result.resp is not None:
                result.resp.read()
        except Exception:
            pass
        # NEW (H9 post-acceptance): a 404'd attempt's own connection was
        # never closed before looping to try the next candidate path --
        # `result` (and its `.conn`) is about to be discarded/overwritten
        # by the next iteration either way, so this is the last chance.
        try:
            if result.conn is not None:
                result.conn.close()
        except Exception:
            pass
    return result


def call_databricks_count_tokens(base_url: str, api_key: str, body: dict, extra_headers: dict, state_dir) -> UpstreamResult:
    """Blocking (non-streaming) relay to Databricks' count_tokens endpoint."""
    return proxy_anthropic(base_url, api_key, body, extra_headers, state_dir, path="/v1/messages/count_tokens")


def passthrough_reader_thread(resp, q) -> None:
    """Background thread: read the upstream Databricks Claude response in raw chunks and post them to q."""
    try:
        while True:
            chunk = resp.read1(65536)
            if not chunk:
                q.put(("eof", None))
                break
            q.put(("raw", chunk))
    except Exception as e:
        q.put(("exc", e))
    finally:
        try:
            resp.close()
        except Exception:
            pass
