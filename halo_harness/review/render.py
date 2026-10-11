"""halo_harness.review.render -- the header line, the print-mode text and the
`--json` object for a `ReviewResult`.
"""

from __future__ import annotations

import json

from halo_harness.review.findings import Finding
from halo_harness.review.run import ReviewResult

_BADGE = {"CONFIRMED": "CONFIRMED", "PLAUSIBLE": "PLAUSIBLE", "DISMISSED": "DISMISSED"}


def format_cost(usd: float) -> str:
    return f"${usd:.2f}" if usd >= 0.01 or usd == 0 else f"${usd:.4f}"


def counts(result: ReviewResult) -> "tuple[int, int, int]":
    confirmed = sum(1 for f in result.findings if f.verdict == "CONFIRMED")
    plausible = sum(1 for f in result.findings if f.verdict == "PLAUSIBLE")
    return len(result.findings), confirmed, plausible


def header_line(result: ReviewResult) -> str:
    total, confirmed, plausible = counts(result)
    word = "finding" if total == 1 else "findings"
    reviewers = len(result.reviewers)
    return (f"{total} {word} ({confirmed} confirmed, {plausible} plausible) from {reviewers} "
            f"reviewer{'' if reviewers == 1 else 's'} in {result.elapsed_s:.0f} s, {format_cost(result.cost_usd)}")


def location(f: Finding) -> str:
    if not f.file:
        return "(no file)"
    return f"{f.file}:{f.line}" if f.line else f.file


def finding_text(f: Finding, index: int) -> str:
    lines = [f"{index}. [{f.severity}] {location(f)}  {_BADGE.get(f.verdict, f.verdict)}  ({f.category})",
             f"   {f.short_summary}"]
    if f.summary and f.summary != f.short_summary:
        lines += [f"   {ln}" for ln in f.summary.splitlines()]
    if f.failure_scenario:
        lines.append(f"   Failure scenario: {f.failure_scenario}")
    if f.reason:
        lines.append(f"   Judge: {f.reason}")
    if f.outcome:
        lines.append(f"   Fix: {f.outcome}" + (f" -- {f.fix_note}" if f.fix_note else ""))
    return "\n".join(lines)


def render_text(result: ReviewResult) -> str:
    out = [f"Review of {result.target.label}", header_line(result), ""]
    if not result.findings:
        out.append("No findings.")
    out += [finding_text(f, i) for i, f in enumerate(result.findings, 1)]
    failed = [r for r in result.reviewers if not r.get("ok")]
    if failed:
        out += ["", "Reviewers that did not finish:"]
        out += [f"  {r['dimension']} ({r['part']}): {r.get('error')}" for r in failed]
    if result.dismissed:
        out += ["", f"{len(result.dismissed)} finding(s) dismissed by the judge (see --json for the reasons)."]
    out += [""] + [f"Note: {n}" for n in result.notes] if result.notes else []
    return "\n".join(out).rstrip() + "\n"


def to_json(result: ReviewResult) -> dict:
    obj = {"target": result.target.to_json(), "findings": [f.to_dict() for f in result.findings],
           "dismissed": [f.to_dict() for f in result.dismissed], "reviewers": list(result.reviewers),
           "cost_usd": result.cost_usd, "elapsed_s": result.elapsed_s}
    if result.notes:
        obj["notes"] = list(result.notes)
    return obj


def render_json(result: ReviewResult) -> str:
    return json.dumps(to_json(result), indent=2, ensure_ascii=False)
