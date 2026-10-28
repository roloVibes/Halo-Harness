"""halo_harness.agent.model_switch_history -- Halo 3.3.5.0 R0: the history
fitted to what the model a session moved to can take.

The session log is never rewritten: the conversion runs on the wire copy of
every request after a switch (`apply_to_wire`, called where the request is
derived: `_derive_and_build` and the compaction call), so a switch back to a
model that takes images sends the images again.

`convert(messages, caps)` over the canonical (Anthropic-shaped) messages
`agent/derive.py` builds:

- images -> their captions (`image_attach.path_mention_text`, plus the
  media type and size when the log kept them) when the target has no
  vision; an image inside a tool result too;
- thinking blocks (`thinking` / `redacted_thinking`, and an assistant
  turn's `reasoning`) dropped when the target has no thinking; on the
  Anthropic dialect a thinking block without a `signature` (written by
  another provider's model) is dropped either way, since the API refuses it;
- tool-call turns: each dialect's builder re-shapes `tool_use` /
  `tool_result` for its wire (native Ollama, OpenAI chat, Anthropic); on the
  Anthropic dialect a call id another provider wrote with characters outside
  `[A-Za-z0-9_-]` is rewritten the same way in the call and its result; when
  the target has no tool support (the capability probe or the declared
  capabilities say so), every call and result is flattened to text;
- the history always ends up holding a user turn with text, so a converted
  history never reaches Qwen as "no user query found in messages".
"""

from __future__ import annotations

import json
import re
from typing import Optional

_ID_OK = re.compile(r"[^A-Za-z0-9_-]")
_THINK_TYPES = ("thinking", "redacted_thinking")


def caption(block: dict) -> str:
    from halo_harness.agent.image_attach import path_mention_text
    base = path_mention_text(block)
    bits = [str(block.get("media_type") or ((block.get("source") or {}).get("media_type") or ""))]
    if block.get("width") and block.get("height"):
        bits.append(f"{block['width']}x{block['height']}")
    detail = " ".join(b for b in bits if b)
    return f"{base[:-1]} ({detail}; this model takes no images)]" if detail and base.endswith("]") else \
        f"{base} (this model takes no images)"


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text") or "")
            elif isinstance(b, dict) and b.get("type") == "image":
                parts.append(caption(b))
        return "\n".join(p for p in parts if p)
    return "" if content is None else str(content)


def _fix_id(raw, dialect: str, counts: dict) -> str:
    raw = str(raw or "")
    if dialect != "anthropic-passthrough":
        return raw
    fixed = _ID_OK.sub("_", raw) or "call"
    if fixed != raw:
        counts["ids"] = counts.get("ids", 0) + 1
    return fixed


def _block(b, caps: dict, counts: dict, names: dict, out: list) -> None:
    kind = b.get("type") if isinstance(b, dict) else None
    dialect = caps.get("dialect") or ""
    if kind == "image" and not caps.get("vision", True):
        counts["images"] += 1
        out.append({"type": "text", "text": caption(b)})
    elif kind in _THINK_TYPES and (not caps.get("thinking", True)
                                   or (dialect == "anthropic-passthrough" and not b.get("signature") and kind == "thinking")):
        counts["thinking"] += 1
    elif kind == "tool_use":
        names[b.get("id")] = b.get("name")
        if not caps.get("tools", True):
            counts["tools"] += 1
            args = json.dumps(b.get("input") or {}, ensure_ascii=False, sort_keys=True)
            out.append({"type": "text", "text": f"[tool call: {b.get('name')} {args}]"})
        else:
            out.append({**b, "id": _fix_id(b.get("id"), dialect, counts)})
    elif kind == "tool_result":
        if not caps.get("tools", True):
            counts["tools"] += 1
            name = names.get(b.get("tool_use_id")) or "a tool"
            flag = " (error)" if b.get("is_error") else ""
            out.append({"type": "text", "text": f"[result of {name}{flag}: {_text_of(b.get('content'))}]"})
            return
        inner = b.get("content")
        if isinstance(inner, list) and not caps.get("vision", True):
            new_inner: list = []
            for x in inner:
                if isinstance(x, dict) and x.get("type") == "image":
                    counts["images"] += 1
                    new_inner.append({"type": "text", "text": caption(x)})
                else:
                    new_inner.append(x)
            inner = new_inner
        out.append({**b, "content": inner, "tool_use_id": _fix_id(b.get("tool_use_id"), dialect, counts)})
    else:
        out.append(b)


def convert(messages: list, caps: dict) -> "tuple[list, dict]":
    """`(messages, counts)`; `counts` = {images, thinking, tools} (and `ids` on the Anthropic dialect)."""
    counts = {"images": 0, "thinking": 0, "tools": 0}
    names: dict = {}
    out: list = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            out.append(msg)
            continue
        content = msg.get("content")
        new = {k: v for k, v in msg.items() if not (k == "reasoning" and not caps.get("thinking", True))}
        if "reasoning" in msg and "reasoning" not in new:
            counts["thinking"] += 1
        if isinstance(content, list):
            blocks: list = []
            for b in content:
                _block(b, caps, counts, names, blocks)
            if not blocks:
                blocks = [{"type": "text", "text": "(no text)"}]
            new["content"] = blocks
        out.append(new)
    if not any(m.get("role") == "user" and _text_of(m.get("content")).strip() for m in out if isinstance(m, dict)):
        out.append({"role": "user", "content": [{"type": "text", "text": "Continue."}]})
    return out, counts


def count(messages: list, caps: dict) -> dict:
    return convert(messages, caps)[1]


def apply_to_wire(session, messages: list) -> list:
    """The wire copy converted for the model a switch moved the session to (unchanged without a switch)."""
    caps = getattr(session, "_switch_caps", None)
    if not caps or caps.get("model") != getattr(getattr(session, "model_ref", None), "raw", None):
        return messages
    return convert(messages, caps)[0]


def switch_reserve(session, budget):
    """The reply budget of a call to a LOCAL model a switch fitted: the switch's reserve (else `budget`)."""
    caps = getattr(session, "_switch_caps", None)
    reserve = getattr(session, "_switch_reserve", None)
    ref = getattr(session, "model_ref", None)
    from halo_harness.agent.model_window import kind_of
    if not caps or not isinstance(reserve, int) or caps.get("model") != getattr(ref, "raw", None) or kind_of(ref) == "cloud":
        return budget
    return reserve


def caps_for(ref, *, catalog_row: Optional[dict] = None, vision: Optional[bool] = None,
             tools_probe: Optional[bool] = None, dialect: Optional[str] = None) -> dict:
    """What `ref` can take: vision (the model profile or the catalog's
    capabilities), thinking (`effort_on`'s kind), tools (the declared
    capabilities and the measured probe; a cloud route keeps its tools)."""
    from halo_harness.providers.effort_on import _thinks
    caps_list = (catalog_row or {}).get("capabilities") if isinstance(catalog_row, dict) else None
    declared = {str(c).lower() for c in caps_list} if isinstance(caps_list, (list, tuple)) and caps_list else None
    local = getattr(ref, "provider", "") in ("ollama", "local") or getattr(ref, "local", False)
    see = bool(vision) or bool(declared and "vision" in declared)
    thinks = _thinks(catalog_row)
    tools = True
    if local and tools_probe is False:
        tools = False
    elif declared is not None and getattr(ref, "provider", "") == "ollama" and "tools" not in declared:
        tools = False
    return {"model": getattr(ref, "raw", None), "vision": see,
            "thinking": thinks if thinks is not None else not local, "tools": tools,
            "dialect": dialect or getattr(ref, "dialect", "")}
