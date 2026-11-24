"""scripts/release_gate.py -- the CI gate of scripts/release.py (Halo 3.1.0.0 R1; 3.6.0.0 R13: the candidate branch).

The main line is protected: its required checks are the jobs below, and no commit reaches master that has not passed them on an
`rc/**` branch. A push to `rc/**` runs every platform's suites on that commit (suites.yml), so release.py pushes the
version commit to `rc/<version>` and this gate waits for that run:

1. the `push` run of suites.yml on the branch for the EXACT sha is found (it may take a moment to appear) and polled
   with `gh run view` until it completes (up to 90 minutes); a `gh` read that fails while it waits (a network
   fault) is asked again, and three failures in a row stop the gate with the last reason (3.6.0.16);
2. every job in `required_jobs()` must be in it and conclude `success` -- the conclusion VALUE of each job is read,
   never an exit code of a watch command, and a missing or skipped required job fails like a red one; the
   failing jobs are named;
3. the run's log is read once (`gh run view --log`) and every "driver retried once" line is returned as a warning
   (a retry was the early sign of three real bugs in one week): it does not stop the release, it is printed.

The required jobs are ONE list here: Linux x4, Windows x4 and macOS x4 (the shards), studio-ui, and the six `realcheck`
legs (checkout and installed, per OS): nineteen. Since 3.6.0.0 macOS and the real-use check are required by default
(`REQUIRE_MACOS` / `REQUIRE_REALCHECK` below). Only an emergency leaves one out, per run, with release.py's
`--emergency-skip-macos-gate` (the four macOS shards and the two macOS realcheck legs) or
`--emergency-skip-realcheck-gate` (the six realcheck legs); the run then names the switch and every leg it left out.

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
REQUIRE_MACOS = True  # 3.6.0.0: the owner's bar is Windows, macOS and Linux
REQUIRE_REALCHECK = True  # ... driven the way a person drives Halo (scripts/realcheck.py)
# suites.yml: `realcheck (${{ matrix.os }}${{ matrix.install == 'installed' && ', installed' || '' }})`, two legs per OS:
# the checkout and the installed wheel (join batch 1: the gate named only the first, so the second went unread)
REALCHECK_JOBS = ("realcheck ({})", "realcheck ({}, installed)")
RETRY_MARK = "driver retried once"
WAIT_S = 90 * 60
POLL_S = 30.0
FIND_WAIT_S = 300.0
GH_TRIES = 3  # 3.6.0.16: a `gh` read that fails while the gate waits is asked again; this many failures in a row stop it
_FIELDS = "databaseId,status,conclusion,event,headSha,headBranch,displayTitle,createdAt"


class GateError(Exception):
    """A one-line reason the release stops at the gate."""


class NoGh(GateError):
    """`gh` is not on PATH: asking again cannot help."""


def required_jobs(*, macos: "bool | None" = None, realcheck: "bool | None" = None) -> "list[str]":
    """The job names that must conclude success, in the order they are reported."""
    macos = REQUIRE_MACOS if macos is None else macos
    realcheck = REQUIRE_REALCHECK if realcheck is None else realcheck
    platforms = ["linux", "windows"] + (["macos"] if macos else [])
    out = [f"suites ({p}, py3.12, shard {i}/{SHARDS})" for p in platforms for i in range(SHARDS)]
    out.append("studio-ui (build + drift gate)")
    if realcheck:
        out += [form.format(p) for p in platforms for form in REALCHECK_JOBS]
    return out


def skipped_jobs(*, macos: "bool | None" = None, realcheck: "bool | None" = None) -> "list[str]":
    """The jobs of the full list that these switches leave out (empty by default), in the order they are reported."""
    kept = set(required_jobs(macos=macos, realcheck=realcheck))
    return [n for n in required_jobs(macos=True, realcheck=True) if n not in kept]


def head_sha(repo_dir: Path) -> str:
    """HEAD of `repo_dir` (read-only, local)."""
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo_dir), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    sha = (r.stdout or "").strip()
    if r.returncode != 0 or len(sha) < 40:
        raise GateError(f"could not read HEAD in {repo_dir}: {(r.stderr or '').strip()[:200]}")
    return sha


def _gh(run_fn: Callable, args: list, repo_dir: Path, want_json: bool = True):
    try:
        r = run_fn(["gh", *args], cwd=str(repo_dir), capture_output=True, text=True, check=False,
                   encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise NoGh("the CI gate needs the `gh` CLI on PATH (logged in to github.com)")
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


def _again(call: Callable, *, sleep_fn: Callable, pause_s: float, log: Callable):
    """3.6.0.16: `call()` is one `gh` read of the gate's waiting. One that fails (a TLS handshake timeout on the
    network) used to end the release tool while its run was still going; now it is asked again after `pause_s`.
    GH_TRIES failures IN A ROW stop the gate with the last reason; a missing `gh` stops it at once."""
    for n in range(1, GH_TRIES + 1):
        try:
            return call()
        except NoGh:
            raise
        except GateError as e:
            if n == GH_TRIES:
                raise
            log(f"release.py: {e}; asking again ({n} of {GH_TRIES - 1})")
            sleep_fn(pause_s)


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


def never_ran(run_view: dict, required: "list[str]") -> set:
    """The required jobs that were cancelled before any step ran (the view says `steps: []`): no runner took them."""
    return {str(j.get("name", "")) for j in run_view.get("jobs") or []
            if isinstance(j, dict) and j.get("name") in required and j.get("conclusion") == "cancelled"
            and j.get("steps") == []}


def retried_lines(run_fn, repo_dir, run_id, *, limit: int = 20) -> "list[str]":
    """Each "driver retried once" line of the run's log, as `<job>: <the line>` (the log is read once)."""
    try:
        text = _gh(run_fn, ["run", "view", str(run_id), "--log"], repo_dir, want_json=False)
    except GateError:
        return ["(the run's log could not be read, so its retries were not counted)"]
    out, seen = [], set()
    for line in (text or "").splitlines():
        # 3.6.0.20: only a TEST's own line is a retry ("[PASS] <test> (...) (driver retried once: why)"), once per
        # job and test. The workflow's own script, echoed by the runner, names the mark too, and its summary step
        # prints the test's line again and a `::warning`: two releases printed fifty false warnings from those.
        if RETRY_MARK not in line or "[PASS]" not in line:
            continue
        parts = line.split("\t")
        job = parts[0].strip() if len(parts) >= 3 else "?"
        tail = line[line.index(RETRY_MARK):].strip()
        what = parts[-1].strip() if len(parts) >= 3 else line.strip()
        test = what.split("[PASS]", 1)[-1].split("(", 1)[0].strip()
        if (job, test) in seen:
            continue
        seen.add((job, test))
        out.append(f"{job}: {test + ' -- ' if test else ''}{tail}"[:300])
    return out[:limit] + ([f"... and {len(out) - limit} more"] if len(out) > limit else [])


def wait_for(run_id, run_fn, repo_dir, *, sleep_fn=time.sleep, clock_fn=time.monotonic,
             wait_s: float = WAIT_S, poll_s: float = POLL_S, log: Callable = print) -> dict:
    """Poll `gh run view` until the run completes; GateError after `wait_s`."""
    deadline = clock_fn() + wait_s
    while True:
        v = _again(lambda: view(run_fn, repo_dir, run_id), sleep_fn=sleep_fn, pause_s=poll_s, log=log)
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
        runs = _again(lambda: branch_runs(sha, branch, run_fn, repo_dir), sleep_fn=sleep_fn,
                      pause_s=min(poll_s, 10.0), log=log)
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
        hint = ""
        if never_ran(v, required) == {b.rsplit(": ", 1)[0] for b in bad}:
            # 3.6.0.20: a job cancelled with no step is not a result of the code (no runner took it)
            hint = (f" (none of these ran: no runner took them. `gh run rerun {run_id} --failed`, then start the "
                    f"release again: it takes up the candidate branch)")
        raise GateError(f"the suites run {run_id} on {branch} for {sha[:12]} is not green -- failing jobs: "
                        + "; ".join(bad) + hint)
    warnings = retried_lines(run_fn, repo_dir, run_id)
    return [f"suites run {run_id} on {branch}: all {len(required)} required jobs concluded success for {sha[:12]}"], \
        warnings


def describe(branch: str, *, macos: "bool | None" = None, realcheck: "bool | None" = None) -> str:
    """The gate's line in a dry run."""
    req = required_jobs(macos=macos, realcheck=realcheck)
    return (f"wait for the suites run (push) on {branch} for the version commit, up to {WAIT_S // 60} min; all "
            f"{len(req)} required jobs must conclude success, each red or missing one named ({', '.join(req)}); "
            f'"{RETRY_MARK}" lines in its log are printed as warnings')
