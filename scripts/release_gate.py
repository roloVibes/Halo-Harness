"""scripts/release_gate.py -- the CI gate of scripts/release.py (Halo 3.1.0.0 R1; 3.6.0.0 R13: the candidate branch).

The main line is protected: nine required checks, and no commit reaches master that has not passed them on an
`rc/**` branch. A push to `rc/**` runs every platform's suites on that commit (suites.yml), so release.py pushes the
version commit to `rc/<version>` and this gate waits for that run:

1. the `push` run of suites.yml on the branch for the EXACT sha is found (it may take a moment to appear) and polled
   with `gh run view` until it completes (up to 90 minutes);
2. every job in `required_jobs()` must be in it and conclude `success` -- the conclusion VALUE of each job is read,
   never an exit code of a watch command, and a missing or skipped required job fails like a red one; the
   failing jobs are named;
3. the run's log is read once (`gh run view --log`) and every "driver retried once" line is returned as a warning
   (a retry was the early sign of three real bugs in one week): it does not stop the release, it is printed.

The required jobs are ONE list here: Linux x4 and Windows x4 (the shards) and studio-ui. macOS x4 and `realcheck`
join it when `REQUIRE_MACOS` / `REQUIRE_REALCHECK` below are flipped to True (the coordinator flips them once those
jobs are green), or per run with release.py's `--require-macos` / `--require-realcheck`.

Every `gh` call goes through `run_fn` (tests pass a fake `gh`, tests/helpers/fake_gh.py).
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Callable

WORKFLOW = "suites.yml"
SHARDS = 4
REQUIRE_MACOS = False  # the coordinator flips this when the macOS shards are green
REQUIRE_REALCHECK = False  # ... and this when the real-use check job is
REALCHECK_JOB = "realcheck"
RETRY_MARK = "driver retried once"
WAIT_S = 90 * 60
POLL_S = 30.0
FIND_WAIT_S = 300.0
_FIELDS = "databaseId,status,conclusion,event,headSha,headBranch,displayTitle,createdAt"


class GateError(Exception):
    """A one-line reason the release stops at the gate."""


def required_jobs(*, macos: "bool | None" = None, realcheck: "bool | None" = None) -> "list[str]":
    """The job names that must conclude success, in the order they are reported."""
    macos = REQUIRE_MACOS if macos is None else macos
    realcheck = REQUIRE_REALCHECK if realcheck is None else realcheck
    platforms = ["linux", "windows"] + (["macos"] if macos else [])
    out = [f"suites ({p}, py3.12, shard {i}/{SHARDS})" for p in platforms for i in range(SHARDS)]
    out.append("studio-ui (build + drift gate)")
    if realcheck:
        out.append(REALCHECK_JOB)
    return out


def head_sha(repo_dir: Path) -> str:
    """HEAD of `repo_dir` (read-only, local)."""
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
        return getattr(r, "stdout", "") or ""
    try:
        return json.loads(getattr(r, "stdout", "") or "null")
    except ValueError:
        raise GateError(f"`gh {' '.join(args[:3])}` printed no JSON")


def branch_runs(sha: str, branch: str, run_fn, repo_dir) -> list:
    """The push runs of suites.yml on `branch` for exactly `sha`, newest first."""
    got = _gh(run_fn, ["run", "list", "--workflow", WORKFLOW, "--branch", branch, "--event", "push", "--commit", sha,
                       "--json", _FIELDS, "--limit", "20"], repo_dir)
    return [r for r in (got or []) if isinstance(r, dict) and r.get("headSha") == sha]


def view(run_fn, repo_dir, run_id) -> dict:
    got = _gh(run_fn, ["run", "view", str(run_id), "--json", "databaseId,status,conclusion,headSha,headBranch,jobs"],
              repo_dir)
    return got if isinstance(got, dict) else {}


def job_conclusions(run_view: dict) -> dict:
    return {str(j.get("name", "")): j.get("conclusion") for j in run_view.get("jobs") or [] if isinstance(j, dict)}


def failing(run_view: dict, required: "list[str]") -> "list[str]":
    """`<job>: <conclusion>` for every required job that is not a success (missing ones included)."""
    got = job_conclusions(run_view)
    return [f"{name}: {got.get(name) or 'missing'}" for name in required if got.get(name) != "success"]


def retried_lines(run_fn, repo_dir, run_id, *, limit: int = 20) -> "list[str]":
    """Each "driver retried once" line of the run's log, as `<job>: <the line>` (the log is read once)."""
    try:
        text = _gh(run_fn, ["run", "view", str(run_id), "--log"], repo_dir, want_json=False)
    except GateError:
        return ["(the run's log could not be read, so its retries were not counted)"]
    out = []
    for line in (text or "").splitlines():
        if RETRY_MARK not in line:
            continue
        parts = line.split("\t")
        job = parts[0].strip() if len(parts) >= 3 else "?"
        tail = line[line.index(RETRY_MARK):].strip()
        what = parts[-1].strip() if len(parts) >= 3 else line.strip()
        test = what.split("[PASS]", 1)[-1].split("(", 1)[0].strip() if "[PASS]" in what else ""
        out.append(f"{job}: {test + ' -- ' if test else ''}{tail}"[:300])
    return out[:limit] + ([f"... and {len(out) - limit} more"] if len(out) > limit else [])


def wait_for(run_id, run_fn, repo_dir, *, sleep_fn=time.sleep, clock_fn=time.monotonic,
             wait_s: float = WAIT_S, poll_s: float = POLL_S, log: Callable = print) -> dict:
    """Poll `gh run view` until the run completes; GateError after `wait_s`."""
    deadline = clock_fn() + wait_s
    while True:
        v = view(run_fn, repo_dir, run_id)
        if v.get("status") == "completed":
            return v
        if clock_fn() >= deadline:
            raise GateError(f"the suites run {run_id} did not finish within {wait_s / 60:.0f} min (still {v.get('status')})")
        log(f"release.py: waiting for the suites run {run_id} ({v.get('status')})")
        sleep_fn(poll_s)


def candidate_gate(sha: str, *, branch: str, repo_dir: Path, run_fn: Callable, macos: "bool | None" = None,
                   realcheck: "bool | None" = None, sleep_fn: Callable = time.sleep,
                   clock_fn: Callable = time.monotonic, wait_s: float = WAIT_S, poll_s: float = POLL_S,
                   find_wait_s: float = FIND_WAIT_S, log: Callable = print) -> "tuple[list[str], list[str]]":
    """The gate on the candidate branch's run for `sha`: (accepted lines, retry warnings), or GateError naming
    the failing jobs."""
    required = required_jobs(macos=macos, realcheck=realcheck)
    log(f"release.py: waiting for the suites on {branch} at {sha[:12]} (up to {wait_s / 60:.0f} min)")
    found, find_deadline = None, clock_fn() + find_wait_s
    while found is None:
        runs = branch_runs(sha, branch, run_fn, repo_dir)
        found = runs[0] if runs else None
        if found is None:
            if clock_fn() >= find_deadline:
                raise GateError(f"no suites run (push) on {branch} for {sha[:12]} appeared in `gh run list`")
            sleep_fn(min(poll_s, 10.0))
    run_id = found["databaseId"]
    v = wait_for(run_id, run_fn, repo_dir, sleep_fn=sleep_fn, clock_fn=clock_fn, wait_s=wait_s, poll_s=poll_s,
                 log=log)
    if v.get("headSha") and v.get("headSha") != sha:
        raise GateError(f"the suites run {run_id} is for {str(v.get('headSha'))[:12]}, not {sha[:12]}")
    bad = failing(v, required)
    if bad:
        raise GateError(f"the suites run {run_id} on {branch} for {sha[:12]} is not green -- failing jobs: "
                        + "; ".join(bad))
    warnings = retried_lines(run_fn, repo_dir, run_id)
    return [f"suites run {run_id} on {branch}: all {len(required)} required jobs concluded success for {sha[:12]}"], \
        warnings


def describe(branch: str, *, macos: "bool | None" = None, realcheck: "bool | None" = None) -> str:
    """The gate's line in a dry run."""
    req = required_jobs(macos=macos, realcheck=realcheck)
    return (f"wait for the suites run (push) on {branch} for the version commit, up to {WAIT_S // 60} min; all "
            f"{len(req)} required jobs must conclude success ({', '.join(req)}); "
            f'"{RETRY_MARK}" lines in its log are printed as warnings')
