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
    card = getattr(session, "_prompt_card", None) or _probed_card(session)
    return "user-front" if card.get("system_role") == "weak" else "system"


def _probed_card(session) -> dict:
    """3.3.6.0 R1: the battery's dialect facts (providers/placement_apply.prompt_card) when no card was set."""
    try:
        from halo_harness.providers.placement_apply import prompt_card
        return prompt_card(session)
    except Exception:
        return {}


WEAK_NOTE = "(Halo's instructions for this session are at the start of the first user message.)"


def _instructions_to_user(session, system_text: str, messages: list) -> "tuple[str, list]":
    """A probed weak system role (the battery: it ignored the system message): the instructions go into the first
    user message, after the memory, before the user's words; the system message keeps one line pointing there."""
    if not (system_text or "").strip():
        return system_text, messages
    for i, msg in enumerate(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content")
            blocks = list(content) if isinstance(content, list) else [{"type": "text", "text": str(content or "")}]
            from halo_harness.agent.prompt_composition import block_part, known_texts
            known = known_texts(session)
            at = next((j + 1 for j in range(len(blocks) - 1, -1, -1) if isinstance(blocks[j], dict)
                       and block_part(blocks[j].get("text"), known) == "memory"), 0)
            blocks = blocks[:at] + [{"type": "text", "text": system_text}] + blocks[at:]
            card = _probed_card(session)
            model = getattr(getattr(session, "model_ref", None), "raw", "this model")
            _queue_line(session, f"{model} ignores the system role (probed {card.get('probed') or '?'}): Halo's "
                                 "instructions go at the front of the user turn")
            return WEAK_NOTE, messages[:i] + [{**msg, "content": blocks}] + messages[i + 1:]
    return system_text, messages


def _profile_tools_max(session) -> None:
    ref = getattr(session, "model_ref", None)
    session._lean_profile_tools_max = None
    if getattr(ref, "provider", "") == "huggingface":  # 3.3.8.0 R2: a local server's profile (providers/hf_profile.py)
        from halo_harness.providers.hf_profile import tools_max as hf_tools_max
        session._lean_profile_tools_max = hf_tools_max(ref)
        return
    if getattr(ref, "provider", "") != "ollama":
        return
    try:
        from halo_harness.ollama_steward.profiles import lookup
        from halo_harness.providers.ollama import resolve_ollama_host
        env = getattr(getattr(session, "settings", None), "effective_env", None)
        host = resolve_ollama_host(ref.host, env)
        tm = (lookup(host, ref.model, role=getattr(session, "role_name", None) or "") or {}).get("tools_max") \
            if host is not None else None  # 3.3.7.0 R3: the lane's own profile first
        from halo_harness.providers.dialect_apply import tools_max  # 3.3.6.0 R4: the dialect record's wins
        tm = tools_max(session) or tm
        session._lean_profile_tools_max = tm if isinstance(tm, int) and tm > 0 else None
    except Exception:
        log.debug("prompt_wire: the profile's tools_max could not be read", exc_info=True)


def _task_text(messages: list) -> str:
    """The newest user message's own words (the task the tool budget ranks by)."""
    for msg in reversed(messages or []):
        if isinstance(msg, dict) and msg.get("role") == "user":
            c = msg.get("content")
            return c if isinstance(c, str) else " ".join(str(b.get("text") or "") for b in c or [] if isinstance(b, dict)
                                                         and b.get("type") == "text")[-4000:]
    return ""


def _by_name_line(session, offered: list) -> str:  # 3.3.16.1: the names the diet left out (agent/prompt_diet.py)
    from halo_harness.agent.prompt_diet import by_name_line
    dropped = getattr(session, "_diet_dropped", None)
    names = dropped if isinstance(dropped, list) else [t.get("name") for t in offered if isinstance(t, dict)]
    return by_name_line(names)


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
    raw = (system_text, messages, tools)
    if purpose == "turn":
        session._diet_line = None
    known = known_texts(session)
    messages, dups = dedupe(list(messages or []), known)
    lean = L.active(session)
    placement = placement_for(session)
    if lean:
        system_text = L.lean_system(session, system_text)  # 3.3.16.1: the instructions, not the reference prose
        messages = _replace_memory(messages, known, lambda t: L.lean_memory_block(session, t))
        known = {**known, "memory": set(known.get("memory", ())) | {L.lean_memory_block(session, t)
                                                                     for t in known.get("memory", ())}}
    if placement in ("system", "user-front"):
        messages, mem = _take_memory(messages, known)
        if mem and placement == "system":
            system_text = (system_text or "").rstrip() + "\n\n" + mem
        elif mem:
            messages = _front_of_first_user(messages, mem)
    if placement == "user-front" and not getattr(session, "_prompt_card", None) and _probed_card(session).get("from"):
        system_text, messages = _instructions_to_user(session, system_text, messages)
    if lean and tools:
        _profile_tools_max(session)
        tools, dropped = L.cap_tools(session, tools, _task_text(messages))
        from halo_harness.agent.helpers_words import tail as helpers_tail  # 3.6.0.10 M6: from the tools really sent
        helpers = helpers_tail(session, tools)
        if helpers:
            system_text = (system_text or "").rstrip() + helpers
        if dropped and tools:  # 3.3.6.0 R4 (G3): the rest are reachable by name (and through ToolSearch)
            system_text = (system_text or "").rstrip() + "\n\n" + _by_name_line(session, [])
        if dropped and purpose == "turn":
            model = getattr(getattr(session, "model_ref", None), "raw", "this model")
            line = (f"{dropped} tool{'s' if dropped != 1 else ''} not offered to {model} "
                    f"(window {L.call_window(session) or 0:,}): the core tools first, the rest by ToolSearch"
                    if tools else f"no tools offered to {model}: its card says it takes none")
            said = getattr(session, "_prompt_lines_said", None)
            new = not (isinstance(said, set) and line in said)
            _queue_line(session, line)
            session._diet_line = line if new else None  # 3.6.0.12 OS: a one-shot shaped again takes it back
    if purpose == "turn" and getattr(session, "_preflight_sent_now", False):
        messages = order_for_survival(messages, known)
    comp = compose(session, messages, tools, system_text, placement=placement, known=known, duplicates=dups)
    if purpose == "turn":
        prefix = json.dumps([system_text, tools or []], ensure_ascii=False, default=str)
        session._prompt_composition = comp
        session._prompt_prefix = {"tokens": comp["prefix_tokens"],
                                  "hash": hashlib.sha1(prefix.encode("utf-8")).hexdigest()[:12]}
        from halo_harness.agent.model_window import kind_of
        if lean and kind_of(getattr(session, "model_ref", None)) == "ollama":  # 3.6.0.19 LM: its one reader's calls
            session._turn_raw = (raw, tools)  # 3.6.0.12 OS: what `one_shot_shaper` shapes again for the window asked
    return system_text, messages, tools


def one_shot_shaper(session, ref, request, *, raw=None, post=None, purpose: str = "turn"):
    """3.6.0.12 OS: for the main call of an Ollama model on a lean request (a one-shot's; 3.6.0.19 LM: a session of more
    turns' too; a helper call and a cloud model get None and are untouched), `reshape(w)`: this call's request shaped
    again with the diet of a window of `w` (nothing queued, nothing kept; ollama_window_truth.start_window measures each
    ladder step of a one-shot with it); `reshape(None)`: the request shaped for the window the call's block is kept at
    (`session._shape_window`, when it is this model's: a one-shot's ask, a session held at a spill cap), the request the
    call sends, its "not offered" line the one queued; with no such window, or the one `request` was shaped for, the
    very `request`. `request` is `shape`'s output for this call (`raw`, its input, defaults to the one `shape` kept);
    `post` is applied to each shaped request (a measure's fixed paths)."""
    from halo_harness.agent import prompt_lean as L
    from halo_harness.agent.model_window import kind_of
    from halo_harness.agent.ollama_window_truth import is_main_call
    try:
        kept = getattr(session, "_turn_raw", None)
        if raw is None and kept and kept[1] is request[2]:
            raw = kept[0]
        if raw is None or not request[2] or not is_main_call(session, ref) or kind_of(ref) != "ollama" \
                or not L.active(session):
            return None
        before = L.call_window(session)  # the window `request` was shaped for
    except Exception:
        return None
    shaped: dict = {}

    def _at(window: int, how: str):
        was = (getattr(session, "_shape_window", None), getattr(session, "_shape_model", None),
               getattr(session, "_diet_dropped", None))
        session._shape_window, session._shape_model = window, getattr(ref, "raw", None)
        try:
            out = _shape(session, *raw, how)
        except Exception:
            log.debug("prompt_wire: shaping a one-shot's request again failed; sent as shaped", exc_info=True)
            return request
        finally:
            if how != "turn":
                session._shape_window, session._shape_model, session._diet_dropped = was
        return post(out) if post else out

    def reshape(window=None):
        if window is None:
            window = getattr(session, "_shape_window", None) \
                if getattr(session, "_shape_model", None) == getattr(ref, "raw", None) else None
            if window == before or not isinstance(window, int):
                return request
            _take_back(session, getattr(session, "_diet_line", None))
            return _at(window, purpose)
        if window == before:
            return request
        if window not in shaped:
            shaped[window] = _at(window, "measure")
        return shaped[window]
    return reshape


def _take_back(session, line) -> None:
    """A line `_shape` queued for this call and no one has read yet, taken back (the call is shaped again)."""
    if not line:
        return
    from halo_harness.agent.ollama_window import _state
    st = _state(session)
    if line in (st.get("markers") or []):
        st["markers"] = [m for m in st["markers"] if m != line]
        said = getattr(session, "_prompt_lines_said", None)
        if isinstance(said, set):
            said.discard(line)
