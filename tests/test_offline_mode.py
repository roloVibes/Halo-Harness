"""tests.test_offline_mode -- Halo 2.0.3 round 5e: enforced offline mode.
`providers.http`'s `_check_offline_allowed`/`open_upstream`/`urlopen_tls`
gate, the allow-list (`ollama.hosts`/`huggingface.local_servers`/the
managed-server registry), loopback still reachable under offline, the
status bar's "offline" chip, and an invariant test (test_privacy_scan.py's
own grep style) that every raw network-opening call in the tracked tree
goes through the one choke point or is a named, reasoned exception.

Hermetic throughout: every test scopes `BRIDGE_TEST_HOME`/`BRIDGE_STATE_DIR`
itself (`_fresh_state_dir`/`build_fake_home`, the same helpers every other
suite in this tree uses) and restores `HALO_OFFLINE` when it touches it --
never the real `~/.halo`.
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.fake_home import build_fake_home

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()


def _env(fn):
    """Snapshot/restore HALO_OFFLINE and BRIDGE_TEST_HOME/BRIDGE_STATE_DIR
    around one test -- the same per-test env-scoping convention every other
    suite here uses, applied to exactly the names this file touches."""
    import functools

    @functools.wraps(fn)
    def wrapper(ctx):
        keys = ("HALO_OFFLINE", "BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")
        saved = {k: os.environ.get(k) for k in keys}
        try:
            return fn(ctx)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    return wrapper


# ---------------------------------------------------------------------------
# The gate itself
# ---------------------------------------------------------------------------

@test
@_env
def test_offline_off_by_default_never_blocks(ctx: Ctx):
    os.environ.pop("HALO_OFFLINE", None)
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-off-")))
    from halo_harness.providers.http import _check_offline_allowed
    _check_offline_allowed("example.com")  # must not raise


@test
@_env
def test_offline_on_blocks_a_remote_host_with_the_plain_sentence(ctx: Ctx):
    os.environ["HALO_OFFLINE"] = "1"
    from halo_harness.providers.http import OfflineBlocked, _check_offline_allowed
    try:
        _check_offline_allowed("example.com")
        ctx.check("a remote host must raise OfflineBlocked", False)
    except OfflineBlocked as e:
        ctx.check(f"message names the host, got {e!r}", str(e) == "offline mode: not connecting to example.com")


@test
@_env
def test_offline_on_allows_loopback(ctx: Ctx):
    os.environ["HALO_OFFLINE"] = "1"
    from halo_harness.providers.http import _check_offline_allowed
    for host in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
        _check_offline_allowed(host)  # must not raise


@test
@_env
def test_offline_on_allows_a_configured_ollama_host(ctx: Ctx):
    """A LAN Ollama host the user actually configured in ollama.hosts is
    allow-listed by hostname, even though it is neither loopback nor the
    default host -- privacy-scan-safe: a hostname, never a numeric
    private-range IP literal. Fix pass C-1 (review finding 1): a bare
    configured hostname is no longer enough BY ITSELF -- `gpubox.local`
    qualifies because it is an `.local` mDNS name (a real LAN host would
    plausibly be named this way), never because it merely appears in
    ollama.hosts (that was finding 1's own bug: it let `ollama.com`
    through the exact same way)."""
    os.environ["HALO_OFFLINE"] = "1"
    fh_home = Path(tempfile.mkdtemp(prefix="offline-allow-"))
    os.environ["BRIDGE_TEST_HOME"] = str(fh_home)
    from halo_harness.theme import set_config_value
    set_config_value("ollama.hosts", [{"name": "gpubox", "url": "http://gpubox.local:11434"}])
    from halo_harness.providers.http import _check_offline_allowed
    _check_offline_allowed("gpubox.local")  # must not raise
    from halo_harness.providers.http import OfflineBlocked
    try:
        _check_offline_allowed("some-other-host.example")
        ctx.check("an UNCONFIGURED LAN-shaped host must still be refused", False)
    except OfflineBlocked:
        pass


@test
@_env
def test_offline_on_allows_a_configured_hf_local_server(ctx: Ctx):
    """Fix pass C-1 (review finding 1): the explicit `offline_ok: true`
    marker path -- a manual local-server entry whose URL is a real DNS
    name (not `.local`, not a bare single-label name, not a private IP
    literal) still counts as local once the user explicitly says so."""
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-hf-")))
    from halo_harness.theme import set_config_value
    set_config_value("huggingface.local_servers",
                      [{"name": "box", "url": "http://llm-box.example:8080", "offline_ok": True}])
    from halo_harness.providers.http import _check_offline_allowed
    _check_offline_allowed("llm-box.example")  # must not raise


@test
@_env
def test_offline_on_refuses_an_ollama_cloud_host_configured_as_a_host(ctx: Ctx):
    """Fix pass C-1 (review finding 1, critical): the exact repro --
    saving the Ollama tab with a cloud host (`https://ollama.com`, keyed
    by `api_key`, which the init Ollama tab's own help text invites with
    "add a LAN or cloud host") must never be allow-listed. Before this
    fix `allowlisted_local_hosts()` returned `ollama.com` right along
    with `127.0.0.1`, and `/offline on` kept sending `ol:` turns there."""
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-olcloud-")))
    from halo_harness.theme import set_config_value
    set_config_value("ollama.hosts", [{"name": "cloud", "url": "https://ollama.com", "api_key": "fake-not-real"}])
    from halo_harness.providers.http import OfflineBlocked, _check_offline_allowed
    try:
        _check_offline_allowed("ollama.com")
        ctx.check("ollama.com configured as a host must still be refused under offline", False)
    except OfflineBlocked as e:
        ctx.check(f"the plain user-facing sentence, got {e!r}",
                  str(e) == "offline mode: not connecting to ollama.com")


@test
@_env
def test_offline_on_refuses_ollama_cloud_via_ambient_env_with_no_config(ctx: Ctx):
    """Fix pass C-1: the SAME leak with no config.json entries at all --
    `OLLAMA_HOST=https://ollama.com` is the synthesized default host
    `resolve_ollama_hosts` builds when `ollama.hosts` is empty."""
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-olcloud-env-")))
    os.environ["OLLAMA_HOST"] = "https://ollama.com"
    try:
        from halo_harness.providers.http import OfflineBlocked, _check_offline_allowed
        try:
            _check_offline_allowed("ollama.com")
            ctx.check("ollama.com via ambient OLLAMA_HOST must still be refused under offline", False)
        except OfflineBlocked:
            pass
    finally:
        os.environ.pop("OLLAMA_HOST", None)


@test
@_env
def test_offline_on_refuses_a_public_hostname_entry_in_hf_local_servers(ctx: Ctx):
    """Fix pass C-1: the same bug, `huggingface.local_servers` side -- a
    public hostname pasted in by mistake (or a token-gated proxy that
    happens to be internet-facing) is never local just by being
    configured."""
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-hfpublic-")))
    from halo_harness.theme import set_config_value
    set_config_value("huggingface.local_servers", [{"name": "proxy", "url": "https://some-public-host.example"}])
    from halo_harness.providers.http import OfflineBlocked, _check_offline_allowed
    try:
        _check_offline_allowed("some-public-host.example")
        ctx.check("a public hostname entry must be refused under offline", False)
    except OfflineBlocked:
        pass


@test
@_env
def test_offline_on_allows_a_private_ip_literal_host(ctx: Ctx):
    """Fix pass C-1: a host configured as a literal private/documentation-
    range IP address (never a real LAN address in this tree -- 192.0.2.0/24
    is the RFC 5737 TEST-NET-1 documentation range `tests/test_privacy_
    scan.py`'s own `_LAN_IP_RE` does not flag) is local by
    `_is_private_ip_literal`, no hostname/marker needed."""
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-ipliteral-")))
    from halo_harness.theme import set_config_value
    set_config_value("ollama.hosts", [{"name": "docbox", "url": "http://192.0.2.10:11434"}])
    from halo_harness.providers.http import _check_offline_allowed
    _check_offline_allowed("192.0.2.10")  # must not raise


@test
@_env
def test_offline_on_allows_the_managed_server_registry(ctx: Ctx):
    os.environ["HALO_OFFLINE"] = "1"
    state_dir = Path(tempfile.mkdtemp(prefix="offline-managed-"))
    os.environ["BRIDGE_STATE_DIR"] = str(state_dir)
    from halo_harness.providers.local_runtime import save_registry
    save_registry(state_dir, [{"model": "m", "runtime": "llama-server", "pid": 1, "port": 1234,
                                "base_url": "http://127.0.0.1:1234", "started": "now", "keep": False}])
    from halo_harness.providers.http import allowlisted_local_hosts
    ctx.check(f"127.0.0.1 is in the allow-list from the registry, got {allowlisted_local_hosts()}",
              "127.0.0.1" in allowlisted_local_hosts())


# ---------------------------------------------------------------------------
# open_upstream / urlopen_tls themselves
# ---------------------------------------------------------------------------

@test
@_env
def test_open_upstream_refuses_a_remote_host(ctx: Ctx):
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-ou-")))
    from halo_harness.providers.http import OfflineBlocked, open_upstream
    try:
        open_upstream("example.com", 443, True)
        ctx.check("open_upstream must refuse a remote host while offline", False)
    except OfflineBlocked as e:
        ctx.check(f"is-a-UpstreamConnectError and names the host, got {e}",
                  "offline mode: not connecting to example.com" == str(e))


@test
@_env
def test_open_upstream_still_reaches_a_real_loopback_server(ctx: Ctx):
    """The allow-list point of the brief, proven against a REAL socket: a
    loopback listener is reachable even with offline mode on."""
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-loop-")))
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.listen(1)
    accepted = []

    def _accept_once():
        try:
            conn, _ = srv.accept()
            accepted.append(conn)
        except Exception:
            pass

    t = threading.Thread(target=_accept_once, daemon=True)
    t.start()
    from halo_harness.providers.http import open_upstream
    try:
        conn = open_upstream("127.0.0.1", port, False, connect_timeout=5)
        t.join(timeout=5)
        ctx.check("a real TCP connection to loopback was accepted", bool(accepted))
        conn.close()
    finally:
        for c in accepted:
            try:
                c.close()
            except Exception:
                pass
        srv.close()


# ---------------------------------------------------------------------------
# pick_proxy / the proxy choke point (fix pass C-1, review finding 2)
# ---------------------------------------------------------------------------

def _save_proxy_env():
    keys = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "NO_PROXY", "no_proxy")
    return {k: os.environ.get(k) for k in keys}


def _restore_proxy_env(saved):
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@test
@_env
def test_pick_proxy_never_proxies_loopback_or_allow_listed_hosts(ctx: Ctx):
    """Fix pass C-1 (review finding 2): nothing used to exempt loopback
    (or an allow-listed LAN host) from `HTTPS_PROXY`/`HTTP_PROXY` at all
    -- under offline mode a loopback/LAN request's prompt body would go
    to the proxy host. A non-local host is still proxied exactly as
    before (no regression) -- this fix is unconditional, not gated on
    offline mode being on."""
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-proxy-")))
    from halo_harness.theme import set_config_value
    set_config_value("ollama.hosts", [{"name": "docbox", "url": "http://192.0.2.11:11434"}])
    saved = _save_proxy_env()
    try:
        for k in ("https_proxy", "HTTP_PROXY", "http_proxy", "NO_PROXY", "no_proxy"):
            os.environ.pop(k, None)
        os.environ["HTTPS_PROXY"] = "http://192.0.2.254:3128"
        from halo_harness.providers.http import pick_proxy
        ctx.check("loopback is never proxied", pick_proxy("127.0.0.1") is None)
        ctx.check("an allow-listed LAN host is never proxied", pick_proxy("192.0.2.11") is None)
        ctx.check("a non-local host is still proxied (no regression)",
                  pick_proxy("example.com") == "http://192.0.2.254:3128")
    finally:
        _restore_proxy_env(saved)


@test
@_env
def test_open_upstream_uses_a_direct_opener_for_loopback_with_a_proxy_set(ctx: Ctx):
    """Fix pass C-1 (review finding 2), the brief's own pinning test:
    offline + a proxy env set -> the opener `open_upstream` builds for a
    LAN/loopback target is DIRECT, never a tunnel/proxy connection. Proven
    against a real loopback listener (same style as `test_open_upstream_
    still_reaches_a_real_loopback_server` above) with HTTPS_PROXY pointed
    at a bogus, never-dialed address -- if the fix regressed, this would
    either hang (a black-holed proxy) or connect to the wrong `conn.host`
    instead of the real loopback target."""
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-proxy-direct-")))
    saved = _save_proxy_env()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.listen(1)
    accepted = []

    def _accept_once():
        try:
            conn, _ = srv.accept()
            accepted.append(conn)
        except Exception:
            pass

    t = threading.Thread(target=_accept_once, daemon=True)
    t.start()
    try:
        for k in ("https_proxy", "HTTP_PROXY", "http_proxy", "NO_PROXY", "no_proxy"):
            os.environ.pop(k, None)
        os.environ["HTTPS_PROXY"] = "http://192.0.2.254:9"
        from halo_harness.providers.http import open_upstream
        conn = open_upstream("127.0.0.1", port, False, connect_timeout=5)
        t.join(timeout=5)
        ctx.check("the real loopback listener was accepted (never the bogus proxy)", bool(accepted))
        ctx.check(f"conn.host is the real target, not the proxy, got {conn.host!r}", conn.host == "127.0.0.1")
        conn.close()
    finally:
        _restore_proxy_env(saved)
        for c in accepted:
            try:
                c.close()
            except Exception:
                pass
        srv.close()


@test
@_env
def test_urlopen_tls_refuses_a_remote_host_given_a_bare_string(ctx: Ctx):
    """team_config.py's own caller passes a bare URL STRING, never a
    Request object -- the host-extraction fallback (`req if not hasattr
    (req, "full_url")`) must still work, not silently skip the gate."""
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-urlopen-")))
    from halo_harness.providers.http import OfflineBlocked, urlopen_tls
    try:
        urlopen_tls("https://example.com/team.json", timeout=1)
        ctx.check("urlopen_tls must refuse a remote host given a bare string", False)
    except OfflineBlocked as e:
        ctx.check(f"names the real host, got {e}", "example.com" in str(e))


@test
@_env
def test_urlopen_tls_refuses_a_remote_host_given_a_request_object(ctx: Ctx):
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-urlopen2-")))
    import urllib.request
    from halo_harness.providers.http import OfflineBlocked, urlopen_tls
    req = urllib.request.Request("https://api.github.com/x", headers={"User-Agent": "halo"})
    try:
        urlopen_tls(req, timeout=1)
        ctx.check("urlopen_tls must refuse a remote Request object while offline", False)
    except OfflineBlocked as e:
        ctx.check(f"names the real host, got {e}", "api.github.com" in str(e))


@test
@_env
def test_urlopen_tls_redirect_hop_is_re_gated_under_offline(ctx: Ctx):
    """Fix pass C-1 (review finding 21): `urlopen_tls` only ever gated the
    FIRST url -- urllib's own default redirect handler then followed any
    `Location` header with no gate of its own, so a loopback/allow-listed
    URL that answers with a 302 could bounce an offline call to an
    arbitrary host. `127.0.0.2` is deliberately NOT loopback by this
    tree's own narrow `_LOOPBACK_HOSTS` check (a literal set, never the
    whole 127.0.0.0/8 block) and is not configured anywhere, so it is
    refused exactly like any other non-local host -- same two addresses
    the finding's own verified repro used, both loopback-only (never a
    real network call)."""
    import http.server
    import socketserver
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-redirect-")))

    class _FastHTTPServer(http.server.HTTPServer):
        def server_bind(self):
            # `HTTPServer.server_bind` (unlike plain `TCPServer.server_
            # bind`) also does `self.server_name = socket.getfqdn(host)`
            # -- a REVERSE DNS lookup that is both a real resolver round
            # trip (never acceptable in a test) and, measured on this
            # host, ~9s slow for the unusual loopback address `127.0.0.2`.
            # Nothing this test's handlers do reads `server_name`, so the
            # literal address is just as good and keeps this hermetic.
            socketserver.TCPServer.server_bind(self)
            self.server_name = self.server_address[0]
            self.server_port = self.server_address[1]

    class _QuietHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

    port_holder = {}

    class _TargetHandler(_QuietHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

    class _RedirectHandler(_QuietHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.2:{port_holder['port']}/secret-path")
            self.send_header("Content-Length", "0")
            self.end_headers()

    target_srv = _FastHTTPServer(("127.0.0.2", 0), _TargetHandler)
    port_holder["port"] = target_srv.server_port
    redirect_srv = _FastHTTPServer(("127.0.0.1", 0), _RedirectHandler)
    for srv in (target_srv, redirect_srv):
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        from halo_harness.providers.http import OfflineBlocked, urlopen_tls
        url = f"http://127.0.0.1:{redirect_srv.server_port}/start"
        try:
            urlopen_tls(url, timeout=5)
            ctx.check("a redirect to a non-allow-listed host must be refused", False)
        except OfflineBlocked as e:
            ctx.check(f"names the redirect target, got {e}", "127.0.0.2" in str(e))
    finally:
        target_srv.shutdown()
        redirect_srv.shutdown()
        target_srv.server_close()
        redirect_srv.server_close()


@test
def test_is_offline_refusal_message_never_matches_a_connect_failure_message(ctx: Ctx):
    from halo_harness.providers.http import (
        format_connect_error, format_offline_refusal, is_connect_failure_message, is_offline_refusal_message,
    )
    connect_msg = format_connect_error("example.com", "boom")
    offline_msg = format_offline_refusal("example.com")
    ctx.check("a connect failure is never mistaken for an offline refusal",
              not is_offline_refusal_message(connect_msg))
    ctx.check("an offline refusal is never mistaken for a connect failure",
              not is_connect_failure_message(offline_msg))
    ctx.check("each marker matches its own message", is_connect_failure_message(connect_msg)
              and is_offline_refusal_message(offline_msg))


# ---------------------------------------------------------------------------
# The status bar's "offline" chip
# ---------------------------------------------------------------------------

@test
def test_status_bar_offline_chip(ctx: Ctx):
    """`StatusBar` is a real Textual `Static` widget -- `_refresh_display`'s
    own `self.update(text)` needs a mounted App (`textual._context.
    NoActiveAppError` otherwise, the same reason every OTHER test in this
    tree that touches the status bar uses a `_FakeStatusBar` double instead
    of the real widget). Rather than skip the real rendering logic
    entirely, `Static.update` itself is patched to just CAPTURE its `text`
    argument -- `_refresh_display`'s own Text-building (offline_str/
    saved-suffix included) still runs for real; only the actual widget
    paint is skipped."""
    from textual.widgets import Static
    from halo_harness.tui.widgets.statusbar import StatusBar
    captured = []
    original = Static.update
    Static.update = lambda self, content="": captured.append(content)
    try:
        bar = StatusBar(cwd="")
        ctx.check("offline defaults to False", bar.offline is False)
        ctx.check("no 'offline' chip rendered while off", "offline" not in captured[-1].plain)
        bar.set_offline(True)
        ctx.check("set_offline(True) takes effect", bar.offline is True)
        ctx.check(f"the 'offline' chip is rendered, got {captured[-1].plain!r}", "offline" in captured[-1].plain)
        bar.set_offline(False)
        ctx.check("chip disappears again", "offline" not in captured[-1].plain)
        bar.apply_status({"saved_usd": 0.0042})
        ctx.check(f"apply_status picks up saved_usd, got {bar.saved_usd}", bar.saved_usd == 0.0042)
        ctx.check(f"the chip shows the saved figure, got {captured[-1].plain!r}",
                  "saved $0.0042" in captured[-1].plain)
        bar.apply_status({})
        ctx.check("a status dict with no saved_usd key never blanks out a real reading", bar.saved_usd == 0.0042)
    finally:
        Static.update = original


# ---------------------------------------------------------------------------
# Invariant: every raw network-opening call in the tracked tree goes through
# the choke point, or is one of these named, reasoned exceptions.
# ---------------------------------------------------------------------------

# Each pattern is a raw primitive capable of opening a socket OUTSIDE
# providers.http's own open_upstream/urlopen_tls. (file, reason):
_ALLOWED_RAW_NETWORK_CALLERS = {
    "halo_harness/providers/http.py":
        "the choke point itself -- open_upstream/urlopen_tls/default_tls_context are DEFINED here using "
        "these primitives; _check_offline_allowed runs inside both before either is ever used",
    "halo_harness/tools/webfetch.py":
        "needs a same-host-redirect handler urlopen_tls doesn't offer; calls providers.http."
        "_check_offline_allowed directly, right before opening, so it is still gated",
    "halo_harness/mcp/oauth.py":
        "MCP SERVER OAuth discovery/token exchange -- a user-configured MCP server's own endpoint "
        "(which may itself be local), a separate concern from the model-provider/update/catalog network "
        "surface this round's brief enumerates; not wired to the offline gate this round",
}

_RAW_NETWORK_RE = re.compile(
    r"urllib\.request\.urlopen\(|http\.client\.HTTPSConnection\(|http\.client\.HTTPConnection\("
    r"|socket\.create_connection\(|urllib\.request\.build_opener\("
    r"|(?:^|[^.\w])urlopen\("
)


def _tracked_py_files() -> "list[Path]":
    try:
        out = subprocess.run(["git", "ls-files", "halo_harness"], capture_output=True, text=True,
                              cwd=str(REPO_DIR), check=True)
        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "halo_harness"],
                                    capture_output=True, text=True, cwd=str(REPO_DIR), check=True)
        lines = list(dict.fromkeys(out.stdout.splitlines() + untracked.stdout.splitlines()))
        return [REPO_DIR / p for p in lines if p.endswith(".py")]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in (REPO_DIR / "halo_harness").rglob("*.py") if "__pycache__" not in p.parts]


@test
def test_every_raw_network_call_is_the_choke_point_or_a_named_exception(ctx: Ctx):
    problems = []
    for path in _tracked_py_files():
        try:
            rel = path.resolve().relative_to(REPO_DIR).as_posix()
        except ValueError:
            continue
        if rel in _ALLOWED_RAW_NETWORK_CALLERS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for m in _RAW_NETWORK_RE.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            problems.append(f"{rel}:{line_no}: raw network call {m.group(0)!r} outside the choke point "
                             f"and not in _ALLOWED_RAW_NETWORK_CALLERS")
    ctx.check("no un-allowlisted raw network call found:\n  " + "\n  ".join(problems), not problems)


@test
def test_allowed_raw_network_callers_list_is_still_accurate(ctx: Ctx):
    """The companion direction: every file in the allow-list must still
    actually contain a raw network call -- an allow-list entry nobody
    needs any more is exactly the kind of stale carve-out that quietly
    hides a REAL gap reappearing somewhere else later."""
    problems = []
    for rel in _ALLOWED_RAW_NETWORK_CALLERS:
        path = REPO_DIR / rel
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        if not _RAW_NETWORK_RE.search(text):
            problems.append(f"{rel}: allow-listed but no raw network call found any more -- remove the entry")
    ctx.check("every allow-list entry is still needed:\n  " + "\n  ".join(problems), not problems)


# ---------------------------------------------------------------------------
# Network paths outside the http.py choke point (fix pass C-1, review
# finding 3): the update check, cc:/cx: turns + one-shot calls, `halo
# models --cx --refresh`, `--plugin-url`'s git clone, and `hf:mlx`'s
# download must all consult `network.offline` before starting too.
# ---------------------------------------------------------------------------

@test
@_env
def test_latest_available_skips_git_and_http_under_offline_but_not_online(ctx: Ctx):
    os.environ["HALO_OFFLINE"] = "1"
    state_dir = Path(tempfile.mkdtemp(prefix="offline-update-"))
    calls = []

    def _run(cmd, **kwargs):
        calls.append(cmd)
        raise AssertionError("git ls-remote must not run while offline")

    def _fetch(url, **kwargs):
        calls.append(url)
        raise AssertionError("the GitHub API must not be reached while offline")

    from halo_harness.update import latest_available
    result = latest_available("main", refresh=True, state_dir=state_dir, run_fn=_run, fetch_json=_fetch)
    ctx.check(f"no network call made while offline, calls={calls!r}", calls == [])
    ctx.check(f"reason mentions offline mode, got {result!r}", "offline" in (result.get("reason") or "").lower())

    # Online counterpart (the brief's own "online -> unchanged"): must
    # reach _fetch_latest as before -- bypass BRIDGE_TEST_NO_BACKGROUND_
    # NET too, which would otherwise short-circuit this for an unrelated
    # reason (a test-only seam, not this fix).
    os.environ["HALO_OFFLINE"] = "0"
    saved_bg = os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
    online_calls = []

    def _run_online(cmd, **kwargs):
        online_calls.append(cmd)
        class _R:
            returncode = 1
            stdout = ""
        return _R()

    def _fetch_online(url, **kwargs):
        online_calls.append(url)
        return None

    try:
        latest_available("main", refresh=True, state_dir=state_dir, run_fn=_run_online, fetch_json=_fetch_online)
        ctx.check(f"online -> run_fn/fetch_json IS reached (unchanged), calls={online_calls!r}",
                  len(online_calls) >= 1)
    finally:
        if saved_bg is not None:
            os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = saved_bg


@test
@_env
def test_apply_update_refuses_under_offline(ctx: Ctx):
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-apply-update-")))
    import io
    import contextlib
    import halo_harness.update as upd
    import halo_harness.update_cli as upd_cli

    def _boom_pids():
        raise AssertionError("other_halo_pids must not run before the offline check")

    def _boom_run(cmd, **kwargs):
        raise AssertionError("the reinstall command must not run while offline")

    original_pids, original_run = upd.other_halo_pids, upd.run
    upd.other_halo_pids, upd.run = _boom_pids, _boom_run
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf):
            code = upd_cli.apply_update()
        ctx.check(f"apply_update returns an error result, got {code!r}", code == 1)
        ctx.check(f"stderr names the offline sentence, got {buf.getvalue()!r}",
                  "offline mode: not connecting to" in buf.getvalue())
    finally:
        upd.other_halo_pids, upd.run = original_pids, original_run


@test
@_env
def test_cx_turn_refuses_under_offline_before_touching_codex(ctx: Ctx):
    """Tests `_preflight_cx` directly (not the full `ensure_cx_state`,
    which -- on a box where `codex` genuinely IS installed and logged in
    -- would proceed to actually START a real codex subprocess once
    preflight passes; this suite must never risk that no matter what
    happens to be installed on whatever machine runs it)."""
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-cx-turn-")))
    import halo_harness.agent.codex_runtime as cxrt
    calls = []
    original = cxrt.resolve_codex_launch_argv
    cxrt.resolve_codex_launch_argv = lambda: (calls.append(1) or original())
    try:
        err = cxrt._preflight_cx()
        ctx.check(f"a cx: turn must refuse while offline, got {err!r}",
                  err is not None and "offline mode: not connecting to" in err)
        ctx.check("resolve_codex_launch_argv (and so codex itself) is never reached", calls == [])

        os.environ["HALO_OFFLINE"] = "0"
        cxrt._preflight_cx()
        ctx.check("online -> the codex-launch resolution IS reached (unchanged)", calls == [1])
    finally:
        cxrt.resolve_codex_launch_argv = original


@test
@_env
def test_cc_turn_refuses_under_offline_before_touching_claude(ctx: Ctx):
    """Tests `_preflight_cc` directly -- see `test_cx_turn_refuses_
    under_offline_before_touching_codex`'s own docstring for why (this
    dev box genuinely has `claude` installed and logged in, so routing
    this through `ensure_cc_state` would risk starting a real subprocess
    once preflight passes)."""
    os.environ["HALO_OFFLINE"] = "1"
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-cc-turn-")))
    import halo_harness.agent.cc_runtime as ccrt
    calls = []
    original = ccrt.resolve_claude_launch_argv
    ccrt.resolve_claude_launch_argv = lambda: (calls.append(1) or original())
    try:
        err = ccrt._preflight_cc()
        ctx.check(f"a cc: turn must refuse while offline, got {err!r}",
                  err is not None and "offline mode: not connecting to" in err)
        ctx.check("resolve_claude_launch_argv (and so claude itself) is never reached", calls == [])

        os.environ["HALO_OFFLINE"] = "0"
        ccrt._preflight_cc()
        ctx.check("online -> the claude-launch resolution IS reached (unchanged)", calls == [1])
    finally:
        ccrt.resolve_claude_launch_argv = original


class _StubCompletedProcess:
    returncode = 1
    stdout = ""
    stderr = ""


@test
@_env
def test_one_shot_cx_call_refuses_under_offline_but_not_online(ctx: Ctx):
    os.environ["HALO_OFFLINE"] = "1"
    # The online half resolves the real launcher first; on a machine without a
    # codex install (the Kali VM) that fails before the stubbed subprocess.run
    # is reached, so point Halo at the fake codex (the stub still intercepts).
    os.environ["HALO_CODEX_EXE"] = '"' + sys.executable + '" "' + str(
        Path(__file__).resolve().parent / "helpers" / "fake_codex.py") + '"'
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-cx-oneshot-")))
    import halo_harness.agent.codex_process as cxp
    import halo_harness.agent.codex_runtime as cxrt
    # Pass-B finding 14: `one_shot_cx_call` now runs the subprocess through
    # `run_bounded_codex_subprocess` (its own process-group/watchdog
    # wrapper around `subprocess.Popen`, never a bare `subprocess.run`) --
    # stubbed there instead of on `subprocess.run`, which this call no
    # longer reaches at all. `one_shot_cx_call` imports the name LOCALLY
    # at call time (`from halo_harness.agent.codex_process import
    # run_bounded_codex_subprocess`), so patching the module attribute
    # here is what that import actually resolves.
    original = cxp.run_bounded_codex_subprocess
    calls = []
    cxp.run_bounded_codex_subprocess = lambda *a, **k: (calls.append(1), _StubCompletedProcess())[1]
    try:
        try:
            cxrt.one_shot_cx_call("gpt-5", "sys", "user")
            ctx.check("the cx: one-shot call must refuse while offline", False)
        except RuntimeError as e:
            ctx.check(f"names the plain offline sentence, got {e!r}",
                      "offline mode: not connecting to" in str(e))
        ctx.check("no subprocess is ever invoked while offline", calls == [])

        os.environ["HALO_OFFLINE"] = "0"
        try:
            cxrt.one_shot_cx_call("gpt-5", "sys", "user")
        except RuntimeError:
            pass  # the stub's own dummy output is never parseable -- expected
        ctx.check("online -> the subprocess IS invoked (unchanged, stubbed)", calls == [1])
    finally:
        cxp.run_bounded_codex_subprocess = original


@test
@_env
def test_one_shot_cc_call_refuses_under_offline_but_not_online(ctx: Ctx):
    os.environ["HALO_OFFLINE"] = "1"
    # The online half resolves the real claude launcher first; without one
    # (CI runners) point Halo at the fake so the stubbed subprocess is reached.
    os.environ["BRIDGE_CLAUDE_EXE"] = '"' + sys.executable + '" "' + str(
        Path(__file__).resolve().parent / "helpers" / "fake_claude_cc.py") + '"'
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-cc-oneshot-")))
    import subprocess
    import halo_harness.agent.cc_runtime as ccrt
    original = subprocess.run
    calls = []
    subprocess.run = lambda *a, **k: (calls.append(1), _StubCompletedProcess())[1]
    try:
        try:
            ccrt.one_shot_cc_call("claude-x", "sys", "user")
            ctx.check("the cc: one-shot call must refuse while offline", False)
        except RuntimeError as e:
            ctx.check(f"names the plain offline sentence, got {e!r}",
                      "offline mode: not connecting to" in str(e))
        ctx.check("no subprocess is ever invoked while offline", calls == [])

        os.environ["HALO_OFFLINE"] = "0"
        try:
            ccrt.one_shot_cc_call("claude-x", "sys", "user")
        except RuntimeError:
            pass  # the stub's own dummy output is never parseable -- expected
        ctx.check("online -> the subprocess IS invoked (unchanged, stubbed)", calls == [1])
    finally:
        subprocess.run = original


@test
@_env
def test_refresh_cx_catalog_skips_under_offline_but_not_online(ctx: Ctx):
    os.environ["HALO_OFFLINE"] = "1"
    # The online half resolves the real launcher first; on a machine without a
    # codex install (the Kali VM) that fails before the stubbed subprocess.run
    # is reached, so point Halo at the fake codex (the stub still intercepts).
    os.environ["HALO_CODEX_EXE"] = '"' + sys.executable + '" "' + str(
        Path(__file__).resolve().parent / "helpers" / "fake_codex.py") + '"'
    state_dir = Path(tempfile.mkdtemp(prefix="offline-cx-refresh-"))
    import halo_harness.agent.codex_process as cxp
    import halo_harness.providers.codex_models as cxm
    calls = []
    original_resolve = cxm.resolve_codex_launch_argv
    # Pass-B finding 14: `refresh_cx_catalog`'s per-alias ping now runs
    # through `run_bounded_codex_subprocess` (never a bare `subprocess.
    # run`, which it imports LOCALLY at call time the same way `one_shot_
    # cx_call` does -- see that test's own comment) -- stubbed there
    # instead.
    original_run = cxp.run_bounded_codex_subprocess
    cxm.resolve_codex_launch_argv = lambda: (calls.append(("resolve",)) or original_resolve())
    # Codex IS actually installed on this box -- a real `codex exec` ping
    # per alias must never run even in the "online" half below, so
    # run_bounded_codex_subprocess is stubbed too.
    cxp.run_bounded_codex_subprocess = lambda *a, **k: (
        calls.append(("run", a[0] if a else None)), _StubCompletedProcess())[1]
    try:
        result = cxm.refresh_cx_catalog(state_dir=state_dir)
        ctx.check(f"codex is never pinged while offline, calls={calls!r}", calls == [])
        ctx.check(f"the (empty) cache is returned unchanged, got {result!r}", isinstance(result, dict))

        os.environ["HALO_OFFLINE"] = "0"
        cxm.refresh_cx_catalog(state_dir=state_dir, timeout=1.0)
        ctx.check(f"online -> resolve_codex_launch_argv IS reached (unchanged), calls={calls!r}",
                  calls and calls[0] == ("resolve",))
        ctx.check("online -> the (stubbed) codex ping ran at least once", any(c[0] == "run" for c in calls))
    finally:
        cxm.resolve_codex_launch_argv = original_resolve
        cxp.run_bounded_codex_subprocess = original_run


@test
@_env
def test_clone_plugin_url_refuses_under_offline_but_not_online(ctx: Ctx):
    import halo_harness.plugin_fetch as pf
    calls = []

    def _fake_run(argv, **kwargs):
        calls.append(argv)
        class _R:
            returncode = 1
        return _R()

    original = pf.subprocess.run
    pf.subprocess.run = _fake_run
    try:
        os.environ["HALO_OFFLINE"] = "1"
        state_dir_a = Path(tempfile.mkdtemp(prefix="offline-plugin-a-"))
        result = pf.clone_plugin_url("https://example.invalid/one.git", state_dir_a)
        ctx.check("clone_plugin_url returns None while offline", result is None)
        ctx.check(f"git clone is never invoked while offline, calls={calls!r}", calls == [])

        os.environ["HALO_OFFLINE"] = "0"
        state_dir_b = Path(tempfile.mkdtemp(prefix="offline-plugin-b-"))
        pf.clone_plugin_url("https://example.invalid/two.git", state_dir_b)
        ctx.check("online -> git clone IS invoked (unchanged, stubbed)", len(calls) == 1)
    finally:
        pf.subprocess.run = original


@test
@_env
def test_ensure_mlx_server_for_ref_refuses_under_offline_but_not_online(ctx: Ctx):
    import io
    import contextlib
    import types
    import halo_harness.headless as hl
    import halo_harness.providers.huggingface_mlx as mlx_mod

    os.environ["BRIDGE_STATE_DIR"] = str(Path(tempfile.mkdtemp(prefix="offline-mlx-")))
    ref = types.SimpleNamespace(provider="huggingface", mlx=True, model="org/repo")
    calls = []
    original = mlx_mod.ensure_mlx_server
    mlx_mod.ensure_mlx_server = lambda *a, **k: (calls.append(1), (None, []))[1]
    try:
        os.environ["HALO_OFFLINE"] = "1"
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            hl._ensure_mlx_server_for_ref(ref, Path(os.environ["BRIDGE_STATE_DIR"]))
        ctx.check(f"ensure_mlx_server is never called while offline, calls={calls!r}", calls == [])
        ctx.check(f"stderr names the offline sentence, got {buf.getvalue()!r}",
                  "offline mode: not connecting to" in buf.getvalue())

        os.environ["HALO_OFFLINE"] = "0"
        hl._ensure_mlx_server_for_ref(ref, Path(os.environ["BRIDGE_STATE_DIR"]))
        ctx.check("online -> ensure_mlx_server IS called (unchanged)", calls == [1])
    finally:
        mlx_mod.ensure_mlx_server = original


# ---------------------------------------------------------------------------
# /offline (commands.builtins._cmd_offline)
# ---------------------------------------------------------------------------

@test
@_env
def test_cmd_offline_bare_reports_state_and_on_off_persists(ctx: Ctx):
    from halo_harness.commands.builtins import HeadlessFacade, _cmd_offline
    os.environ.pop("HALO_OFFLINE", None)
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="offline-cmd-")))
    facade = HeadlessFacade(cwd=REPO_DIR)
    bare = _cmd_offline("", facade)
    ctx.check(f"bare reports off by default, got {bare!r}", "Offline mode: off" in bare)
    on = _cmd_offline("on", facade)
    ctx.check(f"on acknowledges, got {on!r}", "Offline mode: on" in on)
    from halo_harness.providers.http import offline_mode_enabled
    ctx.check("offline_mode_enabled() reflects it immediately, same process", offline_mode_enabled() is True)
    off = _cmd_offline("off", facade)
    ctx.check(f"off acknowledges, got {off!r}", "Offline mode: off" in off)
    ctx.check("offline_mode_enabled() reflects the toggle back off", offline_mode_enabled() is False)
    bad = _cmd_offline("sideways", facade)
    ctx.check(f"a bad argument gets a usage line, got {bad!r}", bad == "Usage: /offline [on|off]")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
