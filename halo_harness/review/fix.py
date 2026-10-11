"""halo_harness.review.fix -- `--fix`: one `coder` sub-agent per CONFIRMED
finding applies a minimal fix in the working tree (never committing), then the
judge re-verifies the finding against the new state of the file.

Fixes run one after another so two fixes never edit the same file at once.
Outcome per finding: `fixed` (the file changed and the judge no longer finds
the problem), `no_change_needed`, or `skipped` (with a note saying why).
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Callable, Optional

from halo_harness.review.agents import FIXER_NAME, aborted, next_tool_id, run_child
from halo_harness.review.findings import Finding, parse_fix_outcome
from halo_harness.review.target_model import ReviewTarget
from halo_harness.review.verify import finding_payload, judge_one

_REPAIR = ('Your reply held no JSON outcome. Output only {"outcome": "fixed" | "skipped" | "no_change_needed", '
           '"note": "..."} in one fenced json block.')


def _file_state(cwd: Path, rel: str) -> Optional[str]:
    try:
        return hashlib.sha256((cwd / rel).read_bytes()).hexdigest()
    except OSError:
        return None


def _current_excerpt(cwd: Path, rel: str, limit: int = 12_000) -> str:
    """The file's changes against HEAD, or its numbered content outside a repo."""
    try:
        r = subprocess.run(["git", "diff", "--no-color", "--no-ext-diff", "-U3", "HEAD", "--", rel], cwd=str(cwd),
                           capture_output=True, timeout=60)
        text = r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        text = ""
    if not text.strip():
        try:
            lines = (cwd / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            text = "".join(f"{i:>5}| {ln}\n" for i, ln in enumerate(lines, 1))
        except OSError:
            text = "(file not readable)"
    return text[:limit] + ("\n... [truncated]\n" if len(text) > limit else "")


def fixer_prompt(f: Finding, target: ReviewTarget) -> str:
    return "\n".join([f"Review target: {target.label}", f"Working tree: {target.cwd or '.'}",
                      "CONFIRMED finding to fix:", finding_payload(f), f"Judge's reason: {f.reason or '(none)'}",
                      "<diff>", target.excerpt_for(f.file), "</diff>"])


def fix_one(rt, f: Finding, target: ReviewTarget, *, sink: Optional[Callable] = None) -> None:
    """Sets `f.outcome` and `f.fix_note`; never raises."""
    cwd = Path(target.cwd or rt.parent.cwd)
    desc = f"fix {f.file}:{f.line or '?'}"
    before = _file_state(cwd, f.file)
    res = run_child(rt, subagent=FIXER_NAME, prompt=fixer_prompt(f, target), description=desc,
                    tool_id=next_tool_id("review-fix"), sink=sink)
    if res.aborted:
        f.outcome, f.fix_note = "skipped", "interrupted before the fix finished"
        return
    if res.is_error:
        f.outcome, f.fix_note = "skipped", f"the fixer did not finish: {res.text[:200]}"
        return
    outcome, note = parse_fix_outcome(res.text)
    if note.startswith("the fixer's reply held no JSON") and res.task_id:
        again = run_child(rt, subagent=FIXER_NAME, prompt=_REPAIR, description=desc,
                          tool_id=next_tool_id("review-fix"), sink=sink, task_id=res.task_id)
        if not again.is_error:
            outcome, note = parse_fix_outcome(again.text)
    f.outcome, f.fix_note = outcome, note
    if outcome != "fixed":
        return
    if _file_state(cwd, f.file) == before:
        f.outcome, f.fix_note = "skipped", "the fixer reported a fix but the file did not change"
        return
    verdict, reason = judge_one(rt, f, target, sink=sink, excerpt=_current_excerpt(cwd, f.file),
                                after_fix=True, label="re-verify")
    if verdict == "DISMISSED":
        f.fix_note = (f"{note} Re-verified: {reason}").strip()
    else:
        f.outcome = "skipped"
        f.fix_note = f"fix applied but re-verification still reports the problem ({verdict}): {reason}"


def fix_findings(rt, target: ReviewTarget, findings: "list[Finding]", *, sink: Optional[Callable] = None) -> None:
    for f in findings:
        if f.verdict != "CONFIRMED":
            continue
        if aborted(rt):
            f.outcome, f.fix_note = "skipped", "interrupted"
            continue
        try:
            fix_one(rt, f, target, sink=sink)
        except Exception as e:
            f.outcome, f.fix_note = "skipped", f"fix failed: {type(e).__name__}: {e}"
