"""halo_harness.review.findings -- the typed finding, and tolerant parsing of a
reviewer's or judge's reply.

Field names follow the ReportFindings contract: file, line, short_summary,
summary, failure_scenario, verdict, category, severity, outcome.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

SEVERITIES = ("high", "medium", "low")
VERDICTS = ("CONFIRMED", "PLAUSIBLE", "DISMISSED")
OUTCOMES = ("fixed", "skipped", "no_change_needed")

_SEVERITY_ALIASES = {"critical": "high", "blocker": "high", "major": "high", "error": "high",
                     "moderate": "medium", "warning": "medium", "warn": "medium",
                     "minor": "low", "info": "low", "nit": "low", "style": "low"}
_FENCE = re.compile(r"```[A-Za-z0-9_-]*[ \t]*\r?\n(.*?)```", re.DOTALL)


@dataclass
class Finding:
    file: str = ""
    line: Optional[int] = None
    severity: str = "medium"
    category: str = "other"
    short_summary: str = ""
    summary: str = ""
    failure_scenario: str = ""
    verdict: str = "PLAUSIBLE"
    reason: str = ""
    outcome: Optional[str] = None
    fix_note: str = ""
    dimensions: "list[str]" = field(default_factory=list)

    def key(self) -> tuple:
        return (self.file, self.line or 0, self.category)

    def to_dict(self) -> dict:
        d = {"file": self.file, "line": self.line, "short_summary": self.short_summary, "summary": self.summary,
             "failure_scenario": self.failure_scenario, "verdict": self.verdict, "category": self.category,
             "severity": self.severity, "outcome": self.outcome, "reason": self.reason,
             "dimensions": list(self.dimensions)}
        if self.fix_note:
            d["fix_note"] = self.fix_note
        return d


def normalize_severity(value) -> str:
    s = str(value or "").strip().lower()
    if s in SEVERITIES:
        return s
    return _SEVERITY_ALIASES.get(s, "medium")


def _to_line(value) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    m = re.match(r"\s*(\d+)", str(value or ""))
    return int(m.group(1)) if m and int(m.group(1)) > 0 else None


def extract_json(text: str):
    """The first JSON value found in `text`: fenced blocks first, then any
    array or object embedded in prose. Raises ValueError when there is none."""
    text = text or ""
    candidates = [m.group(1).strip() for m in _FENCE.finditer(text)] + [text.strip()]
    for cand in candidates:
        if not cand:
            continue
        try:
            return json.loads(cand)
        except ValueError:
            pass
    decoder = json.JSONDecoder()
    for source in candidates:
        for i, ch in enumerate(source):
            if ch in "[{":
                try:
                    value, _end = decoder.raw_decode(source[i:])
                except ValueError:
                    continue
                if isinstance(value, (list, dict)):
                    return value
    raise ValueError("no JSON value found in the reply")


def parse_findings(text: str, dimension: str = "") -> "Optional[list[Finding]]":
    """A list of findings (possibly empty), or None when the reply holds no
    parsable JSON array at all (the caller repairs once)."""
    try:
        value = extract_json(text)
    except ValueError:
        return None
    if isinstance(value, dict):
        inner = value.get("findings")
        value = inner if isinstance(inner, list) else [value] if value.get("summary") or value.get("short_summary") else None
    if not isinstance(value, list):
        return None
    out: "list[Finding]" = []
    for item in value:
        if not isinstance(item, dict):
            continue
        short = str(item.get("short_summary") or item.get("title") or "").strip()
        summary = str(item.get("summary") or item.get("description") or "").strip()
        if not (short or summary):
            continue
        out.append(Finding(
            file=str(item.get("file") or item.get("path") or "").strip(), line=_to_line(item.get("line")),
            severity=normalize_severity(item.get("severity")),
            category=str(item.get("category") or "other").strip().lower() or "other",
            short_summary=short or summary[:100], summary=summary or short,
            failure_scenario=str(item.get("failure_scenario") or "").strip(),
            dimensions=[dimension] if dimension else []))
    return out


def parse_verdict(text: str) -> "Optional[tuple[str, str]]":
    """`(VERDICT, reason)` from a judge reply, or None when unparsable."""
    try:
        value = extract_json(text)
    except ValueError:
        m = re.search(r"\b(CONFIRMED|PLAUSIBLE|DISMISSED)\b", text or "")
        return (m.group(1), "") if m else None
    if isinstance(value, list) and value and isinstance(value[0], dict):
        value = value[0]
    if not isinstance(value, dict):
        return None
    verdict = str(value.get("verdict") or "").strip().upper()
    if verdict not in VERDICTS:
        return None
    return verdict, str(value.get("reason") or "").strip()


def parse_fix_outcome(text: str) -> "tuple[str, str]":
    """`(outcome, note)` from a coder reply; unparsable replies count as skipped."""
    try:
        value = extract_json(text)
    except ValueError:
        return "skipped", "the fixer's reply held no JSON outcome"
    if isinstance(value, list) and value and isinstance(value[0], dict):
        value = value[0]
    if not isinstance(value, dict):
        return "skipped", "the fixer's reply held no JSON outcome"
    outcome = str(value.get("outcome") or value.get("status") or "").strip().lower()
    return (outcome if outcome in OUTCOMES else "skipped"), str(value.get("note") or "").strip()
