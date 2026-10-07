"""tests.test_governor_review -- Halo 2.0.5 round 4: the REVIEW.md
items' own tests plus the round brief's additions -- clock-jump clamps,
Retry-After HTTP-date + cap, abort mid-wait, lock timeout, corrupt
state recovery, log rotation, 500-neutral, the lanes validator, `/gov`
+ `halo gov` output, doctor's health line, the agent-loop retry
ownership change, the xp retryable mapping, and the same-host fallback
warning. All hermetic: scoped state dirs, no network, bounded sleeps.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

REPO_DIR = Path(__file__).resolve().parent.parent


def _fresh_state():
    from halo_harness.providers import governor_state
    governor_state.reset_degraded_for_tests()
    d = Path(tempfile.mkdtemp(prefix="halo-govrev-"))
    os.environ["GOVERNOR_STATE_DIR"] = str(d)
    return d


def _clear_state_env():
    os.environ.pop("GOVERNOR_STATE_DIR", None)


@test
def test_retry_after_http_date_and_cap(ctx: Ctx):
    from halo_harness.providers import governor
    _fresh_state()
    try:
        future = (datetime.now(timezone.utc) + timedelta(seconds=45)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        got = governor.retry_after_seconds({"retry-after": future}, cap=120.0)
        ctx.check(f"HTTP-date parsed (~45s), got {got}", got is not None and 40 <= got <= 50)
        far = (datetime.now(timezone.utc) + timedelta(seconds=3600)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        capped = governor.retry_after_seconds({"retry-after": far}, cap=120.0)
        ctx.check(f"an absurd date is capped at 120, got {capped}", capped == 120.0)
        ctx.check("delta-seconds still work", governor.retry_after_seconds({"retry-after": "7"}) == 7.0)
        ctx.check("absent -> None", governor.retry_after_seconds({}) is None)
        ctx.check("garbage -> None", governor.retry_after_seconds({"retry-after": "soonish"}) is None)
        past = (datetime.now(timezone.utc) - timedelta(seconds=30)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        ctx.check("a past date clamps to 0", governor.retry_after_seconds({"retry-after": past}) == 0.0)
    finally:
        _clear_state_env()


@test
def test_clock_jump_clamps(ctx: Ctx):
    from halo_harness.providers import governor_state as gs
    _fresh_state()
    try:
        now = time.time()
        st = {"cooldown_until": now + 10_000.0, "last_refill": now - 5_000.0, "tokens": 0.0, "burst": 8.0}
        gs.clamp_state_for_clock_jumps(st, now)
        ctx.check(f"an absurd future cooldown clamped below ladder+cap, got {st['cooldown_until'] - now:.0f}s",
                  st["cooldown_until"] - now <= gs.MAX_LADDER_COOLDOWN_S + 120.0)
        ctx.check(f"refill interval clamped to 60s, got {now - st['last_refill']:.0f}s",
                  now - st["last_refill"] <= 61.0)
    finally:
        _clear_state_env()


@test
def test_abort_interrupts_a_waiting_acquire(ctx: Ctx):
    from halo_harness.providers import governor
    _fresh_state()
    try:
        key = "host:gw-abort.test"
        p = {"rate_rps": 2.0, "burst": 1, "max_inflight": 1, "cooldown_base": 1.0,
             "backoff_mult": 0.5, "ramp_after": 2, "ramp_inc": 0.5, "max_wait": 60.0}
        h = governor.acquire(key, p, agent="w", role="worker")
        governor.report(h, ok=False, status=429, retry_after=30, params=p)
        stop = threading.Event()

        def abort():
            return stop.is_set()

        result = {}

        def waiter():
            try:
                result["h"] = governor.acquire(key, p, agent="o", role="orchestrator",
                                               max_wait=60.0, abort=abort)
            except governor.GovernorAborted as e:
                result["aborted"] = str(e)

        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.4)
        stop.set()
        t.join(timeout=5)
        ctx.check("the waiting acquire raised GovernorAborted", "aborted" in result)
        ctx.check("no permit was granted", "h" not in result)
        st = governor.inspect(key)
        ctx.check("the waiter ticket was deregistered", st["waiting"] == 0)
    finally:
        _clear_state_env()


@test
def test_corrupt_state_recovers_with_defaults(ctx: Ctx):
    from halo_harness.providers import governor
    d = _fresh_state()
    try:
        key = "host:gw-corrupt.test"
        p = {"rate_rps": 3.0, "burst": 3, "max_inflight": 2}
        (d / (governor.gs._safe(key) + ".json")).write_text("{not json", encoding="utf-8")
        h = governor.acquire(key, p, agent="w", role="worker", max_wait=2)
        governor.report(h, ok=True, status=200, params=p)
        st = governor.inspect(key)
        ctx.check("a corrupt bucket reset to defaults and works", st is not None and st["rate_ceiling"] == 3.0)
        ctx.check("state is persisting again", governor.gs.is_degraded() is None)
    finally:
        _clear_state_env()


@test
def test_log_rotation_at_1mb(ctx: Ctx):
    from halo_harness.providers import governor_state as gs
    d = _fresh_state()
    try:
        key = "host:gw-rotate.test"
        big = {"x": "y" * 200}
        for i in range(6_000):  # ~1.2 MB total
            gs.append_log(key, {"i": i, **big})
        files = sorted(f.name for f in d.iterdir())
        ctx.check(f"the log rotated to a .1 generation, got {files}",
                  any(f.endswith(".log.jsonl.1") for f in files))
        main_log = d / (gs._safe(key) + ".log.jsonl")
        ctx.check(f"the live log is back under 1 MB ({main_log.stat().st_size} bytes)",
                  main_log.stat().st_size < 1_100_000)
    finally:
        _clear_state_env()


@test
def test_500_is_neutral_unless_the_body_says_overloaded(ctx: Ctx):
    from halo_harness.providers import governor
    _fresh_state()
    try:
        ctx.check("500 is not in the overload set", governor.is_overload_status(500) is False)
        ctx.check("503 is", governor.is_overload_status(503) is True)
        ctx.check("a body saying overloaded counts",
                  governor.is_overload_body("HTTP 500: upstream capacity exceeded") is True)
        ctx.check("a plain bug body does not", governor.is_overload_body("TypeError: 'NoneType'") is False)
        key = "host:gw-500.test"
        p = {"rate_rps": 2.0, "burst": 3, "max_inflight": 2, "max_retries": 2,
             "backoff_mult": 0.5, "cooldown_base": 0.2, "ramp_after": 2, "ramp_inc": 0.5}
        seq = [(500, "TypeError: 'NoneType' is not subscriptable"), (200, "ok")]

        def do():
            s, b = seq.pop(0)
            return s, b, {}

        status, _ = governor.governed(key, p, do, agent="w", role="worker")
        st = governor.inspect(key)
        ctx.check("a 500 with a plain-bug body returned as-is (no overload retry)", status == 500)
        ctx.check(f"rate untouched by the plain 500, got {st['rate']}", st["rate"] == 2.0)
    finally:
        _clear_state_env()


@test
def test_lanes_validator_one_line_per_problem(ctx: Ctx):
    from halo_harness.providers.gateway_routing import validate_lanes
    probs = validate_lanes({"coder": "or:deepseek/x", "reviewer": "ol:tiny"})
    ctx.check("reviewer weaker than coder -> exactly one plain line", len(probs) == 1 and "reviewer" in probs[0])
    ctx.check("equal tiers pass", validate_lanes({"coder": "or:a", "reviewer": "or:b", "judge": "or:c"}) == [])
    ctx.check("no coder configured -> no complaint",
              validate_lanes({"reviewer": "ol:tiny"}) == [])
    ctx.check("a stronger verifier is fine", validate_lanes({"coder": "or:a", "judge": "cc:b"}) == [])
    from halo_harness.providers.gateway_routing import lane_ok, tier_for
    ctx.check("roles.lanes gates the weakest tier a role may use",
              lane_ok("researcher", "ol:tiny", {"researcher": 3}) is True
              and lane_ok("researcher", "cc:big", {"researcher": 3}) is True
              and lane_ok("judge", "ol:tiny", {"judge": 1}) is False)
    ctx.check("no lane entry -> no restriction", lane_ok("judge", "ol:tiny", None) is True)
    ctx.check("a model table tier wins over the family default",
              tier_for("or:m/x", model_table={"or:m/x": {"tier": 1}}) == 1)


@test
def test_gov_cli_and_slash_print_the_same_table(ctx: Ctx):
    from halo_harness.providers import governor
    _fresh_state()
    try:
        key = "host:gw-surface.test"
        p = {"rate_rps": 4.0, "burst": 4, "max_inflight": 2, "max_retries": 1,
             "backoff_mult": 0.5, "cooldown_base": 0.2, "ramp_after": 2, "ramp_inc": 0.5}
        h = governor.acquire(key, p, agent="impl", role="coder", session="s1", model="or:demo/m")
        governor.report(h, ok=False, status=429, retry_after=2, params=p)
        from halo_harness.gov_cli import cmd_gov, _bucket_key_for_arg
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_gov([])
        out = buf.getvalue()
        ctx.check("exit 0", rc == 0)
        ctx.check("the bucket table names the host", "host:gw-surface.test" in out)
        ctx.check("the table shows the cut rate", "1.0/4.0 rps" in out or "2.0/4.0 rps" in out)
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            rc2 = cmd_gov(["gw-surface.test", "--json"])
        data = json.loads(buf2.getvalue())
        ctx.check("the json payload carries buckets and recent calls",
                  rc2 == 0 and data["buckets"] and data["recent_calls"])
        rec = data["recent_calls"][0]
        ctx.check("a recent call names agent/role/session/model",
                  rec.get("agent") == "impl" and rec.get("role") == "coder"
                  and rec.get("session") == "s1" and rec.get("model") == "or:demo/m")
        ctx.check("host arg -> bucket key", _bucket_key_for_arg("https://gw-surface.test/api") == key)
        # the slash command prints the same lines
        from halo_harness.commands.builtins import _cmd_gov

        class _Facade:
            cwd = str(REPO_DIR)
            settings = None

        slash_out = _cmd_gov("", _Facade())
        ctx.check("/gov prints the same bucket line", "host:gw-surface.test" in slash_out)
        slash_out2 = _cmd_gov("gw-surface.test", _Facade())
        ctx.check("/gov <host> adds the recent-calls block", "Recent calls for" in slash_out2
                  and "impl" in slash_out2)
    finally:
        _clear_state_env()


@test
def test_doctor_shows_gateway_health(ctx: Ctx):
    _fresh_state()
    try:
        from halo_harness.providers import governor
        from halo_harness.doctor import _check_governor
        ctx.check("no buckets yet -> check skipped (None)", _check_governor() is None)
        key = "host:gw-doctor.test"
        p = {"rate_rps": 2.0, "burst": 2, "max_inflight": 1, "max_retries": 1,
             "backoff_mult": 0.5, "cooldown_base": 0.2, "ramp_after": 2, "ramp_inc": 0.5}
        h = governor.acquire(key, p, agent="w", role="worker")
        governor.report(h, ok=False, status=429, retry_after=30, params=p)
        line = _check_governor()
        ctx.check(f"the health line names the gateway, got {line!r}",
                  line is not None and "host:gw-doctor.test" in line and "OPEN" in line)
    finally:
        _clear_state_env()


@test
def test_loop_ladder_steps_aside_for_governed_overload(ctx: Ctx):
    """The retry-ownership change: `_overload_owned_by_governor` is True
    for 429/503 (the Governor already paced and retried them at the
    http.py choke point) and False for a non-overload retryable (404,
    a plain 500), so the loop's own ladder keeps those."""
    from halo_harness.agent.loop import _overload_owned_by_governor
    ctx.check("429 is owned by the governor", _overload_owned_by_governor(429) is True)
    ctx.check("503 is owned", _overload_owned_by_governor(503) is True)
    ctx.check("a plain 404 keeps the loop's ladder", _overload_owned_by_governor(404) is False)
    ctx.check("a plain 500 keeps the loop's ladder",
              _overload_owned_by_governor(500, "TypeError: boom") is False)
    ctx.check("an overloaded 500 is owned",
              _overload_owned_by_governor(500, "upstream capacity exceeded") is True)
    # the suite's own env turns the governor off -- then NOTHING is owned
    os.environ["HALO_GOVERNOR"] = "0"
    try:
        ctx.check("governor off -> the loop owns 429 again",
                  _overload_owned_by_governor(429) is False)
    finally:
        os.environ["HALO_GOVERNOR"] = "1"


@test
def test_governed_upstream_retries_and_releases_at_the_choke_point(ctx: Ctx):
    """The http.py integration, driven directly: a 429 storm is retried
    inside the choke point, succeeds transparently, and the bucket state
    shows the cut. Also the env-off path: HALO_GOVERNOR=0 -> plain call."""
    from halo_harness.providers import governor
    from halo_harness.providers.http import governed_upstream
    _fresh_state()
    try:
        calls = {"n": 0}
        seq = [429, 429, 200]

        class _R:
            def __init__(self, status):
                self.status = status
                self.headers = {"retry-after": "0"} if status == 429 else {}
                self.resp = None
                self.conn = None
                self.body_bytes = None

        def do():
            calls["n"] += 1
            return _R(seq.pop(0))

        result = governed_upstream("gw-choke.test", do, {"agent": "impl", "role": "coder"})
        ctx.check(f"three upstream attempts, got {calls['n']}", calls["n"] == 3)
        ctx.check("the 200 surfaced", result.status == 200)
        st = governor.inspect("host:gw-choke.test")
        ctx.check("the bucket recorded the cut", st["rate"] < st["rate_ceiling"])
        ctx.check("the recent-calls log names the agent and role",
                  any(r.get("agent") == "impl" and r.get("role") == "coder"
                      for r in governor.recent_calls("host:gw-choke.test")))
        os.environ["HALO_GOVERNOR"] = "0"
        try:
            calls["n"] = 0
            seq_off = [200]

            def do_off():
                calls["n"] += 1
                r = _R(seq_off.pop(0))
                return r

            result2 = governed_upstream("gw-choke.test", do_off, {"agent": "x", "role": "worker"})
            ctx.check(f"env-off -> exactly one call, got {calls['n']}", calls["n"] == 1)
            ctx.check("env-off returns the result untouched", result2.status == 200)
        finally:
            os.environ["HALO_GOVERNOR"] = "1"
    finally:
        _clear_state_env()


@test
def test_xp_retryable_codes_map_onto_governor_events(ctx: Ctx):
    """The xp: mapping: an xp 429 (gateway code or not) is overload ->
    Governor-owned; a retryable NON-overload xp code (the 409 idempotency
    replay) keeps the loop's ladder. `providers.experiential.
    is_retryable_code` stays the source of retryability for the latter."""
    from halo_harness.providers.experiential import is_retryable_code
    from halo_harness.providers.http import governed_upstream
    from halo_harness.providers import governor
    _fresh_state()
    try:
        # the xp table's own published retryable codes (2.0.4 round 5):
        # unavailable_route/gateway_overloaded/... retry; idempotency_
        # conflict (and the replay-unavailable 409, same-key resend) never
        # do. Retryability of a NON-overload code keeps the loop's ladder;
        # an xp 429 is overload and the Governor owns it.
        body_retry = {"error": {"code": "unavailable_route"}}
        ctx.check("a published retryable xp code", is_retryable_code(body_retry) is True)
        body_409n = {"error": {"code": "idempotency_conflict"}}
        ctx.check("the xp 409 conflict code is not retryable", is_retryable_code(body_409n) is False)

        class _R:
            def __init__(self, status, body):
                self.status = status
                self.headers = {}
                self.resp = None
                self.conn = None
                self.body_bytes = None
                self._body = body

        def do_409():
            return _R(409, body_retry)

        result = governed_upstream("gw-xp.test", do_409, {"agent": "x", "role": "worker"})
        st = governor.inspect("host:gw-xp.test")
        ctx.check("a retryable xp code on a non-overload status passes the choke point untouched (the loop retries it)",
                  result.status == 409 and st["consecutive_err"] == 0)

        def do_429():
            return _R(429, {"error": {"code": "rate_limited"}})

        seq2 = {"n": 0}

        def do_429_then_200():
            seq2["n"] += 1
            if seq2["n"] == 1:
                r = _R(429, {})
                r.headers = {"retry-after": "0"}
                return r
            return _R(200, "ok")

        result2 = governed_upstream("gw-xp2.test", do_429_then_200, {"agent": "x", "role": "worker"})
        st2 = governor.inspect("host:gw-xp2.test")
        ctx.check("an xp 429 was retried by the governor and the 200 surfaced", result2.status == 200)
        ctx.check("the xp 429 cut the bucket's rate", st2["rate"] < st2["rate_ceiling"])
    finally:
        _clear_state_env()


@test
def test_same_host_fallback_warning(ctx: Ctx):
    from halo_harness.providers.gateway_routing import warn_same_host_fallbacks
    # both or: refs resolve to the openrouter.ai gateway host (the
    # provider default); the dbx: ref is a different (provider-level)
    # bucket -- only the same-host one warns.
    table = {"coder": "or:primary/model"}
    fallbacks = {"coder": ["or:other/model", "dbx:endpoint"]}
    lines = warn_same_host_fallbacks(fallbacks, table, None)
    ctx.check(f"one warning for the same-host fallback, got {lines}", len(lines) == 1)
    ctx.check("the warning names the fallback and the primary", "or:other/model" in lines[0])


# ---------------------------------------------------------------------------
# 2.0.5 release-review fix pass (findings 1, 2, 4 + nit 9)
# ---------------------------------------------------------------------------

class _RevEnv:
    """Scopes BRIDGE_TEST_HOME/BRIDGE_STATE_DIR + GOVERNOR_STATE_DIR +
    HALO_GOVERNOR=1 and writes a FAST `governor.*` config (the older
    tests in this file only scope GOVERNOR_STATE_DIR and never read
    config). Resets the degraded flag on both ends, like _fresh_state."""

    def __init__(self, *, max_retries: int = 1):
        self._max_retries = max_retries

    def __enter__(self):
        from halo_harness.providers import governor_state
        governor_state.reset_degraded_for_tests()
        self._saved = {k: os.environ.get(k) for k in
                       ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "GOVERNOR_STATE_DIR", "HALO_GOVERNOR")}
        d = Path(tempfile.mkdtemp(prefix="halo-govrev2-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["GOVERNOR_STATE_DIR"] = str(d / ".halo" / "governor")
        os.environ["HALO_GOVERNOR"] = "1"
        (d / ".halo").mkdir(parents=True, exist_ok=True)
        (d / ".halo" / "config.json").write_text(json.dumps({
            "governor": {"enabled": True, "max_retries": self._max_retries, "cooldown_base": 0.2,
                         "backoff_mult": 0.5, "rate_rps": 8.0, "burst": 8,
                         "max_inflight": 4, "max_wait": 3.0},
        }), encoding="utf-8")
        self.home = d
        return self

    def __exit__(self, *exc):
        from halo_harness.providers import governor_state
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        governor_state.reset_degraded_for_tests()


@test
def test_governor_retry_drains_the_real_connection(ctx: Ctx):
    """Finding 1's pin, on a REAL socket: a do_call that reuses ONE
    http.client.HTTPConnection (the call_* shape -- each opens the
    connection once and `_send` re-requests it) against a localhost
    server serving 429-with-JSON-body rows (Content-Length, keep-alive)
    then a 200. The retry branch must drain+close the overload response
    before looping, or the next conn.request() raises (ResponseNotReady/
    CannotSendRequest -- call_* wraps it as a marker-less
    UpstreamConnectError the loop then retries as a 502). The 200 must
    surface and the server must have seen at least 2 POSTs."""
    import http.client
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from halo_harness.providers.http import UpstreamResult, governed_upstream

    posts = {"n": 0}

    class _H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"  # keep-alive

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            posts["n"] += 1
            if posts["n"] <= 2:
                status, obj = 429, {"error": {"message": "rate limit hit", "type": "rate_limit_error"}}
                extra = {"Retry-After": "0"}
            else:
                status, obj, extra = 200, {"ok": True}, {}
            body = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for k, v in extra.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    class _Srv(ThreadingHTTPServer):
        def handle_error(self, request, client_address):
            pass  # the client tearing down mid-keep-alive at test end is not a failure

    with _RevEnv(max_retries=2):
        srv = _Srv(("127.0.0.1", 0), _H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)

            def do_call():
                conn.request("POST", "/v1/chat/completions", body=b"{}",
                             headers={"Content-Type": "application/json", "Content-Length": "2"})
                resp = conn.getresponse()
                return UpstreamResult(status=resp.status, resp=resp, conn=conn,
                                      headers={k.lower(): v for k, v in resp.getheaders()})

            result = governed_upstream("127.0.0.1", do_call, {"agent": "pin", "role": "coder"})
            ctx.check(f"the 200 surfaced after the governor's retries (server saw {posts['n']} POSTs)",
                      result.status == 200)
            ctx.check(f"the server saw at least 2 POSTs, got {posts['n']}", posts["n"] >= 2)
            try:
                result.resp.close()
            except Exception:
                pass
            conn.close()
        finally:
            srv.shutdown()
            srv.server_close()


@test
def test_loop_upstream_error_branch_steps_aside_on_real_429(ctx: Ctx):
    """Finding 2's pin: the REAL UpstreamError branch of Session._step,
    driven by one full turn against the mock upstream's 429 scenario with
    HALO_GOVERNOR=1. The governor already paced and retried the 429 at
    the choke point (max_retries=1 in the fixture config -> exactly 2
    requests), so the loop's own ladder must step aside after ONE
    loop-level attempt -- the mock never sees a loop-level re-send."""
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, send_json_response
    from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
    ensure_default_provider_credentials()

    def _serve_429(h, b):
        send_json_response(h, 429, {"error": {"message": "rate limit hit", "type": "rate_limit_error"}},
                           {"Retry-After": "0"})

    SCENARIOS["revfix-429"] = _serve_429
    mock = MockUpstream().start()
    try:
        with _RevEnv() as env:
            from halo_harness.agent.assemble import SessionContext
            from halo_harness.agent.loop import Session
            from halo_harness.hooks import HookRunner
            from halo_harness.model import ModelProfile, parse_model_ref
            from halo_harness.providers.stream import ProviderCreds
            cwd = env.home / "project"
            cwd.mkdir(parents=True, exist_ok=True)
            state_dir = Path(os.environ["BRIDGE_STATE_DIR"])
            session = Session(
                cwd=cwd, model_ref=parse_model_ref("or:mock/revfix-429"), model_profile=ModelProfile(),
                creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
                state_dir=state_dir, model_label="mock/revfix-429",
                session_context=SessionContext(cwd=cwd, model_label="mock/revfix-429"),
                openrouter_base_url=mock.base_url, max_turns=2,
                hook_runner=HookRunner({}, cwd=cwd, session_id="govrev-429",
                                       transcript_path=str(state_dir / "revfix429.jsonl")),
            )
            events_out = list(session.turn("say anything"))
            errors = [e for e in events_out if getattr(e, "kind", "") == "error"]
            ctx.check(f"the turn surfaced the 429 error, got {[getattr(e, 'kind', '') for e in events_out]}",
                      bool(errors) and any("429" in str(getattr(e, "data", {})) for e in errors))
            ctx.check(f"exactly one loop-level attempt: the mock saw {len(mock.requests)} POSTs (2 = the "
                      f"governor's own ladder, more = the loop re-sent)",
                      len(mock.requests) == 2)
    finally:
        mock.stop()
        SCENARIOS.pop("revfix-429", None)


@test
def test_post_connect_drop_ladders_even_with_governor_on(ctx: Ctx):
    """Release-regression pin (found by the pre-tag full suite,
    test_step_retries_a_post_connect_failure_through_the_normal_ladder):
    a REAL socket drop after the request was sent, with HALO_GOVERNOR=1.
    The wire mapper re-labels the drop a plain 502, but no HTTP response
    existed -- the Governor paces response statuses only (its exception
    path re-raises without retrying), so the Governor never paced this
    and the loop's own backoff ladder must own the retry: phase 1's two
    immediate re-dials (2 POSTs), one laddered re-send (3rd POST) which
    the scenario answers -- the turn RECOVERS, no error event."""
    import time as _time
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
    from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
    ensure_default_provider_credentials()
    seen = [0]

    def _serve_drop_then_ok(h, b):
        seen[0] += 1
        if seen[0] <= 2:  # hard-close AFTER the request was read: a post-connect drop
            h.connection.close()
            return
        _finish(h, [
            {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"content": "ok"}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        ])

    SCENARIOS["revfix-drop"] = _serve_drop_then_ok
    mock = MockUpstream().start()
    try:
        with _RevEnv() as env:
            from halo_harness.agent.assemble import SessionContext
            from halo_harness.agent.loop import Session
            from halo_harness.hooks import HookRunner
            from halo_harness.model import ModelProfile, parse_model_ref
            from halo_harness.providers.stream import ProviderCreds
            cwd = env.home / "project"
            cwd.mkdir(parents=True, exist_ok=True)
            state_dir = Path(os.environ["BRIDGE_STATE_DIR"])
            session = Session(
                cwd=cwd, model_ref=parse_model_ref("or:mock/revfix-drop"), model_profile=ModelProfile(),
                creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
                state_dir=state_dir, model_label="mock/revfix-drop",
                session_context=SessionContext(cwd=cwd, model_label="mock/revfix-drop"),
                openrouter_base_url=mock.base_url, max_turns=2,
                hook_runner=HookRunner({}, cwd=cwd, session_id="govrev-drop",
                                       transcript_path=str(state_dir / "revfixdrop.jsonl")),
            )
            t0 = _time.monotonic()
            events_out = list(session.turn("say anything"))
            elapsed = _time.monotonic() - t0
            kinds = [getattr(e, "kind", "") for e in events_out]
            ctx.check(f"the turn RECOVERED via the ladder, got kinds={kinds}",
                      "error" not in kinds)
            ctx.check(f"phase 1's 2 immediate re-dials + the ladder's one re-send = 3 POSTs, "
                      f"the mock saw {len(mock.requests)}", len(mock.requests) == 3)
            ctx.check(f"a real backoff sleep happened before the re-send, got elapsed={elapsed:.2f}s",
                      elapsed >= 1.0)
    finally:
        mock.stop()
        SCENARIOS.pop("revfix-drop", None)


@test
def test_lock_failed_falls_through_to_the_ungoverned_call(ctx: Ctx):
    """Finding 4's pin: the bucket lock held the way a stuck process
    holds it -- governed_upstream's acquire times out (LOCK_TIMEOUT_S
    patched down for the test) and the call still returns do_call()'s
    result with the degraded flag set (governor_state.warn_once /
    is_degraded), never a raw LockFailed escaping the choke point. The
    same-thread hold works because _Lock's per-key RLock is reentrant
    while the OS-level flock/msvcrt lock is not."""
    from halo_harness.providers import governor_state as gs
    from halo_harness.providers.http import UpstreamResult, governed_upstream

    with _RevEnv():
        key = "host:lockpin.test"
        sentinel = UpstreamResult(status=200, headers={}, resp=None, conn=None)
        old_timeout = gs.LOCK_TIMEOUT_S
        gs.LOCK_TIMEOUT_S = 0.4  # fast on POSIX; msvcrt's LK_LOCK still costs ~10s/attempt on Windows
        try:
            with gs._Lock(key):
                result = governed_upstream("lockpin.test", lambda: sentinel,
                                           {"agent": "pin", "role": "coder"})
            ctx.check("governed_upstream returned do_call()'s result", result is sentinel)
            ctx.check(f"the degraded flag is set afterwards, got {gs.is_degraded()!r}",
                      bool(gs.is_degraded()))
        finally:
            gs.LOCK_TIMEOUT_S = old_timeout


@test
def test_500_peek_keeps_a_long_overload_body(ctx: Ctx):
    """Finding 5's pin: the 500-overload peek reads the body BOUNDED at
    64 KB (was 2048) -- the peeked bytes become `body_bytes`, which the
    wire mapper treats as the WHOLE body, so a provider error page whose
    overload wording sits past the first 2 KB must not be cut short."""
    from halo_harness.providers.http import UpstreamResult, governed_upstream

    class _R:
        def __init__(self):
            self.status = 500
            self.headers = {}
            body = {"error": {"message": "x" * 5000 + " upstream overloaded"}}
            self._body = json.dumps(body).encode("utf-8")

        def read(self, n=-1):
            return self._body if n is None or n < 0 or n >= len(self._body) else self._body[:n]

        def close(self):
            pass

    with _RevEnv(max_retries=1):
        result = governed_upstream("peekpin.test", lambda: UpstreamResult(
            status=500, headers={}, resp=_R(), conn=None), {"agent": "pin", "role": "coder"})
        ctx.check(f"the overload body survived the peek whole (>2048 bytes), got {len(result.body_bytes or b'')}",
                  result.body_bytes is not None and len(result.body_bytes) > 2048
                  and b"upstream overloaded" in result.body_bytes)


@test
def test_reregistered_waiter_is_persisted(ctx: Ctx):
    """Finding 7's pin: a waiter REAPED between passes (another process's
    `_reap` drops it, or a missed save made it stale) is re-registered by
    the `mine is None` branch -- and that re-registration must be
    PERSISTED. Previously the branch never set `took`, so the write only
    came from the 1 s `updated` fallback or the 1 s heartbeat: with a
    fresh `updated` and the heartbeat suppressed, the on-disk waiter's
    `hb` stayed frozen and every other process kept reaping it (priority
    fairness silently broken). `_WAITER_STALE` is patched small so every
    pass reaps our own waiter and walks the re-registration path; the
    ONLY thing that can move the on-disk `hb` is the branch's own save."""
    from halo_harness.providers import governor
    from halo_harness.providers import governor_state as gs
    _fresh_state()
    try:
        key = "host:regpin.test"
        state_file = gs.paths(key)[0]
        blocked = {"rate_rps": 8.0, "burst": 0, "max_inflight": 1, "max_wait": 30.0}
        stop = {"flag": False}
        holder = {}

        def _acquire():
            try:
                governor.acquire(key, blocked, agent="pin", role="worker",
                                 abort=lambda: stop["flag"])
            except BaseException as e:
                holder["err"] = e

        def _disk_hb() -> float:
            try:
                st = json.loads(state_file.read_text(encoding="utf-8"))
                ws = (st.get("waiters") or {}) if isinstance(st, dict) else {}
                return max((float(w.get("hb", 0)) for w in ws.values()), default=0.0)
            except (OSError, ValueError):
                return 0.0

        old_stale, old_hb = governor._WAITER_STALE, governor._HEARTBEAT_WRITE_S
        # every pass reaps our own waiter (walks the re-registration
        # branch); the heartbeat cannot write (30 s) -- and the watch
        # window (0.7 s) is well inside the 1 s `updated` fallback's
        # earliest possible fire, so ONLY the branch's own save can move
        # the on-disk hb in time.
        governor._WAITER_STALE, governor._HEARTBEAT_WRITE_S = 0.05, 30.0
        t = threading.Thread(target=_acquire, daemon=True)
        t.start()
        try:
            deadline = time.time() + 3.0
            hb0 = 0.0
            while time.time() < deadline:  # the initial out-of-loop registration save
                hb0 = _disk_hb()
                if hb0:
                    break
                time.sleep(0.02)
            advanced = 0.0
            deadline2 = time.time() + 0.7
            while time.time() < deadline2:
                advanced = _disk_hb() - hb0
                if advanced > 0.05:  # a re-registration pass landed on disk
                    break
                time.sleep(0.02)
            ctx.check(f"the re-registered waiter's hb advanced on disk ({advanced:.2f}s past the "
                      f"initial registration) -- the re-registration itself persists", advanced > 0.05)
        finally:
            stop["flag"] = True
            t.join(timeout=5)
            governor._WAITER_STALE, governor._HEARTBEAT_WRITE_S = old_stale, old_hb
        ctx.check(f"the aborted acquire raised GovernorAborted, got {holder.get('err')!r}",
                  isinstance(holder.get("err"), governor.GovernorAborted))
    finally:
        _clear_state_env()


@test
def test_halo_governor_typo_values_never_force_the_governor_on(ctx: Ctx):
    """Nit 9's pin: only an explicit yes-spelling of HALO_GOVERNOR
    ("1"/"true"/"yes"/"on") forces on and only a no-spelling forces off;
    anything else (a typo like "of", prose, an empty string) is IGNORED
    and config decides -- a stray value can never silently switch every
    governed call on."""
    from halo_harness.providers.http import governor_params_for_host

    with _RevEnv() as env:
        cfg_path = Path(os.environ["BRIDGE_STATE_DIR"]) / "config.json"
        saved = os.environ.get("HALO_GOVERNOR")
        try:
            for typo in ("of", "yes please", "l", ""):
                os.environ["HALO_GOVERNOR"] = typo
                ctx.check(f"typo {typo!r} defers to config (enabled here -> on)",
                          governor_params_for_host("probe") is not None)
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg["governor"]["enabled"] = False
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
            os.environ["HALO_GOVERNOR"] = "1"
            ctx.check("an explicit 1 still forces on over config off",
                      governor_params_for_host("probe") is not None)
            for typo in ("of", "TRUE-ish"):
                os.environ["HALO_GOVERNOR"] = typo
                ctx.check(f"typo {typo!r} defers to config off -> off",
                          governor_params_for_host("probe") is None)
            os.environ["HALO_GOVERNOR"] = "0"
            ctx.check("an explicit 0 forces off", governor_params_for_host("probe") is None)
            os.environ["HALO_GOVERNOR"] = "ON"
            ctx.check("case-insensitive: ON forces on", governor_params_for_host("probe") is not None)
            os.environ.pop("HALO_GOVERNOR", None)
            ctx.check("unset defers to config off", governor_params_for_host("probe") is None)
        finally:
            if saved is None:
                os.environ.pop("HALO_GOVERNOR", None)
            else:
                os.environ["HALO_GOVERNOR"] = saved
@test
def test_reads_never_create_the_governor_state_dir(ctx: Ctx):
    """Release-gate pin (CI's REAL STATE DIR GUARD caught the leak on a
    clean runner, red since round 4): the READ paths -- `inspect_all`
    (`/gov`'s table, doctor's gateway health), `load`,
    `read_recent_calls` -- resolve the state dir but must never CREATE
    it; `halo doctor` on a fresh machine used to conjure an empty
    `~/.halo/governor/` out of a pure read. The WRITERS (the bucket
    lock, `save`, the call-log append) create it on demand instead, so
    a governed call still works on a clean machine."""
    saved = {k: os.environ.get(k) for k in
             ("GOVERNOR_STATE_DIR", "BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    home = Path(tempfile.mkdtemp(prefix="halo-govread-"))
    try:
        os.environ.pop("GOVERNOR_STATE_DIR", None)
        os.environ["BRIDGE_TEST_HOME"] = str(home)
        os.environ.pop("BRIDGE_STATE_DIR", None)
        from halo_harness.providers import governor, governor_state
        governor_state.reset_degraded_for_tests()
        gov_dir = governor_state.state_dir()
        ctx.check(f"state_dir resolves under the scoped home, got {gov_dir}",
                  str(gov_dir).startswith(str(home)))
        # the three read paths, on a home with NO governor state at all
        _ = governor.inspect_all()
        _ = governor_state.load("host:never-seen", {"rate_rps": 1.0}, time.time())
        _ = governor_state.read_recent_calls("host:never-seen")
        ctx.check(f"a pure read created the dir anyway ({gov_dir.exists()})",
                  not gov_dir.exists())
        # a governed call (the real writer path: lock + state) still works
        # and creates the dir on demand
        h = governor.acquire("host:govread.test", {"rate_rps": 2.0, "burst": 2,
                                                   "max_inflight": 1, "max_retries": 0},
                             agent="w", role="worker")
        governor.report(h, ok=True, params={"rate_rps": 2.0})
        ctx.check(f"the writer path created the dir on demand ({gov_dir.exists()})",
                  gov_dir.exists())
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
