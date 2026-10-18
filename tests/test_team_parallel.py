"""tests.test_team_parallel -- Halo 3.1.2.0 round R2: the members of one agent
stage run at the same time (halo_harness/team/parallel.py, run_stage.py),
through tests/helpers/team_rig.py's fakes whose spawn blocks on an event:
three members all running at once (the row's `members_state` and the
`team` frame carry each one's state); a lineup tier's `max_parallel: 2`
keeps the third `ready` until one finishes; one failing member fails the
stage after the others end (the lead does not run); the serial path is
gone: every member runs on the stage's pool. No model is called.

Run: python -m tests.test_team_parallel
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers import team_rig as R  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

TEAM = """\
name: crew
brief: docs/BRIEF.md
members:
  - {name: a, lineup: LINEUP, role: coder}
  - {name: b, lineup: LINEUP, role: reviewer}
  - {name: c, lineup: LINEUP, role: tester}
  - {name: boss, lineup: LINEUP, role: main}
blocks:
  - {id: copy, kind: folder, path: content/, claims: section}
workflow:
  stages:
    - {id: work, kind: agent, members: [a, b, c, boss], lead: boss, reads: [brief], writes: [copy], trigger: manual}
"""
TIERED = """\
name: tiered
roles: {main: default-model, coder: default-model, reviewer: default-model, tester: default-model}
tiers:
  - {name: lead, members: [main]}
  - {name: workers, members: [coder, reviewer, tester], max_parallel: 2}
"""


class Held(R.Fakes):
    """Fakes whose workers block until their event is set; records who runs at once and on which thread."""

    def __init__(self, fail=()):
        super().__init__(fail=fail)
        self.events = {m: threading.Event() for m in ("a", "b", "c")}
        self.inside: set = set()
        self.peak = 0
        self.threads: dict = {}
        self.lock = threading.Lock()

    def spawn(self, member, prompt, *, cwd, env, stage, run_dir):
        name = member["name"]
        with self.lock:
            self.calls.append(("spawn", name, stage, prompt))
            self.threads[name] = threading.current_thread().name
            self.inside.add(name)
            self.peak = max(self.peak, len(self.inside))
        if name in self.fail:
            with self.lock:
                self.inside.discard(name)
            return {"ok": False, "error": f"{name} broke"}
        if name in self.events:
            self.events[name].wait(20)
        with self.lock:
            self.inside.discard(name)
        return {"ok": True, "text": f"{name}'s part", "cost_usd": 0.01, "session_id": f"s-{name}"}


def _runner(lineup: str, fakes):
    from halo_harness.team import spec as S
    from halo_harness.team.run import TeamRunner, open_run
    root, state = R.repo(TEAM.replace("LINEUP", lineup))
    if lineup == "tiered":
        (root / ".halo" / "teams").mkdir(parents=True, exist_ok=True)
        (root / ".halo" / "teams" / "tiered.yaml").write_text(TIERED, encoding="utf-8")
    team = S.load_team(root, state)
    run_dir = open_run(team, cwd=root, state_dir=state)
    return TeamRunner(team, run_dir, cwd=root, state_dir=state, **fakes.seams())


def _wait(fn, timeout: float = 15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.02)
    return fn()


def _tick(runner) -> threading.Thread:
    t = threading.Thread(target=runner.tick, daemon=True)
    t.start()
    return t


def _members(runner) -> dict:
    return dict(runner.row("work").get("members_state") or {})


@test
def test_three_members_run_at_once_and_the_lead_merges_after(ctx: Ctx):
    from halo_harness.studio.team_live import frame_of
    from halo_harness.team.board import read_events
    fakes = Held()
    runner = _runner("standard", fakes)
    runner.request("work")
    t = _tick(runner)
    ctx.check("all three are inside their spawn at once", _wait(lambda: len(fakes.inside) == 3))
    ctx.check(f"the row: the three running, the lead pending, the stage running, got {_members(runner)}",
              _members(runner) == {"a": "running", "b": "running", "c": "running", "boss": "pending"}
              and runner.row("work")["state"] == "running")
    line = next(e for e in reversed(read_events(runner.run_dir)) if (e.get("data") or {}).get("member"))
    frame = frame_of(runner.run_dir, line)
    ctx.check(f"a member's move is a `state` line whose team frame carries the row, got {frame and frame['data'].get('row', {}).get('members_state')}",
              frame is not None and frame["data"]["action"] == "stage"
              and frame["data"]["row"]["members_state"]["a"] == "running")
    for e in fakes.events.values():
        e.set()
    t.join(20)
    row = runner.row("work")
    ctx.check(f"the stage is done when all are, got {row['state']} {row.get('members_state')}", row["state"] == "done"
              and row["members_state"] == {"a": "done", "b": "done", "c": "done", "boss": "done"})
    order = [c[1] for c in fakes.calls if c[0] == "spawn"]
    lead = next(c[3] for c in fakes.calls if c[0] == "spawn" and c[1] == "boss")
    ctx.check(f"the lead ran last with the three hand-backs, got {order}", order[-1] == "boss" and fakes.peak == 3
              and all(f"{m}'s part" in lead for m in ("a", "b", "c")) and "YOU LEAD THIS STAGE" in lead)
    moves = [(e["data"]["member"], e["data"]["was"], e["data"]["member_state"]) for e in read_events(runner.run_dir)
             if (e.get("data") or {}).get("member")]
    ctx.check(f"each member moved ready -> running -> done on its own, got {moves}",
              all((m, "ready", "running") in moves and (m, "running", "done") in moves for m in ("a", "b", "c"))
              and ("boss", "pending", "running") in moves)


@test
def test_max_parallel_two_keeps_the_third_ready_until_one_finishes(ctx: Ctx):
    fakes = Held()
    runner = _runner("tiered", fakes)
    from halo_harness.team.parallel import limit
    ctx.check("the tier's max_parallel is the stage's cap", limit(runner.team, ["a", "b", "c"], cwd=runner.root) == 2
              and limit(runner.team, ["boss"], cwd=runner.root) == 1)
    runner.request("work")
    t = _tick(runner)
    ctx.check("two are inside", _wait(lambda: len(fakes.inside) == 2))
    time.sleep(0.3)
    first = sorted(fakes.inside)
    third = next(m for m in ("a", "b", "c") if m not in first)
    ctx.check(f"the third waits ready, got {_members(runner)}", len(fakes.inside) == 2
              and _members(runner)[third] == "ready" and all(_members(runner)[m] == "running" for m in first))
    fakes.events[first[0]].set()
    ctx.check("one finished: the third starts", _wait(lambda: third in fakes.inside or _members(runner).get(third) != "ready"))
    ctx.check(f"never more than two at once, got {fakes.peak}", fakes.peak == 2 and _members(runner)[first[0]] == "done")
    for e in fakes.events.values():
        e.set()
    t.join(20)
    ctx.check(f"then the stage is done, got {runner.row('work')['state']}", runner.row("work")["state"] == "done")


@test
def test_one_failing_member_fails_the_stage_after_the_others_end(ctx: Ctx):
    fakes = Held(fail=("b",))
    runner = _runner("standard", fakes)
    runner.request("work")
    t = _tick(runner)
    ctx.check("b failed while a and c still run", _wait(lambda: _members(runner).get("b") == "failed"
                                                        and len(fakes.inside) == 2))
    ctx.check(f"the stage still runs, got {runner.row('work')['state']}", runner.row("work")["state"] == "running"
              and _members(runner)["a"] == "running" and _members(runner)["c"] == "running")
    for e in fakes.events.values():
        e.set()
    t.join(20)
    row = runner.row("work")
    ctx.check(f"failed once the others ended, naming b, got {row['state']} {row['error']!r} {row.get('members_state')}",
              row["state"] == "failed" and "b: b broke" in row["error"] and row["members_state"]["a"] == "done"
              and row["members_state"]["c"] == "done" and row["members_state"]["boss"] == "skipped")
    ctx.check("the lead did not run", not any(c[0] == "spawn" and c[1] == "boss" for c in fakes.calls))


@test
def test_the_serial_path_is_gone(ctx: Ctx):
    import inspect
    from halo_harness.team import parallel, run_stage
    fakes = Held()
    for e in fakes.events.values():
        e.set()
    runner = _runner("standard", fakes)
    runner.request("work")
    runner.tick()
    ctx.check(f"every member, the lead too, ran on the stage's pool, got {fakes.threads}",
              len(fakes.threads) == 4 and all(n.startswith("team-work") for n in fakes.threads.values()))
    src = inspect.getsource(run_stage)
    ctx.check("run_stage calls spawn only in the launch it hands the pool, and runs no member loop of its own",
              src.count("runner.spawn(") == 1 and "return lambda: runner.spawn(" in src
              and 'for name in live["order"]' not in src)
    ctx.check("the pool is parallel.run_members", "ThreadPoolExecutor" in inspect.getsource(parallel.run_members))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="team parallel tests"))
