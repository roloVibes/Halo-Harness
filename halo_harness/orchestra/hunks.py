"""halo_harness.orchestra.hunks -- conflict hunks in, the judge's text out.

A conflicted file keeps both versions between git's markers (diff3 style,
so the common base is there too):

    <<<<<<< HEAD
    ours
    ||||||| base
    base
    =======
    theirs
    >>>>>>> orchestra/<run>-worker-2

`extract_hunks(text)` lists them; `judge_prompt(hunks, goal, file)` is the
whole prompt the fresh judge sees (the goal and the hunks, nothing else;
3.1.8.0 R3: plus an EVIDENCE block when the goal carries the lanes'
evidence lines -- their tests, sources and reproductions, never a summary);
`parse_resolution(answer, n)` reads the judge's answer (the replacement
text for one hunk, or `=== hunk k ===` blocks for several); and
`apply_resolution(text, texts)` swaps each marked region for its text. All
of it is code; the judge only writes the replacement lines.
"""

from __future__ import annotations

import re
from typing import Optional

_START, _BASE, _MID, _END = "<<<<<<< ", "||||||| ", "=======", ">>>>>>> "
_BLOCK = re.compile(r"^=== hunk (\d+) ===[ \t]*$", re.M)


def extract_hunks(text: str) -> list:
    """`[{index, start_line, end_line, ours, base, theirs, ours_label, theirs_label}]`
    (1-based lines of the markers themselves)."""
    hunks, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        if not lines[i].startswith(_START):
            i += 1
            continue
        start = i
        part = {"ours": [], "base": [], "theirs": []}
        where = "ours"
        ours_label = lines[i][len(_START):].strip()
        i += 1
        while i < len(lines) and not lines[i].startswith(_END):
            line = lines[i]
            if line.startswith(_BASE) and where == "ours":
                where = "base"
            elif line.rstrip() == _MID and where in ("ours", "base"):
                where = "theirs"
            else:
                part[where].append(line)
            i += 1
        theirs_label = lines[i][len(_END):].strip() if i < len(lines) else ""
        hunks.append({"index": len(hunks) + 1, "start_line": start + 1, "end_line": i + 1,
                      "ours": "\n".join(part["ours"]), "base": "\n".join(part["base"]),
                      "theirs": "\n".join(part["theirs"]), "ours_label": ours_label,
                      "theirs_label": theirs_label})
        i += 1
    return hunks


def judge_prompt(hunks: list, goal, file: str) -> str:
    """Everything the judge is given: the goal and the conflict hunks."""
    what = getattr(goal, "what", "") if not isinstance(goal, dict) else goal.get("what", "")
    done = getattr(goal, "done_when", "") if not isinstance(goal, dict) else goal.get("done_when", "")
    parts = [
        "Two workers changed the same lines of one file. Resolve the conflict so that BOTH changes are kept "
        "wherever they can be, and the goal is met.",
        f"GOAL: {what}\nDONE WHEN: {done}\nFILE: {file}",
    ]
    evidence = goal.get("evidence") if isinstance(goal, dict) else getattr(goal, "evidence", None)
    if evidence:  # 3.1.8.0 R3 (outcomes/lane.py): what the lanes ran and read, never their own summary
        parts.append("EVIDENCE (what each lane's worker ran and read, from its transcript):\n"
                     + "\n".join(f"- {line}" for line in evidence))
    for h in hunks:
        parts.append(f"--- hunk {h['index']} (lines {h['start_line']}-{h['end_line']}) ---\n"
                     f"[already merged]\n{h['ours']}\n[common base]\n{h['base']}\n[incoming]\n{h['theirs']}")
    if len(hunks) == 1:
        parts.append("Answer with ONLY the replacement lines for the hunk: no markers, no explanation, no fence.")
    else:
        parts.append("Answer with one block per hunk, each starting with a line `=== hunk N ===` followed by its "
                     "replacement lines: no markers, no explanation, no fence.")
    return "\n\n".join(parts)


def _strip_fence(text: str) -> str:
    stripped = text.strip("\n")
    m = re.match(r"^```[\w+-]*\n(.*?)\n?```\s*$", stripped, re.S)
    return m.group(1) if m else stripped


def parse_resolution(answer: str, count: int) -> Optional[list]:
    """The replacement text for each of `count` hunks, or None when the
    answer does not give exactly one per hunk."""
    text = _strip_fence(str(answer or "").replace("\r\n", "\n"))
    if any(line.startswith((_START, _END)) for line in text.splitlines()):
        return None
    marks = list(_BLOCK.finditer(text))
    if not marks:
        return [text] if count == 1 else None
    blocks = {}
    for k, m in enumerate(marks):
        end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
        blocks[int(m.group(1))] = _strip_fence(text[m.end():end].strip("\n"))
    if sorted(blocks) != list(range(1, count + 1)):
        return None
    return [blocks[i] for i in range(1, count + 1)]


def apply_resolution(text: str, texts: list) -> str:
    """`text` with the k-th marked region replaced by `texts[k]`."""
    hunks = extract_hunks(text)
    if len(hunks) != len(texts):
        raise ValueError(f"{len(hunks)} hunk(s) in the file, {len(texts)} resolution(s)")
    lines = text.splitlines()
    out, prev = [], 0
    for h, new in zip(hunks, texts):
        out.extend(lines[prev:h["start_line"] - 1])
        if new != "":
            out.extend(new.split("\n"))
        prev = h["end_line"]
    out.extend(lines[prev:])
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")
