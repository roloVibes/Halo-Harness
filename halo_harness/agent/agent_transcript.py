"""halo_harness.agent.agent_transcript -- one agent's activity in one shape
(Halo 3.0.5.0 "Fleet" round R1).

`agent_tail` (the control socket) reads an agent's transcript file and
`agent_event` feed frames stream a followed agent live; both hand out the
same small entries, so a client renders a tail and a live stream with one
code path:

    {"kind": "user",        "text", "tag"?}      a prompt, a steer note
    {"kind": "text",        "text"}               what the agent wrote
    {"kind": "thinking",    "text"}               its reasoning, when the route returns any
    {"kind": "tool_call",   "id", "name", "input", "label"}
    {"kind": "spawn",       "id", "name", "task"}  an Agent/Task call (a sub-agent of its own)
    {"kind": "tool_result", "id", "name"?, "text", "is_error"}
    {"kind": "handback",    "text"}               its final answer (a finished agent's last text)
    {"kind": "control",     "cmd", "by", ...}     a command recorded from Studio or the CLI
    {"kind": "note",        "text"}               a one-line notice (a child steered, stopped, paused)
    {"kind": "ask",         "what", "name"?}      a permission card, question or plan review opened
    {"kind": "error",       "text"} / {"kind": "done", "reason"}

Every entry carries `ts` when the source had one. Long text is capped.
"""

from __future__ import annotations

import json
import time
from typing import Optional

TEXT_CAP = 2000
ARG_CAP = 160
FLUSH_BYTES = 1800
FLUSH_S = 2.0
SPAWN_TOOLS = ("Agent", "Task")
_ARG_KEYS = ("command", "file_path", "path", "pattern", "url", "query", "description", "prompt", "subagent_type")


def one_line(value, cap: int = ARG_CAP) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = " ".join(str(text).split())
    return text if len(text) <= cap else text[:cap - 3] + "..."


def first_line(text, cap: int = 120) -> str:
    for line in str(text or "").splitlines():
        if line.strip():
            return one_line(line.strip(), cap)
    return ""


def tool_label(name: str, args) -> str:
    """`Bash: npm test` -- the tool and the one argument that says what it does."""
    if isinstance(args, dict):
        for key in _ARG_KEYS:
            if isinstance(args.get(key), str) and args[key].strip():
                return f"{name}: {one_line(args[key], 100)}"
        return f"{name}: {one_line(args, 100)}" if args else str(name)
    return str(name)


def _cap(text) -> str:
    text = text if isinstance(text, str) else _content_text(text)
    return text if len(text) <= TEXT_CAP else text[:TEXT_CAP] + f"... ({len(text) - TEXT_CAP} more characters)"


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return "" if content is None else json.dumps(content, ensure_ascii=False, default=str)


def _tool_entry(block: dict, ts) -> dict:
    name, args = str(block.get("name") or "?"), block.get("input")
    if name in SPAWN_TOOLS and isinstance(args, dict):
        task = args.get("prompt") or args.get("description") or args.get("org") or ""
        return {"kind": "spawn", "id": block.get("id"), "name": str(args.get("subagent_type") or args.get("org")
                                                                    or "general-purpose"), "task": first_line(task), "ts": ts}
    shown = args if len(json.dumps(args, default=str)) <= TEXT_CAP else one_line(args, TEXT_CAP)
    return {"kind": "tool_call", "id": block.get("id"), "name": name, "input": shown,
            "label": tool_label(name, args), "ts": ts}


def entries_from_nodes(nodes: list, *, final: bool = False) -> list:
    """Every entry of one transcript (a session log's node list), in order.
    `final` marks the last `text` entry as the agent's `handback`."""
    out: list = []
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        kind, ts = node.get("type"), node.get("ts")
        if kind == "user":
            text = _content_text(node.get("content"))
            if text.strip():
                out.append({"kind": "user", "text": _cap(text), "tag": node.get("kind"), "ts": ts})
        elif kind == "assistant":
            reasoning = node.get("reasoning")
            said = reasoning.get("text") or reasoning.get("content") if isinstance(reasoning, dict) else None
            if isinstance(said, str) and said.strip():
                out.append({"kind": "thinking", "text": _cap(said), "ts": ts})
            for block in node.get("content") or []:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                thought = block.get("thinking") or block.get("text") if btype == "thinking" else None
                if btype == "text" and str(block.get("text") or "").strip():
                    out.append({"kind": "text", "text": _cap(block["text"]), "ts": ts})
                elif isinstance(thought, str) and thought.strip():
                    out.append({"kind": "thinking", "text": _cap(thought), "ts": ts})
                elif btype == "tool_use":
                    out.append(_tool_entry(block, ts))
        elif kind == "tool_result":
            out.append({"kind": "tool_result", "id": node.get("tool_use_id"), "name": node.get("tool"),
                        "text": _cap(node.get("content")), "is_error": bool(node.get("is_error")), "ts": ts})
        elif kind == "meta" and isinstance(node.get("fleet"), dict):
            out.append({"kind": "control", **node["fleet"], "ts": ts})
        elif kind == "meta" and isinstance(node.get("fleet_note"), str):
            out.append({"kind": "note", "text": node["fleet_note"], "ts": ts})
        elif kind == "error":
            out.append({"kind": "error", "text": _cap(node.get("message") or ""), "ts": ts})
    if final:
        for entry in reversed(out):
            if entry["kind"] == "text":
                entry["kind"] = "handback"
                break
            if entry["kind"] in ("user", "tool_call", "spawn"):
                break
    return out


def tail(entries: list, n: int, kinds=None) -> list:
    if kinds:
        wanted = {str(k) for k in kinds}
        entries = [e for e in entries if e.get("kind") in wanted]
    return entries[-max(1, int(n)):] if entries else []


def entry_from_event(ev) -> Optional[dict]:
    """A live event's entry (text and thinking deltas are coalesced by `LiveText`)."""
    kind, data = getattr(ev, "kind", ""), getattr(ev, "data", None) or {}
    ts = getattr(ev, "ts", None) or time.time()
    if kind == "tool_use_ready":
        return _tool_entry({"id": data.get("id"), "name": data.get("name"), "input": data.get("input")}, ts)
    if kind == "tool_result":
        return {"kind": "tool_result", "id": data.get("id"), "name": data.get("name"),
                "text": _cap(data.get("content") if data.get("content") is not None else data.get("summary") or ""),
                "is_error": bool(data.get("is_error")), "ts": ts}
    if kind == "user_message":
        return {"kind": "user", "text": _cap(data.get("text") or ""), "ts": ts}
    if kind in ("permission_request", "question", "plan_review"):
        return {"kind": "ask", "what": kind, "name": data.get("name"), "ts": ts}
    if kind == "error":
        return {"kind": "error", "text": _cap(data.get("message") or ""), "ts": ts}
    if kind in ("notification", "system_note"):
        return {"kind": "note", "text": _cap(data.get("text") or ""), "ts": ts}
    if kind == "turn_done":
        return {"kind": "done", "reason": data.get("reason"), "ts": ts}
    return None


class LiveText:
    """Coalesces one agent's text/thinking deltas into chunk entries: a chunk
    is cut when another kind of event arrives, at FLUSH_BYTES, or FLUSH_S
    after it started (checked as deltas arrive)."""

    def __init__(self) -> None:
        self.kind: Optional[str] = None
        self.parts: list = []
        self.size = 0
        self.t0 = 0.0

    def feed(self, ev) -> list:
        kind = getattr(ev, "kind", "")
        out: list = []
        if kind in ("text_delta", "thinking_delta"):
            want = "text" if kind == "text_delta" else "thinking"
            if self.parts and want != self.kind:
                out.extend(self.flush())
            if not self.parts:
                self.kind, self.t0 = want, time.monotonic()
            piece = str((getattr(ev, "data", None) or {}).get("text") or "")
            self.parts.append(piece)
            self.size += len(piece.encode("utf-8", "replace"))
            if self.size >= FLUSH_BYTES or time.monotonic() - self.t0 >= FLUSH_S:
                out.extend(self.flush())
            return out
        out.extend(self.flush())
        entry = entry_from_event(ev)
        if entry is not None:
            out.append(entry)
        return out

    def flush(self) -> list:
        if not self.parts:
            return []
        text, kind = "".join(self.parts), self.kind
        self.parts, self.size, self.kind = [], 0, None
        return [{"kind": kind, "text": text, "ts": time.time()}] if text else []
