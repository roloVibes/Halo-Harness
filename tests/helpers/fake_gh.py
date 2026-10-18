"""tests.helpers.fake_gh -- a stand-in for the `gh` CLI as scripts/release.py's
step 0 (scripts/release_gate.py) calls it through `run_fn` (Halo 3.1.0.0 R1).
No process, no network: each call is answered from the scenario below.

    FakeGh(linux="success", windows="success", windows_polls=2)

* `gh run list --event push --commit <sha>` -> one push run (id 101) for that
  sha whose run and Linux job concluded `linux` (None: no run at all);
* `gh run view 101` -> that run with its jobs (the Windows job skipped);
* `gh workflow run suites.yml -f sha=<sha>` -> records the dispatch;
* `gh run list --event workflow_dispatch` -> the dispatched run (id 202,
  titled with the sha) once dispatched, or `existing_windows` (a run that
  was there before);
* `gh run view 202` -> `in_progress` for the first `windows_polls - 1` views,
  then completed with `windows` as the run's and the Windows job's conclusion.
Every other command answers returncode 0 with empty output (git archive keeps
the side effect test_release_script's own fake gives it).
"""
from __future__ import annotations

import json
from pathlib import Path


class _R:
    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = ""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def _arg(cmd: list, flag: str):
    return cmd[cmd.index(flag) + 1] if flag in cmd and cmd.index(flag) + 1 < len(cmd) else None


class FakeGh:
    def __init__(self, *, linux: "str | None" = "success", windows: str = "success", windows_polls: int = 1,
                 existing_windows: "str | None" = None, created: str = "2999-01-01T00:00:00Z",
                 title_has_sha: bool = True):
        self.linux, self.windows, self.windows_polls = linux, windows, windows_polls
        self.existing_windows, self.created, self.title_has_sha = existing_windows, created, title_has_sha
        self.calls: list = []
        self.sha: "str | None" = None
        self.dispatched = False
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
        if args[:2] == ["workflow", "run"]:
            self.dispatched = True
            sha_arg = next((a for a in args if a.startswith("sha=")), "")
            self.sha = sha_arg[4:] or self.sha
            return _R()
        if args[:2] == ["run", "list"]:
            return _R(json.dumps(self._list(_arg(args, "--event"), _arg(args, "--commit"))))
        if args[:2] == ["run", "view"]:
            return _R(json.dumps(self._view(args[2])))
        return _R()

    def _windows_run(self, status: str, conclusion) -> dict:
        title = f"suites windows leg for {self.sha}" if self.title_has_sha else "suites"
        return {"databaseId": 202, "status": status, "conclusion": conclusion, "event": "workflow_dispatch",
                "headSha": "f" * 40, "displayTitle": title, "createdAt": self.created}

    def _list(self, event, commit) -> list:
        if commit:
            self.sha = commit
        if event == "push":
            if self.linux is None or not commit:
                return []
            return [{"databaseId": 101, "status": "completed", "conclusion": self.linux, "event": "push",
                     "headSha": commit, "displayTitle": "a commit", "createdAt": "2026-10-18T08:00:00Z"}]
        if event == "workflow_dispatch":
            if self.dispatched:
                return [self._windows_run("queued", None)]
            if self.existing_windows is not None:
                return [self._windows_run("completed", self.existing_windows)]
        return []

    def _view(self, run_id: str) -> dict:
        if run_id == "101":
            return {"databaseId": 101, "status": "completed", "conclusion": self.linux, "headSha": self.sha,
                    "jobs": [{"name": "suites (linux, py3.12)", "conclusion": self.linux},
                             {"name": "studio-ui (build + drift gate)", "conclusion": "success"},
                             {"name": "suites (windows, py3.12)", "conclusion": "skipped"}]}
        if run_id == "202":
            if not self.dispatched:
                conclusion = self.existing_windows
                return {"databaseId": 202, "status": "completed", "conclusion": conclusion,
                        "jobs": [{"name": "suites (windows, py3.12)", "conclusion": conclusion}]}
            self._views += 1
            if self._views < self.windows_polls:
                return {"databaseId": 202, "status": "in_progress", "conclusion": None, "jobs": []}
            return {"databaseId": 202, "status": "completed", "conclusion": self.windows,
                    "jobs": [{"name": "suites (linux, py3.12)", "conclusion": "skipped"},
                             {"name": "suites (windows, py3.12)", "conclusion": self.windows}]}
        return {}
