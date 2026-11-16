"""tests.test_hotfix_101_fail_fast -- 1.0.1 hotfix 2: DNS/connection
failures must fail fast (bounded connect, no backoff-ladder retries) and
name the host in a clear message. 2.0.1 finding 18 removed phase 1's own
former single immediate retry for a genuine CONNECT-phase failure (a retry
cannot help DNS) -- it is terminal on the very first attempt now, so the
documented 8s connect budget is really just 8s, never up to 16s; a POST-
connect failure (a dropped keep-alive, no CONNECT_FAILURE_MARKER) still
gets its own one immediate re-dial (see test_hotfix_101_fail_fast.py's own
`test_step_retries_a_post_connect_failure_through_the_normal_ladder`).
Every case is time-bounded (< 10s) and never touches a real network beyond
an intentionally-unresolvable RFC 2606 `.invalid` hostname.
"""
from __future__ import annotations

import http.client
import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

# RFC 2606 reserves .invalid as a TLD that will NEVER resolve -- a real,
# deterministic "unresolvable host" without depending on any live DNS
# blackhole/network condition.
_UNRESOLVABLE_HOST = "totally-unresolvable-host.invalid"
_UNRESOLVABLE_DBX_URL = f"https://{_UNRESOLVABLE_HOST}"


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in
                       ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_ENV_FILE",
                        "BRIDGE_DBX_BASE_URL", "BRIDGE_DBX_TOKEN", "DATABRICKS_HOST", "DATABRICKS_TOKEN",
                        "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "OPENROUTER_API_KEY")}
        d = Path(tempfile.mkdtemp(prefix="hotfix101-failfast-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["BRIDGE_ENV_FILE"] = str(d / "no-env-file")
        self.state_dir = d / ".halo"
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# format_connect_error / UpstreamConnectError.host
# ---------------------------------------------------------------------------

@test
def test_format_connect_error_names_host_and_says_the_required_phrase(ctx: Ctx):
    from halo_harness.providers.http import format_connect_error
    msg = format_connect_error("your-workspace.cloud.databricks.com", "gaierror: Name or service not known")
    ctx.check(f"names the host, got {msg!r}", "your-workspace.cloud.databricks.com" in msg)
    ctx.check(f"says cannot resolve/reach, got {msg!r}", "cannot resolve/reach" in msg)
    ctx.check(f"says check the machine's network, DNS or VPN, got {msg!r}",
              "check the machine's network, DNS or VPN" in msg)


@test
def test_upstream_connect_error_carries_host(ctx: Ctx):
    from halo_harness.providers.http import UpstreamConnectError
    e = UpstreamConnectError("boom", host="example.invalid")
    ctx.check(f"host attribute set, got {e.host!r}", e.host == "example.invalid")


# ---------------------------------------------------------------------------
# _bounded_connect: the actual wall-clock cap, independent of real DNS
# behavior on the test box -- a hung `conn.connect()` (simulating a
# black-holed/unresponsive resolver, which a per-socket `timeout=` does NOT
# bound since getaddrinfo runs before any socket exists) must still be
# capped at `timeout_s`, not the fake call's own (much longer) sleep.
# ---------------------------------------------------------------------------

class _HangingConn:
    def __init__(self, hang_s: float):
        self.hang_s = hang_s
        self.connected = threading.Event()

    def connect(self):
        time.sleep(self.hang_s)
        self.connected.set()  # only reached if NOT abandoned in time


@test
def test_bounded_connect_caps_a_hung_connect_call(ctx: Ctx):
    from halo_harness.providers.http import UpstreamConnectError, _bounded_connect
    conn = _HangingConn(hang_s=5.0)
    t0 = time.monotonic()
    try:
        _bounded_connect(conn, 0.3, "example.invalid")
        ctx.check("expected UpstreamConnectError on timeout", False)
    except UpstreamConnectError as e:
        elapsed = time.monotonic() - t0
        ctx.check(f"capped near the 0.3s budget, not the 5s hang, got {elapsed:.2f}s", elapsed < 1.5)
        ctx.check(f"names the host even on a bare timeout, got {e}", "example.invalid" in str(e))
        ctx.check(f"still says the required phrase, got {e}",
                  "cannot resolve/reach" in str(e) and "DNS or VPN" in str(e))
    ctx.check("the abandoned background thread was never force-killed (still running)",
              not conn.connected.is_set())


class _LateSucceedingConn:
    """2.0.1 finding 18: simulates a connect() that blows the budget but
    then succeeds shortly after -- close() is tracked so the test can
    prove the abandoned connection gets cleaned up instead of leaking
    its socket forever."""

    def __init__(self, hang_s: float):
        self.hang_s = hang_s
        self.connected = threading.Event()
        self.closed = threading.Event()

    def connect(self):
        time.sleep(self.hang_s)
        self.connected.set()

    def close(self):
        self.closed.set()


@test
def test_bounded_connect_closes_an_abandoned_connection_that_later_succeeds(ctx: Ctx):
    """2.0.1 finding 18: an abandoned connect thread that later succeeds
    must not leak its socket forever -- `_bounded_connect`'s own `_target`
    now closes `conn` itself once it finishes, since this function already
    raised and nobody else will ever get a reference to it."""
    from halo_harness.providers.http import UpstreamConnectError, _bounded_connect
    conn = _LateSucceedingConn(hang_s=0.5)
    try:
        _bounded_connect(conn, 0.1, "example.invalid")
        ctx.check("expected UpstreamConnectError on timeout", False)
    except UpstreamConnectError:
        pass
    ctx.check("the late connect eventually succeeds (not force-killed)", conn.connected.wait(3.0))
    ctx.check("close() was called on the abandoned-then-succeeded connection", conn.closed.wait(3.0))


@test
def test_bounded_connect_propagates_a_fast_exception(ctx: Ctx):
    from halo_harness.providers.http import UpstreamConnectError, _bounded_connect

    class _RefusingConn:
        def connect(self):
            raise ConnectionRefusedError("[simulated] connection refused")

    t0 = time.monotonic()
    try:
        _bounded_connect(_RefusingConn(), 8.0, "example.invalid")
        ctx.check("expected UpstreamConnectError", False)
    except UpstreamConnectError as e:
        elapsed = time.monotonic() - t0
        ctx.check(f"a fast failure returns immediately, not after the 8s budget, got {elapsed:.2f}s", elapsed < 1.0)
        ctx.check(f"wraps the real cause, got {e}", "refused" in str(e).lower())


# ---------------------------------------------------------------------------
# open_upstream: a real unresolvable hostname fails fast (bounded), never the
# ~64s an unbounded getaddrinfo hang would take.
# ---------------------------------------------------------------------------

@test
def test_open_upstream_unresolvable_host_fails_in_under_10s(ctx: Ctx):
    from halo_harness.providers.http import UpstreamConnectError, open_upstream
    t0 = time.monotonic()
    try:
        open_upstream(_UNRESOLVABLE_HOST, 443, True, connect_timeout=8)
        ctx.check("expected UpstreamConnectError for an unresolvable host", False)
    except UpstreamConnectError as e:
        elapsed = time.monotonic() - t0
        ctx.check(f"failed in well under 10s, got {elapsed:.1f}s", elapsed < 10.0)
        ctx.check(f"names the host, got {e}", _UNRESOLVABLE_HOST in str(e))
        ctx.check(f"says the required phrase, got {e}",
                  "cannot resolve/reach" in str(e) and "DNS or VPN" in str(e))


@test
def test_probe_databricks_status_unresolvable_host_fails_in_under_10s(ctx: Ctx):
    from halo_harness.providers.databricks import probe_databricks_status
    from halo_harness.providers.http import UpstreamConnectError
    t0 = time.monotonic()
    try:
        probe_databricks_status(_UNRESOLVABLE_DBX_URL, "tok")
        ctx.check("expected UpstreamConnectError", False)
    except UpstreamConnectError as e:
        elapsed = time.monotonic() - t0
        ctx.check(f"doctor/init/catalog-refresh probe fails in well under 10s, got {elapsed:.1f}s", elapsed < 10.0)
        ctx.check(f"names the host, got {e}", _UNRESOLVABLE_HOST in str(e))


@test
def test_doctor_work_vpn_reachability_unresolvable_host_fails_fast_and_names_host(ctx: Ctx):
    from halo_harness.doctor import _work_check_vpn_reachability
    t0 = time.monotonic()
    line = _work_check_vpn_reachability(_UNRESOLVABLE_DBX_URL)
    elapsed = time.monotonic() - t0
    ctx.check(f"doctor --work VPN check returns in well under 10s, got {elapsed:.1f}s", elapsed < 10.0)
    ctx.check(f"MISSING and names the host, got {line!r}", "MISSING" in line and _UNRESOLVABLE_HOST in line)
    ctx.check(f"says the required phrase, got {line!r}",
              "cannot resolve/reach" in line and "DNS or VPN" in line)


# ---------------------------------------------------------------------------
# is_connect_failure_message: the marker `agent/loop.py`'s own `_step`
# checks to skip the backoff ladder WITHOUT changing either wire mapper's
# status/err_type (`databricks_unreachable_response`/`map_upstream_error`
# both stay byte-for-byte unchanged for bridge.py's sake -- see
# test_bridge.py::test_dbx_dns_failure_502_vpn_hint).
# ---------------------------------------------------------------------------

@test
def test_is_connect_failure_message_survives_both_wire_mappers(ctx: Ctx):
    from halo_harness.providers.databricks import databricks_unreachable_response
    from halo_harness.providers.errors import map_upstream_error
    from halo_harness.providers.http import format_connect_error, is_connect_failure_message

    raw = format_connect_error("your-workspace.cloud.databricks.com", "boom")
    ctx.check(f"the raw canonical message is recognized, got {raw!r}", is_connect_failure_message(raw))

    _status, jbody_dbx, _hdrs = databricks_unreachable_response(raw)
    ctx.check(f"still recognized after databricks_unreachable_response's VPN-hint wrap, got "
              f"{jbody_dbx['error']['message']!r}", is_connect_failure_message(jbody_dbx["error"]["message"]))

    _status2, jbody_or, _hdrs2 = map_upstream_error(502, {"error": {"message": raw}}, "openrouter")
    ctx.check(f"still recognized after map_upstream_error's generic 502 wrap, got "
              f"{jbody_or['error']['message']!r}", is_connect_failure_message(jbody_or["error"]["message"]))

    ctx.check("an ordinary upstream 500 message is NOT mistaken for a connect failure",
              not is_connect_failure_message("internal server error, please retry"))


# ---------------------------------------------------------------------------
# Phase 1 (providers/stream.py): a genuine CONNECT-phase failure is terminal
# on the FIRST attempt -- 2.0.1 finding 18 removed the former single
# immediate retry (a retry cannot help DNS) -- never the 1-2-4-8-16s ladder
# either, for BOTH the openai-chat and the anthropic-passthrough dialect's
# own phase1.
# ---------------------------------------------------------------------------

@test
def test_openai_chat_dialect_connect_failure_is_terminal_on_the_first_attempt_no_retry(ctx: Ctx):
    import halo_harness.providers.http as http_mod
    from halo_harness.providers.routing import Route
    from halo_harness.providers.stream import CompletionRequest, ProviderCreds, UpstreamError, stream_completion

    real_open_upstream = http_mod.open_upstream
    call_count = [0]

    def flaky(host, port, tls, connect_timeout=8, on_connect=None):
        call_count[0] += 1
        raise ConnectionRefusedError("[simulated] connection refused")

    http_mod.open_upstream = flaky
    try:
        model = "mock/model"
        req = CompletionRequest(
            body={"model": model, "max_tokens": 100, "messages": [{"role": "user", "content": "hi"}]},
            route=Route(provider="openrouter", upstream_model=model, dialect="openai-chat"),
            profile={"context_tokens": 128000, "max_output_tokens": 16384},
            creds=ProviderCreds(base_url="https://example.invalid", api_key="k"),
            state_dir=Path(tempfile.mkdtemp(prefix="hotfix101-p1-")), extra_headers={}, model_label=model,
            ping_interval=15.0,
        )
        t0 = time.monotonic()
        try:
            list(stream_completion(req))
            ctx.check("expected UpstreamError", False)
        except UpstreamError as e:
            from halo_harness.providers.http import is_connect_failure_message
            elapsed = time.monotonic() - t0
            ctx.check(f"exactly 1 connect attempt (finding 18: never retried, never a ladder), "
                      f"got {call_count[0]}", call_count[0] == 1)
            ctx.check(f"no backoff sleep at all -- near-instant, got {elapsed:.2f}s", elapsed < 1.0)
            ctx.check(f"the resulting UpstreamError's message is recognized as a connect failure "
                      f"(what agent/loop.py's _step keys off to skip its own ladder), got {e.message!r}",
                      is_connect_failure_message(e.message))
    finally:
        http_mod.open_upstream = real_open_upstream


@test
def test_step_never_ladder_retries_a_connect_failure(ctx: Ctx):
    """The outer `_step` retry ladder (agent/loop.py) must see the SAME
    terminal result phase 1 already produced -- never re-invoke `_stream`
    (and therefore never re-attempt the connect) additional times on a
    1-2-4-8-16s timer just because the failure mapped to a 502."""
    import halo_harness.providers.http as http_mod
    from tests.helpers.mock_openai import MockUpstream

    real_open_upstream = http_mod.open_upstream
    call_count = [0]

    def flaky(host, port, tls, connect_timeout=8, on_connect=None):
        call_count[0] += 1
        raise ConnectionRefusedError("[simulated] connection refused")

    http_mod.open_upstream = flaky
    try:
        from halo_harness import headless
        with _Env() as env, tempfile.TemporaryDirectory() as cwd:
            os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
            build = headless.build_session(cwd=Path(cwd), model_ref_raw="or:mock/model", bare=True,
                                            print_mode=True, max_turns=3)
            session = build.session
            t0 = time.monotonic()
            events_seen = list(session.turn("hello"))
            elapsed = time.monotonic() - t0
            kinds = [e.kind for e in events_seen]
            ctx.check(f"turn ends in an error event, got kinds={kinds}", "error" in kinds)
            ctx.check(f"exactly 1 connect attempt total for the WHOLE turn (finding 18: no phase-1 retry, "
                      f"no outer ladder re-invoking _stream either), got {call_count[0]}", call_count[0] == 1)
            ctx.check(f"no backoff delay anywhere -- the whole turn resolves in well under 2s, got {elapsed:.2f}s",
                      elapsed < 2.0)
    finally:
        http_mod.open_upstream = real_open_upstream


# ---------------------------------------------------------------------------
# 1.0.1 fixpass finding 2: a failure AFTER the connection was already open
# (conn.request()/getresponse() raised, never open_upstream()/_bounded_
# connect itself) must NOT carry CONNECT_FAILURE_MARKER -- it has to ride
# the ordinary retryable-502 ladder (MAX_RETRIES, backoff), exactly like
# before this hotfix, instead of agent/loop.py's _step treating a dropped
# keep-alive/mid-response RST as a fail-fast DNS/VPN problem.
# ---------------------------------------------------------------------------

class _DropsOnRequest:
    """A fake `conn` `open_upstream()` hands back once connected -- simulates
    a keep-alive the peer already dropped/reset by the time `request()` is
    called, WITHOUT any real socket (never touches the network)."""

    def request(self, *a, **kw):
        raise http.client.RemoteDisconnected("Remote end closed connection without response")

    def getresponse(self):  # pragma: no cover -- request() always raises first
        raise AssertionError("getresponse() should never be reached")


@test
def test_post_connect_failure_message_has_no_connect_marker(ctx: Ctx):
    """call_openai_chat / _dbx_post / proxy_anthropic: open_upstream()
    succeeds (faked, no real socket) but conn.request() raises -- the
    UpstreamConnectError this raises must be marker-free (format_post_
    connect_error, never format_connect_error) so is_connect_failure_
    message is False and agent/loop.py's _step does not fail-fast it."""
    import halo_harness.providers.http as http_mod
    from halo_harness.providers.http import UpstreamConnectError, is_connect_failure_message

    real_open_upstream = http_mod.open_upstream
    http_mod.open_upstream = lambda *a, **kw: _DropsOnRequest()
    try:
        cases = (
            ("call_openai_chat", http_mod.call_openai_chat,
             dict(base_url="https://example.invalid", api_key="k", body={}, extra_headers={},
                  state_dir=Path(tempfile.mkdtemp(prefix="hotfix101-postconnect-")))),
            ("_dbx_post", http_mod._dbx_post,
             dict(base_url="https://example.invalid", path="/x", api_key="k", req_body={}, extra_headers={},
                  state_dir=Path(tempfile.mkdtemp(prefix="hotfix101-postconnect-")))),
            ("proxy_anthropic", http_mod.proxy_anthropic,
             dict(base_url="https://example.invalid", api_key="k", body={}, extra_headers={},
                  state_dir=Path(tempfile.mkdtemp(prefix="hotfix101-postconnect-")))),
        )
        for label, fn, kwargs in cases:
            try:
                fn(**kwargs)
                ctx.check(f"{label}: expected UpstreamConnectError", False)
            except UpstreamConnectError as e:
                ctx.check(f"{label}: message has NO connect-failure marker, got {e}",
                          not is_connect_failure_message(str(e)))
                ctx.check(f"{label}: still describes the interrupted connection, got {e}",
                          "interrupted" in str(e))
    finally:
        http_mod.open_upstream = real_open_upstream


@test
def test_step_retries_a_post_connect_failure_through_the_normal_ladder(ctx: Ctx):
    """The mirror image of test_step_never_ladder_retries_a_connect_failure:
    once open_upstream() has already succeeded, a failure from conn.
    request()/getresponse() must ride agent/loop.py's ordinary retryable-502
    ladder (recover on a later attempt) rather than dying after phase 1's
    own single immediate retry -- the exact scenario review finding 2
    reports ("a load balancer drops a keep-alive connection while Databricks
    queues the request")."""
    import halo_harness.providers.stream as stream_mod
    from halo_harness.providers.http import UpstreamConnectError, format_post_connect_error
    from tests.helpers.mock_openai import MockUpstream

    real_call_openai_chat = stream_mod.call_openai_chat
    call_count = [0]

    def flaky_then_ok(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] <= 2:  # phase 1's own attempt0 + attempt1 (its one immediate retry)
            raise UpstreamConnectError(
                format_post_connect_error("mock-host", "Remote end closed connection without response"),
                host="mock-host")
        return real_call_openai_chat(*args, **kwargs)

    stream_mod.call_openai_chat = flaky_then_ok
    mock = MockUpstream().start()
    try:
        from halo_harness import headless
        with _Env(), tempfile.TemporaryDirectory() as cwd:
            os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
            os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
            build = headless.build_session(cwd=Path(cwd), model_ref_raw="or:mock/model", bare=True,
                                            print_mode=True, max_turns=3)
            session = build.session
            t0 = time.monotonic()
            events_seen = list(session.turn("hello"))
            elapsed = time.monotonic() - t0
            kinds = [e.kind for e in events_seen]
            ctx.check(f"phase 1 exhausted its own 2 attempts, THEN the outer ladder retried once more "
                      f"(a 3rd call succeeding), got call_count={call_count[0]}", call_count[0] == 3)
            ctx.check(f"no error event -- the turn recovered via the retry ladder, got kinds={kinds}",
                      "error" not in kinds)
            ctx.check(f"a real backoff sleep happened (the ladder, not phase 1's instant retry), "
                      f"got elapsed={elapsed:.2f}s", elapsed >= 1.0)
    finally:
        stream_mod.call_openai_chat = real_call_openai_chat
        mock.stop()


# ---------------------------------------------------------------------------
# 3.6.0.1 (win-local-connect): the connect bound for a loopback host. A refused
# connect to a closed loopback port takes ~2 s on Windows (the SYN is retried
# after the RST), and `localhost` tries ::1 first: each address gets at most
# LOOPBACK_CONNECT_S, a remote host / TLS / a smaller caller bound keep theirs.
# ---------------------------------------------------------------------------

_PROXY_VARS = ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")


class _FakeCreateConnection:
    """Replaces `socket.create_connection` (http.client copies it into each new
    connection, so it is patched before `open_upstream` builds one); records the
    per-address timeout each call was given, then runs `behave`."""

    def __init__(self, behave):
        self.behave = behave
        self.timeouts: list = []
        self._real = socket.create_connection
        self._proxies: dict = {}

    def __call__(self, address, timeout=None, source_address=None, *a, **kw):
        self.timeouts.append(timeout)
        return self.behave(address, timeout, self._real)

    def __enter__(self):
        self._proxies = {k: os.environ.pop(k) for k in _PROXY_VARS if k in os.environ}
        socket.create_connection = self
        return self

    def __exit__(self, *exc):
        socket.create_connection = self._real
        os.environ.update(self._proxies)


class _ShortLoopbackBound:
    """Sets the providers.http switch that turns on the short loopback bound
    (on: Windows, off: Linux/macOS) for the block, so each path runs on every
    system; never patches sys.platform."""

    def __init__(self, on: bool):
        self.on = on

    def __enter__(self):
        from halo_harness.providers import http as http_mod
        self._mod = http_mod
        self._saved = getattr(http_mod, "_SHORT_LOOPBACK_BOUND", None)
        http_mod._SHORT_LOOPBACK_BOUND = self.on
        return self

    def __exit__(self, *exc):
        if self._saved is None:
            del self._mod._SHORT_LOOPBACK_BOUND
        else:
            self._mod._SHORT_LOOPBACK_BOUND = self._saved


class _FakeGetaddrinfo:
    """Replaces `socket.getaddrinfo`: `localhost` resolves to ::1 then 127.0.0.1
    (Windows' order); anything else to the name itself as an IPv4 entry."""

    def __init__(self):
        self._real = socket.getaddrinfo

    def __call__(self, host, port, family=0, type=0, proto=0, flags=0):
        if host == "localhost":
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", port, 0, 0)),
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, port))]

    def __enter__(self):
        socket.getaddrinfo = self
        return self

    def __exit__(self, *exc):
        socket.getaddrinfo = self._real


def _refuse_at_once(address, timeout, real):
    raise ConnectionRefusedError(10061, "refused (fake)")


def _time_out_at_once(address, timeout, real):
    raise TimeoutError("timed out")


@test
def test_open_upstream_bounds_a_loopback_connect_per_address(ctx: Ctx):
    """The Windows path (forced, so it runs on every system)."""
    with _ShortLoopbackBound(True):
        _bounds_a_loopback_connect_per_address(ctx)


def _bounds_a_loopback_connect_per_address(ctx: Ctx):
    from halo_harness.providers import http as http_mod
    bound = getattr(http_mod, "LOOPBACK_CONNECT_S", None)
    ctx.check(f"http.LOOPBACK_CONNECT_S exists and is 0.5, got {bound!r}", bound == 0.5)
    bound = bound or 0.5
    for host in ("127.0.0.1", "localhost", "::1", "127.0.0.2"):
        with _FakeCreateConnection(_refuse_at_once) as fake:
            try:
                http_mod.open_upstream(host, 9, False, connect_timeout=8)
                raised = False
            except http_mod.UpstreamConnectError:
                raised = True
        ctx.check(f"{host}: UpstreamConnectError, each address bounded at {bound} s, got {fake.timeouts}",
                  raised and fake.timeouts and all(t is not None and t <= bound for t in fake.timeouts))
    for host, tls, caller, want in (("gpu-box", False, 8, 8), ("127.0.0.1", True, 8, 8), ("127.0.0.1", False, 0.2, 0.2)):
        with _FakeCreateConnection(_refuse_at_once) as fake:
            try:
                http_mod.open_upstream(host, 9, tls, connect_timeout=caller)
            except http_mod.UpstreamConnectError:
                pass
        ctx.check(f"{host} tls={tls} caller={caller}: keeps the caller's bound {want}, got {fake.timeouts}",
                  fake.timeouts == [want])


@test
def test_a_probe_s_loopback_connect_that_times_out_is_worded_as_nothing_listening(ctx: Ctx):
    """The Windows path (forced, so it runs on every system). A probe (a caller
    bound under LOOPBACK_RETRY_FROM_S) gets one short try; its timeout is the
    refusal Windows has not reported yet."""
    with _ShortLoopbackBound(True):
        _loopback_timeout_wording(ctx)


def _loopback_timeout_wording(ctx: Ctx):
    from halo_harness.providers import http as http_mod
    with _FakeCreateConnection(_time_out_at_once) as fake:
        try:
            http_mod.open_upstream("127.0.0.1", 9, False, connect_timeout=1.5)
            msg = ""
        except http_mod.UpstreamConnectError as e:
            msg = str(e)
    ctx.check(f"a probe's loopback timeout: one short try, got {fake.timeouts}", fake.timeouts == [0.5])
    ctx.check(f"a probe's loopback timeout: refused wording naming 127.0.0.1:9, not DNS/VPN, got {msg!r}",
              "nothing is listening" in msg and "127.0.0.1:9" in msg and "connection refused" in msg
              and "DNS or VPN" not in msg and http_mod.is_connect_failure_message(msg))
    with _FakeCreateConnection(_time_out_at_once):
        try:
            http_mod.open_upstream("gpu-box", 9, False, connect_timeout=8)
            msg = ""
        except http_mod.UpstreamConnectError as e:
            msg = str(e)
    ctx.check(f"a remote host's timeout keeps the network/DNS/VPN wording, got {msg!r}",
              "DNS or VPN" in msg and "nothing is listening" not in msg)


@test
def test_the_short_loopback_bound_is_windows_only(ctx: Ctx):
    """Linux/macOS refuse a loopback connect at once, so the short bound only
    hurts there (a full listen backlog drops the SYN and the retry comes ~1 s
    later): off Windows a loopback connect keeps the caller's bound and a
    loopback timeout keeps the ordinary wording."""
    from halo_harness.providers import http as http_mod
    ctx.check(f"the switch follows the system: {getattr(http_mod, '_SHORT_LOOPBACK_BOUND', None)!r}",
              getattr(http_mod, "_SHORT_LOOPBACK_BOUND", None) == (os.name == "nt"))
    with _ShortLoopbackBound(False):
        for host in ("127.0.0.1", "localhost", "::1"):
            with _FakeCreateConnection(_refuse_at_once) as fake:
                try:
                    http_mod.open_upstream(host, 9, False, connect_timeout=8)
                except http_mod.UpstreamConnectError:
                    pass
            ctx.check(f"not Windows, {host}: the caller's 8 s per address, got {fake.timeouts}",
                      bool(fake.timeouts) and all(t == 8 for t in fake.timeouts))
        with _FakeCreateConnection(_time_out_at_once):
            try:
                http_mod.open_upstream("127.0.0.1", 9, False, connect_timeout=8)
                msg = ""
            except http_mod.UpstreamConnectError as e:
                msg = str(e)
        ctx.check(f"not Windows: a loopback timeout keeps the ordinary timeout wording, got {msg!r}",
                  "nothing is listening" not in msg and http_mod.is_connect_failure_message(msg))
    with _ShortLoopbackBound(True), _FakeCreateConnection(_refuse_at_once) as fake:
        try:
            http_mod.open_upstream("127.0.0.1", 9, False, connect_timeout=8)
        except http_mod.UpstreamConnectError:
            pass
    ctx.check(f"Windows: 127.0.0.1 still bounded at 0.5 s, got {fake.timeouts}", fake.timeouts == [0.5])


# 3.6.0.1 (jf-connect): a local server that is briefly busy (its accept queue full) answers a connect only
# after about a second. The fake below is that server, with no clock: a try whose per-address bound is under
# _BUSY_ACCEPTS_AFTER_S times out, a longer one reaches a real loopback listener.
_BUSY_ACCEPTS_AFTER_S = 1.0


def _busy_server(listener_port):
    def behave(address, timeout, real):
        if timeout is not None and timeout < _BUSY_ACCEPTS_AFTER_S:
            raise TimeoutError("timed out (fake: the accept queue is full)")
        return real(("127.0.0.1", listener_port), timeout)
    return behave


def _time_out_then_refuse():
    calls: list = []

    def behave(address, timeout, real):
        calls.append(timeout)
        if len(calls) == 1:
            raise TimeoutError("timed out")
        raise ConnectionRefusedError(10061, "refused (fake)")
    return behave


@test
def test_windows_a_real_request_reaches_a_briefly_busy_local_server(ctx: Ctx):
    """The judge's scenario, the Windows path forced: a real request (the default 8 s bound) to a loopback
    server that accepts only after ~1 s connects, as in 3.6.0.0: the short try times out, ONE more try with the
    caller's own bound connects. A probe (a bound under 5 s) keeps one short try. Off Windows nothing changes."""
    from halo_harness.providers import http as http_mod
    ctx.check(f"http.LOOPBACK_RETRY_FROM_S is 5, got {getattr(http_mod, 'LOOPBACK_RETRY_FROM_S', None)!r}",
              getattr(http_mod, "LOOPBACK_RETRY_FROM_S", None) == 5)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    port = srv.getsockname()[1]
    try:
        for host, caller in (("127.0.0.1", 8), ("127.0.0.1", 5), ("localhost", 8)):
            conn, err = None, None
            with _ShortLoopbackBound(True), _FakeGetaddrinfo(), _FakeCreateConnection(_busy_server(port)) as fake:
                try:
                    conn = http_mod.open_upstream(host, port, False, connect_timeout=caller)
                except http_mod.UpstreamConnectError as e:
                    err = str(e)
            if conn is not None:
                conn.close()
            ctx.check(f"Windows, {host}, caller {caller} s: connects (short try(s), then one try at {caller} s), "
                      f"got error {err!r}, tries {fake.timeouts}",
                      conn is not None and err is None and fake.timeouts[-1] == caller
                      and all(t <= 0.5 for t in fake.timeouts[:-1]) and len(fake.timeouts) >= 2)
        conn, err = None, None
        with _ShortLoopbackBound(True), _FakeCreateConnection(_busy_server(port)) as fake:
            try:
                conn = http_mod.open_upstream("127.0.0.1", port, False, connect_timeout=1.5)
            except http_mod.UpstreamConnectError as e:
                err = str(e)
        if conn is not None:
            conn.close()
        ctx.check(f"Windows, a probe (1.5 s): one short try and no retry, got tries {fake.timeouts}",
                  conn is None and err is not None and fake.timeouts == [0.5])
        conn = None
        with _ShortLoopbackBound(False), _FakeCreateConnection(_busy_server(port)) as fake:
            try:
                conn = http_mod.open_upstream("127.0.0.1", port, False, connect_timeout=8)
            except http_mod.UpstreamConnectError:
                pass
        if conn is not None:
            conn.close()
        ctx.check(f"not Windows: one try at the caller's 8 s, as 3.6.0.0, got {fake.timeouts}",
                  conn is not None and fake.timeouts == [8])
    finally:
        srv.close()


@test
def test_windows_a_real_request_s_retry_words_what_the_last_try_saw(ctx: Ctx):
    """The Windows path forced. The retry that also times out says it timed out after the caller's seconds (it
    was NOT refused); a retry that is refused says nothing is listening. A refusal on the first try is final."""
    from halo_harness.providers import http as http_mod
    msg = ""
    with _ShortLoopbackBound(True), _FakeCreateConnection(_time_out_at_once) as fake:
        try:
            http_mod.open_upstream("127.0.0.1", 9, False, connect_timeout=8)
        except http_mod.UpstreamConnectError as e:
            msg = str(e)
    ctx.check(f"timed out twice: tries [0.5, 8], got {fake.timeouts}", fake.timeouts == [0.5, 8])
    ctx.check(f"timed out twice: says it timed out after 8 s on this computer, names 127.0.0.1:9, no refusal, "
              f"no DNS/VPN, got {msg!r}",
              "timed out after 8 s" in msg and "127.0.0.1:9" in msg and "nothing is listening" not in msg
              and "connection refused" not in msg and "DNS or VPN" not in msg
              and http_mod.is_connect_failure_message(msg))
    msg = ""
    with _ShortLoopbackBound(True), _FakeCreateConnection(_time_out_then_refuse()) as fake:
        try:
            http_mod.open_upstream("127.0.0.1", 9, False, connect_timeout=8)
        except http_mod.UpstreamConnectError as e:
            msg = str(e)
    ctx.check(f"timed out, then refused: tries [0.5, 8], got {fake.timeouts}", fake.timeouts == [0.5, 8])
    ctx.check(f"timed out, then refused: nothing is listening, got {msg!r}",
              "nothing is listening" in msg and "127.0.0.1:9" in msg and http_mod.is_connect_failure_message(msg))
    with _ShortLoopbackBound(True), _FakeCreateConnection(_refuse_at_once) as fake:
        try:
            http_mod.open_upstream("127.0.0.1", 9, False, connect_timeout=8)
        except http_mod.UpstreamConnectError:
            pass
    ctx.check(f"refused at once: one try, no retry, got {fake.timeouts}", fake.timeouts == [0.5])


def _listener_or_never(listener_port):
    """create_connection fake: ::1 never answers (a timeout), 127.0.0.1 reaches
    the real listener; records the address of every attempt."""
    def behave(address, timeout, real):
        if address[0] in ("::1", "localhost"):
            raise TimeoutError("timed out (fake ::1)")
        return real(("127.0.0.1", listener_port), timeout)
    return behave


@test
def test_windows_tries_ipv4_first_for_localhost(ctx: Ctx):
    """Windows resolves `localhost` to ::1 first and a server on 127.0.0.1 only
    then costs 0.5 s per new connection; the IPv4 loopback address goes first.
    A remote name and the non-Windows path are never reordered."""
    from halo_harness.providers import http as http_mod
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    port = srv.getsockname()[1]
    seen: list = []

    def _rec(behave):
        def inner(address, timeout, real):
            seen.append(address[0])
            return behave(address, timeout, real)
        return inner

    try:
        for _ in range(2):  # every new connection, not only the first
            del seen[:]
            conn = None
            with _ShortLoopbackBound(True), _FakeGetaddrinfo(), _FakeCreateConnection(_rec(_listener_or_never(port))):
                try:
                    conn = http_mod.open_upstream("localhost", port, False, connect_timeout=8)
                except http_mod.UpstreamConnectError as e:
                    seen.append(f"error: {e}")
            if conn is not None:
                conn.close()
            ctx.check(f"Windows, localhost: one attempt, on 127.0.0.1, got {seen}", seen == ["127.0.0.1"])
        del seen[:]
        with _ShortLoopbackBound(True), _FakeGetaddrinfo(), _FakeCreateConnection(_rec(_refuse_at_once)):
            try:
                http_mod.open_upstream("gpu-box", 9, False, connect_timeout=8)
            except http_mod.UpstreamConnectError:
                pass
        ctx.check(f"a remote name is passed through as it is, got {seen}", seen == ["gpu-box"])
        del seen[:]
        with _ShortLoopbackBound(False), _FakeGetaddrinfo(), _FakeCreateConnection(_rec(_refuse_at_once)):
            try:
                http_mod.open_upstream("localhost", 9, False, connect_timeout=8)
            except http_mod.UpstreamConnectError:
                pass
        ctx.check(f"not Windows: localhost is left to the system's order, got {seen}", seen == ["localhost"])
    finally:
        srv.close()


@test
def test_localhost_reaches_a_127_listener_when_ipv6_is_slow_to_refuse(ctx: Ctx):
    """Simulates Windows: `localhost` tries ::1 first and its refusal takes ~2 s; the
    per-address bound gives it up and 127.0.0.1 answers inside the caller's 1.5 s."""
    from halo_harness.providers import http as http_mod
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)
    port = srv.getsockname()[1]

    def _windows_localhost(address, timeout, real):
        if address[0] == "localhost":
            time.sleep(min(timeout if timeout is not None else 2.0, 2.0))  # the ::1 attempt
            return real(("127.0.0.1", address[1]), timeout)
        return real(address, timeout)

    conn = None
    try:
        with _ShortLoopbackBound(True), _FakeCreateConnection(_windows_localhost):
            try:
                conn = http_mod.open_upstream("localhost", port, False, connect_timeout=1.5)
                err = None
            except http_mod.UpstreamConnectError as e:
                err = str(e)
        ctx.check(f"localhost connected inside the 1.5 s bound, got error {err!r}", conn is not None and err is None)
    finally:
        if conn is not None:
            conn.close()
        srv.close()


@test
def test_a_dead_loopback_port_is_given_up_inside_the_probe_bounds(ctx: Ctx):
    """Real sockets, Windows only (a refused loopback connect costs ~2 s there;
    Linux and macOS refuse at once and take the caller's bound unchanged).
    Each probe is timed on its own and keeps the BEST of three tries: a loaded
    runner has to be slow three times in a row to turn it red."""
    from tests.helpers.runner import SkipTest
    if os.name != "nt":
        raise SkipTest("Windows-only real-socket check (the injected tests cover every system)")
    from halo_harness.providers import huggingface_local_probe as hf
    from halo_harness.providers.ollama import OllamaHost, probe_version
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    def _best_of_three(call):
        best, got = None, None
        for _ in range(3):
            t0 = time.monotonic()
            got = call()
            took = time.monotonic() - t0
            best = took if best is None else min(best, took)
            if best < 1.5:
                break
        return got, best

    # The probes' own bounds (1.5 s): a probe gets one short try. A caller bound of 5 s or more is a real
    # request, which tries a short-bound timeout once more (jf-connect) and so waits for Windows' ~2 s refusal.
    got, took = _best_of_three(
        lambda: probe_version(OllamaHost(name="t", url=f"http://127.0.0.1:{port}")))
    ctx.check(f"probe_version on a dead loopback port: None in under 1.5 s (best of 3), got {got!r} after {took:.2f}s",
              got is None and took < 1.5)
    saved = os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
    try:
        found, took = _best_of_three(
            lambda: hf.auto_detect_local_servers(env={"HF_LOCAL_PROBE_PORTS": str(port)}, force=True))
    finally:
        if saved is not None:
            os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = saved
    ctx.check(f"auto_detect_local_servers on a dead port: [] in under 1.5 s (best of 3), got {found!r} after "
              f"{took:.2f}s", found == [] and took < 1.5)


@test
def test_probe_version_reaches_a_127_only_server_named_localhost(ctx: Ctx):
    """Real sockets, Windows only (::1 refused after ~2 s, past the 1.5 s probe
    bound). Best of three tries: one slow moment on a runner is not a fault."""
    from tests.helpers.runner import SkipTest
    if os.name != "nt":
        raise SkipTest("Windows-only real-socket check (the injected tests cover every system)")
    import json as _json
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from halo_harness.providers.ollama import OllamaHost, probe_version

    class _H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = _json.dumps({"version": "0.9.0"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _H)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        got = None
        for _ in range(3):
            got = probe_version(OllamaHost(name="t", url=f"http://localhost:{srv.server_address[1]}"))
            if isinstance(got, dict):
                break
        ctx.check(f"probe_version(localhost) answers from the 127.0.0.1 server (best of 3), got {got!r}",
                  isinstance(got, dict) and got.get("version") == "0.9.0")
    finally:
        srv.shutdown()
        srv.server_close()
        th.join(5)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
