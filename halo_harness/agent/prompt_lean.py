"""halo_harness.agent.prompt_lean -- Halo 3.3.5.0 R4: the lean profile, what
Halo sends a local model (or any model with a window under 64k).

    knobs()                          {lean, topics_max, memory_max_tokens, preflight} from config `prompt.*`
    is_local(ref)                    an `ol:`, `hf:local`, `hf:mlx` or `local:` model
    active(session)                  `prompt.lean`: on | off | auto (auto: local, or a window under 64k)
    trim_topics(text, entries, n)    one line per topic file (its name and one sentence), the n newest
    cap_memory(text, max_tokens)     MEMORY.md held to max_tokens, the newest entries kept, the cut said once
    lean_memory_block(session, text) both, on one memory block, the same answer for the whole session
    tools_cap(session, window)       how many tools the model gets (None: no cap)
    cap_tools(session, tools)        (tools, dropped): the core tools first, the long tail dropped

The cap per window: under 16,384 the core names (`ollama_fit.CORE_TOOL_NAMES`),
up to 32,768 the built-in set, under 65,536 sixty-four; the steward profile's
`tools_max` wins when set; a model whose card says no tools gets none. The
answer for a memory block is kept on the session, so the prefix the model's
cache holds stays byte-stable while topic files are touched.
"""

from __future__ import annotations

import os
import re
from typing import Optional

LEAN_WINDOW = 65536
DEFAULTS = {"lean": "auto", "topics_max": 12, "memory_max_tokens": 4000, "preflight": "ask"}
_SENTENCE = re.compile(r"^(.{1,160}?[.!?])(\s|$)")


def knobs() -> dict:
    from halo_harness.theme import get_config_value
    out = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        try:
            v = get_config_value(f"prompt.{key}", default=default)
        except Exception:
            v = default
        if isinstance(default, int) and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
            v = default
        if key == "lean" and v not in ("auto", "on", "off"):
            v = "on" if v is True else "off" if v is False else default
        if key == "preflight" and v not in ("ask", "compact", "send"):
            v = default
        out[key] = v
    return out


def is_local(ref) -> bool:
    from halo_harness.agent.model_window import kind_of
    return ref is not None and kind_of(ref) != "cloud"


def window_of(session) -> Optional[int]:
    w = getattr(getattr(session, "model_profile", None), "context_tokens", None)
    return w if isinstance(w, int) and w > 0 else None


def active(session) -> bool:
    mode = knobs()["lean"]
    if mode in ("on", "off"):
        return mode == "on"
    w = window_of(session)
    return is_local(getattr(session, "model_ref", None)) or (w is not None and w < LEAN_WINDOW)


def _sentence(text: str) -> str:
    t = " ".join(str(text or "").split())
    m = _SENTENCE.match(t)
    if m:
        return m.group(1)
    return t if len(t) <= 160 else t[:157].rstrip() + "..."


def _touched(entry) -> float:
    try:
        return os.path.getmtime(entry.path)
    except (OSError, TypeError, AttributeError):
        return 0.0


def trim_topics(text: str, entries: list, topics_max: int) -> str:
    """The topic index as one pointer line per topic file, the newest `topics_max`, then "N more"."""
    head, _, _ = text.partition("\n\n")
    if not entries:
        return text
    newest = sorted(entries, key=lambda e: (-_touched(e), getattr(e, "name", "")))
    keep = newest[:topics_max] if topics_max else []
    lines = [f"- {e.name}: {_sentence(e.description) or '(no description)'}" for e in keep]
    more = len(entries) - len(keep)
    if more > 0:
        lines.append(f"{more} more: `/memory topics` lists every topic file")
    return head + "\n\n" + "\n".join(lines)


def cap_memory(text: str, max_tokens: int) -> str:
    """The MEMORY.md part held to `max_tokens`: headings kept, then the newest
    entries (the file's last lines) that fit, in the file's order."""
    from halo_harness.agent.prompt_composition import tokens_of
    if not max_tokens or tokens_of(text) <= max_tokens:
        return text
    lines = text.split("\n")
    lead = [ln for ln in lines[:3]]  # the directory line, the blank, the heading
    rest = lines[3:]
    heads = [i for i, ln in enumerate(rest) if ln.startswith("#")]
    budget = max_tokens - tokens_of("\n".join(lead)) - 40
    kept: set = set(heads)
    used = sum(tokens_of(rest[i]) for i in heads)
    for i in range(len(rest) - 1, -1, -1):
        if i in kept or not rest[i].strip():
            continue
        cost = tokens_of(rest[i]) + 1
        if used + cost > budget:
            break
        kept.add(i)
        used += cost
    cut = sum(1 for i, ln in enumerate(rest) if i not in kept and ln.strip())
    body = [ln for i, ln in enumerate(rest) if i in kept]
    note = (f"[{cut} older memory lines not sent: this model's memory budget is {max_tokens:,} tokens "
            f"(prompt.memory_max_tokens); the file holds them all]")
    return "\n".join(lead + body + ["", note])


def lean_memory_block(session, text: str) -> str:
    from halo_harness.agent.prompt_composition import TOPICS_HEAD, split_memory
    cache = getattr(session, "_lean_memory_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        try:
            session._lean_memory_cache = cache
        except Exception:
            pass
    if text in cache:
        return cache[text]
    k = knobs()
    mem, topics = split_memory(text)
    entries = []
    store = getattr(getattr(session, "session_context", None), "memory_store", None)
    if topics and store is not None:
        try:
            entries = store.entries()
        except Exception:
            entries = []
    if topics.startswith(TOPICS_HEAD) and entries:
        topics = trim_topics(topics, entries, k["topics_max"])
    mem = cap_memory(mem, k["memory_max_tokens"]) if mem else mem
    out = "\n\n".join(p for p in (mem, topics) if p)
    cache[text] = out
    return out


def _builtin_names() -> list:
    try:
        from halo_harness.tools.registry import default_tools
        return [t.name for t in default_tools()]
    except Exception:
        return []


def tools_cap(session, window: Optional[int]) -> Optional[int]:
    """The steward profile's `tools_max`, else the lean class of the window; None: no cap."""
    from halo_harness.providers.ollama_fit import CORE_TOOL_NAMES
    profile = getattr(session, "_lean_profile_tools_max", None)
    if isinstance(profile, int) and profile > 0:
        return profile
    if not isinstance(window, int) or window <= 0:
        return None
    if window < 16384:
        return len(CORE_TOOL_NAMES)
    if window <= 32768:
        return max(len(CORE_TOOL_NAMES), len(_builtin_names()))
    return 64 if window < LEAN_WINDOW else None


def no_tools(session) -> bool:
    caps = getattr(session, "_switch_caps", None) or {}
    if caps.get("tools") is False and caps.get("model") == getattr(getattr(session, "model_ref", None), "raw", None):
        return True
    card = getattr(session, "_prompt_card", None) or {}
    return card.get("tools") == "none" or bool(card.get("embedding_only"))


def cap_tools(session, tools) -> "tuple[list, int]":
    """(the tools sent, how many were not offered): the core names first, then
    the built-in set, then the rest in the catalog's order, up to the cap; the
    kept ones go out in the catalog's own order (a stable prefix)."""
    from halo_harness.providers.ollama_fit import CORE_TOOL_NAMES
    tools = list(tools or [])
    if not tools:
        return tools, 0
    if no_tools(session):
        return [], len(tools)
    cap = tools_cap(session, window_of(session))
    if cap is None or len(tools) <= cap:
        return tools, 0
    builtin = set(_builtin_names())
    name = lambda t: t.get("name") if isinstance(t, dict) else None  # noqa: E731
    rank = {id(t): (0 if name(t) in CORE_TOOL_NAMES else 1 if name(t) in builtin else 2, i) for i, t in enumerate(tools)}
    keep = {id(t) for t in sorted(tools, key=lambda t: rank[id(t)])[:cap]}
    out = [t for t in tools if id(t) in keep]
    return out, len(tools) - len(out)
