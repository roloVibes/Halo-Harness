"""tests.test_ci_summary_survives -- 3.6.0.0 test rig: a suites shard whose run timed out before it printed a
RESULT line still gets its job summary and still uploads its logs.

On the candidate's run two macOS shards left no logs at all: the "Job summary" step runs under GitHub's
`bash -eo pipefail`, its `line=$(grep ... | tail | tr)` failed when grep matched nothing, the step failed, and the
"Upload logs on failure" step (an `if:` with no status function, so an implied success()) was skipped. These tests run
each job's real summary script under the same shell options with a log that has no RESULT line, and read each upload
step's condition.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "suites.yml"


def _jobs():
    import yaml
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def _bash():
    """A POSIX bash: on Windows Git's own (System32\\bash.exe is WSL's, which cannot read Windows paths)."""
    if os.name == "nt":
        git = shutil.which("git")
        for cand in ([Path(git).resolve().parent.parent / "bin" / "bash.exe",
                      Path(git).resolve().parent.parent.parent / "bin" / "bash.exe"] if git else []):
            if cand.is_file():
                return str(cand)
        return None
    return shutil.which("bash")


def _fill(script: str) -> str:
    """The step's script as the runner hands it to bash: the run_all step failed (a timeout), the other two skipped."""
    values = {"matrix.os": "macos", "matrix.shard": "1", "github.event_name": "push", "github.sha": "0" * 40,
              "steps.bridge.outcome": "skipped", "steps.run_all.outcome": "failure",
              "steps.tui.outcome": "skipped"}

    def sub(m):
        return values.get(m.group(1).strip(), "")
    return re.sub(r"\$\{\{([^}]*)\}\}", sub, script)


@test
def test_a_shard_with_no_result_line_still_writes_its_job_summary(ctx: Ctx):
    bash = _bash()
    ctx.check("a POSIX bash is found to run the workflow's script (Git's on Windows)", bool(bash))
    if not bash:
        return
    summaries = [(name, s["run"]) for name, job in _jobs().items() for s in job.get("steps", [])
                 if s.get("name") == "Job summary"]
    ctx.check(f"suites.yml has a Job summary step in each suites job, found {[n for n, _ in summaries]}",
              len(summaries) >= 2)
    for name, script in summaries:
        with tempfile.TemporaryDirectory() as tmp:
            tmpp = Path(tmp)
            # A run that timed out: test output, but no RESULT: or exit= line anywhere.
            (tmpp / "run_all.log").write_text("=== tests.test_x ===\n  [PASS] one\n  [....] two\n", encoding="utf-8")
            (tmpp / "script.sh").write_text(_fill(script), encoding="utf-8", newline="\n")
            env = dict(os.environ, RUNNER_TEMP=tmp, GITHUB_STEP_SUMMARY=str(tmpp / "summary.md"))
            ran = subprocess.run([bash, "--noprofile", "--norc", "-eo", "pipefail", "script.sh"], cwd=tmp, env=env,
                                 capture_output=True, text=True, timeout=60)
            summary = (tmpp / "summary.md").read_text(encoding="utf-8") if (tmpp / "summary.md").is_file() else ""
            ctx.check(f"{name}: the summary script exits 0 under -eo pipefail with no RESULT line, got exit "
                      f"{ran.returncode}: {ran.stderr[-300:]}", ran.returncode == 0)
            ctx.check(f"{name}: the summary marks run_all FAIL and says no RESULT line was captured, got "
                      f"{summary[-400:]!r}",
                      "**FAIL** `tests/run_all.py` -- no RESULT line captured" in summary)


@test
def test_the_logs_upload_even_when_an_earlier_step_failed(ctx: Ctx):
    uploads = [(name, str(s.get("if", ""))) for name, job in _jobs().items() for s in job.get("steps", [])
               if s.get("name") == "Upload logs on failure"]
    ctx.check(f"suites.yml has an upload step in each suites job, found {[n for n, _ in uploads]}", len(uploads) >= 2)
    for name, cond in uploads:
        ctx.check(f"{name}: the upload's condition starts with always() so a failed summary cannot skip it, got {cond!r}",
                  cond.replace(" ", "").startswith("always()&&("))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
