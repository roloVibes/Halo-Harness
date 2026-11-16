"""tests.helpers.fake_gh -- a stand-in for the `gh` CLI as scripts/release.py's gate (scripts/release_gate.py) calls
it through `run_fn` (Halo 3.1.0.0 R1; 3.6.0.0 R13: the candidate branch). No process, no network: each call is
answered from the scenario below.

    FakeGh(conclusions=None, polls=1, appear_after=0, retried=(), head_sha=None)

* `gh run list --workflow suites.yml --branch <b> --event push --commit <sha>` -> the push run (id 303) on that branch
  for that sha, once it has been asked for `appear_after` times (a run takes a moment to show up); `appear_after`
  None: it never appears;
* `gh run view 303 --json ...` -> `in_progress` for the first `polls - 1` views, then completed with one job per
  name in `jobs` (the required list by default, macOS and realcheck included) whose conclusion is `conclusions.get(
  name, "success")` -- a name mapped to None is left out of the run;
* `gh run view 303 --log` -> a log whose lines carry `retried` (each a (job, test) pair) the way tests/run_all.py
  prints a driver retry;
Every other command answers returncode 0 with empty output (`git archive -o <path>` writes the file it names, the
side effect the release's checksums step reads).
"""
from __future__ import annotations

import json
from pathlib import Path

RUN_ID = 303


class _R:
    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = ""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def _arg(cmd: list, flag: str):
    return cmd[cmd.index(flag) + 1] if flag in cmd and cmd.index(flag) + 1 < len(cmd) else None


def all_jobs() -> list:
    shards = [f"suites ({p}, py3.12, shard {i}/4)" for p in ("linux", "windows", "macos") for i in range(4)]
    return shards + ["studio-ui (build + drift gate)"] + [f"realcheck ({p}{f}" for p in ("linux", "windows", "macos")
                                                         for f in (")", ", installed)")]


class FakeGh:
    def __init__(self, *, conclusions: "dict | None" = None, polls: int = 1, appear_after: "int | None" = 0,
                 retried=(), head_sha: "str | None" = None, jobs: "list | None" = None):
        self.conclusions = dict(conclusions or {})
        self.polls, self.appear_after, self.retried = polls, appear_after, list(retried)
        self.head_sha, self.jobs = head_sha, list(jobs or all_jobs())
        self.calls: list = []
        self.sha: "str | None" = None
        self.branch: "str | None" = None
        self._lists = 0
        self._views = 0

    def gh_calls(self) -> list:
        return [c for c in self.calls if c and c[0] == "gh"]

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        if not cmd:
            return _R()
        if cmd[0] == "git" and "archive" in cmd:
            try:
                out = Path(cmd[cmd.index("-o") + 1])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"fake-archive-contents")
            except (OSError, ValueError):
                pass
            return _R()
        if cmd[0] != "gh":
            return _R()
        args = cmd[1:]
        if args[:2] == ["run", "list"]:
            return _R(json.dumps(self._list(_arg(args, "--branch"), _arg(args, "--event"), _arg(args, "--commit"))))
        if args[:2] == ["run", "view"] and "--log" in args:
            return _R(self._log())
        if args[:2] == ["run", "view"]:
            return _R(json.dumps(self._view(args[2])))
        return _R()

    def _list(self, branch, event, commit) -> list:
        self.sha, self.branch = commit or self.sha, branch or self.branch
        self._lists += 1
        if event != "push" or not commit or self.appear_after is None or self._lists <= self.appear_after:
            return []
        return [{"databaseId": RUN_ID, "status": "queued", "conclusion": None, "event": "push",
                 "headSha": commit, "headBranch": branch, "displayTitle": "release", "createdAt": "2026-11-15T08:00:00Z"}]

    def _view(self, run_id: str) -> dict:
        if str(run_id) != str(RUN_ID):
            return {}
        self._views += 1
        sha = self.head_sha or self.sha
        if self._views < self.polls:
            return {"databaseId": RUN_ID, "status": "in_progress", "conclusion": None, "headSha": sha, "jobs": []}
        jobs = [{"name": n, "conclusion": self.conclusions.get(n, "success")} for n in self.jobs
                if not (n in self.conclusions and self.conclusions[n] is None)]
        overall = "success" if all(j["conclusion"] == "success" for j in jobs) else "failure"
        return {"databaseId": RUN_ID, "status": "completed", "conclusion": overall, "headSha": sha,
                "headBranch": self.branch, "jobs": jobs}

    def _log(self) -> str:
        lines = ["suites (linux, py3.12, shard 0/4)\tSet up job\t2026-11-15T08:00:01.0000000Z Current runner version"]
        for job, test in self.retried:
            lines.append(f"{job}\ttests/run_all.py\t2026-11-15T08:10:00.0000000Z   [PASS] {test} (12.30s) "
                         f"(driver retried once: Runtime.evaluate timed out)")
        return "\n".join(lines) + "\n"
