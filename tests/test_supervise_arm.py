"""tests.test_supervise_arm -- Halo 3.1.8.0 R1: the supervisor arms the
lineups' schedules and triggers (supervise/arm.py), the store entries carry
`owner: supervisor`, a fire is a background run that is idempotent (a due fire
while the previous one runs is skipped), the feed observes `on: event` /
`on: message`, and the double-fire guard (agents_schedule.supervisor_owns, and
a session's `_arm_team_scheduler_once` skipping a team the supervisor owns). No
model is called.

Run: python -m tests.test_supervise_arm
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="supervise-arm-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        self.state_dir = d / ".halo"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.cwd = d / "project"
        self.cwd.mkdir()
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _lineup(e: _Env):
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_yaml import save_team_template
    watch = e.cwd / "watch.txt"
    watch.write_text("v1", encoding="utf-8")
    save_agent_bio("sup-bio", {
        "description": "runs on a cadence and on triggers",
        "models": {"preference": "or:mock/sup"},
        "schedule": {"every": "1s", "prompt": "check the build"},
        "triggers": [{"on": "event", "name": "turn_done"}, {"on": "message", "from": "worker"}],
    }, state_dir=e.state_dir)
    ok = save_team_template("sup-team", {
        "description": "the supervisor arming fixture",
        "agents": [{"agent": "sup-bio", "role": "main"},
                   {"agent": "sup-bio", "role": "subagent", "as": "worker"}],
    }, state_dir=e.state_dir)
    assert ok[0], ok[1]


class _FakePopen:
    instances = 0

    def __init__(self, argv, **kw):
        _FakePopen.instances += 1
        self.pid = os.getpid()  # a live pid, so is_our_process reports the fire still runs (idempotency)


@test
def test_armer_arms_a_lineup_and_marks_it_supervisor(ctx: Ctx):
    with _Env() as e:
        _lineup(e)
        from halo_harness.agents_schedule import list_schedules
        from halo_harness.supervise.arm import Armer
        fired = []
        armer = Armer(e.state_dir, fire_fn=lambda s, entry: fired.append(entry["id"]) or "fired", tick_s=0.05)
        named = armer.scan([e.cwd], force=True)
        ctx.check(f"it armed the team, got {named}", "sup-team" in named)
        entries = [en for en in list_schedules(e.state_dir) if en.get("team") == "sup-team"]
        ctx.check("every entry is marked owner supervisor", entries and all(en.get("owner") == "supervisor" for en in entries))
        kinds = sorted(en["kind"] for en in entries)
        ctx.check(f"one schedule + two triggers armed, got {kinds}", kinds == ["schedule", "trigger", "trigger"])
        # it fires on its cadence
        deadline = time.time() + 6.0
        while time.time() < deadline and not fired:
            time.sleep(0.05)
        ctx.check(f"the 1s cadence fired, got {len(fired)}", len(fired) >= 1)
        armer.stop()
        ctx.check("stop disarms the supervisor's entries",
                  not [en for en in list_schedules(e.state_dir) if en.get("team") == "sup-team"])


@test
def test_a_fire_is_a_bg_run_and_idempotent(ctx: Ctx):
    with _Env() as e:
        _lineup(e)
        from halo_harness.supervise.arm import BgJobs, Supervised, fire
        _FakePopen.instances = 0
        session = Supervised(e.state_dir, e.cwd, {}, BgJobs(_FakePopen))
        entry = {"name": "sup-bio", "agent": "sup-bio", "team": "sup-team", "prompt": "go", "kind": "schedule"}
        note1 = fire(session, entry)
        ctx.check(f"the first fire starts a bg run, got {note1!r}", "background run" in note1 and entry.get("running_bg"))
        note2 = fire(session, entry)
        ctx.check(f"a fire while the previous bg run is alive is skipped, got {note2!r}", note2.startswith("skipped:"))
        ctx.check("only one process was started", _FakePopen.instances == 1)


@test
def test_the_double_fire_guard(ctx: Ctx):
    with _Env() as e:
        _lineup(e)
        from halo_harness.agents_schedule import armed_by_live_session, supervisor_owns
        from halo_harness.supervise.arm import Armer
        from halo_harness.supervise.pulse import Pulse
        Pulse(e.state_dir).write("running", {})
        armer = Armer(e.state_dir, fire_fn=lambda s, en: "fired", tick_s=0.05)
        armer.scan([e.cwd], force=True)
        try:
            ctx.check("supervisor_owns is true while the pulse is live", supervisor_owns("sup-team", e.state_dir))
            ctx.check("armed_by_live_session is false (the supervisor is not a plain session)",
                      not armed_by_live_session("sup-team", e.state_dir))
        finally:
            armer.stop()
        ctx.check("supervisor_owns is false once disarmed", not supervisor_owns("sup-team", e.state_dir))


@test
def test_a_session_skips_a_team_the_supervisor_owns(ctx: Ctx):
    with _Env() as e:
        _lineup(e)
        from halo_harness.supervise.arm import Armer
        from halo_harness.supervise.pulse import Pulse
        from halo_harness.teams_runtime import load_team_control
        Pulse(e.state_dir).write("running", {})
        armer = Armer(e.state_dir, fire_fn=lambda s, en: "fired", tick_s=0.05)
        armer.scan([e.cwd], force=True)

        class _Loop:  # the bits agent/loop._arm_team_scheduler_once reads
            agent_depth = 0
            state_dir = e.state_dir
            def __init__(self):
                self.team_control = load_team_control("sup-team", cwd=e.cwd, state_dir=e.state_dir)
                self._team_scheduler = None
            _arm_team_scheduler_once = _import_arm_once()
        try:
            loop = _Loop()
            loop._arm_team_scheduler_once()
            ctx.check("the session did not arm its own scheduler (the supervisor owns the team)",
                      loop._team_scheduler is None)
        finally:
            armer.stop()


@test
def test_feed_observes_event_and_message(ctx: Ctx):
    with _Env() as e:
        _lineup(e)
        from halo_harness.supervise.arm import Armer
        fired = []
        armer = Armer(e.state_dir, fire_fn=lambda s, en: fired.append((en.get("on"), en["id"])) or "fired", tick_s=0.05)
        armer.scan([e.cwd], force=True)
        try:
            armer.feed({"event": "turn_done", "session_id": "s1"}, lambda sid: str(e.cwd))
            armer.feed({"event": "subagent_end", "session_id": "s1", "data": {"name": "worker"}}, lambda sid: str(e.cwd))
            ctx.check(f"the event trigger fired once, got {fired}", sum(1 for on, _ in fired if on == "event") == 1)
            ctx.check(f"the message trigger fired once, got {fired}", sum(1 for on, _ in fired if on == "message") == 1)
        finally:
            armer.stop()


def _import_arm_once():
    from halo_harness.agent.loop import Session
    return Session._arm_team_scheduler_once


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
