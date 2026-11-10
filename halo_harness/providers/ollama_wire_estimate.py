"""halo_harness.providers.ollama_wire_estimate -- Halo 3.3.16.1 "the estimate is the wire's".

The window was chosen from an estimate over the Anthropic-shaped request (content blocks, `input_schema`)
while the body sent is Ollama-shaped (flat message strings, `{"type": "function", "function": ...}` tools):
the two differed by about 0.5 % on a first turn, enough to put a request one side or the other of a
power-of-two window. `wire_estimate` counts the body that is sent: the same flattening and tool
conversion `ollama_request.build_ollama_request_body` applies, then `ollama_prompt`'s one rule (chars /
3.5 + the reply's room).

    wire_shape(system, messages, tools) -> (wire messages, wire tools)
    wire_estimate(system, messages, tools, *, reply_tokens=None) -> int
"""

from __future__ import annotations


def wire_shape(system_text: str, messages, tools) -> "tuple[list, list]":
    from halo_harness.providers.ollama_request import _ollama_messages_from_oai
    from halo_harness.providers.request import anthropic_tool_to_openai
    from halo_harness.providers.translate import _flatten_messages
    wire_messages = _ollama_messages_from_oai(_flatten_messages(list(messages or []), system_text or ""))
    ordered = sorted((t for t in tools or [] if isinstance(t, dict)), key=lambda t: t.get("name", ""))
    return wire_messages, [anthropic_tool_to_openai(t) for t in ordered]


def wire_estimate(system_text: str, messages, tools, *, reply_tokens=None) -> int:
    """The estimate of the request as it goes on the wire (what `_floor_of` reads back from a sent body)."""
    from halo_harness.providers.ollama_prompt import estimate_request_tokens
    try:
        wire_messages, wire_tools = wire_shape(system_text, messages, tools)
    except Exception:
        return estimate_request_tokens(messages, tools, system_text, reply_tokens=reply_tokens)
    return estimate_request_tokens(wire_messages, wire_tools, "", reply_tokens=reply_tokens)
