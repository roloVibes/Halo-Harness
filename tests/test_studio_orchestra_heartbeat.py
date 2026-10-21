"""tests.test_studio_orchestra_heartbeat -- Halo 3.1.8.0 R1: Studio reads the
cross-process runner heartbeat (supervise/heartbeat.py). A run another process
drives (a live `<run>/runner.json` from a child process, pid and start token
real) reads `running` in the run list, `POST orchestra/run` answers 409 naming
it, and approving its plan while it is not waiting is a 409; once the child is
gone the same run reads `interrupted` again. No model is called; the child is a
plain `python -c` sleep against the scoped home.

Run: python -m tests.test_studio_orchestra_heartbeat
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers import orchestra_studio_rig as R  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
GOAL = {"what": "Write the five functions of basket.py", "done_when": "the tests pass", "stop_when": "two returns",
        "workers": 5, "files": ["basket.py"]}


def _started(run_dir: Path) -> None:
    """Make the run look started and unfinished (its lead step running, no report)."""
    from halo_harness.orchestra import jsonl
    graph = jsonl.read_json(run_dir / "workflow.json", {})
    for s in graph.get("steps") or []:
        s["state"] = "running" if s.get("id") == "lead" else ("done" if s.get("id") == "goal" else "pending")
    jsonl.write_json(run_dir / "workflow.json", graph)


def _beat_from(child, run_dir: Path) -> None:
    from halo_harness.orchestra import jsonl
    from halo_harness.remote import proc_ident
    jsonl.write_json(run_dir / "runner.json", {"pid": child.pid, "pstart": proc_ident.start_token(child.pid),
                                               "beat": round(time.time(), 3), "by": "supervise"})


@test
def test_a_run_driven_elsewhere_is_running_and_refuses_a_second_runner(ctx: Ctx):
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("orch-hb-")
    run_dir = F.make_run(repo)
    _started(run_dir)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(0.3)
        _beat_from(child, run_dir)
        with R.Studio(repo) as s:
            st, rows = s.get("orchestra/runs")
            row = next((r for r in rows if r["run_id"] == run_dir.name), {})
            ctx.check(f"a run another process drives reads running, got {row.get('state')}", row.get("state") == "running")
            st, body = s.post("orchestra/run", dict(GOAL, test=f"{F.PY} -m unittest -q test_basket"))
            ctx.check(f"POST run is a 409 naming the run, got {st} {body}",
                      st == 409 and body.get("run_id") == run_dir.name and "elsewhere" in body.get("error", ""))
            # its goal reviews its plan, and a split exists, but it is not waiting: approve is a 409
            from halo_harness.orchestra import jsonl
            goal = jsonl.read_json(run_dir / "goal.json", {})
            jsonl.write_json(run_dir / "goal.json", dict(goal, plan="review"))
            jsonl.write_json(run_dir / "split.json", {"base": "", "lead_cost_usd": 0.0, "lead_sessions": [],
                                                      "jobs": [{"id": "job-1", "title": "write add_item",
                                                                "claims": ["basket.py#add_item"], "worker": 1}]})
            st, body = s.post(f"orchestra/{run_dir.name}/approve", {})
            ctx.check(f"approving a plan it is not waiting on is a 409, got {st} {body}",
                      st == 409 and "elsewhere" in body.get("error", ""))
    finally:
        child.kill()
        child.wait(10)
    with R.Studio(repo) as s:
        st, rows = s.get("orchestra/runs")
        row = next((r for r in rows if r["run_id"] == run_dir.name), {})
        ctx.check(f"with the runner gone the run is interrupted again, got {row.get('state')}", row.get("state") == "interrupted")
    R.cleanup(repo)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
