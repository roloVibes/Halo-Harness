"""scripts/realcheck/report.py -- one line per step as it ends, the JSON of the run, and the Markdown table a CI step
summary shows."""
from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict, dataclass, field

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


@dataclass
class Result:
    name: str
    status: str
    seconds: float
    budget: float
    detail: str = ""                               # what a person would have seen (FAIL) or why not run (SKIP)
    evidence: dict = field(default_factory=dict)   # numbers and excerpts behind it
    expected_until: str = ""                       # a FAIL another round is fixing ("R10")

    def line(self) -> str:
        note = f" [expected until {self.expected_until} lands]" if self.status == FAIL and self.expected_until else ""
        return f"{self.name:<12} {self.status}  {self.seconds:6.1f}s  {self.detail}{note}".rstrip()


def run_info(halo_version: str, mode: str) -> dict:
    return {"platform": sys.platform, "os": platform.platform(), "python": platform.python_version(),
            "halo": halo_version, "mode": mode}


def to_json(results: list, info: dict) -> str:
    return json.dumps({"info": info, "ok": all(r.status != FAIL for r in results),
                       "steps": [asdict(r) for r in results]}, indent=2, ensure_ascii=False)


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def markdown(results: list, info: dict) -> str:
    """The table for $GITHUB_STEP_SUMMARY."""
    head = (f"### realcheck ({info.get('platform')}, Python {info.get('python')}, {info.get('halo')})\n\n"
            "| step | result | seconds | budget | what a person would see |\n|---|---|---:|---:|---|\n")
    rows = []
    for r in results:
        note = f" (expected until {r.expected_until} lands)" if r.status == FAIL and r.expected_until else ""
        rows.append(f"| {r.name} | {r.status} | {r.seconds:.1f} | {r.budget:.0f} | {_cell(r.detail + note)[:400]} |")
    passed = sum(r.status == PASS for r in results)
    failed = sum(r.status == FAIL for r in results)
    tail = f"\n\n{passed} passed, {failed} failed, {len(results) - passed - failed} skipped.\n"
    return head + "\n".join(rows) + tail
