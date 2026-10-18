"""scripts/release_gate.py -- step 0 of scripts/release.py (Halo 3.1.0.0 round
R1): a release needs BOTH platforms green on the exact sha it tags.

Since 3.1.0.0 the suites workflow runs its Linux job on every push and its
Windows job only on tags, nightly and `workflow_dispatch` (input `sha`), so
release.py asks for the Windows run itself:

1. the latest `push` run of suites.yml for the sha must have concluded
   `success`, its Linux job included;
2. `gh workflow run suites.yml -f sha=<sha>` dispatches the Windows job for
   the sha; the run is found by its title (`run-name` carries the sha) and
   polled with `gh run view` until it completes (up to 90 minutes);
3. it must conclude `success`, its Windows job included.

`--skip-windows` (an owner who already has a green dispatch for the sha)
skips the dispatch and accepts the newest finished green Windows run for the
sha. Either way the accepted run ids are printed. Every `gh` call goes
through `run_fn` (tests pass a fake `gh`); the conclusion VALUE is read, never
an exit code of a watch command.
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

WORKFLOW = "suites.yml"
LINUX_JOB = "suites (linux"
WINDOWS_JOB = "suites (windows"
WAIT_S = 90 * 60
POLL_S = 30.0
_FIELDS = "databaseId,status,conclusion,event,headSha,displayTitle,createdAt"


class GateError(Exception):
    """A one-line reason the release stops at step 0."""


def head_sha(repo_dir: Path) -> str:
    """The sha being released: HEAD of `repo_dir` (read-only, local)."""
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo_dir), capture_output=True, text=True)
    sha = (r.stdout or "").strip()
    if r.returncode != 0 or len(sha) < 40:
        raise GateError(f"could not read HEAD in {repo_dir}: {(r.stderr or '').strip()[:200]}")
    return sha


def _gh(run_fn: Callable, args: list, repo_dir: Path, want_json: bool = True):
    try:
        r = run_fn(["gh", *args], cwd=str(repo_dir), capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise GateError("the CI gate needs the `gh` CLI on PATH (logged in to github.com)")
    except subprocess.SubprocessError as e:
        raise GateError(f"`gh {' '.join(args[:3])}` failed: {e}")
    if getattr(r, "returncode", 0) != 0:
        raise GateError(f"`gh {' '.join(args[:3])}` exited {r.returncode}: {(getattr(r, 'stderr', '') or '').strip()[:200]}")
    if not want_json:
        return None
    try:
        return json.loads(getattr(r, "stdout", "") or "null")
    except ValueError:
        raise GateError(f"`gh {' '.join(args[:3])}` printed no JSON")


def _runs(run_fn, repo_dir, event: str, sha: "str | None" = None, limit: int = 20) -> list:
    args = ["run", "list", "--workflow", WORKFLOW, "--event", event, "--json", _FIELDS, "--limit", str(limit)]
    if sha:
        args += ["--commit", sha]
    got = _gh(run_fn, args, repo_dir)
    return [r for r in (got or []) if isinstance(r, dict)]


def view(run_fn, repo_dir, run_id) -> dict:
    got = _gh(run_fn, ["run", "view", str(run_id), "--json", "databaseId,status,conclusion,headSha,displayTitle,jobs"], repo_dir)
    return got if isinstance(got, dict) else {}


def job_conclusion(run_view: dict, prefix: str) -> "str | None":
    for job in run_view.get("jobs") or []:
        if isinstance(job, dict) and str(job.get("name", "")).startswith(prefix):
            return job.get("conclusion")
    return None


def _green(run_view: dict, prefix: str) -> bool:
    return (run_view.get("status") == "completed" and run_view.get("conclusion") == "success"
            and job_conclusion(run_view, prefix) == "success")


def linux_run(sha: str, run_fn, repo_dir) -> dict:
    """The newest push run for `sha` whose Linux job ran (a tag push skips it); GateError unless that run and
    its Linux job concluded success."""
    runs = [r for r in _runs(run_fn, repo_dir, "push", sha) if r.get("headSha") == sha]
    for r in runs:
        v = view(run_fn, repo_dir, r["databaseId"])
        if job_conclusion(v, LINUX_JOB) in (None, "skipped"):
            continue
        if not _green(v, LINUX_JOB):
            raise GateError(f"the Linux suites run {r['databaseId']} for {sha[:12]} is {v.get('status')}/"
                            f"{v.get('conclusion')} (Linux job: {job_conclusion(v, LINUX_JOB)}), not success")
        return v
    raise GateError(f"no Linux suites run (push) for {sha[:12]}: push the commit and let CI run first")


def _created(run: dict) -> float:
    try:
        return datetime.fromisoformat(str(run.get("createdAt", "")).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def dispatched_run(sha: str, run_fn, repo_dir, since: float) -> "dict | None":
    """The Windows run this release dispatched: among the dispatch runs created after `since` (two minutes of
    clock slack), the newest titled with the sha (`run-name`), else the newest one."""
    recent = [r for r in _runs(run_fn, repo_dir, "workflow_dispatch") if _created(r) >= since - 120]
    titled = [r for r in recent if sha in str(r.get("displayTitle", ""))]
    return (titled or recent or [None])[0]


def green_windows_run(sha: str, run_fn, repo_dir) -> "tuple[dict, dict] | None":
    """`--skip-windows`: the newest finished run whose Windows job concluded success for `sha` -- a dispatch
    titled with the sha, else a tag push or a nightly run of that exact sha. `(run, view)` or None."""
    candidates = [r for r in _runs(run_fn, repo_dir, "workflow_dispatch") if sha in str(r.get("displayTitle", ""))]
    for event in ("push", "schedule"):
        candidates += [r for r in _runs(run_fn, repo_dir, event, sha) if r.get("headSha") == sha]
    for r in candidates:
        if r.get("status") != "completed":
            continue
        v = view(run_fn, repo_dir, r["databaseId"])
        if _green(v, WINDOWS_JOB):
            return r, v
    return None


def wait_for(run_id, run_fn, repo_dir, *, sleep_fn=time.sleep, clock_fn=time.monotonic,
             wait_s: float = WAIT_S, poll_s: float = POLL_S, log: Callable = print) -> dict:
    """Poll `gh run view` until the run completes; GateError after `wait_s`."""
    deadline = clock_fn() + wait_s
    while True:
        v = view(run_fn, repo_dir, run_id)
        if v.get("status") == "completed":
            return v
        if clock_fn() >= deadline:
            raise GateError(f"the Windows run {run_id} did not finish within {wait_s / 60:.0f} min (still {v.get('status')})")
        log(f"release.py: waiting for the Windows run {run_id} ({v.get('status')})")
        sleep_fn(poll_s)


def ci_gate(sha: str, *, repo_dir: Path, run_fn: Callable, skip_windows: bool = False,
            sleep_fn: Callable = time.sleep, clock_fn: Callable = time.monotonic, wall_fn: Callable = time.time,
            wait_s: float = WAIT_S, poll_s: float = POLL_S, find_wait_s: float = 300.0,
            log: Callable = print) -> "list[str]":
    """Step 0. Returns the lines naming the runs it accepted; raises GateError otherwise."""
    linux = linux_run(sha, run_fn, repo_dir)
    accepted = [f"Linux run {linux.get('databaseId')} concluded success for {sha[:12]}"]
    if skip_windows:
        got = green_windows_run(sha, run_fn, repo_dir)
        if got is None:
            raise GateError(f"--skip-windows: no finished green Windows run for {sha[:12]} to accept "
                            f"(run without --skip-windows to dispatch one)")
        return accepted + [f"Windows run {got[0]['databaseId']} concluded success for {sha[:12]} "
                           f"(--skip-windows: accepted, not dispatched)"]
    since = wall_fn()
    _gh(run_fn, ["workflow", "run", WORKFLOW, "-f", f"sha={sha}"], repo_dir, want_json=False)
    log(f"release.py: dispatched the Windows suites for {sha[:12]}; waiting up to {wait_s / 60:.0f} min")
    found, find_deadline = None, clock_fn() + find_wait_s
    while found is None:
        found = dispatched_run(sha, run_fn, repo_dir, since)
        if found is None:
            if clock_fn() >= find_deadline:
                raise GateError(f"the dispatched Windows run for {sha[:12]} never appeared in `gh run list`")
            sleep_fn(min(poll_s, 10.0))
    v = wait_for(found["databaseId"], run_fn, repo_dir, sleep_fn=sleep_fn, clock_fn=clock_fn, wait_s=wait_s,
                 poll_s=poll_s, log=log)
    if not _green(v, WINDOWS_JOB):
        raise GateError(f"the Windows run {found['databaseId']} for {sha[:12]} concluded {v.get('conclusion')} "
                        f"(Windows job: {job_conclusion(v, WINDOWS_JOB)}), not success")
    return accepted + [f"Windows run {found['databaseId']} concluded success for {sha[:12]} (dispatched by this release)"]


def describe(sha: str, skip_windows: bool) -> str:
    """The step 0 line a dry run prints."""
    if skip_windows:
        return (f"CI gate for {sha[:12]}: the latest Linux suites run must be success; --skip-windows: accept the "
                f"newest green Windows run for the sha instead of dispatching one")
    return (f"CI gate for {sha[:12]}: the latest Linux suites run must be success; dispatch the Windows suites "
            f"(gh workflow run {WORKFLOW} -f sha={sha[:12]}...), wait up to {WAIT_S // 60} min, it must conclude success")

