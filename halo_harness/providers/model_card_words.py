"""halo_harness.providers.model_card_words -- Halo 3.3.5.0 R0b: a model card
in words (providers/model_card.py builds the record).

    how_lines(card)    the exact way Halo will call it: think, tools, images,
                       window and reserve, dialect
    chips(card)        the picker's chips {think, tools, vision, purpose, window}
    card_line(card)    one line (`halo models --cards`, the TUI picker's row)
    card_lines(card)   `halo models show <ref>` and `/model` with no argument
    what_words(card)   "a coding model", "an embedding model", ...
"""

from __future__ import annotations

PURPOSE_WORDS = {"coder": "a coding model", "instruct": "a chat (instruct) model", "reasoning": "a reasoning model",
                 "vision": "a vision model", "embedding": "an embedding model", "unknown": "a model of unknown purpose"}
ROLE_WORDS = {"orchestrator": "orchestrator", "coder": "coder lane", "reviewer": "reviewer", "small": "small",
              "eyes": "eyes"}


def what_words(card: dict) -> str:
    return PURPOSE_WORDS.get(card.get("purpose") or "unknown", "a model")


def _think_line(card: dict) -> str:
    kind, thinks, choice = card.get("kind"), card.get("thinks"), card.get("think_choice")
    if kind == "cloud":
        return "effort: the route's own levels (/effort lists them)"
    if kind != "ollama":
        return "no effort field (a local server takes none)"
    if thinks == "no":
        return "no think field (the model does not think)"
    from halo_harness.providers.effort_on import think_value, think_word
    word = think_word(think_value(None, card.get("name") or "", explicit=False, think_choice=choice))
    if choice and choice != "default":
        return f"{word} (you set it: models.think)"
    own = "it thinks" if thinks == "default-on" else "the model decides"
    return f"think default: no think field sent, so {own} (/effort on|off sets it)"


def _tools_line(card: dict) -> str:
    tools, kind, dialect = card.get("tools"), card.get("kind"), card.get("dialect")
    if card.get("embedding_only"):
        return "no tools: an embedding model does not chat"
    if tools == "none":
        return "no tools: answers only (tool turns in the history go as text)"
    fmt = ("native Ollama format" if kind == "ollama" and dialect == "native" else
           "the provider's own format" if kind == "cloud" else "OpenAI format")
    why = {"probed": "the probe made a call", "declared": "declared, not probed",
           "unknown": "nothing says; sent as usual"}.get(tools, "")
    return f"tools: {fmt} ({why})" if why else f"tools: {fmt}"


def _window_line(card: dict) -> str:
    w = card.get("window") or {}
    tokens = w.get("tokens")
    if not isinstance(tokens, int) or tokens <= 0:
        return "window unknown (nothing says; the server's default applies)"
    from halo_harness.agent.model_switch import class_reserve
    return f"window {tokens:,} ({w.get('source') or 'unknown'}), reserve {class_reserve(tokens):,}"


def how_lines(card: dict) -> "list[str]":
    out = []
    if card.get("embedding_only"):
        out.append("embeddings only: not a chat model, so Halo sends it no conversation")
    out.append(_think_line(card))
    out.append(_tools_line(card))
    v = card.get("vision")  # 3.3.6.0 R6: None is "nothing says" -- the turn asks before it shares an image
    out.append("images sent as images" if v else "images as captions (no vision)" if v is False or card.get("kind") == "cloud"
               else "images: nothing says it sees (the turn offers the eyes first)")
    out.append(_window_line(card))
    dialect = card.get("dialect") or ""
    out.append("dialect: native (/api/chat)" if dialect == "native" else
               "dialect: OpenAI (/v1/chat/completions)" if dialect == "openai" else f"dialect: {dialect or 'the route'}")
    return out


def _k(tokens) -> str:
    if not isinstance(tokens, int) or tokens <= 0:
        return ""
    return f"{tokens // 1024}k" if tokens % 4096 == 0 else f"{round(tokens / 1000)}k"


def chips(card: dict) -> dict:
    tools = card.get("tools")
    return {"think": {"yes": "think", "default-on": "thinks", "no": ""}.get(card.get("thinks"), ""),
            "tools": {"probed": "tools", "declared": "tools", "none": "no tools", "unknown": "tools?"}.get(tools, ""),
            "vision": "vision" if card.get("vision") else "",
            "purpose": "" if card.get("purpose") == "unknown" else str(card.get("purpose") or ""),
            "window": _k((card.get("window") or {}).get("tokens"))}


def chip_words(card: dict) -> str:
    return " · ".join(v for v in chips(card).values() if v)


def card_line(card: dict, meter: "dict | None" = None) -> str:
    fits = [ROLE_WORDS[r] for r, ok in (card.get("fit_for") or {}).items() if ok]
    tail = f" · fit: {meter.get('word') or meter['level']}" if meter and meter.get("level") else ""
    return f"{card.get('ref')}: {chip_words(card) or '?'} · roles: {', '.join(fits) or 'none'}{tail}"


def _vision_word(card: dict) -> str:
    v = card.get("vision")
    return ("yes" if v else "no" if v is False else "unknown") + (f", {card['vision_truth']}" if card.get("vision_truth") else "")


def card_lines(card: dict, meter: "dict | None" = None) -> "list[str]":
    src = card.get("sources") or {}
    params = f"{card['params']:g}B" if isinstance(card.get("params"), (int, float)) else "size unknown"
    out = [f"{card.get('ref')}: {what_words(card)} ({card.get('kind')}" + (f" on {card['host']}" if card.get("host") else "") + ")",
           f"  family {card.get('family') or '?'} · {params}" + (f" · {card['quant']}" if card.get("quant") else ""),
           f"  thinks: {card.get('thinks')} ({src.get('thinks', '?')})",
           f"  tools: {card.get('tools')} ({src.get('tools', '?')})",
           f"  vision: {_vision_word(card)} ({src.get('vision', '?')})",
           f"  purpose: {card.get('purpose')} ({src.get('purpose', '?')})"]
    if meter:
        out.append(f"  fit here: {meter.get('word') or meter.get('level')} ({meter.get('why')})")
    out.append("  how Halo calls it:")
    out.extend(f"    {line}" for line in card.get("how") or [])
    out.append("  roles:")
    marks = card.get("fit_source") or {}
    for role, ok in (card.get("fit_for") or {}).items():
        tail = " (expected)" if marks.get(role) == "expected" and card.get("profile") else ""
        out.append(f"    {ROLE_WORDS[role]}: " + ("yes" if ok else f"no ({(card.get('fit_why') or {}).get(role, '')})") + tail)
    from halo_harness.providers.model_card_blocks import block_lines  # 3.3.6.0 R1: E4's four blocks
    if card.get("profile"):
        from halo_harness.providers.battery_profile import date_of
        out.append(f"  probed {date_of(card['profile'])} (halo models probe {card.get('ref')} --force re-probes)")
    else:
        out.append(f"  not probed yet: halo models probe {card.get('ref')} (every value below is expected)")
    out.extend(block_lines(card.get("blocks") or {}))
    return out
