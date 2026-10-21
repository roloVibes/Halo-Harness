"""tests.test_supervise_queue -- Halo 3.1.8.0 R1: the supervisor's goal queue
(supervise/queue.py), its history (supervise/history.py), the `halo goal` CLI
(supervise/goal_cli.py), the config section (supervise/settings.py) and the
`halo work` goal adapter (work/adapters/goal.py). No model is called.

Run: python -m tests.test_supervise_queue
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="supervise-queue-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        self.state_dir = d / ".halo"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.repo = d / "repo"
        self.repo.mkdir()
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@test
def test_add_states_history_and_counts(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise import history, queue
        g = queue.add(e.state_dir, "write it", repo=str(e.repo), budget_usd=2.0, lineup="halo-dev-cycle", kind="orchestra")
        ctx.check("queued with an id and defaults", g["state"] == "queued" and g["id"].startswith("g-")
                  and g["kind"] == "orchestra" and g["budget_usd"] == 2.0 and g["held"] is False)
        ctx.check("a blank what is rejected", _raises(lambda: queue.add(e.state_dir, "  ", repo=str(e.repo))))
        ctx.check("a bad --as is rejected", _raises(lambda: queue.add(e.state_dir, "x", repo=str(e.repo), kind="nope")))
        queue.set_state(e.state_dir, g["id"], "running", "started", run_dir=str(e.repo / "run"))
        queue.set_state(e.state_dir, g["id"], "done", "finished", cost_usd=0.75)
        got = queue.load(e.state_dir, g["id"])
        ctx.check("done carries cost and ended", got["state"] == "done" and got["cost_usd"] == 0.75 and got["ended"])
        lines = [(r.get("from"), r.get("to")) for r in history.read(e.state_dir, g["id"])]
        ctx.check(f"history has the three moves, got {lines}",
                  lines == [("", "queued"), ("queued", "running"), ("running", "done")])
        ctx.check("counts put done in done", queue.counts(e.state_dir)["done"] == 1)
        s = history.summary(e.state_dir)
        ctx.check(f"summary: one done, no waiting, the cost, got {s}", s["done"] == 1 and s["waiting"] == 0 and s["cost_usd"] == 0.75)


@test
def test_resolve_prefix_and_remove(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise import queue
        g = queue.add(e.state_dir, "a", repo=str(e.repo))
        ctx.check("resolve by full id", queue.resolve(e.state_dir, g["id"])["id"] == g["id"])
        ctx.check("resolve by prefix", queue.resolve(e.state_dir, g["id"][:4])["id"] == g["id"])
        ctx.check("an unknown ref is None", queue.resolve(e.state_dir, "g-zzzzzz") is None)
        ctx.check("remove drops it", queue.remove(e.state_dir, g["id"]) and queue.load(e.state_dir, g["id"]) is None)


@test
def test_goal_cli_add_list_show_and_verbs(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise import queue
        from halo_harness.supervise.goal_cli import cmd_goal
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_goal(["add", "ship the notes", "--repo", str(e.repo), "--budget", "1.5", "--as", "job"])
        ctx.check(f"add exits 0 and names the goal, got {buf.getvalue()!r}", rc == 0 and "queued g-" in buf.getvalue())
        g = queue.all_goals(e.state_dir)[0]
        out = io.StringIO()
        with redirect_stdout(out):
            cmd_goal(["list"])
        ctx.check("list shows the goal and the job kind", g["id"] in out.getvalue() and "[job]" in out.getvalue())
        show = io.StringIO()
        with redirect_stdout(show):
            cmd_goal(["show", g["id"]])
        ctx.check("show prints what and the budget", "ship the notes" in show.getvalue() and "$1.5" in show.getvalue())
        with redirect_stdout(io.StringIO()):
            cmd_goal(["hold", g["id"]])
        ctx.check("hold sets held", queue.load(e.state_dir, g["id"])["held"] is True)
        with redirect_stdout(io.StringIO()):
            cmd_goal(["release", g["id"]])
        ctx.check("release clears held", queue.load(e.state_dir, g["id"])["held"] is False)
        with redirect_stdout(io.StringIO()):
            cmd_goal(["rm", g["id"]])
        ctx.check("rm drops it", queue.load(e.state_dir, g["id"]) is None)
        ctx.check("rm on a missing goal exits 1", cmd_goal(["rm", "g-nope"]) == 1)


@test
def test_cancel_and_resume_a_running_goal(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise import queue
        from halo_harness.supervise.goal_cli import cmd_goal
        g = queue.add(e.state_dir, "x", repo=str(e.repo), kind="orchestra")
        rd = e.repo / ".halo" / "orchestra" / "run1"
        rd.mkdir(parents=True)
        (rd / "run.json").write_text(json.dumps({"run_id": "run1", "repo_root": str(e.repo)}), encoding="utf-8")
        queue.set_state(e.state_dir, g["id"], "running", "started", run_dir=str(rd))
        with redirect_stdout(io.StringIO()):
            cmd_goal(["cancel", g["id"]])
        got = queue.load(e.state_dir, g["id"])
        ctx.check("cancel stops it, why cancelled", got["state"] == "stopped" and got["why"] == "cancelled"
                  and (got.get("failure") or {}).get("kind") == "cancelled")
        ctx.check("the run got a stop.json", (rd / "stop.json").is_file())
        with redirect_stdout(io.StringIO()):
            cmd_goal(["resume", g["id"]])
        ctx.check("resume re-queues it", queue.load(e.state_dir, g["id"])["state"] == "queued")


@test
def test_pause_a_running_goal_requeues_it(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise import queue
        from halo_harness.supervise.goal_cli import cmd_goal
        g = queue.add(e.state_dir, "x", repo=str(e.repo), kind="orchestra")
        rd = e.repo / ".halo" / "orchestra" / "run2"
        rd.mkdir(parents=True)
        (rd / "run.json").write_text(json.dumps({"run_id": "run2", "repo_root": str(e.repo)}), encoding="utf-8")
        queue.set_state(e.state_dir, g["id"], "running", "started", run_dir=str(rd))
        with redirect_stdout(io.StringIO()):
            cmd_goal(["pause", g["id"]])
        got = queue.load(e.state_dir, g["id"])
        ctx.check("pause re-queues and holds it", got["state"] == "queued" and got["held"] is True and got["why"] == "paused")
        ctx.check("the paused run got a stop.json", (rd / "stop.json").is_file())


@test
def test_config_section_defaults_and_values(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise.settings import settings
        cfg = settings(e.state_dir)
        ctx.check(f"defaults, got {cfg}", cfg["tick_s"] == 5.0 and cfg["max_running"] == 1 and cfg["asks"] == "park"
                  and cfg["retries"] == 1 and cfg["max_minutes"] == 0 and cfg["budget_usd"] is None)
        (e.state_dir / "config.json").write_text(json.dumps(
            {"supervise": {"tick_s": 2, "max_running": 3, "asks": "deny", "budget_usd": 5, "retries": 2,
                           "max_minutes": 30, "replan": "auto"}}), encoding="utf-8")
        cfg = settings(e.state_dir)
        ctx.check(f"values read back, got {cfg}", cfg["tick_s"] == 2.0 and cfg["max_running"] == 3 and cfg["asks"] == "deny"
                  and cfg["budget_usd"] == 5.0 and cfg["retries"] == 2 and cfg["max_minutes"] == 30 and cfg["replan"] == "auto")
        (e.state_dir / "config.json").write_text(json.dumps({"supervise": {"asks": "wat", "max_running": 0}}), encoding="utf-8")
        cfg = settings(e.state_dir)
        ctx.check("a bad value takes the default", cfg["asks"] == "park" and cfg["max_running"] == 1)


@test
def test_config_section_is_a_known_key(ctx: Ctx):
    from halo_harness.schemas.config_json import known_keys
    ctx.check("supervise is a known config section", "supervise" in known_keys())


@test
def test_work_lists_goals_as_a_unit_kind(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise import queue
        from halo_harness.work.store import UnitStore, run_kind
        g1 = queue.add(e.state_dir, "first", repo=str(e.repo))
        g2 = queue.add(e.state_dir, "second", repo=str(e.repo), kind="job")
        queue.set_state(e.state_dir, g2["id"], "running", "started", bg_id="bg1")
        folder = queue.root(e.state_dir)
        ctx.check("the supervise folder reads as a goal run", run_kind(folder) == "supervise")
        store = UnitStore(folder)
        rows = {u.id: u for u in store.units()}
        ctx.check(f"both goals are units, got {sorted(rows)}", set(rows) == {g1["id"], g2["id"]})
        ctx.check("a queued goal is ready, a running one is running",
                  rows[g1["id"]].state == "ready" and rows[g2["id"]].state == "running")
        ctx.check("the report rows carry the kind goal", all(r["kind"] == "goal" for r in store.rows()))


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except ValueError:
        return True


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
