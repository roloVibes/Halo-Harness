"""halo_harness.agent.prompt_composition -- Halo 3.3.5.0 R4: what a request
Halo is about to send is made of, in tokens, and the doubled block taken out.

    known_texts(session)              the log's snapshot texts by part (claude_md, memory, harness)
    block_part(text, known)           "memory" | "claude_md" | "harness" | "summary" | "text"
    split_memory(text)                (the MEMORY.md part, the topic index part) of one memory block
    dedupe(messages, known)           (messages, duplicates): memory and CLAUDE.md blocks kept once (the newest)
    compose(session, messages, tools, system, placement=...) -> Composition
    composition_line(comp)            "prompt 30,756: system 3,587 · memory 9,900 · topics 6,400 · ..."
    ledger_fields(comp)               {system, memory, topic_index, tools_schema, history, user, total}

Composition = {system: {tokens, parts: {harness, claude_md, memory, topic_index,
tools_schema}}, history: {tokens, turns}, user: {tokens, parts: {text, memory,
topic_index, attachments}}, total, prefix_tokens, placement, duplicates: [{part,
tokens, where}]}. One estimator: `providers.ollama_prompt`'s chars / 3.5 (the
one `prepare_window` uses); `total` is the prompt part (the reply's room is
not prompt), and the JSON framing the parts leave out is counted in history.
`system.parts.memory` is memory sent in the system message (a local model),
`user.parts.memory` memory sent in a user-role message (a cloud model, or a
model whose system role is weak). CLAUDE.md is counted under system wherever
it rides (it is the instructions); Halo's own snapshots (environment, the
roster, the deferred tool names, plan mode, the files read) are `harness`.
"""

from __future__ import annotations

import json
import math
from typing import Optional

MEMORY_HEAD = "# Memory (auto-loaded from MEMORY.md)"
TOPICS_HEAD = "## Topic files (read on demand"
DIR_HEAD = "Memory directory: "
SUMMARY_MARK = "<compacted-summary>"
HARNESS_KINDS = ("environment", "roster", "deferred_tools", "plan_mode", "files_read", "permission_mode")
_DEDUPED = ("memory", "claude_md")


def tokens_of(text) -> int:
    """chars / 3.5 of `text` as JSON (the request estimator's own rule)."""
    from halo_harness.providers.ollama_prompt import CHARS_PER_TOKEN
    if not text:
        return 0
    n = len(json.dumps(text, ensure_ascii=False, default=str)) - (2 if isinstance(text, str) else 0)
    return int(math.ceil(n / CHARS_PER_TOKEN))


def is_memory_block(text: str) -> bool:
    return isinstance(text, str) and text.startswith(DIR_HEAD) and (MEMORY_HEAD in text or TOPICS_HEAD in text)


def known_texts(session) -> dict:
    """The texts of every snapshot node in the session's log, by part."""
    out = {"claude_md": set(), "memory": set(), "harness": set()}
    log = getattr(session, "log", None)
    try:
        nodes = log.nodes() if log is not None else []
    except Exception:
        nodes = []
    for n in nodes:
        if n.get("type") != "snapshot":
            continue
        kind = n.get("kind")
        part = ("claude_md" if kind == "claude_md" else "memory" if kind == "memory_index"
                else "harness" if kind in HARNESS_KINDS else None)
        if part is None:
            continue
        for b in n.get("content") or []:
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                out[part].add(b["text"])
    return out


def block_part(text: str, known: Optional[dict] = None) -> str:
    known = known or {}
    if not isinstance(text, str):
        return "text"
    if text in known.get("memory", ()) or is_memory_block(text):
        return "memory"
    if text in known.get("claude_md", ()):
        return "claude_md"
    if text in known.get("harness", ()):
        return "harness"
    if SUMMARY_MARK in text:
        return "summary"
    return "text"


def split_memory(text: str) -> "tuple[str, str]":
    """(the MEMORY.md part with the directory line, the topic index part) of one memory block."""
    at = text.find("\n\n" + TOPICS_HEAD)
    if at < 0:
        return (text, "") if not text.startswith(TOPICS_HEAD) else ("", text)
    return text[:at], text[at + 2:]


def _text_blocks(msg):
    content = msg.get("content") if isinstance(msg, dict) else None
    if not isinstance(content, list):
        return []
    return [(i, b) for i, b in enumerate(content) if isinstance(b, dict) and b.get("type") == "text"]


def dedupe(messages: list, known: Optional[dict] = None) -> "tuple[list, list]":
    """Every memory block and every CLAUDE.md block but the newest of its part
    taken out of the wire copy (the log is never touched); a message left
    with nothing keeps one line saying where the block went."""
    seen: dict = {p: [] for p in _DEDUPED}
    for mi, msg in enumerate(messages or []):
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        for bi, b in _text_blocks(msg):
            part = block_part(b.get("text"), known)
            if part in seen:
                seen[part].append((mi, bi, b.get("text") or ""))
    drop: dict = {}
    duplicates = []
    for part, spots in seen.items():
        for mi, bi, text in spots[:-1]:
            drop.setdefault(mi, set()).add(bi)
            duplicates.append({"part": part, "tokens": tokens_of(text), "where": f"message {mi + 1}"})
    if not drop:
        return messages, []
    out = []
    for mi, msg in enumerate(messages):
        if mi not in drop:
            out.append(msg)
            continue
        content = [b for bi, b in enumerate(msg["content"]) if bi not in drop[mi]]
        if not content:
            content = [{"type": "text", "text": "(an earlier copy of the memory and instructions; they are sent once)"}]
        out.append({**msg, "content": content})
    return out, duplicates


def _last_user(messages: list) -> int:
    for i in range(len(messages or []) - 1, -1, -1):
        if isinstance(messages[i], dict) and messages[i].get("role") == "user":
            return i
    return -1


def compose(session, messages, tools, system, *, placement: str = "user", known: Optional[dict] = None,
            duplicates: Optional[list] = None) -> dict:
    """See the module docstring. `system` is the system text as it will be sent
    (with the memory block in it when `placement` is "system")."""
    from halo_harness.providers.ollama_prompt import estimate_request_tokens, reply_reserve
    known = known if known is not None else known_texts(session)
    sp = {"harness": 0, "claude_md": 0, "memory": 0, "topic_index": 0, "tools_schema": 0}
    up = {"text": 0, "memory": 0, "topic_index": 0, "attachments": 0}
    sys_text = system or ""
    if placement == "system":
        at = sys_text.find(DIR_HEAD)
        if at >= 0:
            mem, top = split_memory(sys_text[at:])
            sp["memory"], sp["topic_index"] = tokens_of(mem), tokens_of(top)
            sys_text = sys_text[:at]
    sp["harness"] = tokens_of(sys_text)
    sp["tools_schema"] = tokens_of(list(tools)) if tools else 0
    last = _last_user(messages)
    turns = sum(1 for m in messages or [] if isinstance(m, dict) and m.get("role") == "assistant")
    you = 0
    for mi, msg in enumerate(messages or []):
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text":
                text = b.get("text") or ""
                part = block_part(text, known) if msg.get("role") == "user" else "text"
                if part == "memory":
                    mem, top = split_memory(text)
                    up["memory"] += tokens_of(mem)
                    up["topic_index"] += tokens_of(top)
                elif part == "claude_md":
                    sp["claude_md"] += tokens_of(text)
                elif part == "harness":
                    sp["harness"] += tokens_of(text)
                elif mi == last and part == "text":
                    you += tokens_of(text)
            elif mi == last and b.get("type") in ("image", "document", "image_url"):
                from halo_harness.providers.ollama_prompt import CHARS_PER_TOKEN, _chars
                up["attachments"] += int(math.ceil(_chars(b) / CHARS_PER_TOKEN))  # the estimate leaves image bytes out
    up["text"] = you
    total = max(1, estimate_request_tokens(messages, tools, system) - reply_reserve(None))
    named = sum(sp.values()) + sum(up.values())
    history = max(0, total - named)
    sys_tokens = sum(sp.values())
    return {"system": {"tokens": sys_tokens, "parts": sp}, "history": {"tokens": history, "turns": turns},
            "user": {"tokens": sum(up.values()), "parts": up}, "total": total,
            "prefix_tokens": tokens_of(system or "") + sp["tools_schema"],  # the system message and the tools
            "placement": placement, "duplicates": list(duplicates or [])}


def ledger_fields(comp: Optional[dict]) -> Optional[dict]:
    if not comp:
        return None
    sp, up = comp["system"]["parts"], comp["user"]["parts"]
    return {"system": sp["harness"] + sp["claude_md"], "memory": sp["memory"] + up["memory"],
            "topic_index": sp["topic_index"] + up["topic_index"], "tools_schema": sp["tools_schema"],
            "history": comp["history"]["tokens"], "user": up["text"] + up["attachments"], "total": comp["total"]}


def composition_line(comp: Optional[dict]) -> str:
    """"prompt 30,756: system 3,587 · memory 9,900 · topics 6,400 · tools 2,100 · history 8,700 · you 69"."""
    f = ledger_fields(comp)
    if not f:
        return "prompt: nothing sent yet"
    bits = [("system", f["system"]), ("memory", f["memory"]), ("topics", f["topic_index"]),
            ("tools", f["tools_schema"]), ("history", f["history"]), ("you", f["user"])]
    line = f"prompt {f['total']:,}: " + " · ".join(f"{k} {v:,}" for k, v in bits)
    dups = comp.get("duplicates") or []
    if dups:
        line += f" · {len(dups)} repeated block{'s' if len(dups) != 1 else ''} taken out ({sum(d['tokens'] for d in dups):,})"
    return line
