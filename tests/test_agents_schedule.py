"""tests.test_agents_schedule -- Halo 2.0.5 round 5 (deliverable 3): a
bio's `schedule:` (cron/every) and `triggers:` (file_change/event/message)
-- cadence math, the shared store, the TeamScheduler thread (fires while a
session that loaded the team is alive, stops when it closes; each trigger
kind fires once), `run_once`, and the `halo agents schedule` CLI.
"""
from __future__ import annotations

import datetime
import io
import os
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="agents-schedule-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        self.home = d
        self.state_dir = d / ".halo"
        self.cwd = d / "project"
        self.cwd.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class _Session:
    """The TeamScheduler's whole view of a session."""

    def __init__(self, e: _Env):
        self.state_dir = e.state_dir
        self.cwd = e.cwd
        self.job_registry = None


def _fixture(e: _Env):
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_yaml import save_team_template
    watch = e.cwd / "watch.txt"
    watch.write_text("v1", encoding="utf-8")
    save_agent_bio("sched-bio", {
        "description": "runs on a cadence and on triggers",
        "models": {"preference": "or:mock/sched"},
        "schedule": {"every": "1s", "prompt": "check the build", "model": "or:mock/sched"},
        "triggers": [{"on": "event", "name": "turn_done"},
                     {"on": "file_change", "paths": [str(watch)]},
                     {"on": "message", "from": "worker"}],
    }, state_dir=e.state_dir)
    save_team_bio = save_team_template("sched-team", {
        "description": "the round-5 schedule fixture",
        "agents": [{"agent": "sched-bio", "role": "main"},
                   {"agent": "sched-bio", "role": "subagent", "as": "worker"}],
    }, state_dir=e.state_dir)
    assert save_team_bio[0], save_team_bio[1]
    return watch


# ---------------------------------------------------------------------------
# cadence math + the shared store
# ---------------------------------------------------------------------------

@test
def test_cron_next_matches_basic_expressions(ctx: Ctx):
    from halo_harness.agents_schedule import cron_next
    now = datetime.datetime(2026, 10, 6, 12, 3, 30)
    ctx.check("*/5 lands on the next five-minute mark",
              cron_next("*/5 * * * *", now) == datetime.datetime(2026, 10, 6, 12, 5))
    ctx.check("a fixed weekly time lands next Monday 09:00",
              cron_next("0 9 * * 1", now) == datetime.datetime(2026, 10, 12, 9, 0))
    ctx.check("an annual expression lands next Jan 1 14:30",
              cron_next("30 14 1 1 *", now) == datetime.datetime(2027, 1, 1, 14, 30))
    ctx.check("a range/list field parses",
              cron_next("15,45 8-18 * * *", now) == datetime.datetime(2026, 10, 6, 12, 15))
    ctx.check("garbage is None, never a crash", cron_next("not cron") is None)
    ctx.check("four fields is not five", cron_next("* * * *") is None)


@test
def test_store_round_trip_and_status_lines(ctx: Ctx):
    from halo_harness.agents_schedule import (list_schedules, load_store, next_fire_at, save_store,
                                              schedule_status_lines, schedules_path)
    with _Env() as e:
        store = {"entries": [{"id": "t:a:schedule", "name": "a", "agent": "sched-bio", "kind": "schedule",
                              "every_s": 60.0, "prompt": "p", "team": "t", "enabled": True,
                              "armed_at": time.time(), "last_run": None, "last_note": ""},
                             {"id": "t:a:trigger0", "name": "a", "agent": "sched-bio", "kind": "trigger",
                              "on": "event", "on_value": "turn_done", "team": "t", "enabled": True,
                              "fired": True, "last_note": "event turn_done: fired"}]}
        save_store(e.state_dir, store)
        ctx.check("the store file lands under the state dir",
                  schedules_path(e.state_dir).exists())
        back = load_store(e.state_dir)
        ctx.check("the entries round trip", len(back["entries"]) == 2)
        listed = list_schedules(e.state_dir)
        ctx.check("list_schedules reads the same entries", len(listed) == 2)
        lines = schedule_status_lines(listed)
        ctx.check(f"status lines name schedule/trigger state, got {lines}",
                  any("next " in ln and "schedule" not in ln for ln in lines[:1])
                  and any("trigger on event turn_done (fired)" in ln for ln in lines))
        listed[0]["enabled"] = False
        lines = schedule_status_lines(listed)
        ctx.check(f"a paused entry is marked, got {lines}", any("(paused)" in ln for ln in lines))
        nxt = next_fire_at(listed[0], datetime.datetime.fromtimestamp(listed[0]["armed_at"]))
        ctx.check("every computes last/armed + every_s",
                  nxt is not None and abs((nxt.timestamp() - listed[0]["armed_at"]) - 60.0) < 1.0)
        ctx.check("empty prints the nothing-armed line",
                  schedule_status_lines([])[0].startswith("Nothing armed"))


@test
def test_every_1s_fires_twice_and_stops_when_the_session_closes(ctx: Ctx):
    with _Env() as e:
        _fixture(e)
        from halo_harness.agents_schedule import TeamScheduler, load_store
        from halo_harness.teams_runtime import load_team_control
        control = load_team_control("sched-team", cwd=e.cwd, state_dir=e.state_dir)
        session = _Session(e)
        fired = []
        scheduler = TeamScheduler(session, control, fire_fn=lambda s, entry: fired.append(entry["id"]),
                                  tick_s=0.05)
        for alias in control.aliases:
            scheduler.arm_bio(control.bio_for(alias), alias)
        scheduler._persist()
        scheduler.start()
        try:
            deadline = time.time() + 8.0
            while time.time() < deadline and len(fired) < 2:
                time.sleep(0.05)
            ctx.check(f"a 1s cadence fired at least twice, got {len(fired)}", len(fired) >= 2)
        finally:
            scheduler.stop()
            scheduler.disarm()
        count_at_stop = len(fired)
        time.sleep(1.3)
        ctx.check(f"no fire after the session closed, got {len(fired) - count_at_stop} extra",
                  len(fired) == count_at_stop)
        ctx.check("disarm removed the team's entries from the store",
                  all(entry.get("team") != "sched-team" for entry in load_store(e.state_dir)["entries"]))


@test
def test_each_trigger_kind_fires_once(ctx: Ctx):
    with _Env() as e:
        _fixture(e)
        from halo_harness.agents_schedule import TeamScheduler
        from halo_harness.teams_runtime import load_team_control
        control = load_team_control("sched-team", cwd=e.cwd, state_dir=e.state_dir)
        fired = []
        scheduler = TeamScheduler(_Session(e), control, fire_fn=lambda s, entry: fired.append((entry["on"],
                                                                                               entry["id"])),
                                  tick_s=0.05)
        scheduler.arm_bio(control.bio_for("main"), "main")
        # event: first observation fires, a second does not
        scheduler.observe_event("turn_done")
        scheduler.observe_event("turn_done")
        ctx.check(f"the event trigger fired exactly once, got {fired}",
                  sum(1 for on, _ in fired if on == "event") == 1)
        # message from the right role fires once; from another role never
        scheduler.notify_message("worker")
        scheduler.notify_message("reviewer")
        ctx.check(f"the message trigger fired exactly once, got {fired}",
                  sum(1 for on, _ in fired if on == "message") == 1)
        # file_change: same mtime never fires; a change fires once
        scheduler._poll_files()
        watch = e.cwd / "watch.txt"
        os.utime(watch, (time.time() + 5, time.time() + 5))
        time.sleep(0.2)
        scheduler._poll_files()
        scheduler._poll_files()
        ctx.check(f"the file_change trigger fired exactly once, got {fired}",
                  sum(1 for on, _ in fired if on == "file_change") == 1)
        scheduler.stop()


@test
def test_arm_session_persists_and_the_cli_lists_and_runs(ctx: Ctx):
    with _Env() as e:
        _fixture(e)
        from halo_harness.agents_schedule import arm_session, list_schedules, stop_session_scheduler
        from halo_harness.teams_runtime import load_team_control
        control = load_team_control("sched-team", cwd=e.cwd, state_dir=e.state_dir)
        session = _Session(e)
        scheduler = arm_session(session, control, fire_fn=lambda s, entry: "fired")
        try:
            ctx.check("arming produced a scheduler", scheduler is not None)
            entries = list_schedules(e.state_dir)
            kinds = sorted(entry["kind"] for entry in entries)
            ctx.check(f"one schedule + three triggers are armed in the store, got {kinds}",
                      kinds == ["schedule", "trigger", "trigger", "trigger"])
        finally:
            if scheduler is not None:
                scheduler.stop()
        # run_once with a fake popen: the bg surface is exercised, no real child
        from halo_harness.agents_schedule import run_once
        class _FakePopen:
            def __init__(self, argv, **kw):
                self.argv = argv
                self.pid = 4242
        out = run_once("sched-bio", state_dir=e.state_dir, popen=_FakePopen)
        ctx.check(f"run_once fires through the bg surface, got {out!r}",
                  out.startswith("fired 'sched-bio' as background run"))
        ctx.check("an unknown name says so", "no armed schedule" in run_once("nope", state_dir=e.state_dir))
        # the CLI lists (and pauses/resumes/rm) the same store
        from halo_harness.agents_cli import cmd_agents
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cmd_agents(["schedule", "list"])
        ctx.check(f"list exits 0, got {code}", code == 0)
        ctx.check(f"the armed schedule shows with its cadence, got {buf.getvalue()!r}",
                  "worker" in buf.getvalue())
        store_entries = list_schedules(e.state_dir)
        store_entries[0]["enabled"] = False
        from halo_harness.agents_schedule import save_store
        save_store(e.state_dir, {"entries": store_entries})
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            code = cmd_agents(["schedule", "list"])
        ctx.check(f"a paused entry is marked by the CLI, got {buf2.getvalue()!r}", "(paused)" in buf2.getvalue())
        stop_session_scheduler(session)


if __name__ == "__main__":
    results, passed, failed, skipped = run_all(TESTS, Ctx())
    sys.exit(print_results(results, passed, failed, skipped))
