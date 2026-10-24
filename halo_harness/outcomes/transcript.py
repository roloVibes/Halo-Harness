"""halo_harness.outcomes.transcript -- one agent's transcript as the tool calls
it made, each with its result, and its final text (Halo 3.1.8.0 R3).

A transcript comes in one of two shapes and `calls(transcript)` reads both:

* session-log nodes (agent/log.py: `assistant` nodes with `tool_use`
  blocks, `tool_result` nodes with the full output) -- what a session's
  `.jsonl` holds and what a live child's `log.nodes()` returns;
* agent_transcript entries (`tool_call` / `spawn` / `tool_result` / `text` /
  `handback`) -- the shape `agent_tail` and the Studio stream use (their
  long results are capped from the front, so an exit note at the end can be
  cut: such a result's exit reads as unknown).

`find_log(session_id, cwd=..., state_dir=...)` is a finished worker's own
session file: `<state>/sessions/<slug of cwd>/<id>.jsonl`, else the one file
of that id under any project folder. Nothing here writes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

CUT_MARK = "more characters)"  # agent_transcript._cap's tail on a capped result


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(b.get("text") or "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return "" if content is None else json.dumps(content, ensure_ascii=False, default=str)


def _is_nodes(transcript: list) -> bool:
    return any(isinstance(x, dict) and "type" in x and "kind" not in x for x in transcript)


def _from_nodes(nodes: list) -> "tuple[list, str]":
    out, by_id, final = [], {}, ""
    for node in nodes:
        if not isinstance(node, dict):
            continue
        kind = node.get("type")
        if kind == "assistant":
            said = [str(b.get("text") or "") for b in node.get("content") or []
                    if isinstance(b, dict) and b.get("type") == "text" and str(b.get("text") or "").strip()]
            if said:
                final = "\n".join(said)
            for block in node.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    call = {"id": block.get("id"), "name": str(block.get("name") or ""), "ts": node.get("ts"),
                            "input": block.get("input") if isinstance(block.get("input"), dict) else {},
                            "text": "", "is_error": None, "done": False, "cut": False}
                    out.append(call)
                    by_id[call["id"]] = call
        elif kind == "tool_result":
            call = by_id.get(node.get("tool_use_id"))
            if call is not None:
                call.update(text=_text(node.get("content")), is_error=bool(node.get("is_error")), done=True,
                            result_ts=node.get("ts"))
    return out, final


def _from_entries(entries: list) -> "tuple[list, str]":
    out, by_id, final = [], {}, ""
    for e in entries:
        if not isinstance(e, dict):
            continue
        kind = e.get("kind")
        if kind in ("text", "handback") and str(e.get("text") or "").strip():
            final = str(e["text"])
        elif kind in ("tool_call", "spawn"):
            args = e.get("input") if isinstance(e.get("input"), dict) else {}
            name = str(e.get("name") or "") if kind == "tool_call" else "Agent"
            call = {"id": e.get("id"), "name": name, "ts": e.get("ts"), "input": args, "text": "",
                    "is_error": None, "done": False, "cut": False}
            out.append(call)
            by_id[call["id"]] = call
        elif kind == "tool_result":
            call = by_id.get(e.get("id"))
            if call is not None:
                text = str(e.get("text") or "")
                call.update(text=text, is_error=bool(e.get("is_error")), done=True, result_ts=e.get("ts"),
                            cut=text.endswith(CUT_MARK))
    return out, final


def calls(transcript) -> "tuple[list, str]":
    """`(calls, final_text)`: every tool call in order, each `{id, name, input,
    ts, text, is_error, done, cut}` (`text` its result, `done` once a result
    came back, `cut` when the result was capped), and the agent's last text."""
    transcript = [x for x in (transcript or []) if isinstance(x, dict)]
    if not transcript:
        return [], ""
    return _from_nodes(transcript) if _is_nodes(transcript) else _from_entries(transcript)


def read_nodes(path) -> list:
    """A session `.jsonl` as its nodes (an unreadable line is skipped)."""
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    node = json.loads(line)
                except ValueError:
                    continue
                if isinstance(node, dict):
                    out.append(node)
    except OSError:
        return []
    return out


def find_log(session_id, *, cwd=None, state_dir=None) -> Optional[Path]:
    """The session file of `session_id` (None when it is not a session id or no file has it)."""
    from halo_harness.safe_id import is_safe_session_id
    if not is_safe_session_id(session_id):
        return None
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    sessions = Path(state_dir) / "sessions"
    if cwd is not None:
        from halo_harness.config.paths import project_slug
        for where in (cwd, Path(cwd).resolve()):
            path = sessions / project_slug(where) / f"{session_id}.jsonl"
            if path.is_file():
                return path
    try:
        return next((p for p in sorted(sessions.glob(f"*/{session_id}.jsonl")) if p.is_file()), None)
    except OSError:
        return None
