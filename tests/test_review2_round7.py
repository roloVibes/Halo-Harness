"""tests.test_review2_round7 -- pins for the vibes/review.md fix pass,
round 7 (MCP findings 43-47, provider tail 33/38-40, P2 tail):

  * f33  team escalation half-switch: now goes through `set_model` and
        re-pins `_primary_model_snapshot` so it is never auto-reverted
  * f38  `call_databricks_count_tokens` had no auth header and the wrong
        path for ant:/xp:/dbx: alike
  * f39  `HTTP(S)_PROXY` userinfo credentials were dropped (no
        Proxy-Authorization anywhere)
  * f40  a non-streamed JSON 200 on the native-Anthropic path had no
        event-synthesis branch at all
  * f43  OAuth refresh / Streamable-HTTP->SSE fallback only ever wrapped
        the connect step, never an auth failure arriving in initialize()
  * f44  the single-handle/parallel-start wait budgets were shorter than
        the two SEQUENTIAL timeouts `_connect_once` can actually take
  * f45  `oauth.refresh_tokens` (up to ~25s of blocking HTTP) ran inline
        on the shared MCP event loop
  * f46  the TCP preflight probed the host directly, ignoring any
        configured HTTP(S)_PROXY
  * f47  a timed-out plugin clone was cached as valid forever, and the
        git clone url had no `--` separator
  * P2 tail: ollama._get_json HTTPException, http.py's _dbx_post
    non-final-404 leak + bad-route caching, oai_stream cache-write
    double-billing, mcp/oauth single-request callback, mcp_cli one
    project-key form, gym_tool_tasks docstring/code agreement
"""
from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()

REPO = Path(__file__).resolve().parent.parent


# ---- f33: team escalation switches through set_model, never half -----------

class _FakeModelRef:
    def __init__(self, raw: str) -> None:
        self.raw = raw


class _FakeTeam:
    def __init__(self, to_ref: str) -> None:
        self.name = "fake-team"
        self.escalated = False
        self._to_ref = to_ref

    def escalation_decision(self, *, tool_failures: bool = False, context_overflow: bool = False):
        if self.escalated:
            return None
        return ("budget_exhausted", self._to_ref, False)


class _EscStub:
    """The minimal Session surface `_maybe_team_escalate` touches --
    `set_model` is stubbed (never the real heavy one) but records every
    call, so the test can tell a real switch from a half one."""

    def __init__(self, team) -> None:
        self.team_control = team
        self.interactive = False
        self.model_label = "or:mock/team-worker"
        self.model_ref = _FakeModelRef("or:mock/team-worker")
        self.model_profile = "OLD_PROFILE"
        self.creds = "OLD_CREDS"
        self.effort = "high"
        self.effort_source = "default"
        self._escalation_decisions = []
        self._approval_waiters = {}
        self.settings = None
        self.state_dir = Path(tempfile.mkdtemp(prefix="f33-esc-"))
        self.set_model_calls = []

        class _RT:
            routes = {}

        self.agent_runtime = _RT()
        self.log = type("L", (), {"nodes": staticmethod(lambda: [])})()

    def _await_reply(self, waiters, request_id):
        return {"action": "accept"}

    def set_model(self, model_ref, model_profile, creds=None) -> None:
        self.set_model_calls.append((model_ref, model_profile, creds))
        self.model_ref = model_ref
        self.model_profile = model_profile
        if creds is not None:
            self.creds = creds
        self.model_label = model_ref.raw


@test
def test_f33_team_escalation_switches_through_set_model(ctx: Ctx):
    from halo_harness.agent.loop import Session
    team = _FakeTeam("or:mock/team-bigger")
    stub = _EscStub(team)
    list(Session._maybe_team_escalate(stub, 1))
    ctx.check(f"set_model was called exactly once (never a raw field assignment), got {len(stub.set_model_calls)}",
              len(stub.set_model_calls) == 1)
    ctx.check(f"the switch actually landed, got {stub.model_label}", stub.model_label == "or:mock/team-bigger")
    ctx.check(f"model_profile/creds moved together with the ref, got {stub.model_profile!r}/{stub.creds!r}",
              stub.model_profile != "OLD_PROFILE" and stub.creds != "OLD_CREDS")
    snap = getattr(stub, "_primary_model_snapshot", None)
    ctx.check(f"the snapshot is re-pinned to the NEW model (never auto-reverted next turn), got {snap!r}",
              snap is not None and snap[0] is stub.model_ref)


# ---- f38: count_tokens gets real per-provider auth + path ------------------

@test
def test_f38_count_tokens_uses_per_provider_auth_and_path(ctx: Ctx):
    from halo_harness.providers.http import call_databricks_count_tokens
    from tests.helpers.mock_anthropic import MockAnthropic
    mock = MockAnthropic().start()
    try:
        body = {"model": "claude-count-tokens-42",
                 "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]}

        r1 = call_databricks_count_tokens(mock.base_url, "ant-key", dict(body), {}, Path(tempfile.mkdtemp()),
                                           route_provider="anthropic")
        req = mock.requests[-1]
        ctx.check(f"ant: route gets 200 and x-api-key, got status={r1.status} headers={req['headers']}",
                  r1.status == 200 and req["headers"].get("x-api-key") == "ant-key")
        ctx.check(f"ant: route uses /v1/messages/count_tokens, got {req['path']}",
                  "/v1/messages/count_tokens" in req["path"])

        r2 = call_databricks_count_tokens(mock.base_url, "xp-key", dict(body), {}, Path(tempfile.mkdtemp()),
                                           route_provider="experiential")
        req = mock.requests[-1]
        ctx.check(f"xp: route gets 200 and x-api-key, got status={r2.status} headers={req['headers']}",
                  r2.status == 200 and req["headers"].get("x-api-key") == "xp-key")
        ctx.check(f"xp: route's path is never doubled /v1/v1, got {req['path']}",
                  req["path"].endswith("/messages/count_tokens") and "/v1/messages/count_tokens" not in req["path"])

        # finding 38: the "databricks" default keeps the ORIGINAL path
        # shape (relative to an already-/ai-gateway/anthropic-suffixed
        # base_url, bridge.py's own proxy caller's long-standing
        # convention -- see call_databricks_count_tokens's own docstring)
        # -- only the missing Authorization DEFAULT is new.
        r3 = call_databricks_count_tokens(mock.base_url, "dbx-tok", dict(body), {}, Path(tempfile.mkdtemp()),
                                           route_provider="databricks")
        req = mock.requests[-1]
        ctx.check(f"dbx: route gets 200 and a Bearer Authorization header, got status={r3.status} headers={req['headers']}",
                  r3.status == 200 and req["headers"].get("authorization") == "Bearer dbx-tok")
        ctx.check(f"dbx: route's path shape is unchanged from before this fix, got {req['path']}",
                  "/v1/messages/count_tokens" in req["path"] and "/ai-gateway/anthropic" not in req["path"])
    finally:
        mock.stop()


# ---- f39: HTTP(S)_PROXY userinfo credentials ---------------------------------

@test
def test_f39_proxy_credentials_header(ctx: Ctx):
    from halo_harness.providers.http import _proxy_auth_header, _ProxiedPlainHTTPConnection
    import base64
    ctx.check("no userinfo -> no Proxy-Authorization header",
              _proxy_auth_header("http://proxy.invalid:3128") is None)
    hdr = _proxy_auth_header("http://alice:s3cret@proxy.invalid:3128")
    ctx.check(f"userinfo -> a Basic Proxy-Authorization header, got {hdr}",
              hdr is not None and hdr.get("Proxy-Authorization", "").startswith("Basic "))
    token = hdr["Proxy-Authorization"].split(" ", 1)[1]
    ctx.check("the token decodes back to user:pass", base64.b64decode(token).decode() == "alice:s3cret")

    captured = {}

    def _fake_super_request(self, method, url, body=None, headers=None, *, encode_chunked=False):
        captured["headers"] = dict(headers or {})

    conn = _ProxiedPlainHTTPConnection("proxy.invalid", 3128, target_host="upstream.invalid", target_port=80,
                                       proxy_auth_header={"Proxy-Authorization": "Basic Zm9v"})
    orig = http.client.HTTPConnection.request
    http.client.HTTPConnection.request = _fake_super_request
    try:
        conn.request("GET", "/path")
    finally:
        http.client.HTTPConnection.request = orig
    ctx.check(f"every proxied plain-HTTP request carries Proxy-Authorization, got {captured.get('headers')}",
              captured.get("headers", {}).get("Proxy-Authorization") == "Basic Zm9v")


# ---- f40: a non-streamed JSON 200 on the native-Anthropic path -------------

@test
def test_f40_synthesize_events_from_message(ctx: Ctx):
    from halo_harness.providers.anthropic_sse import synthesize_events_from_message
    msg = {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-x",
           "content": [{"type": "text", "text": "hello"}], "stop_reason": "end_turn",
           "usage": {"input_tokens": 5, "output_tokens": 2}}
    events = synthesize_events_from_message(msg)
    kinds = [e["type"] for e in events]
    ctx.check(f"message_start first, got {kinds}", kinds[0] == "message_start")
    ctx.check(f"a full content_block start/delta/stop triple for the text block, got {kinds}",
              "content_block_start" in kinds and "content_block_delta" in kinds and "content_block_stop" in kinds)
    ctx.check(f"message_delta carries the stop_reason, got {events}",
              any(e["type"] == "message_delta" and e["delta"].get("stop_reason") == "end_turn" for e in events))
    ctx.check(f"message_stop last, got {kinds}", kinds[-1] == "message_stop")
    text_delta = next(e for e in events if e["type"] == "content_block_delta")
    ctx.check(f"the real text survives into the delta, got {text_delta}", text_delta["delta"].get("text") == "hello")


@test
def test_f40_stream_anthropic_completion_handles_a_plain_json_200(ctx: Ctx):
    import halo_harness.providers.stream as stream_mod

    class _FakeConn:
        sock = None

        def close(self):
            pass

    class _FakeResult:
        def __init__(self):
            self.resp = object()
            self.conn = _FakeConn()
            self.headers = {}

    def _fake_reader(resp, q):
        q.put(("json", {"id": "msg_1", "type": "message", "role": "assistant",
                         "content": [{"type": "text", "text": "hello from json"}],
                         "stop_reason": "end_turn", "usage": {"input_tokens": 3, "output_tokens": 2}}))

    class _FakeReq:
        ping_interval = 15.0
        state_dir = Path(tempfile.mkdtemp(prefix="f40-"))
        prebuilt_anthropic_body = {}

    orig_phase1, orig_reader = stream_mod._run_phase1_anthropic, stream_mod.sse_reader_thread
    stream_mod._run_phase1_anthropic = lambda req, abort=None: ({}, _FakeResult())
    stream_mod.sse_reader_thread = _fake_reader
    try:
        events = list(stream_mod.stream_anthropic_completion(_FakeReq()))
    finally:
        stream_mod._run_phase1_anthropic = orig_phase1
        stream_mod.sse_reader_thread = orig_reader
    kinds = [e.get("type") for e in events]
    ctx.check(f"a plain JSON 200 still produces a real event sequence (never an empty turn), got {kinds}",
              "message_stop" in kinds and any(
                  e.get("type") == "content_block_delta" and e.get("delta", {}).get("text") == "hello from json"
                  for e in events))


# ---- f43: OAuth retry / SSE fallback also cover initialize() failures -----

@test
def test_f43_with_initialize_retries_oauth_on_an_initialize_time_401(ctx: Ctx):
    import asyncio
    from halo_harness.mcp.manager import McpServerConfig, McpServerHandle
    from halo_harness.mcp.client import McpLoop
    from halo_harness.mcp import oauth

    saved_home = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="f43-")))
    try:
        oauth.save_tokens("f43-server", {"access_token": "stale-token", "refresh_token": "the-refresh-token"})

        def _fake_refresh(name, stored, *, oauth_cfg, server_url):
            return {"access_token": "refreshed-token", "refresh_token": "the-refresh-token"}, None

        import halo_harness.mcp.oauth as oauth_mod
        orig_refresh = oauth_mod.refresh_tokens
        oauth_mod.refresh_tokens = _fake_refresh

        stacks, opens = [], []

        class _FakeStack:
            def __init__(self):
                self.closed = False

            async def aclose(self):
                self.closed = True

        class _FakeSession:
            def __init__(self, headers):
                self._headers = headers

            async def initialize(self):
                # the connect step itself always succeeds -- only
                # initialize() (the first REAL MCP request) 401s on the
                # stale token, same shape a real server rejecting an
                # expired bearer token on its first RPC would produce.
                if self._headers.get("Authorization") == "Bearer stale-token":
                    raise RuntimeError("401 Unauthorized")
                return "INIT_OK"

        async def _raw_connect(*, url, headers, connect_timeout):
            opens.append(dict(headers))
            stack = _FakeStack()
            stacks.append(stack)
            return stack, _FakeSession(headers)

        cfg = McpServerConfig(name="f43-server", type="http", url="https://example.invalid/mcp", scope="user")
        loop = McpLoop()
        h = McpServerHandle(cfg, loop, tool_env=dict(os.environ), cwd=REPO, trusted=True)
        try:
            wrapped = h._with_initialize(_raw_connect)
            result = loop.run(
                h._connect_with_oauth_retry(wrapped, headers={"Authorization": "Bearer stale-token"},
                                             connect_timeout=5.0), timeout=5)
            ctx.check(f"two connect attempts were made (stale, then refreshed), got {len(opens)}", len(opens) == 2)
            ctx.check(f"the SECOND attempt used the refreshed token, got {opens}",
                      opens[1].get("Authorization") == "Bearer refreshed-token")
            ctx.check(f"a 3-tuple (stack, session, init_result) is returned, got {result!r}",
                      isinstance(result, tuple) and len(result) == 3 and result[2] == "INIT_OK")
            ctx.check(f"the FIRST (failed-at-initialize) stack was closed, never leaked, got {stacks[0].closed}",
                      stacks[0].closed is True)
        finally:
            oauth_mod.refresh_tokens = orig_refresh
            h.close()
            loop.close()
    finally:
        if saved_home is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved_home


# ---- f44: the connect-wait budget covers BOTH sequential timeouts ---------

@test
def test_f44_single_handle_wait_budget_covers_two_phases(ctx: Ctx):
    from halo_harness.mcp.client import McpLoop
    from halo_harness.mcp.manager import McpServerConfig, McpServerHandle, mcp_timeout_s

    captured = {}
    loop = McpLoop()
    cfg = McpServerConfig(name="f44-budget", type="stdio", command=sys.executable,
                           args=["-c", "import time; time.sleep(0.05)"])
    h = McpServerHandle(cfg, loop, tool_env=dict(os.environ), cwd=REPO)
    orig_wait = loop.wait_future_abortable

    def _spy(fut, timeout=None, abort=None):
        captured["timeout"] = timeout
        # don't actually wait out the real (large) budget -- just prove
        # what budget start() ASKED for, then let the real wait run with
        # a short one so the test stays fast.
        return orig_wait(fut, timeout=0.2, abort=abort)

    loop.wait_future_abortable = _spy
    try:
        try:
            h.start()
        except Exception:
            pass
        expected = mcp_timeout_s() * 2 + 4
        ctx.check(f"start()'s wait budgets for connect+initialize AND THEN list_tools "
                  f"(2x mcp_timeout_s, not 1x), got timeout={captured.get('timeout')}, expected {expected}",
                  captured.get("timeout") == expected)
    finally:
        h.close()
        loop.close()


# ---- f45: oauth refresh runs off the shared MCP event loop's own thread ---

@test
def test_f45_oauth_refresh_runs_off_the_event_loop_thread(ctx: Ctx):
    from halo_harness.mcp.manager import McpServerConfig, McpServerHandle
    from halo_harness.mcp.client import McpLoop
    from halo_harness.mcp import oauth

    saved_home = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="f45-")))
    try:
        oauth.save_tokens("f45-server", {"access_token": "stale", "refresh_token": "rt"})
        captured = {}

        def _fake_refresh(name, stored, *, oauth_cfg, server_url):
            captured["thread"] = threading.get_ident()
            return {"access_token": "fresh", "refresh_token": "rt"}, None

        import halo_harness.mcp.oauth as oauth_mod
        orig_refresh = oauth_mod.refresh_tokens
        oauth_mod.refresh_tokens = _fake_refresh

        async def _fake_connect(*, url, headers, connect_timeout):
            if headers.get("Authorization") == "Bearer stale":
                raise RuntimeError("401 Unauthorized")
            return "ok"

        loop = McpLoop()
        loop_thread = {}

        async def _capture_loop_thread():
            loop_thread["id"] = threading.get_ident()

        loop.run(_capture_loop_thread(), timeout=5)
        cfg = McpServerConfig(name="f45-server", type="http", url="https://example.invalid/mcp", scope="user")
        h = McpServerHandle(cfg, loop, tool_env=dict(os.environ), cwd=REPO, trusted=True)
        try:
            result = loop.run(
                h._connect_with_oauth_retry(_fake_connect, headers={"Authorization": "Bearer stale"},
                                             connect_timeout=5.0), timeout=5)
            ctx.check(f"the retry succeeded, got {result!r}", result == "ok")
            ctx.check(f"refresh_tokens ran OFF the event loop's own thread (asyncio.to_thread), "
                      f"got loop={loop_thread.get('id')} refresh={captured.get('thread')}",
                      captured.get("thread") is not None and captured["thread"] != loop_thread.get("id"))
        finally:
            oauth_mod.refresh_tokens = orig_refresh
            h.close()
            loop.close()
    finally:
        if saved_home is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved_home


# ---- f46: the TCP preflight never probes a proxied host directly ---------

@test
def test_f46_tcp_preflight_skips_the_direct_probe_when_proxied(ctx: Ctx):
    import asyncio
    from halo_harness.mcp.http_sse import preflight_tcp_reachability

    old = {k: os.environ.get(k) for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy",
                                           "NO_PROXY", "no_proxy")}
    for k in old:
        os.environ.pop(k, None)
    try:
        os.environ["HTTPS_PROXY"] = "http://proxy.invalid:3128"
        calls = {"n": 0}

        async def _never_called(host, port):
            calls["n"] += 1
            raise ConnectionRefusedError("must never be dialed directly when proxied")

        asyncio.run(preflight_tcp_reachability("https://example.invalid/mcp", timeout=1.0,
                                                open_connection=_never_called))
        ctx.check(f"a proxied host is never probed directly, got {calls['n']} direct dial(s)", calls["n"] == 0)

        os.environ.pop("HTTPS_PROXY", None)
        calls2 = {"n": 0}

        async def _count_called(host, port):
            calls2["n"] += 1
            raise ConnectionRefusedError("confirmed refusal")

        raised = None
        try:
            asyncio.run(preflight_tcp_reachability("https://example.invalid/mcp", timeout=1.0,
                                                    open_connection=_count_called))
        except ConnectionRefusedError as e:
            raised = e
        ctx.check(f"without a proxy, the direct probe still runs and still fails fast on a refusal, "
                  f"got calls={calls2['n']} raised={raised!r}", calls2["n"] == 1 and raised is not None)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---- f47: a timed-out plugin clone is never cached, url is never a flag ---

@test
def test_f47_timed_out_clone_is_not_cached_and_url_uses_dash_dash(ctx: Ctx):
    import hashlib
    import subprocess
    from halo_harness import plugin_fetch

    state_dir = Path(tempfile.mkdtemp(prefix="f47-"))
    url = "--upload-pack=touch /tmp/pwned"
    argvs = []

    def _fake_run(argv, **kw):
        argvs.append(list(argv))
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kw.get("timeout", 1))

    orig_run = plugin_fetch.subprocess.run
    plugin_fetch.subprocess.run = _fake_run
    try:
        result = plugin_fetch.clone_plugin_url(url, state_dir, timeout=0.1)
        ctx.check("a timed-out clone returns None", result is None)
        ctx.check(f"git is invoked with a '--' separator before the url, got {argvs}",
                  argvs and "--" in argvs[0] and argvs[0].index("--") < argvs[0].index(url))
        digest = hashlib.sha1(url.encode("utf-8", "replace")).hexdigest()[:16]
        dest = state_dir / "plugins-cache" / digest
        ctx.check(f"no half-written cache dir was left behind for this url, got exists={dest.exists()}",
                  not dest.exists())
        result2 = plugin_fetch.clone_plugin_url(url, state_dir, timeout=0.1)
        ctx.check(f"a LATER call retries instead of treating the timeout as a permanent cache hit, "
                  f"got {len(argvs)} git invocation(s)", len(argvs) == 2 and result2 is None)
    finally:
        plugin_fetch.subprocess.run = orig_run


# ---- P2 tail: ollama._get_json catches http.client.HTTPException --------

@test
def test_p2_ollama_get_json_catches_http_exception(ctx: Ctx):
    from halo_harness.providers import ollama

    class _FakeResp:
        status = 200

        def read(self):
            raise http.client.BadStatusLine("garbage status line")

    class _FakeConn:
        sock = None

        def request(self, *a, **k):
            pass

        def getresponse(self):
            return _FakeResp()

        def close(self):
            pass

    import halo_harness.providers.http as http_mod
    orig_open = http_mod.open_upstream
    http_mod.open_upstream = lambda *a, **k: _FakeConn()
    try:
        host = ollama.OllamaHost(name="t", url="http://127.0.0.1:1")
        result = ollama._get_json(host, "/api/tags")
        ctx.check(f"a malformed response degrades to None, never an uncaught HTTPException, got {result!r}",
                  result is None)
    finally:
        http_mod.open_upstream = orig_open


# ---- P2 tail: _dbx_post's skipped-404 connections, and bad-route caching --

@test
def test_p2_dbx_chat_404_closes_connections_and_never_caches_a_bad_route(ctx: Ctx):
    from halo_harness.providers import http as http_mod
    from halo_harness.providers.databricks import dbx_cache_get_route

    closed = []

    class _FakeResp:
        def __init__(self, status):
            self.status = status

        def read(self):
            return b""

        def getheaders(self):
            return []

    class _FakeConn:
        def __init__(self, idx):
            self.idx = idx

        def close(self):
            closed.append(self.idx)

    calls = {"n": 0}

    def _fake_dbx_post(base_url, path, api_key, req_body, extra_headers, state_dir,
                        on_connect=None, governor_ctx=None):
        idx = calls["n"]
        calls["n"] += 1
        return _FakeResp(404), _FakeConn(idx), None  # every candidate 404s, including the last

    orig = http_mod._dbx_post
    http_mod._dbx_post = _fake_dbx_post
    try:
        state_dir = Path(tempfile.mkdtemp(prefix="p2-dbx-"))
        result = http_mod.call_databricks_chat(
            "https://workspace.invalid", "tok", {"model": "p2-unknown-model"}, {}, state_dir, "p2-unknown-model")
        ctx.check(f"every SKIPPED 404's connection was closed before trying the next candidate, "
                  f"got closed={closed} of {calls['n']} candidates", len(closed) == calls["n"] - 1)
        ctx.check(f"the final (also-404) response is still what's returned, got {result.status}",
                  result.status == 404)
        cached = dbx_cache_get_route("p2-unknown-model", state_dir)
        ctx.check(f"a final 404 is never cached as though it were a working route, got {cached!r}", cached is None)
    finally:
        http_mod._dbx_post = orig


# ---- P2 tail: cache-write tokens excluded from input_tokens --------------

@test
def test_p2_map_usage_excludes_cache_write_from_input_tokens(ctx: Ctx):
    from halo_harness.providers.oai_stream import map_usage
    u = {"prompt_tokens": 100, "completion_tokens": 10,
         "prompt_tokens_details": {"cached_tokens": 20}, "cache_write_tokens": 30}
    out = map_usage(u)
    ctx.check(f"cache-write tokens still surface their own bucket, got {out}",
              out.get("cache_creation_input_tokens") == 30)
    ctx.check(f"cache-read tokens still excluded from input_tokens, got {out}",
              out.get("cache_read_input_tokens") == 20)
    ctx.check(f"input_tokens excludes BOTH cache-read AND cache-write (100-20-30=50), "
              f"never double-billing cache writes at price_in too, got {out}",
              out.get("input_tokens") == 50)


# ---- P2 tail: the OAuth callback server ignores stray requests ------------

@test
def test_p2_oauth_callback_server_ignores_requests_on_other_paths(ctx: Ctx):
    from halo_harness.mcp import oauth
    server_url = "http://127.0.0.1:1"  # never actually dialed -- endpoints are explicit below
    printed: list = []
    result: list = []

    def _runner() -> None:
        tokens, err = oauth.run_authorization_flow(
            server_name="p2-oauth-server", server_url=server_url,
            oauth_cfg={"authorization_endpoint": "http://127.0.0.1:1/authorize",
                       "token_endpoint": "http://127.0.0.1:1/token", "client_id": "halo-test-client"},
            open_browser=False, callback_timeout=10.0, print_fn=printed.append)
        result.append((tokens, err))

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and len(printed) < 2:
        time.sleep(0.02)
    ctx.check(f"the authorize URL was printed, got {printed}", len(printed) >= 2)
    authorize_url = printed[1].strip()
    qs = parse_qs(urlparse(authorize_url).query)
    redirect_uri = qs["redirect_uri"][0]
    state = qs["state"][0]
    stray_url = redirect_uri.rsplit("/callback", 1)[0] + "/not-the-callback"
    try:
        urlopen(stray_url, timeout=5.0).read()
        ctx.check("the stray path got a 404 (urlopen should have raised)", False)
    except HTTPError as e:
        ctx.check(f"the stray path got a plain 404, never consuming the one real request, got {e.code}",
                  e.code == 404)
    real_url = f"{redirect_uri}?code=fake-code&state={state}"
    urlopen(real_url, timeout=5.0).read()
    t.join(timeout=15.0)
    ctx.check(f"run_authorization_flow actually returned, got {result}", bool(result))
    code_seen = result[0] if result else (None, None)
    # token exchange itself will fail (127.0.0.1:1 isn't listening) -- the
    # point here is only that the REAL callback was reached and consumed
    # at all, proven by a token-exchange-stage error rather than the
    # "timed out waiting for the browser redirect" the stray request used
    # to cause.
    ctx.check(f"the real callback was reached (a token-exchange failure, never a timeout), got {code_seen}",
              code_seen[0] is None and code_seen[1] is not None and "timed out" not in (code_seen[1] or ""))


# ---- P2 tail: mcp_cli disable/enable updates every matching project key --

@test
def test_p2_mcp_cli_disable_updates_every_matching_project_key(ctx: Ctx):
    from halo_harness import mcp_cli
    from halo_harness.config.paths import claude_json_path

    saved_home = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="p2-mcpcli-")))
    try:
        cwd = Path(tempfile.mkdtemp(prefix="p2-proj-"))
        key_fwd = mcp_cli.normalize_cwd(cwd)
        key_back = key_fwd.replace("/", "\\")
        ctx.check("the two key forms actually differ on this host (else the test proves nothing)",
                  key_fwd != key_back)
        claude_json_path().parent.mkdir(parents=True, exist_ok=True)
        claude_json_path().write_text(json.dumps({
            "projects": {
                key_fwd: {"disabledMcpServers": ["already-disabled"]},
                key_back: {"disabledMcpServers": ["already-disabled"]},
            }
        }), encoding="utf-8")

        mcp_cli.set_server_disabled_in_config("srv-x", cwd=cwd, disabled=True)
        data = json.loads(claude_json_path().read_text(encoding="utf-8"))
        ctx.check(f"disabling updates BOTH existing key forms, got {data['projects']}",
                  "srv-x" in data["projects"][key_fwd]["disabledMcpServers"]
                  and "srv-x" in data["projects"][key_back]["disabledMcpServers"])

        mcp_cli.set_server_disabled_in_config("already-disabled", cwd=cwd, disabled=False)
        data2 = json.loads(claude_json_path().read_text(encoding="utf-8"))
        ctx.check(f"re-enabling clears it from BOTH forms (never a silent no-op), got {data2['projects']}",
                  "already-disabled" not in data2["projects"][key_fwd]["disabledMcpServers"]
                  and "already-disabled" not in data2["projects"][key_back]["disabledMcpServers"])
    finally:
        if saved_home is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved_home


# ---- P2 tail: gym_tool_tasks docstring now agrees with the real code -----

@test
def test_p2_gym_tool_tasks_docstring_matches_repair_behavior(ctx: Ctx):
    import halo_harness.gym_tool_tasks as gtt

    class _NoCallTurn:
        error = None
        tool_blocks = []
        text = "no tool call here"
        timing_ns = None

    class _BadArgsTurn:
        error = None
        text = None
        timing_ns = None
        tool_blocks = [{"name": "Read", "input": {"not_file_path": "x"}}]

    queue = [_NoCallTurn(), _BadArgsTurn()]
    calls = {"repairs": 0}

    def _fake_send_turn_for(**kw):
        return queue.pop(0)

    def _fake_send_repair(**kw):
        calls["repairs"] += 1
        return None, "repair failed"

    orig_turn, orig_repair = gtt.send_turn_for, gtt.send_repair
    gtt.send_turn_for, gtt.send_repair = _fake_send_turn_for, _fake_send_repair
    try:
        result = gtt.run_tool_call_accuracy_task(
            host=None, route=None, profile=None, decision=None,
            scratch_dir=Path(tempfile.mkdtemp(prefix="p2-gym-")), n=2, state_dir=Path(tempfile.mkdtemp()))
        ctx.check(f"a no-tool-call reply gets NO repair round -- only the bad-args trial does "
                  f"(docstring now matches the code), got repairs={calls['repairs']}", calls["repairs"] == 1)
        ctx.check(f"both trials still end up failed, got {result.failed}", result.failed == 2)
    finally:
        gtt.send_turn_for, gtt.send_repair = orig_turn, orig_repair


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
