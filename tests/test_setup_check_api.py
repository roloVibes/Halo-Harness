"""tests.test_setup_check_api -- Setup's Check and Linux fixes routes (Halo
3.3.0.0 R3, studio/setup_check_api.py, setup_check_job.py,
setup_check_state.py) through `api.dispatch` over a scratch home
(tests/helpers/setup_home.py: its own env file, no background network). No
model call: the checks are stubs, the guided first run is the fake
(`HALO_START_FAKE=1`); the two Linux fixes are stubs (nothing downloaded, no
rc file written). Pins: the state's checks, card and last check; a job's
frames in order, its summary, the catch-up read, 409, the 422s, stop; the
Linux fixes block and its route; a state read opens no connection (4b).
Run: python -m tests.test_setup_check_api
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.setup_home import SetupHome as _Env  # noqa: E402

test, TESTS = new_registry()


class _Server:
    """What the Check job needs of the HTTP server: its live-feed bridge; `frames` collects the `setup` frames."""

    def __init__(self):
        self.events, self.events_lock, self.frames = None, threading.Lock(), []
        self.event_taps = [lambda f: self.frames.append(f) if f.get("event") in ("setup", "start") else None]


def _call(e, method, path, body=None, server=None):
    from halo_harness.studio.api import Request, dispatch
    return dispatch(Request(method=method, path=path, query={}, body=body or {}, cwd=e.cwd, state_dir=e.state_dir, server=server))


def _wait_job(limit: float = 90.0) -> None:
    from halo_harness.studio import setup_check_job
    end = time.monotonic() + limit
    while setup_check_job.running() and time.monotonic() < end:
        time.sleep(0.05)


def _forget_jobs() -> None:
    """The one-process runner shares module state: no Check or Start here job is left behind for the next module."""
    from halo_harness.studio import setup_check_job, start_job
    _wait_job()
    with setup_check_job._lock:
        setup_check_job._state["job"] = None
    with start_job._lock:
        start_job._state["job"] = None


def _stub_checks(results: dict, gate=None):
    """Swap each check's `run` for a stub returning (or failing with) `results[key]`; returns the restore."""
    from halo_harness.start import checks as C
    saved = {c["key"]: c["run"] for c in C.CHECKS}

    def make(key):
        def run(_ctx):
            if gate is not None:
                gate.wait(10)
            ok, lines = results[key]
            if not ok:
                raise C.CheckFailed(lines)
            return lines
        return run
    for c in C.CHECKS:
        if c["key"] in results:
            c["run"] = make(c["key"])
    return lambda: [c.update(run=saved[c["key"]]) for c in C.CHECKS]


@test
def test_the_state_carries_the_checks_the_card_and_no_provider(ctx: Ctx):
    with _Env() as e:
        status, s = e.call("GET", "setup/state")
        rows = s["checks"]
        ctx.check(f"the five checks in order, got {[r['key'] for r in rows]}", status == 200
                  and [r["key"] for r in rows] == ["doctor", "catalog", "hello", "gym", "start"])
        ctx.check("doctor, catalog and hello are on by default", [r["default_on"] for r in rows] == [True, True, True, False, False])
        ctx.check(f"each row: what, cost, time, writes, got {rows[0]}", all({"title", "what", "cost", "time", "writes"} <= set(r) for r in rows)
                  and rows[0]["cost"] == "free" and rows[0]["writes"] == "nothing")
        ctx.check(f"hello's cost with no default model, got {rows[2]['cost']!r}", rows[2]["cost"] == "nothing: no default model is set yet")
        ctx.check(f"the card is the guided first run's, got {s['card'][:1]}", s["card"][0] == "The guided first run (halo start)"
                  and any(line.startswith("Estimated cost:") for line in s["card"]))
        ctx.check("no check ran yet; no provider is set", s["last_check"] is None and s["no_provider"] is True)
        from halo_harness.theme import set_config_value
        set_config_value("model", "ol:tiny:1b")
        _status, s = e.call("GET", "setup/state")
        ctx.check(f"a default model: the gym offers it, free; hello's cost says local, got {s['gym_models']} {s['checks'][2]['cost']!r}",
                  s["gym_models"][:1] == [{"ref": "ol:tiny:1b", "cost": "free, a few minutes"}]
                  and s["checks"][2]["cost"] == "one tiny call, free (a local model)" and s["no_provider"] is False)


@test
def test_a_job_publishes_each_check_then_the_summary(ctx: Ctx):
    from halo_harness.studio import setup_check_job
    gate = threading.Event()
    restore = _stub_checks({"doctor": (True, ["config ok"]), "catalog": (False, ["[!!] openrouter: refused"]),
                            "hello": (True, ["pong"])}, gate)
    with _Env() as e:
        server = _Server()
        try:
            status, body = _call(e, "POST", "setup/check", {"checks": ["hello", "doctor", "catalog"]}, server)
            again = _call(e, "POST", "setup/check", {"checks": ["doctor"]}, server)
            gate.set()
            _wait_job()
        finally:
            gate.set()
            restore()
        ctx.check(f"202 with the job, in the list's order, got {status} {body}", status == 202 and body["job"]["keys"] == ["doctor", "catalog", "hello"])
        ctx.check(f"a second POST while it runs is a 409, got {again[0]}", again[0] == 409 and again[1]["error"] == "a check is already running")
        data = [f["data"] for f in server.frames if f["event"] == "setup"]
        ctx.check(f"running then done / failed per check, then the summary, got {[(d['key'], d['state']) for d in data]}",
                  [(d["key"], d["state"]) for d in data] == [("doctor", "running"), ("doctor", "done"), ("catalog", "running"),
                                                             ("catalog", "failed"), ("hello", "running"), ("hello", "done"), ("summary", "finished")])
        job = body["job"]["job"]
        ctx.check("one session id, the job in each frame", {f["session_id"] for f in server.frames} == {f"setup:{job}"} and all(d["job"] == job for d in data))
        ctx.check(f"a done frame carries its lines and title, got {data[1]}", data[1]["lines"] == ["config ok"] and data[1]["title"] == "Doctor")
        ctx.check(f"a running frame says what the check does, got {data[0]['lines']}", data[0]["lines"][0].startswith("checks your config"))
        last = data[-1]
        ctx.check(f"the summary: not ok, each result, got {last}", last["ok"] is False and last["stopped"] is False
                  and [(r["key"], r["ok"]) for r in last["results"]] == [("doctor", True), ("catalog", False), ("hello", True)])
        _status, got = _call(e, "GET", "setup/check")
        ctx.check(f"GET setup/check catches up: the last frame per check and the summary, got {got['job']['checks']}",
                  [(c["key"], c["state"]) for c in got["job"]["checks"]] == [("doctor", "done"), ("catalog", "failed"), ("hello", "done")]
                  and got["job"]["running"] is False and got["job"]["summary"]["ok"] is False)
        record = json.loads((e.state_dir / "studio" / "last-check.json").read_text(encoding="utf-8"))
        ctx.check(f"last-check.json written, got {record.get('ok')} {record.get('when')}", record["ok"] is False and record["when"] > 0
                  and len(record["results"]) == 3)
        _status, s = e.call("GET", "setup/state")
        ctx.check("the state's last_check is it", s["last_check"] == record)
        ctx.check("the job is over", not setup_check_job.running())
        _forget_jobs()


@test
def test_refusals_and_stop(ctx: Ctx):
    with _Env() as e:
        os.environ.pop("HALO_START_FAKE", None)
        for body, want in (({"checks": ["doctor", "nope"]}, "nope: not a check (one of doctor, catalog, hello, gym, start)"),
                           ({"checks": []}, "tick at least one check"), ({}, "tick at least one check")):
            status, got = _call(e, "POST", "setup/check", body)
            ctx.check(f"{body}: a 422, got {status} {got.get('error')!r}", status == 422 and got["error"] == want)
        status, got = _call(e, "POST", "setup/check", {"checks": ["doctor", "start"]})
        ctx.check(f"the guided first run with no provider: the start's own no_provider 422, got {status} {got.get('reason')}",
                  status == 422 and got["reason"] == "no_provider" and got["error"].startswith("No model provider is set up yet"))
        ctx.check("GET on stop is a 405", _call(e, "GET", "setup/check/stop")[0] == 405)
        gate = threading.Event()
        restore = _stub_checks({"doctor": (True, ["ok"]), "catalog": (True, ["ok"]), "hello": (True, ["pong"])}, gate)
        try:
            _call(e, "POST", "setup/check", {"checks": ["doctor", "catalog", "hello"]})
            status, got = _call(e, "POST", "setup/check/stop")
            gate.set()
            _wait_job()
        finally:
            gate.set()
            restore()
        _status, view = _call(e, "GET", "setup/check")
        _forget_jobs()
        summary = view["job"]["summary"]
        ctx.check(f"stop: the running check ends, the rest do not start, got {status} {summary}", status == 200 and got == {"stopping": True}
                  and summary["stopped"] is True and summary["ok"] is False and [r["key"] for r in summary["results"]] == ["doctor"])


@test
def test_the_guided_first_run_runs_through_the_start_job(ctx: Ctx):
    with _Env() as e:
        server = _Server()
        os.environ["HALO_START_FAKE"] = "1"
        try:
            status, body = _call(e, "POST", "setup/check", {"checks": ["start"]}, server)
            _wait_job(120)
        finally:
            os.environ.pop("HALO_START_FAKE", None)
            _forget_jobs()
        setup = [f["data"] for f in server.frames if f["event"] == "setup"]
        starts = [f["data"] for f in server.frames if f["event"] == "start"]
        ctx.check(f"202, got {status} {body.get('error')}", status == 202)
        ctx.check(f"the start's own frames came, its seven steps done, got {len(starts)}",
                  [d["key"] for d in starts if d.get("state") == "done"] == ["lineup", "repo", "goal", "plan", "run", "report", "next"])
        ctx.check(f"the Check row: running, then done with the start's outcome, got {[(d['key'], d['state'], (d.get('lines') or [])[:1]) for d in setup]}",
                  [(d["key"], d["state"]) for d in setup] == [("start", "running"), ("start", "done"), ("summary", "finished")]
                  and setup[1]["lines"][0].startswith("done: lineup my-halo-dev-cycle") and setup[-1]["ok"] is True)


@test
def test_the_linux_fixes_block_and_route(ctx: Ctx):
    from halo_harness import linux_fixes as LF
    from halo_harness.studio import setup_check_state as S
    calls = []
    saved = (S.platform_name, S.rg_on_path, LF.install_static_ripgrep, LF.ensure_local_bin_on_rc, LF.local_bin_on_noninteractive_path)
    try:
        S.platform_name, S.rg_on_path = (lambda: "linux"), (lambda: False)
        LF.local_bin_on_noninteractive_path = lambda **_k: ("rc", "") in calls
        LF.install_static_ripgrep = lambda dest, **_k: calls.append(("rg", str(dest))) or (True, str(dest / "rg"))
        LF.ensure_local_bin_on_rc = lambda **_k: calls.append(("rc", "")) or (True, Path("~/.profile"))
        with _Env() as e:
            S.forget_linux()
            _status, s = e.call("GET", "setup/state")
            fixes = s["linux_fixes"]
            ctx.check(f"a box without rg and ~/.local/bin off PATH: two fixes, got {fixes}", fixes["needed"] is True and fixes["platform"] == "linux"
                      and [i["id"] for i in fixes["items"]] == ["ripgrep", "path"] and "~/.local/bin" in fixes["items"][1]["line"])
            status, s = e.call("POST", "setup/linux-fixes")
            ctx.check(f"Apply: both fixes, through the stubs only, got {calls}", status == 200
                      and calls == [("rg", str(e.home / ".local" / "bin")), ("rc", "")])
            ctx.check(f"the lines say what was written, got {s.get('lines')}", s["lines"][0].startswith("installed rg: ")
                      and s["lines"][1].startswith("added ~/.local/bin to PATH in "))
            ctx.check(f"the state read again: only rg is left (still not on PATH here), got {s['linux_fixes']['items']}",
                      [i["id"] for i in s["linux_fixes"]["items"]] == ["ripgrep"])
            S.platform_name = lambda: "win32"
            S.forget_linux()
            calls.clear()
            status, s = e.call("POST", "setup/linux-fixes")
            ctx.check(f"on Windows: 200, nothing to fix, nothing run, got {status} {s.get('lines')} {calls}", status == 200
                      and s["lines"] == ["nothing to fix on this box"] and calls == [] and s["linux_fixes"] == {"needed": False, "items": [], "platform": "win32"})
    finally:
        S.platform_name, S.rg_on_path, LF.install_static_ripgrep, LF.ensure_local_bin_on_rc, LF.local_bin_on_noninteractive_path = saved
        S.forget_linux()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
