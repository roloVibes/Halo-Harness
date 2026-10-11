"""halo_harness.review.run -- one review: resolve the target, run the dimension
reviewers in parallel, verify, rank, optionally fix.

`run_review(runtime, options)` is the single entry point; the CLI, the
`/review` slash command and the tests all call it. It reports; it never gates
or commits anything.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from halo_harness.review.agents import aborted, next_tool_id, reviewer_name, review_runtime, run_child, run_jobs
from halo_harness.review.dimensions import DEFAULT_LEVEL, DIMENSIONS, LEVELS, reviewer_prompt
from halo_harness.review.findings import Finding, parse_findings
from halo_harness.review.target import resolve_target
from halo_harness.review.target_model import ReviewTarget

_REPAIR = "Your reply could not be parsed. Output only the JSON array of findings, in one fenced json block."


@dataclass
class ReviewOptions:
    target: "list[str]" = field(default_factory=list)
    level: str = DEFAULT_LEVEL
    dimensions: "list[str]" = field(default_factory=lambda: list(DIMENSIONS))
    fix: bool = False
    verify: bool = True


@dataclass
class ReviewResult:
    target: ReviewTarget
    findings: "list[Finding]" = field(default_factory=list)
    dismissed: "list[Finding]" = field(default_factory=list)
    reviewers: "list[dict]" = field(default_factory=list)
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    options: ReviewOptions = field(default_factory=ReviewOptions)
    notes: "list[str]" = field(default_factory=list)
    aborted: bool = False


def _run_reviewer(rt, dim: str, shard, options: ReviewOptions, target: ReviewTarget, sink) -> "tuple[dict, list]":
    t0 = time.monotonic()
    info = {"dimension": dim, "part": shard.label, "ok": True, "findings": 0, "error": None, "elapsed_s": 0.0}
    prompt = reviewer_prompt(dim, shard, options.level, target_label=target.label, kind=target.kind)
    desc = f"review {dim}" + (f" ({shard.label})" if shard.total > 1 else "")
    res = run_child(rt, subagent=reviewer_name(dim), prompt=prompt, description=desc,
                    tool_id=next_tool_id("review"), sink=sink)
    found: Optional[list] = None
    if res.aborted:
        info.update(ok=False, error="interrupted")
    elif res.is_error:
        info.update(ok=False, error=res.text[:300] or "the reviewer did not finish")
    else:
        found = parse_findings(res.text, dim)
        if found is None and res.task_id:      # repair once: ask again for only the JSON
            again = run_child(rt, subagent=reviewer_name(dim), prompt=_REPAIR, description=desc,
                              tool_id=next_tool_id("review"), sink=sink, task_id=res.task_id)
            found = None if again.is_error else parse_findings(again.text, dim)
        if found is None:
            info.update(ok=False, error="the reply held no parsable findings")
    found = found or []
    found = found[:LEVELS[options.level]]
    info["findings"] = len(found)
    info["elapsed_s"] = round(time.monotonic() - t0, 2)
    return info, found


def run_review(runtime, options: ReviewOptions, *, sink: Optional[Callable] = None,
               progress: Optional[Callable[[str], None]] = None) -> ReviewResult:
    """Raises `TargetError` when the target cannot be resolved. `sink` receives
    the sub-agent events the TUI needs; `progress` receives short status lines."""
    from halo_harness.review.verify import dedupe, rank, verify_findings
    note = progress or (lambda _msg: None)
    parent = runtime.parent
    target = resolve_target(options.target, Path(parent.cwd))
    t0, cost0 = time.monotonic(), float(parent.cost_meter.total_usd or 0.0)
    rt = review_runtime(runtime, options.dimensions)
    result = ReviewResult(target=target, options=options)

    shards = target.shards()
    jobs = [(dim, shard) for shard in shards for dim in options.dimensions]
    note(f"{len(jobs)} reviewer(s) on {target.label} ({len(target.files)} file(s))")
    outs = run_jobs(rt, [lambda d=d, s=s: _run_reviewer(rt, d, s, options, target, sink) for d, s in jobs])
    raw: "list[Finding]" = []
    for (dim, shard), out in zip(jobs, outs):
        if isinstance(out, Exception):
            result.reviewers.append({"dimension": dim, "part": shard.label, "ok": False, "findings": 0,
                                     "error": f"{type(out).__name__}: {out}", "elapsed_s": 0.0})
            continue
        info, found = out
        result.reviewers.append(info)
        raw.extend(found)

    if options.verify and raw and not aborted(rt):
        note(f"verifying {len(raw)} finding(s)")
        kept, result.dismissed = verify_findings(rt, target, raw, sink=sink)
    else:
        kept = raw
        if raw and options.verify:
            result.notes.append("interrupted before verification; findings left PLAUSIBLE")
    result.findings = rank(dedupe(kept))

    if options.fix and not options.verify:
        result.notes.append("--fix needs verification (a fix is applied only to a CONFIRMED finding); skipped")
    elif options.fix and not aborted(rt):
        from halo_harness.review.fix import fix_findings
        todo = [f for f in result.findings if f.verdict == "CONFIRMED"]
        note(f"fixing {len(todo)} confirmed finding(s)")
        fix_findings(rt, target, result.findings, sink=sink)
    result.aborted = aborted(rt)
    result.elapsed_s = round(time.monotonic() - t0, 2)
    result.cost_usd = round(max(0.0, float(parent.cost_meter.total_usd or 0.0) - cost0), 6)
    return result
