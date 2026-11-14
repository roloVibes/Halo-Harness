"""halo_harness.crew.trial_run -- one Try it run: a real agent on a throwaway copy (Halo 3.6.0.0 R1).

`throwaway(cwd)` makes the copy: in a git repo a detached worktree of HEAD in a temp folder (`git worktree add
--detach`), else an empty temp folder; `drop(copy)` removes it (the worktree record too). `command(raw, request, ...)`
is `halo -p` as the agent itself (`--agents <its JSON> --agent <name>`), its careful mode as the permission mode (a
print run answers an ask with no: Try it does not wait for you, and the result lists each one), its money cap as
`--max-budget-usd`, and `--output-format stream-json`; `read(line, rec)` folds one stream-json line into the record.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from halo_harness import subprocess_safe as subprocess
from halo_harness.crew.spec import MODES, agents_json

TURNS = 30  # a Try it run's turns when the agent sets none


def _git(args: list, cwd) -> "subprocess.CompletedProcess":
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)


def throwaway(cwd) -> "tuple[Path, str, Path | None]":
    """(the folder the run works in, words for where it is, the repo whose worktree it is or None)."""
    from halo_harness.crew.store import repo_of
    base = Path(tempfile.mkdtemp(prefix="halo-try-"))
    repo = repo_of(cwd)
    if (repo / ".git").exists():
        copy = base / "copy"
        try:
            got = _git(["worktree", "add", "--detach", str(copy), "HEAD"], repo)
            if got.returncode == 0:
                return copy, f"a throwaway copy of {repo.name} (a git worktree of its last commit, removed after)", repo
        except (OSError, subprocess.SubprocessError):
            pass
    work = base / "work"
    work.mkdir()
    return work, "an empty throwaway folder (this project is not a git repo, so nothing of it is copied)", None


def drop(copy: Path, repo) -> None:
    if repo is not None:
        try:
            _git(["worktree", "remove", "--force", str(copy)], repo)
        except (OSError, subprocess.SubprocessError):
            pass
    shutil.rmtree(copy.parent, ignore_errors=True)
    if repo is not None:
        try:
            _git(["worktree", "prune"], repo)
        except (OSError, subprocess.SubprocessError):
            pass


def command(raw: dict, request: str, model: str) -> list:
    more = raw.get("more") or {}
    cmd = [sys.executable, "-m", "halo_harness", "-p", request, "--agents", json.dumps(agents_json(raw)),
           "--agent", str(raw.get("name")), "--permission-mode", MODES.get(raw.get("careful"), "default"),
           "--output-format", "stream-json", "--verbose",
           "--max-turns", str(more.get("max_turns") if isinstance(more.get("max_turns"), int) else TURNS)]
    if model:
        cmd += ["--model", model]
    if isinstance(more.get("max_usd"), (int, float)):
        cmd += ["--max-budget-usd", str(more["max_usd"])]
    return cmd


def spawn(cmd: list, cwd: Path) -> "subprocess.Popen":
    kw: dict = {}
    if os.name == "nt":
        kw["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kw["start_new_session"] = True
    root = str(Path(__file__).resolve().parents[2])  # the run uses this Halo's own code, wherever the copy sits
    env = {**os.environ, "HALO_TRY_RUN": "1", "PYTHONPATH": os.pathsep.join(p for p in (root, os.environ.get("PYTHONPATH", "")) if p)}
    return subprocess.Popen(cmd, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", env=env, **kw)


def kill(proc: "subprocess.Popen") -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=20)
        else:
            import signal
            os.killpg(proc.pid, signal.SIGTERM)
    except (OSError, subprocess.SubprocessError):
        proc.kill()


def read(line: str, rec: dict) -> bool:
    """Fold one stream-json line into `rec`; True when it changed something the page shows."""
    try:
        ev = json.loads(line)
    except ValueError:
        return False
    if not isinstance(ev, dict):
        return False
    if ev.get("type") == "assistant":
        changed = False
        for block in ((ev.get("message") or {}).get("content") or []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                name = str(block.get("name") or "?")
                rec["used"][name] = rec["used"].get(name, 0) + 1
                changed = True
            elif isinstance(block, dict) and block.get("type") == "text" and str(block.get("text") or "").strip():
                rec["now"] = " ".join(str(block["text"]).split())[:200]
                changed = True
        return changed
    if ev.get("type") == "result":
        rec["reply"] = str(ev.get("result") or "")
        rec["cost_usd"] = ev.get("total_cost_usd")
        rec["turns"] = ev.get("num_turns")
        rec["model"] = ev.get("model") or rec.get("model")
        rec["denied"] = [f"{d.get('tool_name')}: {str(d.get('reason') or '')[:160]}" for d in ev.get("permission_denials") or []
                         if isinstance(d, dict)]
        rec["is_error"] = bool(ev.get("is_error"))
        return True
    return False
