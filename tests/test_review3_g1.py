"""tests.test_review3_g1 -- 3.0.2.0 review fix pass, round G1 (providers
wire), the Governor half:

  * review item 9    an unopenable lock file (state dir under a regular
                     file) degrades to in-process limiting; the governed
                     call still runs instead of failing the turn
  * review item 55   Esc while a request is parked in a Governor cooldown
                     ends the turn as "interrupted", never as an error
  * review item 130  the choke point forwards the `waiting` event (with
                     `rate_ceiling`), and the TUI never clears the gov
                     segment on one
  * review item 131  a report whose lock fails no longer leaks its permit:
                     the next acquire in this process releases it

Hermetic: scoped BRIDGE_TEST_HOME/BRIDGE_STATE_DIR/GOVERNOR_STATE_DIR, a
loopback mock upstream only, bounded sleeps.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()

_SCOPED = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "GOVERNOR_STATE_DIR", "HALO_GOVERNOR")


class _Env:
    """Scoped home + Governor state dir + HALO_GOVERNOR=1 + a fast
    `governor.*` config; every variable it touches is restored on exit and
    the degraded flag / in-process mirror are reset on both ends."""

    def __init__(self, **gov):
        self._gov = {"enabled": True, "max_retries": 1, "cooldown_base": 0.2, "backoff_mult": 0.5,
                     "rate_rps": 8.0, "burst": 8, "max_inflight": 4, "max_wait": 3.0, **gov}

    def __enter__(self):
        from halo_harness.providers import governor_state
        governor_state.reset_degraded_for_tests()
        self._saved = {k: os.environ.get(k) for k in _SCOPED}
        d = Path(tempfile.mkdtemp(prefix="halo-r3g1-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["GOVERNOR_STATE_DIR"] = str(d / ".halo" / "governor")
        os.environ["HALO_GOVERNOR"] = "1"
        (d / ".halo").mkdir(parents=True, exist_ok=True)
        (d / ".halo" / "config.json").write_text(json.dumps({"governor": self._gov}), encoding="utf-8")
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


def _bucket(host: str):
    from halo_harness.providers import governor
    from halo_harness.providers.http import governor_params_for_host
    return "host:" + host, governor.params_for({"name": host}, governor_params_for_host(host))


def _set_cooldown(host: str, seconds: float) -> None:
    from halo_harness.providers import governor_state as gs
    key, params = _bucket(host)
    with gs._Lock(key):
        st = gs.load(key, params, time.time())
        st["cooldown_until"] = time.time() + seconds
        gs.save(key, st)


@test
def test_unopenable_lock_file_degrades_instead_of_raising(ctx: Ctx):
    from halo_harness.providers import governor_state as gs
    from halo_harness.providers.http import UpstreamResult, governed_upstream
    with _Env() as env:
        blocker = env.home / "not-a-dir"
        blocker.write_text("a regular file", encoding="utf-8")
        os.environ["GOVERNOR_STATE_DIR"] = str(blocker / "governor")
        sentinel = UpstreamResult(status=200, headers={}, resp=None, conn=None)
        ran = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                got = governed_upstream("api.example.invalid", lambda: ran.append(1) or sentinel,
                                        {"agent": "pin", "role": "coder"})
            except OSError as e:
                got = e
        ctx.check(f"the governed call ran and returned its result, got {got!r}", got is sentinel and ran == [1])
        ctx.check(f"the degraded flag carries the reason, got {gs.is_degraded()!r}", bool(gs.is_degraded()))


@test
def test_report_lock_failure_never_leaks_the_permit(ctx: Ctx):
    from halo_harness.providers import governor, governor_state as gs
    from halo_harness.providers.http import UpstreamResult, governed_upstream
    with _Env(max_inflight=1, max_wait=1.0):
        host = "leak.example.invalid"
        key, params = _bucket(host)
        real_lock = gs._Lock

        class _Contended(real_lock):
            def __enter__(self):
                raise gs.LockFailed("held elsewhere (test)")

        def call_whose_report_cannot_lock():
            gs._Lock = _Contended  # acquire already ran; report() is next
            return UpstreamResult(status=200, headers={}, resp=None, conn=None)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r1 = governed_upstream(host, call_whose_report_cannot_lock, {"agent": "pin", "role": "coder"})
        finally:
            gs._Lock = real_lock
        st = gs.load(key, params, time.time())
        ctx.check(f"the first call still returned, got {r1!r}", r1 is not None and r1.status == 200)
        ctx.check(f"its permit is still on disk before the next lock, got {st['inflight']}",
                  len(st["inflight"]) == 1)
        t0 = time.monotonic()
        try:  # a leaked permit would block this forever (the in-flight cap is never bypassed)
            h = governor.acquire(key, params, agent="pin", role="coder", max_wait=1.0,
                                 abort=lambda: time.monotonic() - t0 > 3.0)
        except governor.GovernorAborted:
            h = None
        waited = time.monotonic() - t0
        st = gs.load(key, params, time.time())
        ctx.check(f"max_inflight=1 still granted promptly (waited {waited:.2f}s)", h is not None and waited < 0.9)
        ctx.check(f"only the new permit is in flight, got {sorted(st['inflight'])}",
                  h is not None and sorted(st["inflight"]) == [h.call_id])
        if h is not None:
            governor.report(h, ok=True, params=params)


@test
def test_waiting_event_reaches_on_event_with_rate_ceiling(ctx: Ctx):
    from halo_harness.providers.http import UpstreamResult, governed_upstream
    with _Env(max_wait=5.0):
        host = "wait.example.invalid"
        _set_cooldown(host, 2.6)  # past one 2 s acquire sleep, so a later pass is still cooling
        seen = []
        sentinel = UpstreamResult(status=200, headers={}, resp=None, conn=None)
        got = governed_upstream(host, lambda: sentinel,
                                {"agent": "pin", "role": "main", "on_event": seen.append})
        waits = [e for e in seen if e.get("event") == "waiting"]
        ctx.check("the call ran after the cooldown", got is sentinel)
        ctx.check(f"a waiting event was forwarded, got {[e.get('event') for e in seen]}", bool(waits))
        ctx.check(f"it carries rate_ceiling and a live cooldown, got {waits[:1]}",
                  bool(waits) and waits[0].get("rate_ceiling") is not None
                  and waits[0].get("cooldown_remaining", 0) > 0)


class _Bar:
    def __init__(self):
        self.calls = []

    def set_gov_state(self, state):
        self.calls.append(state)


class _App:
    def __init__(self):
        self.status_bar = _Bar()


@test
def test_tui_waiting_event_never_clears_the_gov_segment(ctx: Ctx):
    from halo_harness import events
    from halo_harness.tui.dispatch import apply_event
    app = _App()
    healthy_wait = {"event": "waiting", "key": "host:x", "position": 2, "cooldown_remaining": 0.0,
                    "rate": 2.0, "rate_ceiling": 2.0}
    asyncio.run(apply_event(app, events.Event("governor", healthy_wait)))
    ctx.check(f"a waiting event at full rate leaves the segment alone, got {app.status_bar.calls}",
              app.status_bar.calls == [])
    cooling_wait = dict(healthy_wait, rate=1.0, cooldown_remaining=12.0)
    asyncio.run(apply_event(app, events.Event("governor", cooling_wait)))
    ctx.check(f"a cooling waiting event shows rate/ceiling/cooldown, got {app.status_bar.calls}",
              app.status_bar.calls == [(1.0, 2.0, 12.0)])
    asyncio.run(apply_event(app, events.Event("governor", {"event": "recover", "rate": 2.0,
                                                           "rate_ceiling": 2.0})))
    ctx.check("a recover event at ceiling still clears it", app.status_bar.calls[-1] is None)


@test
def test_esc_during_a_governor_cooldown_is_an_interrupt(ctx: Ctx):
    from tests.helpers.mock_openai import MockUpstream
    mock = MockUpstream().start()
    try:
        with _Env(max_wait=30.0) as env:
            from halo_harness.agent.assemble import SessionContext
            from halo_harness.agent.loop import Session
            from halo_harness.hooks import HookRunner
            from halo_harness.model import ModelProfile, parse_model_ref
            from halo_harness.providers.stream import ProviderCreds
            from urllib.parse import urlparse
            _set_cooldown(urlparse(mock.base_url).hostname, 60.0)
            cwd = env.home / "project"
            cwd.mkdir(parents=True, exist_ok=True)
            state_dir = Path(os.environ["BRIDGE_STATE_DIR"])
            session = Session(
                cwd=cwd, model_ref=parse_model_ref("or:mock/r3g1-cool"), model_profile=ModelProfile(),
                creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
                state_dir=state_dir, model_label="mock/r3g1-cool",
                session_context=SessionContext(cwd=cwd, model_label="mock/r3g1-cool"),
                openrouter_base_url=mock.base_url, max_turns=2,
                hook_runner=HookRunner({}, cwd=cwd, session_id="r3g1-cool",
                                       transcript_path=str(state_dir / "r3g1cool.jsonl")),
            )
            threading.Timer(0.8, session.abort.set).start()
            t0 = time.monotonic()
            out = list(session.turn("say anything"))
            elapsed = time.monotonic() - t0
            kinds = [getattr(e, "kind", "") for e in out]
            done = [e.data.get("reason") for e in out if getattr(e, "kind", "") == "turn_done"]
            ctx.check(f"no error event, got kinds={kinds}", "error" not in kinds)
            ctx.check(f"the turn ended interrupted, got {done}", done == ["interrupted"])
            ctx.check(f"it stopped promptly ({elapsed:.1f}s), never waited out the 60 s cooldown",
                      elapsed < 15.0)
            ctx.check(f"nothing reached the upstream, got {len(mock.requests)} requests",
                      len(mock.requests) == 0)
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
