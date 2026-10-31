"""halo_harness.providers.model_card_blocks -- Halo 3.3.6.0 R1: the card's
four plain-language blocks (plans/local-model-fit-brief.md E4), each value
marked with one of Part F's three truths (3.3.6.0 R2, models_library/
truths.py): `verified` (the battery probed it on this host), `declared`
(metadata said it: `/api/show`, the library's chips, the hub's tags) or
`expected` (the family rules, the size, the name).

    blocks(card, profile=None) -> {use_for: [{text, mark}], dont_use_for: [...],
                                   sits: {chip, chips, mark}, limits: [{text, mark}]}
    block_lines(blocks) -> the lines `halo models show` and `/model` print
    fit_block(evidence) -> {text, mark, state, source} | None   3.3.6.0 R3: the fit line the log cites
"""

from __future__ import annotations

from typing import Optional

V, D, E = "verified", "declared", "expected"


def _mark(card: dict, field: str) -> str:
    from halo_harness.models_library.truths import mark_of
    return mark_of(card, field)


def _k(n) -> str:
    return f"{n // 1024}k" if isinstance(n, int) and n >= 1024 else str(n)


def _use(p: dict) -> list:
    sits, tok = p.get("sits"), (p.get("speed") or {}).get("tok_s")
    out = {"full agent": ["tool-using sub-agent roles: coder, reviewer, researcher",
                          "anything that needs format obedience (strict replies, JSON)"],
           "reasoner": ["planning, review and judging (it reasons in thinking)"],
           "coder": ["coding steps as a sub-agent with tools"],
           "bulk worker · non-agentic": ["single-shot extraction, classification, compression, shortlisting"],
           "compactor": ["summaries and compaction: text in, text out"]}.get(sits, [])[:]
    if p.get("interactive") == "yes" and sits in ("full agent", "reasoner", "coder"):
        out.append("talking to it directly (/model)" + (" through the user turn" if p.get("system_role") == "weak" else ""))
    if p.get("output") in ("json", "fenced-json") and sits != "full agent":
        out.append("structured output" + (" (the fence is stripped)" if p.get("output") == "fenced-json" else ""))
    if isinstance(tok, (int, float)) and tok >= 150:
        out.append(f"bulk and mechanical passes: {tok:g} tok/s here")
    return [{"text": t, "mark": V} for t in out[:4]]


def _dont(p: dict) -> list:
    from halo_harness.providers.battery_profile import date_of
    out = []
    if p.get("tools") == "no":
        out.append(f"any tool-using sub-agent (no tool calling, probed {date_of(p)})")
    if p.get("interactive") == "no":
        out.append("chat or /model: it is a step model")
    if p.get("identifiers") == "unverified":
        out.append("authoritative ids (CVE / CWE / hashes): resolve them with a tool or a stronger model")
    if p.get("output") == "prose":
        out.append(f"structured output without a JSON repair loop ({p.get('output_why') or 'prose'})")
    if p.get("instruction") == "task-shaped":
        out.append("strict one-word or no-prose formats without a check")
    if p.get("system_role") == "weak":
        out.append("instructions in the system prompt alone (Halo moves them to the user turn)")
    usable = (p.get("window") or {}).get("usable")
    if isinstance(usable, int) and 0 < usable <= 32768:
        out.append("roles that receive whole sessions (compaction): chunk its inputs")
    if (p.get("resident") or {}).get("pivot_only"):
        out.append("sharing the card with another big model: every switch is a pivot")
    return [{"text": t, "mark": V} for t in out]


def _limits(card: dict, p: Optional[dict]) -> list:
    w = (card.get("window") or {})
    out = []
    if p:
        pw, sp, res = p.get("window") or {}, p.get("speed") or {}, p.get("resident") or {}
        mark = V if pw.get("verified") else E
        bits = [f"trained {pw['trained']:,}" if pw.get("trained") else "", f"usable {pw['usable']:,} here" if pw.get("usable") else "",
                (f"verified on the GPU at {pw['used']:,}" if pw.get("verified") else f"not verified at {pw.get('used') or 0:,}")]
        out.append({"text": "window " + " · ".join(b for b in bits if b), "mark": mark})
        if p.get("size_gb"):
            out.append({"text": f"{p['size_gb']:g} GB" + (f", {p['kv_per_token'] // 1024} KB of cache per token"
                                                         if isinstance(p.get("kv_per_token"), int) else ""), "mark": V})
        if res.get("pivot_only") is True:
            out.append({"text": "pivot-only: it needs the card to itself (20-55 s to switch)", "mark": V})
        elif res.get("co_resides_with"):
            out.append({"text": "co-resides with " + ", ".join(res["co_resides_with"][:3]), "mark": V})
        elif res.get("pivot_only") is None:
            out.append({"text": "co-reside or pivot: no hardware card read for this host", "mark": E})
        if sp.get("tok_s"):
            out.append({"text": f"{sp['tok_s']:g} tok/s, first token {sp.get('ttft_ms') or '?'} ms at "
                                f"{_k(sp.get('at_window'))} (warm; the first call after a load is never timed)", "mark": V})
        out.append({"text": f"cold load {sp['cold_load_s']:g} s" if isinstance(sp.get("cold_load_s"), (int, float))
                    else "cold load: not measured (it was loaded already)", "mark": V if sp.get("cold_load_s") else E})
        return out
    if isinstance(w.get("tokens"), int):
        out.append({"text": f"window {w['tokens']:,} ({w.get('source') or 'unknown'})", "mark": _mark(card, "window")})
    if isinstance(card.get("params"), (int, float)):
        out.append({"text": f"{card['params']:g}B parameters" + (f" · {card['quant']}" if card.get("quant") else ""),
                    "mark": _mark(card, "params")})
    out.append({"text": "speed, cold load, co-reside: not measured (halo models probe)", "mark": E})
    return out


def _expected(card: dict) -> "tuple[list, list, str]":
    purpose, tools = card.get("purpose"), card.get("tools")
    use = {"coder": "coding steps", "reasoning": "planning, review and judging", "vision": "reading images",
           "embedding": "embeddings (search, recall)", "instruct": "chat and general steps"}.get(purpose, "")
    sits = ("bulk worker · non-agentic" if tools == "none" else
            {"coder": "coder", "reasoning": "reasoner", "embedding": "bulk worker · non-agentic"}.get(purpose, "full agent"))
    dont = [f"{r}: {why}" for r, why in (card.get("fit_why") or {}).items()][:3]
    return ([{"text": use, "mark": _mark(card, "purpose")}] if use else []), [{"text": d, "mark": E} for d in dont], sits


def blocks(card: dict, profile: Optional[dict] = None) -> dict:
    if profile:
        return {"use_for": _use(profile), "dont_use_for": _dont(profile),
                "sits": {"chip": profile.get("sits"), "chips": list(profile.get("chips") or []), "mark": V},
                "limits": _limits(card, profile)}
    use, dont, sits = _expected(card)
    if card.get("kind") == "cloud":
        return {"use_for": use, "dont_use_for": dont, "sits": {"chip": "", "chips": [], "mark": E}, "limits": []}
    smark = _mark(card, "tools") if card.get("tools") == "none" else _mark(card, "purpose")
    return {"use_for": use, "dont_use_for": dont, "sits": {"chip": sits, "chips": [sits], "mark": smark},
            "limits": _limits(card, None)}


CARD_ROLES_FROM_PROFILE = ("orchestrator", "coder", "reviewer")  # small (size) and eyes (vision) stay declared
PROFILE_KEYS = ("tools", "system_role", "instruction", "output", "output_why", "identifiers", "reasoning", "window",
                "kv_per_token", "size_gb", "speed", "resident", "interactive", "quirks", "agentic_ready", "probed_at",
                "digest", "ollama_version", "probe_set", "sits", "chips", "host", "model",
                "tool_call_accuracy", "tool_call_why")  # 3.3.6.0 R4: the multi-tool probe


def profile_of(state_dir, ref, host, row) -> Optional[dict]:
    """The battery's profile of this model on this host (the capability cache; no request)."""
    try:
        from halo_harness.providers import ollama_capability as C
        if state_dir is None:
            from halo_harness.config.paths import bridge_home
            state_dir = bridge_home()
        name = getattr(host, "name", None) or getattr(ref, "host", None)
        hit = C.load_profile(state_dir, (row or {}).get("digest"), name, any_age=True) if name else None
        return hit or C.profile_for(state_dir, ref.model, name)
    except Exception:
        return None


def with_profile(card: dict, profile: Optional[dict], state_dir=None, host=None) -> dict:
    """The card with its battery profile: `fit_for` becomes the profile's verdicts (orchestrator, coder,
    reviewer; small and eyes can only be vetoed), `fit_source` says verified or expected per role, the
    blocks, the speed, `system_role`, and a `how` line per placement note. No profile: the declared facts,
    every block marked expected."""
    card["fit_source"] = {r: E for r in card.get("fit_for") or {}}
    card["profile"] = {k: profile.get(k) for k in PROFILE_KEYS} if profile else None
    card["system_role"] = None
    if profile:
        from halo_harness.providers.placement import verdict
        card["system_role"] = "weak" if profile.get("system_role") == "weak" else "ok"
        card["speed"] = dict(profile.get("speed") or {}) or None
        probed = "probed" if profile.get("tools") == "yes" else "none"
        if card.get("tools") != probed and profile.get("tools") in ("yes", "no"):
            from halo_harness.providers.model_card_words import how_lines
            card["tools"] = probed
            card["sources"] = {**(card.get("sources") or {}), "tools": "the battery " + (
                "made a call" if probed == "probed" else "got no call")}
            card["how"] = how_lines(card)
        fit, why = dict(card.get("fit_for") or {}), dict(card.get("fit_why") or {})
        notes: list = []
        for role in fit:
            v = verdict(profile, "main" if role == "orchestrator" else role, state_dir=state_dir)
            notes += [n for n in v["notes"] if n not in notes]
            if role in CARD_ROLES_FROM_PROFILE:
                fit[role] = bool(v["ok"])
                card["fit_source"][role] = V
                if v["ok"]:
                    why.pop(role, None)
                else:
                    why[role] = v["why"]
            elif v["ok"] is False:
                fit[role], why[role], card["fit_source"][role] = False, v["why"], V
        card["fit_for"], card["fit_why"] = fit, why
        card["how"] = list(card.get("how") or []) + [n for n in notes if n not in (card.get("how") or [])]
    card["blocks"] = blocks(card, profile)
    card["twin_verify"] = _twin_verify(state_dir, host, card.get("name"))
    if card["twin_verify"]:
        card["how"] = list(card.get("how") or []) + [f"fitted twin, {card['twin_verify']['line']}"]
    return card


def _twin_verify(state_dir, host, name) -> Optional[dict]:
    """A fitted twin's verify result from the tune store (providers/ollama_twin_verify.py), or None."""
    if host is None or not name or not getattr(host, "url", None):
        return None
    try:
        from halo_harness.providers.ollama_tune_store import twin_verify
        if state_dir is None:
            from halo_harness.config.paths import bridge_home
            state_dir = bridge_home()
        v = twin_verify(state_dir, host_url=host.url, twin=name)
        return {k: v.get(k) for k in ("state", "line", "tok_s", "window")} if v else None
    except Exception:
        return None


def fit_block(ev: Optional[dict]) -> Optional[dict]:
    """3.3.6.0 R3: the fit line from the model's last load on its host (providers/fit_evidence.py), verified (the
    server log or /api/ps measured it); None until a load was seen (the rows' badge says "unverified")."""
    if not ev or not ev.get("line") or ev.get("state") not in ("verified", "spilled"):
        return None
    return {"text": ev["line"], "mark": V, "state": ev.get("state"), "source": ev.get("source")}


def block_lines(b: dict) -> list:
    if not b:
        return []
    m = lambda x: "" if x.get("mark") == V else f" ({x.get('mark') or E})"  # noqa: E731
    out = [f"  fit: {b['fit']['text']}" + (f" ({b['fit']['source']})" if b["fit"].get("source") else "")] if b.get("fit") else []
    if (b.get("kv_dial") or {}).get("text"):  # 3.3.6.0 R4: the KV dial (providers/kv_dial.py)
        out += [f"  kv: {b['kv_dial']['text']}"] + ([f"    {b['kv_dial']['crash']}"] if b["kv_dial"].get("crash") else [])
    if (b.get("sits") or {}).get("chip"):
        s = b["sits"]
        out.append(f"  where it sits: {' · '.join(s.get('chips') or [s['chip']])}{m(s)}")
    for key, title in (("use_for", "use it for"), ("dont_use_for", "don't use it for"), ("limits", "limits")):
        if b.get(key):
            out.append(f"  {title}:")
            out.extend(f"    {x['text']}{m(x)}" for x in b[key])
    if b.get("measured"):  # 3.3.6.0 R4: providers/measured.py
        out.append("  measured:")
        out.extend(f"    {x['text']}" for x in b["measured"])
    if (b.get("dialect") or {}).get("lines"):  # 3.3.6.0 R4: providers/dialect.py
        out.append("  how Halo talks to it:")
        out.extend(f"    {x}" for x in b["dialect"]["lines"])
    return out
