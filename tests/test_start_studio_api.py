"""tests.test_start_studio_api -- Halo 3.1.1.0 R1: Studio's `/api/start`
(studio/start_api.py, start_job.py, start/fresh.py), no browser.

1. a fresh home: `show`; the seven steps' plan; the guided first run's card
   (3.2.2.0 R2); dismiss is remembered; a lineup of your own, an active
   lineup or a start each end "fresh"
2. POST start runs `halo start --yes` on the fake (HALO_START_FAKE=1) as a
   background job: 202, a second POST while it runs is a 409, every step
   published as a `start` frame (session `start:<job>`), then the summary
   frame; GET start shows the job's seven steps done
3. no provider (the fake off): 422 with reason no_provider, nothing started
Run: python -m tests.test_start_studio_api
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _req(method: str, path: str, state: Path, cwd: Path, server=None):
    from halo_harness.studio.api import Request
    return Request(method=method, path=path, query={}, body={}, cwd=cwd, state_dir=state, server=server)


def _state() -> Path:
    from halo_harness.config.paths import bridge_home
    state = Path(bridge_home())
    state.mkdir(parents=True, exist_ok=True)
    return state


class _Server:
    """What start_api needs of the HTTP server: its live-feed bridge (studio/events.bridge_for)."""

    def __init__(self):
        import threading
        self.events, self.events_lock, self.event_taps = None, threading.Lock(), []


@test
def test_fresh_home_and_dismiss(ctx: Ctx):
    from halo_harness.start import fresh
    from halo_harness.studio.api import dispatch
    state = _state()
    cwd = Path(tempfile.mkdtemp(prefix="start-api-cwd-"))
    status, body = dispatch(_req("GET", "start", state, cwd))
    ctx.check(f"a fresh home shows the overlay, got {status} {body}", status == 200 and body["fresh"] is True and body["show"] is True
              and body["job"] is None)
    ctx.check("the seven steps' plan", [p["key"] for p in body["plan"]] == ["lineup", "repo", "goal", "plan", "run", "report", "next"])
    card = "\n".join(body.get("card") or [])
    ctx.check(f"the card: what, models, cost, time, writes (3.2.2.0 R2), got {card[:120]!r}", card.startswith("The guided first run")
              and all(w in card for w in ("Models it will call:", "Estimated cost:", "Time: ", "Writes:", str(state / "teams"))))
    status, body = dispatch(_req("POST", "start/dismiss", state, cwd))
    ctx.check("dismiss answers", status == 200 and body == {"dismissed": True})
    _, body = dispatch(_req("GET", "start", state, cwd))
    ctx.check(f"remembered: still fresh, not shown, got {body}", body["fresh"] is True and body["dismissed"] is True and body["show"] is False)
    (fresh.start_root(state) / fresh.DISMISSED).unlink()
    from halo_harness.theme import set_config_value
    set_config_value("team", "balanced")
    ctx.check("an active lineup is not fresh", fresh.status(cwd, state)["fresh"] is False)
    set_config_value("team", "")
    ctx.check("back to fresh", fresh.status(cwd, state)["fresh"] is True)
    from halo_harness.start.lineup import own_lineup
    own_lineup("balanced", state_dir=state)
    got = fresh.status(cwd, state)
    ctx.check(f"a lineup of your own is not fresh, got {got['own_lineups']}", got["fresh"] is False and got["own_lineups"] == ["my-balanced"])
    (state / "teams" / "my-balanced.yaml").unlink()
    ctx.check("the shipped copies alone are fresh again", fresh.status(cwd, state)["fresh"] is True)


@test
def test_post_start_runs_the_fake_and_streams_frames(ctx: Ctx):
    from halo_harness.studio import start_job
    from halo_harness.studio.api import dispatch
    from halo_harness.studio.events import bridge_for
    state, cwd, server = _state(), Path(tempfile.mkdtemp(prefix="start-api-cwd-")), _Server()
    frames: list = []
    bridge_for(server).taps.append(lambda f: frames.append(f) if f.get("event") == "start" else None)
    saved_fake = os.environ.get("HALO_START_FAKE")
    os.environ["HALO_START_FAKE"] = "1"
    try:
        status, body = dispatch(_req("POST", "start", state, cwd, server))
        again = dispatch(_req("POST", "start", state, cwd, server))
        end = time.monotonic() + 90
        while start_job.running() and time.monotonic() < end:
            time.sleep(0.1)
    finally:
        if saved_fake is None:
            os.environ.pop("HALO_START_FAKE", None)
        else:
            os.environ["HALO_START_FAKE"] = saved_fake
    ctx.check(f"202 with the job, got {status} {body}", status == 202 and body["job"]["job"] and body["job"]["fake"] is True)
    ctx.check(f"a second start while it runs is a 409, got {again[0]}", again[0] == 409
              and again[1]["error"] == "the guided first run is already running")
    ctx.check("it ended", not start_job.running())
    data = [f["data"] for f in frames]
    keys = [d["key"] for d in data if d["state"] == "done"]
    ctx.check(f"each step's frames end done, in order, got {keys}", keys == ["lineup", "repo", "goal", "plan", "run", "report", "next"])
    job = body["job"]["job"]
    ctx.check("every frame is the start's: one session id, the job in its data",
              {f["session_id"] for f in frames} == {f"start:{job}"} and all(d["job"] == job for d in data))
    last = data[-1] if data else {}
    ctx.check(f"the summary frame closes it, got {last}", last.get("key") == "summary" and last["summary"]["ok"] is True
              and last["summary"]["lineup"] == "my-halo-dev-cycle" and "steps" not in last["summary"])
    ctx.check("a frame has the brief's fields", {"step", "total", "key", "title", "why", "command", "state", "lines"} <= set(data[0]))
    _, got = dispatch(_req("GET", "start", state, cwd))
    ctx.check("GET start: the job's seven steps done, its summary", got["job"]["running"] is False
              and [s["state"] for s in got["job"]["steps"]] == ["done"] * 7 and got["job"]["summary"]["ok"] is True)
    ctx.check("after the start the home is no longer fresh", got["fresh"] is False and got["starts"] >= 1)


def _post_and_wait(state, cwd, server) -> "tuple[int, dict]":
    from halo_harness.studio import start_job
    from halo_harness.studio.api import dispatch
    saved_fake = os.environ.get("HALO_START_FAKE")
    os.environ["HALO_START_FAKE"] = "1"
    try:
        status, body = dispatch(_req("POST", "start", state, cwd, server))
        end = time.monotonic() + 90
        while start_job.running() and time.monotonic() < end:
            time.sleep(0.05)
    finally:
        if saved_fake is None:
            os.environ.pop("HALO_START_FAKE", None)
        else:
            os.environ["HALO_START_FAKE"] = saved_fake
    return status, body


@test
def test_a_raising_step_ends_the_job_with_the_line_and_the_log(ctx: Ctx):
    """3.2.2.0 R1: the step's failed frame and the summary frame carry the one line and the log."""
    from halo_harness.start import engine, steps_setup
    from halo_harness.studio.api import dispatch
    from halo_harness.studio.events import bridge_for

    def boom(*_a, **_k):
        raise TypeError("boom")
    state, cwd, server = _state(), Path(tempfile.mkdtemp(prefix="start-api-cwd-")), _Server()
    frames: list = []
    bridge_for(server).taps.append(lambda f: frames.append(f["data"]) if f.get("event") == "start" else None)
    saved = steps_setup.repo
    steps_setup.repo = boom
    try:
        status, _body = _post_and_wait(state, cwd, server)
    finally:
        steps_setup.repo = saved
    last = frames[-1] if frames else {}
    summary = last.get("summary") or {}
    ctx.check(f"202, then the summary frame, got {status} {last}", status == 202 and last.get("key") == "summary")
    ctx.check(f"reason is the one line, error_log a file with the traceback, got {summary}", summary.get("ok") is False
              and summary.get("stopped_at") == "repo" and summary.get("reason") == "TypeError: boom"
              and Path(summary.get("error_log") or "no-log").is_file()
              and "Traceback" in Path(summary["error_log"]).read_text(encoding="utf-8"))
    failed = [d for d in frames if d.get("key") == "repo" and d.get("state") == "failed"]
    ctx.check(f"the repo step's failed frame has both lines, got {failed}", failed and "TypeError: boom" in failed[-1]["lines"]
              and any(ln.startswith("the full error is in ") for ln in failed[-1]["lines"]))
    saved_init = engine.StartRun.__init__
    engine.StartRun.__init__ = boom
    try:
        status2, body2 = _post_and_wait(state, cwd, server)
    finally:
        engine.StartRun.__init__ = saved_init
    s2 = (body2.get("job") or {}).get("summary") or {}
    ctx.check(f"a start that cannot be built: 202 with the job already ended, got {status2} {body2}", status2 == 202
              and s2.get("reason") == "TypeError: boom" and Path(s2.get("error_log") or "no-log").is_file()
              and body2["job"]["running"] is False)
    _, got = dispatch(_req("GET", "start", state, cwd))
    ctx.check("GET start shows that summary", (got["job"] or {}).get("summary", {}).get("reason") == "TypeError: boom")


@test
def test_no_provider_is_a_422(ctx: Ctx):
    from halo_harness.start import provider
    from halo_harness.studio import start_job
    from halo_harness.studio.api import dispatch
    saved = (provider.configured, provider.default_model)
    provider.configured, provider.default_model = (lambda: []), (lambda: "")
    before = start_job.current()
    try:
        status, body = dispatch(_req("POST", "start", _state(), Path(tempfile.mkdtemp(prefix="start-api-cwd-"))))
    finally:
        provider.configured, provider.default_model = saved
    ctx.check(f"422 no_provider, got {status} {body}", status == 422 and body["reason"] == "no_provider" and "halo init" in body["error"])
    ctx.check("nothing started", start_job.current() == before)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
