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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
