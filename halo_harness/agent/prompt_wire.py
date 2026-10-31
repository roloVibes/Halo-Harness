"""halo_harness.agent.prompt_wire -- Halo 3.3.5.0 R4: the wire copy of a
request, shaped before the dialect builders (`agent/loop.py`'s
`_derive_and_build` and the compaction's summary call). The log is never
touched.

    shape(session, system_text, messages, tools, *, purpose="turn") -> (system, messages, tools)

In order:
1. dedupe: a memory block or a CLAUDE.md block that is in the request more
   than once is kept once, the newest (`prompt_composition.dedupe`);
2. placement: on a local model the memory block (MEMORY.md and the topic
   index) moves to the end of the system message -- the front of the
   prompt, the part Ollama may cut, and part of the stable prefix the KV
   cache keeps -- or, when the model's card says its system role is weak
   (`system_role: "weak"`, the dialect record: placement "user-front"), to
   the front of the first user message; a cloud model keeps it where its
   user-role snapshot put it (placement "user");
3. the lean profile (`prompt_lean`): the topic index as pointers, the memory
   capped, the tool catalog capped (a line says how many were not offered);
4. survival order, only on a request the preflight let through over the
   window (`session._preflight_sent_now`): the compaction summary moves into
   the last user message, before the user's own words, so the tail Ollama
   keeps holds the task;
5. the composition (`prompt_composition.compose`) is kept on the session
   (`_prompt_composition`) with the prefix's tokens and hash (`_prompt_prefix`).
"""

from __future__ import annotations

import hashlib
import json
import logging

log = logging.getLogger("bridge")


def placement_for(session) -> str:
    from halo_harness.agent.prompt_lean import is_local
    if not is_local(getattr(session, "model_ref", None)):
        return "user"
    card = getattr(session, "_prompt_card", None) or {}
    return "user-front" if card.get("system_role") == "weak" else "system"


def _profile_tools_max(session) -> None:
    ref = getattr(session, "model_ref", None)
    session._lean_profile_tools_max = None
    if getattr(ref, "provider", "") != "ollama":
        return
    try:
        from halo_harness.ollama_steward.profiles import lookup
        from halo_harness.providers.ollama import resolve_ollama_host
        env = getattr(getattr(session, "settings", None), "effective_env", None)
        host = resolve_ollama_host(ref.host, env)
        tm = (lookup(host, ref.model) or {}).get("tools_max") if host is not None else None
        session._lean_profile_tools_max = tm if isinstance(tm, int) and tm > 0 else None
    except Exception:
        log.debug("prompt_wire: the profile's tools_max could not be read", exc_info=True)


def _take_memory(messages: list, known: dict) -> "tuple[list, str]":
    from halo_harness.agent.prompt_composition import block_part
    found = ""
    out = []
    for msg in messages:
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list) or msg.get("role") != "user":
            out.append(msg)
            continue
        keep = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text" and block_part(b.get("text"), known) == "memory":
                found = b.get("text") or found
            else:
                keep.append(b)
        if keep:
            out.append({**msg, "content": keep} if len(keep) != len(content) else msg)
        elif len(keep) != len(content):
            out.append({**msg, "content": [{"type": "text", "text": "(the memory is in the system prompt)"}]})
    return out, found


def _replace_memory(messages: list, known: dict, fn) -> list:
    from halo_harness.agent.prompt_composition import block_part
    out = []
    for msg in messages:
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list) or msg.get("role") != "user":
            out.append(msg)
            continue
        new = [({**b, "text": fn(b.get("text") or "")}
                if isinstance(b, dict) and b.get("type") == "text" and block_part(b.get("text"), known) == "memory" else b)
               for b in content]
        out.append({**msg, "content": new})
    return out


def _front_of_first_user(messages: list, text: str) -> list:
    for i, msg in enumerate(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content")
            blocks = content if isinstance(content, list) else [{"type": "text", "text": str(content or "")}]
            return messages[:i] + [{**msg, "content": [{"type": "text", "text": text}] + list(blocks)}] + messages[i + 1:]
    return [{"role": "user", "content": [{"type": "text", "text": text}]}] + list(messages)


def order_for_survival(messages: list, known: dict) -> list:
    """The compaction summary moved into the last user message, before the
    user's own words (Ollama keeps 4 tokens of the start and the tail)."""
    from halo_harness.agent.prompt_composition import block_part
    last = max((i for i, m in enumerate(messages) if isinstance(m, dict) and m.get("role") == "user"), default=-1)
    if last < 0:
        return messages
    moved, out = [], []
    for i, msg in enumerate(messages):
        content = msg.get("content") if isinstance(msg, dict) else None
        if i == last or not isinstance(content, list) or msg.get("role") != "user":
            out.append(msg)
            continue
        keep = [b for b in content if not (isinstance(b, dict) and b.get("type") == "text"
                                           and block_part(b.get("text"), known) == "summary")]
        moved += [b for b in content if b not in keep]
        if keep:
            out.append({**msg, "content": keep} if len(keep) != len(content) else msg)
        else:
            out.append({**msg, "content": [{"type": "text", "text": "(the summary of the earlier conversation is "
                                                                    "with the latest message)"}]})
    if not moved:
        return messages
    tail = out[last]
    content = list(tail.get("content") or []) if isinstance(tail.get("content"), list) else \
        [{"type": "text", "text": str(tail.get("content") or "")}]
    # the user's own words go after everything else in the message (Halo's notes, the summary): the tail is the task
    words = [b for b in content if isinstance(b, dict) and b.get("type") == "text"
             and block_part(b.get("text"), known) == "text"]
    rest = [b for b in content if not any(b is w for w in words)]
    out[last] = {**tail, "content": rest + moved + words}
    return out


def _queue_line(session, line: str) -> None:
    said = getattr(session, "_prompt_lines_said", None)
    if not isinstance(said, set):
        said = session._prompt_lines_said = set()
    if line in said:
        return
    said.add(line)
    from halo_harness.agent.ollama_window import _state
    st = _state(session)  # drained before the call (`agent/loop.py`'s `_step`) as a `↳` line
    st["markers"] = st.get("markers", []) + [line]


def composition_now(session):
    """The last request's composition, else the one the next request would have (`/cost`, `/status`)."""
    comp = getattr(session, "_prompt_composition", None)
    if comp:
        return comp
    try:
        from halo_harness.agent.derive import derive_request
        from halo_harness.agent.prompt_composition import compose, known_texts
        system_text, messages, tools = shape(session, *derive_request(session.log, tools=None), purpose="preview")
        return compose(session, messages, tools, system_text, placement=placement_for(session),
                       known=known_texts(session))
    except Exception:
        return None


def shape(session, system_text: str, messages: list, tools, *, purpose: str = "turn"):
    try:
        return _shape(session, system_text, messages, tools, purpose)
    except Exception:
        log.debug("prompt_wire: shaping the request failed; sent as derived", exc_info=True)
        return system_text, messages, tools


def _shape(session, system_text: str, messages: list, tools, purpose: str):
    from halo_harness.agent import prompt_lean as L
    from halo_harness.agent.prompt_composition import compose, dedupe, known_texts
    known = known_texts(session)
    messages, dups = dedupe(list(messages or []), known)
    lean = L.active(session)
    placement = placement_for(session)
    if lean:
        messages = _replace_memory(messages, known, lambda t: L.lean_memory_block(session, t))
        known = {**known, "memory": set(known.get("memory", ())) | {L.lean_memory_block(session, t)
                                                                     for t in known.get("memory", ())}}
    if placement in ("system", "user-front"):
        messages, mem = _take_memory(messages, known)
        if mem and placement == "system":
            system_text = (system_text or "").rstrip() + "\n\n" + mem
        elif mem:
            messages = _front_of_first_user(messages, mem)
    if lean and tools:
        _profile_tools_max(session)
        tools, dropped = L.cap_tools(session, tools)
        if dropped and purpose == "turn":
            model = getattr(getattr(session, "model_ref", None), "raw", "this model")
            _queue_line(session, (f"{dropped} tool{'s' if dropped != 1 else ''} not offered to {model} "
                                  f"(window {L.window_of(session) or 0:,}): the core tools first, the long tail left out"
                                  if tools else f"no tools offered to {model}: its card says it takes none"))
    if purpose == "turn" and getattr(session, "_preflight_sent_now", False):
        messages = order_for_survival(messages, known)
    comp = compose(session, messages, tools, system_text, placement=placement, known=known, duplicates=dups)
    if purpose == "turn":
        prefix = json.dumps([system_text, tools or []], ensure_ascii=False, default=str)
        session._prompt_composition = comp
        session._prompt_prefix = {"tokens": comp["prefix_tokens"],
                                  "hash": hashlib.sha1(prefix.encode("utf-8")).hexdigest()[:12]}
    return system_text, messages, tools
