"""halo_harness.orchestra.gate -- the tests, the record check and the gate.

* `run_tests(run_dir, goal, cwd)` runs the goal's `test` command in `cwd`
  with the scrubbed tool-child environment (providers/config.py
  `tool_child_env`), stops it after `goal.test_timeout_s` seconds (default
  600; the whole process tree), and keeps the last lines of its output.
* `record_equals_disk(run_dir, lanes, ref)`: every claimed unit's text on
  the finished branch equals the lane's last `written` snapshot. A unit in
  a file whose merge conflict the judge resolved may differ; it is listed
  with `judge: true` and still counts as equal.
* `quality_gate(run_dir, goal, lanes, cwd)`: the tests on the finished
  branch decide. Failing tests send back every lane whose unit names
  appear in the output (at most `return_cap` times each); a lane at its
  cap, or a failure that names no lane, stops the run with the reason.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import gitops, jsonl
from halo_harness.orchestra.goal import repo_root_of
from halo_harness.orchestra.lanes import unit_text

TAIL_LINES = 40
_STRIP_PREFIXES = ("HALO_ORCHESTRA_",)


@dataclass
class TestResult:
    ok: bool
    returncode: Optional[int]
    tail: str
    command: str
    timed_out: bool = False
    duration_s: float = 0.0
    passed: Optional[int] = None
    failing: Optional[list] = None     # names of failing tests, when the output lists them

    def to_dict(self) -> dict:
        return asdict(self)

    def no_worse_than(self, before: "TestResult") -> bool:
        """Passing, or failing only tests that already failed in `before`
        (a merge in the middle of the sequence, while later pieces are
        still unwritten). Unreadable output counts as worse."""
        if self.ok:
            return True
        if self.timed_out or self.failing is None or before.failing is None:
            return False
        return bool(self.failing) and set(self.failing) <= set(before.failing)


@dataclass
class GateResult:
    ok: bool
    tests: TestResult
    record_ok: bool
    record: list = field(default_factory=list)
    back: list = field(default_factory=list)      # lane numbers sent back to their workers
    stop_reason: str = ""

    def to_dict(self) -> dict:
        return dict(asdict(self), tests=self.tests.to_dict())


def _child_env() -> dict:
    from halo_harness.providers.config import tool_child_env
    env = tool_child_env(dict(os.environ))
    return {k: v for k, v in env.items() if not k.startswith(_STRIP_PREFIXES)}


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=30)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def passed_count(output: str) -> Optional[int]:
    """Tests that passed, read from a unittest or pytest summary; None when
    the output has neither."""
    ran = re.findall(r"^Ran (\d+) tests? in", output, re.M)
    if ran:
        total = int(ran[-1])
        summary = re.findall(r"^FAILED \(([^)]*)\)", output, re.M)
        bad = 0
        if summary:
            for name, num in re.findall(r"(failures|errors)=(\d+)", summary[-1]):
                bad += int(num)
        return max(0, total - bad)
    passed = re.findall(r"(\d+) passed", output)
    if passed:
        return int(passed[-1])
    if re.search(r"\d+ (failed|error)", output):
        return 0
    return None


def failing_tests(output: str) -> Optional[list]:
    """Failing test names from unittest (`FAIL: test_x (mod.Class)`) or pytest
    (`FAILED path::test_x`) output; None when the run printed no summary."""
    names = re.findall(r"^(?:FAIL|ERROR): (\S+ \([^)]*\))", output, re.M)
    names += re.findall(r"^(?:FAILED|ERROR) (\S+::\S+)", output, re.M)
    if names:
        return sorted(set(names))
    return [] if passed_count(output) is not None else None


def run_tests(run_dir, goal, cwd, *, timeout_s: Optional[int] = None) -> TestResult:
    """The goal's test command in `cwd`. No command counts as passing."""
    command = str(getattr(goal, "test", "") or "").strip()
    if not command:
        return TestResult(True, 0, "(no test command in the goal)", "", passed=None)
    timeout = int(timeout_s or getattr(goal, "test_timeout_s", 600) or 600)
    kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32" else \
        {"start_new_session": True}
    started = time.monotonic()
    timed_out = False
    with tempfile.TemporaryFile() as out:
        try:
            proc = subprocess.Popen(command, shell=True, cwd=str(cwd), stdout=out, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, env=_child_env(), **kwargs)
        except OSError as e:
            return TestResult(False, None, f"could not start the tests: {e}", command)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_tree(proc)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
        out.seek(0)
        text = out.read().decode("utf-8", errors="replace")
    lines = text.replace("\r\n", "\n").splitlines()
    tail = "\n".join(lines[-TAIL_LINES:])
    if timed_out:
        tail += f"\n(the tests ran past {timeout}s and were stopped)"
    rc = None if timed_out else proc.returncode
    return TestResult(ok=(rc == 0), returncode=rc, tail=tail, command=command, timed_out=timed_out,
                      duration_s=round(time.monotonic() - started, 3), passed=passed_count(text),
                      failing=failing_tests(text))


def _judged_files(run_dir) -> set:
    merge = jsonl.read_json(Path(run_dir) / "merge.json", {}) or {}
    return {(c.get("lane"), c.get("file")) for c in merge.get("conflicts") or [] if c.get("tests_ok")}


def record_equals_disk(run_dir, lanes: list, ref: Optional[str] = None) -> tuple:
    """`(ok, rows)`: one row per snapshotted unit `{lane, key, equal, judge}`."""
    run_dir = Path(run_dir)
    repo = repo_root_of(run_dir)
    ref = ref or gitops.finished_branch(run_dir.name)
    judged = _judged_files(run_dir)
    rows, ok, cache = [], True, {}
    for lane in lanes:
        written = lane.written
        for key in lane.job.claims:
            rel = key.split("#", 1)[0]
            if rel not in cache:
                cache[rel] = gitops.show(repo, ref, rel)
            content = cache[rel]
            final = unit_text(content, rel, key) if content is not None else None
            snap = written.get(key)
            equal = snap is not None and final == snap
            judge = (lane.n, rel) in judged
            if not equal and not judge:
                ok = False
            rows.append({"lane": lane.n, "key": key, "equal": equal, "judge": judge and not equal,
                         "snapshot": snap is not None})
    return ok, rows


def unit_names(lane) -> list:
    return [key.split("#", 1)[1].split(".")[-1] for key in lane.job.claims if "#" in key]


def _narrow(blamed: list) -> list:
    """Drop a named lane whose own code calls another named lane's unit
    (its failure is explained by that one: `total` calls `subtotal`);
    every named lane stays when that would drop them all."""
    keep = []
    for lane in blamed:
        text = "\n".join(lane.written.values())
        calls_other = any(re.search(rf"(?<![\w.]){re.escape(name)}\(", text)
                          for other in blamed if other.n != lane.n for name in unit_names(other))
        if not calls_other:
            keep.append(lane)
    return keep or blamed


def quality_gate(run_dir, goal, lanes: list, cwd, *, ref: Optional[str] = None) -> GateResult:
    """Tests on the finished branch, the record check, and the loop decision."""
    tests = run_tests(run_dir, goal, cwd)
    record_ok, record = record_equals_disk(run_dir, lanes, ref)
    if tests.ok:
        return GateResult(True, tests, record_ok, record)
    blamed = _narrow([lane for lane in lanes
                      if any(re.search(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", tests.tail)
                             for name in unit_names(lane))])
    if not blamed:
        why = "ran past the timeout" if tests.timed_out else "fail"
        return GateResult(False, tests, record_ok, record,
                          stop_reason=f"the tests {why} on the finished branch and the output names no "
                                      f"worker's unit: {tests.tail.splitlines()[-1] if tests.tail else ''}")
    capped = [lane for lane in blamed if lane.pieces_returned >= goal.return_cap]
    if capped:
        names = ", ".join(str(lane.n) for lane in capped)
        return GateResult(False, tests, record_ok, record,
                          stop_reason=f"lane {names} reached the return cap ({goal.return_cap}) and the tests "
                                      "still fail on the finished branch")
    return GateResult(False, tests, record_ok, record, back=[lane.n for lane in blamed])
