"""The concord pack's policy hook, `claimed-files` (docs/EXTENSION_API.md "Policy hooks"): while the coordinating
mode is on, a Write or Edit to a file an active Concord task claims is denied with the pack's line

    concord: src/auth.py is claimed by task t-42

Halo starts this once when the policy is armed and keeps it running; it reads one JSON request per line on stdin and
writes one JSON answer per line on stdout, the request's id in it. For each Write or Edit inside the project it runs
Concord's own check, `concord check [--task <yours>] <path>` (the path relative to the project folder, as Concord
records claims), in the project folder with CONCORD_TELEMETRY_DISABLED=1:

    exit 0   no other active task claims the file             -> allow
    exit 1   an overlap; its "  - <task id> (<title>): ..."   -> deny, the task named
    else     a failure, a timeout, or no `concord` on PATH    -> allow, the reason saying so (and on_error: allow
                                                                 covers this script itself failing)

Your own claim: Concord excludes the task `--task` names. Set CONCORD_TASK=<your task id> in the shell you start
halo from (the variable Concord's own Claude Code hook reads); without it, any active claim on the file counts.
Plain Python, nothing of Halo imported.
"""

import json
import os
import re
import shutil
import subprocess
import sys

WRITES = ("Write", "Edit")
TIMEOUT_S = 1.5  # inside Halo's 2 s budget for the answer
TASK_RE = re.compile(r"^\s*-\s+(\S+)\s+\(", re.M)


def _relative(path: str, cwd: str):
    """The path relative to the project folder with forward slashes, or None when it is outside it."""
    full = os.path.abspath(os.path.join(cwd, path))
    root = os.path.abspath(cwd)
    try:
        if os.path.commonpath([os.path.normcase(full), os.path.normcase(root)]) != os.path.normcase(root):
            return None
    except ValueError:  # another drive on Windows
        return None
    return os.path.relpath(full, root).replace(os.sep, "/")


def _allow(reason: str, rule: str) -> dict:
    return {"verdict": "allow", "reason": reason, "rule": rule}


def check(rel: str, cwd: str, task: str) -> dict:
    exe = shutil.which("concord")
    if exe is None:
        return _allow("concord is not on PATH: no claim is checked", "no-concord")
    argv = [exe, "check"] + (["--task", task] if task else []) + [rel]
    env = {**os.environ, "CONCORD_TELEMETRY_DISABLED": "1"}
    try:
        r = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=TIMEOUT_S, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return _allow(f"concord check took over {TIMEOUT_S:g} s: nothing is blocked", "check-failed")
    except OSError as e:
        return _allow(f"concord check did not run ({e}): nothing is blocked", "check-failed")
    if r.returncode == 0:
        return _allow("no other active task claims it", "unclaimed")
    if r.returncode == 1:
        ids = TASK_RE.findall(r.stdout or "")
        if ids:
            return {"verdict": "deny", "reason": f"concord: {rel} is claimed by task {', '.join(dict.fromkeys(ids))}",
                    "rule": "claimed", "scope": "session"}
    tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or [""]
    return _allow(f"concord check answered exit {r.returncode} ({tail[0][:160]}): nothing is blocked", "check-failed")


def verdict(req: dict) -> dict:
    tool, data = req.get("tool"), req.get("input") if isinstance(req.get("input"), dict) else {}
    if tool not in WRITES:
        return _allow("not a write", "other-tools")
    path = data.get("file_path") or data.get("path")
    if not isinstance(path, str) or not path:
        return _allow("no path to check", "no-path")
    cwd = str(req.get("cwd") or os.getcwd())
    rel = _relative(path, cwd)
    if rel is None:
        return _allow("outside the project: Concord claims files of this repo", "outside-repo")
    task = str(os.environ.get("CONCORD_TASK") or "").strip()
    return check(rel, cwd, task)


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        answer = {"verdict": "pass", "reason": "nothing to take out", "rule": "pass"} if req.get("after") else verdict(req)
        sys.stdout.write(json.dumps({"id": req.get("id"), **answer}) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
