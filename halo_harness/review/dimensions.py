"""halo_harness.review.dimensions -- the five reviewer dimensions, the
`--level` caps, and the prompts the reviewers receive.

Each dimension has a system prompt under `review/prompts/<dim>.md`; the user
prompt (built here) carries the target, the level and the diff shard, and ends
with the shared findings contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from halo_harness.review.target_model import Shard

DIMENSIONS = {
    "correctness": "bugs, logic errors, wrong results, broken edge cases, error handling",
    "security": "injection, unsafe file/process handling, credential and data exposure, trust boundaries",
    "performance": "needless work, quadratic loops, blocking calls, memory growth, repeated I/O",
    "tests": "missing, weak or wrong tests for the change; assertions that cannot fail",
    "docs-consistency": "docs, help text, comments and names that no longer match the code or its neighbours",
}
DEFAULT_LEVEL = "medium"
LEVELS = {"low": 3, "medium": 8, "high": 20}
_SPECULATION = {
    "low": "Report only problems you can show with a concrete failing scenario read from the code. "
           "When unsure, leave it out.",
    "medium": "Report problems you can argue from the code. A finding you cannot fully prove is fine when "
              "the scenario is realistic; say what you could not check.",
    "high": "Report likely problems and plausible risks, including ones you cannot fully prove. A judge "
            "adjudicates every finding afterwards, so name the scenario and what would confirm it.",
}
_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

FINDINGS_CONTRACT = """\
Reply with ONE fenced ```json block holding an array of findings (an empty array `[]` when there are none) and
nothing else after it. Each finding is an object with exactly these keys:
  "file": path relative to the repo root, "line": integer line number in the new version (null if none),
  "severity": "high" | "medium" | "low", "category": a short lowercase tag (for example "logic-error",
  "injection", "missing-test"), "short_summary": one line, "summary": what is wrong and why it matters,
  "failure_scenario": the concrete input or sequence that triggers it and what goes wrong.
Order findings most severe first."""


def parse_dimensions(value: Optional[str]) -> "list[str]":
    """`--dimensions a,b` -> validated list in canonical order; None/empty -> all.
    Raises ValueError naming the unknown dimension."""
    if not value:
        return list(DIMENSIONS)
    wanted = [d.strip().lower() for d in value.split(",") if d.strip()]
    unknown = [d for d in wanted if d not in DIMENSIONS]
    if unknown:
        raise ValueError(f"unknown dimension {unknown[0]!r} (choose from {', '.join(DIMENSIONS)})")
    return [d for d in DIMENSIONS if d in wanted]


def validate_level(level: Optional[str]) -> str:
    level = (level or DEFAULT_LEVEL).strip().lower()
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r} (choose from {', '.join(LEVELS)})")
    return level


def prompt_text(name: str) -> str:
    """The text of `review/prompts/<name>.md` (a dimension, `judge` or `fixer`)."""
    return (_PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def reviewer_prompt(dimension: str, shard: Shard, level: str, *, target_label: str, kind: str) -> str:
    cap = LEVELS[level]
    head = [f"Review target: {target_label}", f"Dimension: {dimension} ({DIMENSIONS[dimension]})",
            f"Level: {level} -- report at most {cap} findings. {_SPECULATION[level]}"]
    if shard.total > 1:
        head.append(f"This is part {shard.label} of the change; other reviewers cover the other parts.")
    if kind in ("pr", "branch", "range"):
        head.append("The files on disk may differ from the version in the diff; trust the diff for what "
                    "changed and use Read/Grep for surrounding code.")
    if kind == "paths":
        head.append("These files are reviewed as they are (no diff); line numbers are shown on each line.")
    if shard.omitted:
        head.append("Not included here (read them with Read or `git diff -- <file>` if relevant): "
                    + ", ".join(shard.omitted))
    head.append("Files in this part: " + (", ".join(shard.files) or "(none)"))
    body = shard.text or "(empty)"
    return "\n".join(head) + f"\n\n<diff>\n{body}\n</diff>\n\n" + FINDINGS_CONTRACT
