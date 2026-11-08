"""__NAME__'s policy hook `guard` (pack.yaml contributes.policy; docs/EXTENSION_API.md "Policy hooks"). Halo starts it
once while the `careful` mode is on (`halo pack mode __ID__ careful on`, with the hooks grant) and asks it about every
Write and Edit before the call runs: one JSON request per line on stdin, one JSON answer per line on stdout.

    request  {"id": "r1", "tool": "Write", "input": {"file_path": "...", "content": "..."}, "cwd": "/repo", ...}
    answer   {"id": "r1", "verdict": "deny", "reason": "a file under .git/", "rule": "no-git-dir"}

The rule: a write to a file under a `.git/` folder is denied, every other call is allowed. Plain Python, nothing of
Halo imported; `on_error: allow` in pack.yaml means a slow or broken guard blocks nothing.
"""

import json
import sys


def verdict(req: dict) -> dict:
    data = req.get("input") if isinstance(req.get("input"), dict) else {}
    path = str(data.get("file_path") or data.get("path") or "")
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    if ".git" in parts[:-1]:
        return {"verdict": "deny", "reason": "a file under .git/", "rule": "no-git-dir"}
    if req.get("after"):  # a post-call request (only for a policy that declares after: true)
        return {"verdict": "pass", "reason": "nothing to change", "rule": "pass"}
    return {"verdict": "allow", "reason": "not under .git/", "rule": "other-files"}


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        print(json.dumps({"id": req.get("id"), **verdict(req)}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
