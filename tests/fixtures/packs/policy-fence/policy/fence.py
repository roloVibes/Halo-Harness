"""The policy-fence pack's policy hook (docs/EXTENSION_API.md "Policy hooks"): Halo starts this once when the
policy is armed and keeps it running; it reads one JSON request per line on stdin and writes one JSON answer per
line on stdout, the request's id in it.

    request  {"id": "r1", "tool": "Write", "input": {"file_path": "/tmp/x", "content": "..."}, "cwd": "/repo",
              "session": "...", "agent": "", "mode": "fenced", "permission_mode": "default", "config": {}}
    answer   {"id": "r1", "verdict": "deny", "reason": "outside the project", "rule": "outside-project"}

A Write or Edit whose path is outside `cwd` (the project folder) is denied; every other call is allowed. A
post-call request (3.3.10.0 R2: `"after": true` with the tool's `result`, for a policy that declares `after: true`)
is answered pass. Plain Python, nothing of Halo imported. The HALO_POLICY_TEST_* variables are the tests' seams (a
slow answer, a bad line, an echo of the input, an exit before answering, ask instead of deny, and after the call a
word to redact or a drop); nothing outside the tests sets them.
"""

import json
import os
import sys
import time

WRITES = ("Write", "Edit", "NotebookEdit")


def _inside(path: str, cwd: str) -> bool:
    full = os.path.normcase(os.path.abspath(os.path.join(cwd, path)))
    root = os.path.normcase(os.path.abspath(cwd))
    try:
        return os.path.commonpath([full, root]) == root
    except ValueError:  # another drive on Windows
        return False


def verdict(req: dict) -> dict:
    tool, data = req.get("tool"), req.get("input") if isinstance(req.get("input"), dict) else {}
    if os.environ.get("HALO_POLICY_TEST_ECHO"):
        return {"verdict": "allow", "reason": json.dumps(data, sort_keys=True), "rule": "echo"}
    if tool not in WRITES:
        return {"verdict": "allow", "reason": "not a write", "rule": "other-tools"}
    path = data.get("file_path") or data.get("path") or data.get("notebook_path")
    if not isinstance(path, str) or not path:
        return {"verdict": "allow", "reason": "no path to check", "rule": "no-path"}
    if _inside(path, str(req.get("cwd") or os.getcwd())):
        return {"verdict": "allow", "reason": "inside the project", "rule": "inside-project"}
    if os.environ.get("HALO_POLICY_TEST_ASK"):
        return {"verdict": "ask", "reason": "outside the project", "rule": "outside-project"}
    return {"verdict": "deny", "reason": "outside the project", "rule": "outside-project", "scope": "session"}


def after(req: dict) -> dict:
    """The post-call verdict: pass, or (the tests' seams) a drop, or a redact of one word."""
    text = req.get("result") if isinstance(req.get("result"), str) else ""
    if os.environ.get("HALO_POLICY_TEST_DROP"):
        return {"verdict": "drop", "reason": "the result stays out of the session", "rule": "drop-all"}
    word = os.environ.get("HALO_POLICY_TEST_REDACT")
    if word and word in text:
        return {"verdict": "redact", "reason": "a held word was taken out", "rule": "redact-word",
                "result": text.replace(word, "[held]")}
    return {"verdict": "pass", "reason": "nothing to take out", "rule": "pass"}


def main() -> int:
    slow = int(os.environ.get("HALO_POLICY_TEST_SLOW_MS") or 0)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        if os.environ.get("HALO_POLICY_TEST_EXIT"):
            return 3
        if slow:
            time.sleep(slow / 1000.0)  # the tests' seam for a late answer
        if os.environ.get("HALO_POLICY_TEST_BAD"):
            sys.stdout.write("this is not json\n")
        else:
            answer = after(req) if req.get("after") else verdict(req)
            sys.stdout.write(json.dumps({"id": req.get("id"), **answer}) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
