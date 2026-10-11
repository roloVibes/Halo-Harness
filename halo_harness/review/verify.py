"""halo_harness.review.verify -- the judge pass, dedup and ranking.

Every finding goes to the `judge` role with the diff excerpt for its file; the
judge answers CONFIRMED, PLAUSIBLE or DISMISSED with a reason. Dismissed
findings are set aside (kept for `--json`), the rest are deduplicated and
ranked severity-first, then verdict.
"""

from __future__ import annotations

import json
from typing import Callable, Optional

from halo_harness.review.agents import JUDGE_NAME, next_tool_id, run_child, run_jobs
from halo_harness.review.findings import Finding, parse_verdict
from halo_harness.review.target_model import ReviewTarget

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
_VERDICT_RANK = {"CONFIRMED": 0, "PLAUSIBLE": 1, "DISMISSED": 2}
_REPAIR = ("Your reply could not be parsed. Output only the JSON object "
           '{"verdict": "CONFIRMED" | "PLAUSIBLE" | "DISMISSED", "reason": "..."} in one fenced json block.')


def finding_payload(f: Finding) -> str:
    return json.dumps({"file": f.file, "line": f.line, "severity": f.severity, "category": f.category,
                       "short_summary": f.short_summary, "summary": f.summary,
                       "failure_scenario": f.failure_scenario}, indent=2)


def judge_prompt(f: Finding, target: ReviewTarget, *, excerpt: Optional[str] = None, after_fix: bool = False) -> str:
    lines = [f"Review target: {target.label}", "Finding to judge:", finding_payload(f)]
    if after_fix:
        lines.append("A fix was just applied to the working tree. Decide whether the problem described above "
                     "is STILL present in the code as it is now: CONFIRMED = still present, PLAUSIBLE = "
                     "probably still present, DISMISSED = resolved.")
        label = "Current changes to the file"
    else:
        label = "Diff excerpt for the file"
    body = excerpt if excerpt is not None else target.excerpt_for(f.file)
    lines += [f"{label} ({f.file or 'unknown file'}):", "<diff>", body or "(empty)", "</diff>"]
    return "\n".join(lines)


def judge_one(rt, f: Finding, target: ReviewTarget, *, sink=None, excerpt: Optional[str] = None,
              after_fix: bool = False, label: str = "verify") -> "tuple[str, str]":
    """`(verdict, reason)` for one finding; a judge that errors or cannot be
    parsed leaves the finding PLAUSIBLE with the reason saying so."""
    desc = f"{label} {f.file}:{f.line or '?'}"
    res = run_child(rt, subagent=JUDGE_NAME, prompt=judge_prompt(f, target, excerpt=excerpt, after_fix=after_fix),
                    description=desc, tool_id=next_tool_id("review-judge"), sink=sink)
    if res.aborted:
        return "PLAUSIBLE", "interrupted before the judge finished"
    if res.is_error:
        return "PLAUSIBLE", f"the judge did not finish: {res.text[:200]}"
    parsed = parse_verdict(res.text)
    if parsed is None and res.task_id:
        again = run_child(rt, subagent=JUDGE_NAME, prompt=_REPAIR, description=desc,
                          tool_id=next_tool_id("review-judge"), sink=sink, task_id=res.task_id)
        parsed = None if again.is_error else parse_verdict(again.text)
    if parsed is None:
        return "PLAUSIBLE", "the judge's reply could not be parsed"
    return parsed


def verify_findings(rt, target: ReviewTarget, findings: "list[Finding]", *,
                    sink: Optional[Callable] = None) -> "tuple[list[Finding], list[Finding]]":
    """`(kept, dismissed)` -- every finding gets a verdict and a reason."""
    def job(f: Finding) -> Callable:
        return lambda: judge_one(rt, f, target, sink=sink)

    outcomes = run_jobs(rt, [job(f) for f in findings])
    kept, dismissed = [], []
    for f, out in zip(findings, outcomes):
        if isinstance(out, Exception):
            f.verdict, f.reason = "PLAUSIBLE", f"verification failed: {type(out).__name__}: {out}"
        else:
            f.verdict, f.reason = out
        (dismissed if f.verdict == "DISMISSED" else kept).append(f)
    return kept, dismissed


def dedupe(findings: "list[Finding]") -> "list[Finding]":
    """Same file + line + category is one finding: the higher severity wins
    (then the better verdict) and the summaries are merged."""
    merged: "dict[tuple, Finding]" = {}
    for f in findings:
        cur = merged.get(f.key())
        if cur is None:
            merged[f.key()] = f
            continue
        keep, other = (f, cur) if _order(f) < _order(cur) else (cur, f)
        if other.summary and other.summary not in keep.summary:
            keep.summary = f"{keep.summary}\n{other.summary}".strip()
        if other.failure_scenario and not keep.failure_scenario:
            keep.failure_scenario = other.failure_scenario
        for d in other.dimensions:
            if d not in keep.dimensions:
                keep.dimensions.append(d)
        merged[f.key()] = keep
    return list(merged.values())


def _order(f: Finding) -> tuple:
    return (_SEVERITY_RANK.get(f.severity, 1), _VERDICT_RANK.get(f.verdict, 1))


def rank(findings: "list[Finding]") -> "list[Finding]":
    """Severity first (high, medium, low), then verdict (CONFIRMED before
    PLAUSIBLE), then file and line for a stable order."""
    return sorted(findings, key=lambda f: (*_order(f), f.file, f.line or 0))
