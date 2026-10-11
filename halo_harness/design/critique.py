"""halo_harness.design.critique -- the second-opinion review of one artboard
(Halo 3.0.1.0 round D5). `critique_prompt` is the whole brief for a read-only
turn (Read and Glob only, no MCP servers); `parse_pins` lifts the first fenced
json list out of the reply; `add_pins` turns each entry into a comment pin
tagged `source: critique` with its severity as a `[high]` text prefix.
`variants_prompt` wraps a prompt into "Explore N directions".
"""

from __future__ import annotations

import json
import re

SEVERITIES = ("high", "medium", "low")
MAX_PINS = 8
MAX_VARIANTS = 6
_FENCE = re.compile(r"```(?:json)?[ \t]*\n(.*?)```", re.S | re.I)


def variants_prompt(prompt: str, n: int, base: str) -> str:
    n = max(2, min(MAX_VARIANTS, int(n)))
    names = ", ".join(f"{base}-{chr(97 + i)}" for i in range(n))
    return (f"Make {n} directions of: {prompt}. Each is its own artboard named {names} (same kind), clearly different "
            "in layout, type and colour, all keeping the design system.")


def critique_prompt(project, aid: str) -> str:
    board = next((a for a in project.artboards() if a["id"] == aid), None)
    files = ", ".join(board["files"]) if board and board["files"] else "no files yet"
    look = ("artboards/%s/index.html" % aid) if board and "index.html" in board["files"] else \
        "the render in artboards/%s/ (render.png or render.svg: Read shows images)" % aid
    return f"""You are a design critic giving a second opinion on the artboard '{aid}' (files: {files}).
Use Read to open {look} and system.json; use Glob only to list files.
Judge, in this order: visual hierarchy, spacing rhythm, type scale, colour contrast, consistency with the tokens in
system.json, the copy, and accessibility (labels, focus, touch size, alt text).
Be concrete and specific to this artboard. Each note is one sentence saying what is off and why it matters.
Reply with a short opening line, then ONE fenced json block holding a list of at most {MAX_PINS} notes:
```json
[{{"x": 40, "y": 12, "text": "The headline and the sub-line are the same weight, so nothing leads the eye.", "severity": "high"}}]
```
x and y are percentages (0-100) of the artboard frame where the note belongs; severity is high, medium or low.
"""


def parse_pins(text: str) -> list:
    """The first fenced json list in `text` as clean pins (x, y, text, severity); [] when there is none."""
    for block in _FENCE.findall(text or ""):
        try:
            rows = json.loads(block)
        except ValueError:
            continue
        if not isinstance(rows, list):
            continue
        out = []
        for r in rows:
            if not isinstance(r, dict) or not str(r.get("text") or "").strip():
                continue
            sev = str(r.get("severity") or "medium").lower()
            try:
                x, y = float(r.get("x", 50)), float(r.get("y", 50))
            except (TypeError, ValueError):
                x, y = 50.0, 50.0
            out.append({"x": max(0.0, min(100.0, x)), "y": max(0.0, min(100.0, y)),
                        "text": str(r["text"]).strip()[:300], "severity": sev if sev in SEVERITIES else "medium"})
        return out[:MAX_PINS]
    return []


def add_pins(project, aid: str, text: str, version: int = 0) -> tuple:
    """Parse the reply and pin every note. Returns (pins as comments, one plain sentence)."""
    notes = parse_pins(text)
    if not notes:
        return [], "The critique came back without a pin list, so no pins were added."
    pins = [project.add_comment(aid, f"[{n['severity']}] {n['text']}", x=n["x"], y=n["y"], version=version, source="critique") for n in notes]
    return pins, f"{len(pins)} critique pin(s) added to {aid}."
