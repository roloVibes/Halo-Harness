"""halo_harness.providers.ollama_request -- Halo 2.0.3 round 2: the native
`/api/chat` request builder for the `ol:` dialect. Message flattening
reuses `providers.translate._flatten_messages` (the proxy's own proven
algorithm -- single leading system, tool_result pairing, image hoisting)
UNMODIFIED, exactly like `providers.request.build_request_body` already
does for the openai-chat dialect, then adapts the result to Ollama's own
message shape instead of forking the flattening algorithm a second time.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from halo_harness.providers.ollama import OllamaHost, compute_num_ctx, think_value_for_effort
from halo_harness.providers.request import convert_tools
from halo_harness.providers.translate import _flatten_messages

log = logging.getLogger("bridge")



def _text_only(content) -> str:
    """`_flatten_messages` content is a plain string, or (images present) a
    list of `{"type":"text"|"image_url", ...}` parts -- Ollama's native
    message shape wants a plain string; an `image_url` part contributes no
    TEXT here at all (Halo 2.0.3.1: it rides on the message's own native
    `images` field instead -- see `_images_only` below), never a bare
    placeholder string mixed into the prose."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text") or "")
        return "".join(parts)
    return str(content)


def _images_only(content) -> list:
    """Halo 2.0.3.1: every `image_url` part's base64 payload, stripped of
    its `data:<media>;base64,` wrapper -- Ollama's native `images` field on
    a message is a plain list of base64 strings, no media-type envelope of
    its own (research doc Q1's own chat-shape confirmation covers the
    REQUEST side identically to the reply side this module already
    handles)."""
    if not isinstance(content, list):
        return []
    out = []
    for block in content:
        if not (isinstance(block, dict) and block.get("type") == "image_url"):
            continue
        url = (block.get("image_url") or {}).get("url") or ""
        if url.startswith("data:") and ";base64," in url:
            out.append(url.split(";base64,", 1)[1])
    return out


def _ollama_messages_from_oai(oai_messages: list) -> list:
    """Adapt `_flatten_messages`'s OpenAI-chat-shaped protos into Ollama's
    native shape: a tool-result message keys off `tool_name` instead of
    `tool_call_id` (research doc Q1 -- Ollama's replay shape carries no id
    concept at all: `{"role": "tool", "tool_name": "<name>", "content":
    "<result>"}`), and an assistant's `tool_calls[].function.arguments`
    goes back from the JSON STRING `_flatten_messages` always produces to a
    parsed OBJECT (Ollama's own wire shape, Q1: "arguments is a parsed JSON
    object, not a string"). The upstream tool-call id itself is dropped --
    Ollama never sends or expects one back (see `providers.ollama_stream`
    for where Halo's OWN synthesized id comes from on the way IN)."""
    id_to_name: dict = {}
    out = []
    for msg in oai_messages:
        role = msg.get("role")
        if role == "assistant" and msg.get("tool_calls"):
            calls = []
            for tc in msg["tool_calls"]:
                func = tc.get("function") or {}
                name = func.get("name") or "unknown"
                id_to_name[tc.get("id")] = name
                raw_args = func.get("arguments")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) and raw_args.strip() else {}
                except (json.JSONDecodeError, ValueError):
                    args = {}
                calls.append({"function": {"name": name, "arguments": args}})
            out.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        elif role == "tool":
            name = id_to_name.get(msg.get("tool_call_id"), "unknown")
            out.append({"role": "tool", "tool_name": name, "content": _text_only(msg.get("content"))})
        else:
            native: dict = {"role": role, "content": _text_only(msg.get("content"))}
            # Halo 2.0.3.1: `images` rides alongside `content` only when
            # there's at least one -- an ordinary text-only message's wire
            # shape is completely unchanged (no empty `"images": []` added
            # to every request).
            images = _images_only(msg.get("content"))
            if images:
                native["images"] = images
            out.append(native)
    return out


def build_ollama_request_body(
    *, system_text: str, messages: list, tools: Optional[list] = None, tool_choice=None,
    route, profile, effort: Optional[str] = None, host: OllamaHost,
    trained_context: Optional[int] = None, fit_estimate: Optional[int] = None,
    requested_max_tokens: Optional[int] = None,
    learned_cap: Optional[int] = None, remote: bool = False,
    force_format: "Optional[dict]" = None,
    # Review fix pass (findings 5/6) -- pre-resolved by the SAME caller
    # that already resolved `learned_cap`/`remote` (never re-derived
    # here, same "exactly ONE lookup per request" discipline the round
    # 5b additions above already follow); see `providers.ollama.
    # resolve_num_ctx_and_source`'s own docstring for what each one does.
    recorded_does_not_fit: bool = False, cpu_only: bool = False,
    # Review fix pass (finding 16) -- both default True ("benefit of the
    # doubt"/"unchanged", the exact pre-fix behaviour, for every caller
    # that never resolves either one, e.g. this module's own direct unit
    # tests): `agent/loop.py`'s `_build_ollama_body_for_ref` is the ONE
    # real caller that ever passes a resolved `False` for either --
    # `supports_thinking` from the catalog row's own declared
    # `capabilities` (see `providers.ollama_hw.OllamaContextDecision`),
    # `effort_explicit` from whether THIS session's own `effort` was set
    # by an explicit CLI `--effort`/`/effort` THIS session, never merely
    # carried in from an earlier session's persisted `last_effort` (see
    # that method's own docstring for the three call sites).
    supports_thinking: bool = True, effort_explicit: bool = True,
) -> dict:
    """Build the native `/api/chat` body. `messages`/`system_text` are the
    SAME Anthropic-shaped derived-transcript inputs `providers.request.
    build_request_body` takes. `tool_choice` is accepted only for call-site
    symmetry with the other two dialect builders -- Ollama's native API
    documents no `tool_choice`-equivalent field, so it is never put on the
    wire. `options.num_ctx` is computed fresh (round 2's context-ownership
    rule, `providers.ollama.compute_num_ctx`) and sent on EVERY request --
    never relies on a Modelfile default (research doc Q2's unconfirmed
    override order is moot once Halo always sends the field itself).
    `keep_alive` is sent ONLY when the host entry configures one: a request
    that carries `keep_alive` overrides the server's own `OLLAMA_KEEP_ALIVE`
    for that model, so an unconfigured host must leave the field out and let
    the server's setting (the operator's choice, which may be longer than
    Ollama's 5-minute default) stand. Checked live on the round 2 run: with
    the field left out, the server applied its own expiry.

    Halo 2.0.3 round 3 (brief item 2/3): `num_ctx` is computed BEFORE the
    tool list, not after -- the context-class `tools_max` it drives has to
    be known before `convert_tools` checks the catalog against it, not the
    other way around. `agent/loop.py`'s `_sync_ollama_tools_cap` is what
    actually shrinks the SessionCatalog (so the catalog handed in here is
    ALREADY within bounds in the ordinary case); the `dataclasses.replace`
    below is the backstop assertion `ToolCatalogTooLarge`/`request.py`'s
    own docstring describes -- never a second capping path, just the one
    `profile.tools_max` check finally given a real, context-aware number
    for this dialect instead of round 2's permanently-unbounded `None`.
    That number is never pushed BELOW `len(tools)` though: when every
    tool already on the list is frozen/preloaded (nothing left for
    `_sync_ollama_tools_cap`'s own eviction to remove), failing the turn
    over a catalog that is physically unable to shrink any further would
    be exactly the kind of gating house policy forbids -- the backstop's
    job is catching round 2's unbounded-`None` bug, not blocking a turn
    the catalog layer already did everything it could about.

    Round 5b: `learned_cap`/`remote` are pre-resolved by the SAME
    `providers.ollama_hw.resolve_context_decision` call the caller
    (`agent/loop.py`'s `_build_ollama_body_for_ref`) already made to get
    `trained_context`/`fit_estimate` -- passed straight through to
    `compute_num_ctx` rather than re-derived here, so there is exactly
    ONE lookup of the learned-cap store per request, not two.

    Round 5b part 2 (brief item 1, "reliable tool calls"), FIX PASS
    (2026-10-04 live-run finding): constrained decoding is used ONLY to
    REPAIR a malformed call (`force_format`, below -- `agent/loop.py`'s
    `_attempt_tool_repair`), never to FORCE one on an ordinary turn. The
    first version of this round set `format` on every turn `providers.
    tool_call_schema.expected_to_call_tool` judged "expected to call a
    tool" (right after a tool result) -- that FORCED the model to answer
    in the tool-call shape on every such turn, with no way to just
    answer in prose; on a real local box the model had nothing useful
    left to call, emitted a meaningless call (`TaskStop` on a task that
    didn't exist) every time, Halo dispatched it, the NEXT turn was
    STILL constrained post-tool-result, and the session looped for 25
    minutes (175 requests) until killed by hand. A normal turn -- any
    turn that isn't an explicit repair -- is always decoded FREE now: the
    model must always be able to answer in prose. The generic bare-JSON/
    fenced-JSON leak-parser patterns (`profiles.py`'s `tool_leak_
    patterns`) stay enabled regardless -- a schema-shaped reply that
    still arrives as plain text gets promoted to a real tool_use, which
    is harmless without the constraint forcing it. A STRICTER identical-
    call loop guard (`agent/loop.py`'s `_identical_call_guard_*`, three
    in a row on this dialect) is the new backstop against a model stuck
    repeating one call regardless of why."""
    del tool_choice  # no native-API equivalent (see docstring)
    import dataclasses
    from halo_harness.providers.ollama_fit import resolve_ollama_tools_max
    oai_messages = _flatten_messages(messages, system_text)
    ollama_messages = _ollama_messages_from_oai(oai_messages)
    num_ctx = compute_num_ctx(trained_context, host.max_ctx, fit_estimate, learned_cap=learned_cap, remote=remote,
                               recorded_does_not_fit=recorded_does_not_fit, cpu_only=cpu_only)
    tools_max = max(resolve_ollama_tools_max(num_ctx), len(tools or []))
    tools_profile = profile if tools_max == profile.tools_max else dataclasses.replace(profile, tools_max=tools_max)
    oai_tools = convert_tools(tools, tools_profile)
    body: dict = {
        "model": route.upstream_model,
        "messages": ollama_messages,
        "stream": True,
        "options": {"num_ctx": num_ctx},
    }
    if host.keep_alive is not None:
        body["keep_alive"] = host.keep_alive
    if oai_tools:
        body["tools"] = oai_tools
    if force_format is not None:
        # Round 5b part 2 (brief item 2, "repair loop"): `agent/loop.py`'s
        # `_attempt_tool_repair` wants the tool's OWN exact `input_schema`
        # as the constraint on an ISOLATED, tools-less completion -- the
        # ONLY place this module ever sets `format` now (fix pass: an
        # ordinary turn is never constrained, see this function's own
        # docstring).
        body["format"] = force_format
    think = think_value_for_effort(effort, route.upstream_model,
                                    supports_thinking=supports_thinking and effort_explicit)
    if think is not None:
        body["think"] = think
    if isinstance(requested_max_tokens, int) and requested_max_tokens > 0:
        body["options"]["num_predict"] = requested_max_tokens
    return body
