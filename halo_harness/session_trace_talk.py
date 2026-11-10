"""halo_harness.session_trace_talk -- the trace's THINK and TALK rows (Halo 3.3.16.2; session_trace.py draws them).

* `thinking_rows(node, ts)`: an assistant node's reasoning (`reasoning.text`, or its `thinking` blocks) as one
  "thinking" row each, in the order the model gave them; a model with no thinking gives none.
* `fold_talk(rows, who, parent)`: a sub-agent's log read as talk. Its first user prompt is its parent's task
  (`talk: main -> researcher (task)`); its last assistant text is its hand-back (`talk: researcher -> main
  (hand-back)`), drawn ONCE: the hand-back row takes the place of that text row, never beside it.
* `receipt_row(node, ts, who)`: a Workflow square's receipt (workflows/receipts.py) as the talk to the square.

Rows are session_trace.py's `(ts, kind, title, body, fenced)`.
"""
from __future__ import annotations


def thinking_rows(node: dict, ts: float) -> list:
    out = []
    r = node.get("reasoning")
    said = (r.get("text") or r.get("content")) if isinstance(r, dict) else None
    if isinstance(said, str) and said.strip():
        out.append((ts, "thinking", "thinking", said, False))
    for b in node.get("content") or []:
        thought = (b.get("thinking") or b.get("text")) if isinstance(b, dict) and b.get("type") == "thinking" else None
        if isinstance(thought, str) and thought.strip():
            out.append((ts, "thinking", "thinking", thought, False))
    return out


def fold_talk(rows: list, who: str, parent: str = "main") -> list:
    rows = list(rows)
    first = next((i for i, r in enumerate(rows) if r[1] == "user prompt"), None)
    if first is not None:
        ts, _k, _t, body, fenced = rows[first]
        rows[first] = (ts, "talk", f"talk: {parent} -> {who} (task)", body, fenced)
    last = next((i for i in range(len(rows) - 1, -1, -1) if rows[i][1] == "assistant text"), None)
    if last is not None and not any(r[1] == "tool call" for r in rows[last + 1:]):
        ts, _k, _t, body, fenced = rows[last]
        rows[last] = (ts, "talk", f"talk: {who} -> {parent} (hand-back)", body, fenced)
    return rows


def receipt_row(node: dict, ts: float, who: str) -> tuple:
    square = str(node.get("square") or "-")
    return (ts, "talk", f"talk: {who} -> square {square} (square)", str(node.get("line") or ""), False)
