"""halo_harness.ext.testing -- a pack's tests (extension API 1.1, stable since Halo 3.3.12.0 R4; docs/EXTENSION_API.md
"The stable surface", docs/PACK-AUTHORING.md "Testing"). `halo pack test` is this module's `run`; a pack's own
`tests/pack_test.py` imports it to run the same checks and add its own.

    report = testing.run(folder, kinds=None, timeout_s=10)   every check in a scratch home and project: the manifest,
                                                             the doctor on an installed copy, each kind's checks;
                                                             never a model call, never the network
    report.add(file, what, ok, fix="")                       a check of the pack's own (ok: True, False, or None: skipped)
    report.ok / .exit_code / .text() / .lines() / .result() / .as_json() / .checks / .passed / .failed / .skipped
    testing.manifest(folder) -> dict                         pack.yaml as read ({} when it does not read)
    testing.ask_policy(folder, policy_id, tool, tool_input, mode=None, timeout_s=10) -> the policy's answer
                                                             (a dict: verdict, reason, rule; or {error}) for one call

A failure reads `<file>: <what> -- <fix>`; a skipped check `skip <file>: <what>` (and why); the last line is
`RESULT: N checks, N passed, N failed` (", N skipped" when some were). The scratch home is a fresh folder for each
`run`, removed after; the checks run in a process of their own (halo_harness.packs.test_run) that ends before `run`
returns.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

__all__ = ["Report", "run", "manifest", "ask_policy"]
SCRUB = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "OPENAI_", "BRIDGE_", "HALO_", "CLAUDE_", "ROLO_CLAUDE_",
         "TYPESAFE_", "GEMINI_", "GOOGLE_API")


class Report:
    def __init__(self, pack: str = "", checks=None):
        self.pack = pack
        self.checks: "list[dict]" = list(checks or [])

    def add(self, file, what, ok, fix: str = "", kind: str = "own") -> "Report":
        self.checks.append({"kind": kind, "file": str(file), "what": str(what),
                            "ok": None if ok is None else bool(ok), "fix": str(fix or "")})
        return self

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c["ok"] is True)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if c["ok"] is False)

    @property
    def skipped(self) -> int:
        return sum(1 for c in self.checks if c["ok"] is None)

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.passed > 0

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1

    def result(self) -> str:
        return (f"RESULT: {len(self.checks)} checks, {self.passed} passed, {self.failed} failed"
                + (f", {self.skipped} skipped" if self.skipped else ""))

    def lines(self, *, passed: bool = False) -> "list[str]":
        out = [f"{c['file']}: {c['what']} -- {c['fix'] or 'see the pack docs'}" for c in self.checks if c["ok"] is False]
        out += [f"skip {c['file']}: {c['what']}" + (f" -- {c['fix']}" if c["fix"] else "") for c in self.checks
                if c["ok"] is None]
        out += [f"ok   {c['file']}: {c['what']}" for c in self.checks if passed and c["ok"] is True]
        return out

    def text(self, *, passed: bool = False) -> str:
        return "\n".join(self.lines(passed=passed) + [self.result()])

    def as_json(self) -> dict:
        return {"pack": self.pack, "ok": self.ok, "checks": self.checks, "passed": self.passed, "failed": self.failed,
                "skipped": self.skipped, "result": self.result()}


def _package_root() -> str:
    import halo_harness
    return str(Path(halo_harness.__file__).resolve().parent.parent)


def _env(home: Path) -> dict:
    from halo_harness.providers.config import tool_child_env
    env = {k: v for k, v in tool_child_env(dict(os.environ)).items() if not k.startswith(SCRUB)}
    env.update({"BRIDGE_TEST_HOME": str(home), "BRIDGE_TEST_NO_BACKGROUND_NET": "1", "HALO_OFFLINE": "1",
                "OLLAMA_HOST": "http://127.0.0.1:9", "HALO_PACK_TEST": "1", "PYTHONIOENCODING": "utf-8",
                "PYTHONPATH": os.pathsep.join([_package_root()] + [p for p in os.environ.get("PYTHONPATH", "").split(
                    os.pathsep) if p and p != _package_root()])})
    return env


def run(folder, kinds=None, timeout_s: float = 10.0) -> Report:
    """Every check of `halo pack test` on the pack in `folder`, in a scratch home of its own."""
    folder = Path(folder).resolve()
    home = Path(tempfile.mkdtemp(prefix="halo-pack-test-"))
    argv = [sys.executable, "-m", "halo_harness.packs.test_run", str(folder), "--timeout", str(timeout_s),
            "--kinds", ",".join(kinds or [])]
    try:
        (home / ".halo").mkdir()
        done = subprocess.run(argv, cwd=str(home), env=_env(home), capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=max(120.0, timeout_s * 30))
        last = [ln for ln in done.stdout.splitlines() if ln.startswith("{")]
        data = json.loads(last[-1]) if last else None
    except (subprocess.TimeoutExpired, OSError, ValueError) as e:
        data, done = None, None
        why = f"{type(e).__name__}: {e}"
    finally:
        shutil.rmtree(home, ignore_errors=True)
    if not isinstance(data, dict):
        tail = (done.stderr.strip().splitlines() or [""])[-1] if done is not None else why
        return Report(folder.name).add("pack.yaml", "halo pack test's checks did not finish", False, tail, kind="run")
    return Report(str(data.get("pack") or folder.name), data.get("checks") or [])


def manifest(folder) -> dict:
    from halo_harness.packs.manifest import load_manifest
    data, _problems = load_manifest(Path(folder))
    return data or {}


def ask_policy(folder, policy_id: str, tool: str, tool_input: dict, *, mode=None, timeout_s: float = 10.0) -> dict:
    """Start the pack's policy `policy_id` from `folder`, ask it about one call and stop it: its answer as a dict, or
    `{"error": "..."}`. Nothing is armed and no home is read: the policy runs as a session would start it."""
    from halo_harness.packs.interpreter import pack_env
    from halo_harness.packs.manifest_policy import entry, modes_of, run_argv
    root = Path(folder).resolve()
    e = entry(manifest(root), policy_id)
    if not isinstance(e, dict):
        return {"error": f"the pack declares no policy {policy_id!r}"}
    first = (modes_of(manifest(root)) or [{}])[0].get("id")
    req = {"id": "t1", "tool": tool, "input": tool_input, "cwd": str(root), "session": "pack-test", "agent": "",
           "mode": mode or first, "permission_mode": "default", "config": {}, "policy": policy_id}
    with tempfile.TemporaryDirectory(prefix="halo-pack-test-") as home:
        env = pack_env(root, {**_env(Path(home)), "CLAUDE_PLUGIN_ROOT": str(root), "HALO_POLICY_ID": policy_id})
        try:
            done = subprocess.run(run_argv(e, root), cwd=str(root), env=env, input=json.dumps(req) + "\n",
                                  capture_output=True, text=True, encoding="utf-8", timeout=timeout_s)
        except (subprocess.TimeoutExpired, OSError) as ex:
            return {"error": f"{type(ex).__name__}: {ex}"}
    for line in done.stdout.splitlines():
        try:
            got = json.loads(line)
        except ValueError:
            continue
        if isinstance(got, dict) and got.get("id") == "t1":
            return got
    return {"error": f"no answer (exit {done.returncode})"}
