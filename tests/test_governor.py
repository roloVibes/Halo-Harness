"""tests.test_governor -- Halo 2.0.5 round 4: the Governor's core
behavior, ported from the owner's kit's twelve pytest tests to the house
runner, plus the REVIEW.md changes' own tests (clock clamp, HTTP-date,
abort, lock timeout, thread serialization, 500 neutral, heartbeat
throttle, rotation, timeout counting).

Every test scopes its own governor state dir (GOVERNOR_STATE_DIR --
which ALSO overrides the halo state dir for the governor, so nothing
here ever touches a real ~/.halo) and resets the in-process
mirror/degraded flag, exactly the kit's conftest, translated. The
real-sleep waits are kept small and bounded (the kit's own values
shrunk) so the module stays fast on CI.
"""

from __future__ import annotations

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


def _fresh(ctx_dir=None) -> Path:
    """A fresh GOVERNOR_STATE_DIR + the module-state reset the kit's
    conftest did per-test. Each caller passes its own dir (or gets one)
    and sets the env itself -- see `_scoped`."""
    from halo_harness.providers import governor_state
    governor_state.reset_degraded_for_tests()
    return Path(ctx_dir or tempfile.mkdtemp(prefix="halo-gov-test-"))


class _Scoped:
    """Set GOVERNOR_STATE_DIR for the block, restore after."""

    def __init__(self, path: Path):
        self.path = path
        self._old = None

    def __enter__(self):
        self._old = os.environ.get("GOVERNOR_STATE_DIR")
        os.environ["GOVERNOR_STATE_DIR"] = str(self.path)
        return self

    def __exit__(self, *a):
        if self._old is None:
            os.environ.pop("GOVERNOR_STATE_DIR", None)
        else:
            os.environ["GOVERNOR_STATE_DIR"] = self._old
        return False


def _params(rps=2.0, burst=3, inflight=2, **over):
    p = {"rate_rps": rps, "burst": burst, "max_inflight": inflight,
         "ramp_after": 2, "ramp_inc": 0.5, "backoff_mult": 0.5, "cooldown_base": 1.0}
    p.update(over)
    return p


# ---- the kit's twelve, ported -----------------------------------------------

@test
def test_key_shared_by_gateway_host(ctx: Ctx):
    from halo_harness.providers import governor
    with _Scoped(_fresh()):
        e1 = {"base_url": "https://x.cloud.example.com/serving-endpoints", "name": "gw-model-a"}
        e2 = {"base_url": "https://x.cloud.example.com/serving-endpoints", "name": "gw-model-b"}
        ctx.check("two models on one gateway -> one bucket",
                  governor.key_for(e1) == governor.key_for(e2))
        ctx.check("a keyless kind keys on provider+host",
                  governor.key_for({"name": "ollama", "kind": "ollama", "base_url": ""}).startswith("provider:"))


@test
def test_429_cuts_rate_and_retries_transparently(ctx: Ctx):
    from halo_harness.providers import governor
    with _Scoped(_fresh()):
        key = "host:gw.test"
        seq = [429, 200]

        def do():
            s = seq.pop(0)
            return s, {"choices": [{"message": {"content": "ok"}}]}, ({"retry-after": "1"} if s == 429 else {})

        status, _ = governor.governed(key, _params(rps=2.0), do, agent="w1", role="worker")
        st = governor.inspect(key)
        ctx.check("transparently retried past the 429", status == 200)
        ctx.check(f"rate multiplicatively cut from 2.0, got {st['rate']}", st["rate"] <= 1.0)


@test
def test_sustained_success_ramps_rate_back(ctx: Ctx):
    from halo_harness.providers import governor
    with _Scoped(_fresh()):
        key = "host:gw.test"
        p = _params(rps=4.0)
        h = governor.acquire(key, p, agent="w", role="worker")
        governor.report(h, ok=False, status=429, params=p)
        low = governor.inspect(key)["rate"]
        for _ in range(4):
            h = governor.acquire(key, p, agent="w", role="worker", max_wait=5)
            governor.report(h, ok=True, status=200, params=p)
        ctx.check(f"additive ramp-back above {low}", governor.inspect(key)["rate"] > low)


@test
def test_priority_orchestrator_before_worker(ctx: Ctx):
    from halo_harness.providers import governor
    with _Scoped(_fresh()):
        key = "host:gw.test"
        now = time.time()
        with governor.gs._Lock(key):
            st = governor.gs.load(key, _params(), now)
            st["waiters"] = {
                "wk": {"priority": governor.priority_for("worker"), "ts": now, "hb": now, "pid": os.getpid(), "agent": "w"},
                "or": {"priority": governor.priority_for("orchestrator"), "ts": now + 5, "hb": now, "pid": os.getpid(), "agent": "o"},
            }
            governor.gs.save(key, st)
            ctx.check("orchestrator is front despite arriving later",
                      governor._is_front(st, "or") is True)
            ctx.check("worker is not front", governor._is_front(st, "wk") is False)
        ctx.check("role priorities: main 0, reviewer 1, other 2",
                  governor.priority_for("main") == 0 and governor.priority_for("reviewer") == 1
                  and governor.priority_for("something-else") == 2)
        ctx.check("an explicit bio priority wins over the role",
                  governor.priority_for("worker", explicit=0) == 0)
        ctx.check("governor.priorities overrides the role table",
                  governor.priority_for("watchdog", overrides={"watchdog": 1}) == 1)


@test
def test_concurrency_hard_cap_across_calls(ctx: Ctx):
    from halo_harness.providers import governor
    with _Scoped(_fresh()):
        key = "host:gw.test"
        p = _params(inflight=2)
        h1 = governor.acquire(key, p, agent="a", role="worker")
        h2 = governor.acquire(key, p, agent="b", role="worker")
        ctx.check("two in-flight", governor.inspect(key)["inflight"] == 2)
        got = {}

        def third():
            got["h"] = governor.acquire(key, p, agent="c", role="worker", max_wait=0.3)

        t = threading.Thread(target=third)
        t.start()
        time.sleep(0.6)
        ctx.check("3rd permit NOT granted while the cap is full", "h" not in got)
        governor.report(h1, ok=True, status=200, params=p)
        t.join(timeout=3)
        ctx.check("3rd permit granted after a slot freed", "h" in got)
        governor.report(h2, ok=True, status=200, params=p)
        if "h" in got:
            governor.report(got["h"], ok=True, status=200, params=p)


@test
def test_failopen_only_front_waiter_after_max_wait(ctx: Ctx):
    from halo_harness.providers import governor
    with _Scoped(_fresh()):
        key = "host:gw.test"
        p = _params(inflight=1)
        h = governor.acquire(key, p, agent="w", role="worker")
        governor.report(h, ok=False, status=429, retry_after=30, params=p)
        ctx.check("cooldown set", governor.inspect(key)["cooldown_remaining"] > 5)
        t0 = time.time()
        h2 = governor.acquire(key, p, agent="orch", role="orchestrator", max_wait=1.0)
        waited = time.time() - t0
        ctx.check(f"front waiter let through after ~max_wait (waited {waited:.1f}s)", 0.9 <= waited < 6)
        governor.report(h2, ok=True, status=200, params=p)


@test
def test_transport_error_releases_neutrally(ctx: Ctx):
    from halo_harness.providers import governor
    with _Scoped(_fresh()):
        key = "host:gw.test"
        p = _params(rps=2.0)

        def do():
            raise ConnectionError("dns is not evidence about load")

        try:
            governor.governed(key, p, do, agent="w", role="worker")
            raised = False
        except ConnectionError:
            raised = True
        st = governor.inspect(key)
        ctx.check("the transport error propagated", raised)
        ctx.check("permit released", st["inflight"] == 0)
        ctx.check("rate untouched", st["rate"] == 2.0)
        ctx.check("neither counter moved", st["consecutive_ok"] == 0 and st["consecutive_err"] == 0)


@test
def test_two_timeouts_in_a_row_count_as_overload(ctx: Ctx):
    """REVIEW/round-brief: ONE timeout is a blip (neutral); TWO in a row
    cut the rate -- a saturated gateway stops answering before it starts
    refusing."""
    from halo_harness.providers import governor
    with _Scoped(_fresh()):
        key = "host:gw.test"
        p = _params(rps=2.0)

        def do():
            raise socket.timeout("gateway never answered")

        for _ in range(2):
            try:
                governor.governed(key, p, do, agent="w", role="worker")
            except socket.timeout:
                pass
        st = governor.inspect(key)
        ctx.check(f"rate cut after two timeouts, got {st['rate']}", st["rate"] <= 1.0)
        ctx.check("cooldown set", st["cooldown_remaining"] > 0)
        ctx.check("permit released", st["inflight"] == 0)
        # and a single timeout alone never cuts:
        with _Scoped(_fresh()):
            key2 = "host:gw2.test"
            try:
                governor.governed(key2, p, do, agent="w", role="worker")
            except socket.timeout:
                pass
            st2 = governor.inspect(key2)
            ctx.check(f"ONE timeout is neutral, rate {st2['rate']}", st2["rate"] == 2.0)


@test
def test_pid_alive_delegates_to_bg_run(ctx: Ctx):
    from halo_harness.providers import governor
    ctx.check("None is dead", governor.pid_alive(None) is False)
    ctx.check("negative is dead", governor.pid_alive(-1) is False)
    ctx.check("this process is alive", governor.pid_alive(os.getpid()) is True)
    ctx.check("an absurd pid is dead", governor.pid_alive(4194311) is False)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
