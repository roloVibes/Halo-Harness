"""halo_harness.providers.battery_profile -- Halo 3.3.6.0 R1: the profile a
battery run writes (plans/local-model-fit-brief.md Part E2; the field names
are Part I's glossary).

    Profile = {model, host, digest, ollama_version, probe_set, probed_at,
      tools: yes|no, system_role: honoured|weak, instruction: task-shaped|strict,
      output: json|fenced-json|prose, output_why, identifiers: trusted|unverified,
      reasoning: none|thinking, window: {trained, usable, used, verified: bool},
      kv_per_token, size_gb, speed: {tok_s, ttft_ms, cold_load_s, at_window},
      resident: {co_resides_with: [...], pivot_only: bool | None}, interactive: yes|no,
      quirks: [...], agentic_ready: bool, evidence: {probe: answer}, sits, chips: [...]}

`agentic_ready` is the composite gate: tools and system role and instruction
and JSON (a fenced reply counts: the wire strips the fence, Part E3).
`interactive` asks whether it is worth talking to directly: it calls tools
(a chat in Halo is a tool-using main agent), it answered in `content` on the
user turn, and it generates at `INTERACTIVE_TOK_S` or faster; a weak system
role does not make it "no" (the instruction moves to the user turn, E3).
`sits` is the one placement chip (E4); `chips` adds `pivot-only` and
`not interactive` when they hold. Nothing here sends a request.
"""

from __future__ import annotations

from typing import Optional

INTERACTIVE_TOK_S = 8.0
BULK_TOK_S = 150.0
QUIRK_WORDS = {
    "system": "ignores system prompts (Halo puts its instructions in the user turn)",
    "thinking": "answers in thinking: a small reply budget looks empty (the reserve is raised)",
    "identifiers": "invents reference ids (CVE / CWE / hashes): resolve them with a tool or a stronger model",
    "fence": "wraps JSON in a ``` fence (stripped before parsing)",
    "instruction": "ignores strict format demands: check what it returns",
    "no-tools": "cannot emit a tool call: single-shot steps only",
}
SHORT_WINDOW = 32768


def agentic_ready(p: dict) -> bool:
    return (p.get("tools") == "yes" and p.get("system_role") == "honoured" and p.get("instruction") == "strict"
            and p.get("output") in ("json", "fenced-json"))


def interactive(p: dict) -> str:
    tok = ((p.get("speed") or {}).get("tok_s"))
    answered = bool(((p.get("evidence") or {}).get("instruction") or {}).get("content", "").strip())
    fast = tok is None or tok >= INTERACTIVE_TOK_S
    return "yes" if p.get("tools") == "yes" and answered and fast else "no"


def quirks(p: dict) -> list:
    out = []
    if p.get("tools") == "no":
        out.append(QUIRK_WORDS["no-tools"])
    if p.get("system_role") == "weak":
        out.append(QUIRK_WORDS["system"])
    if p.get("reasoning") == "thinking":
        out.append(QUIRK_WORDS["thinking"])
    if p.get("identifiers") == "unverified":
        out.append(QUIRK_WORDS["identifiers"])
    if p.get("output") == "fenced-json":
        out.append(QUIRK_WORDS["fence"])
    if p.get("instruction") == "task-shaped" and p.get("tools") == "yes":
        out.append(QUIRK_WORDS["instruction"])
    usable = (p.get("window") or {}).get("usable")
    if isinstance(usable, int) and 0 < usable <= SHORT_WINDOW:
        out.append(f"a {usable // 1024}k window here: chunk inputs; never a role that receives whole sessions")
    cold = (p.get("speed") or {}).get("cold_load_s")
    if isinstance(cold, (int, float)) and cold >= 10:
        out.append(f"the first request after a load pays ~{cold:.0f} s")
    return out


def sits(p: dict) -> str:
    """The one placement chip."""
    if p.get("tools") == "no":
        tok = (p.get("speed") or {}).get("tok_s")
        if p.get("output") in ("json", "fenced-json") or (isinstance(tok, (int, float)) and tok >= BULK_TOK_S):
            return "bulk worker · non-agentic"
        return "compactor"
    if agentic_ready(p):
        return "full agent"
    if p.get("reasoning") == "thinking":
        return "reasoner"
    return "coder"


def chips(p: dict) -> list:
    out = [sits(p)]
    if (p.get("resident") or {}).get("pivot_only"):
        out.append("pivot-only")
    if p.get("interactive") == "no":
        out.append("not interactive")
    return out


def finish(p: dict) -> dict:
    """The derived labels filled in on a profile whose probe fields are set."""
    p["agentic_ready"] = agentic_ready(p)
    p["interactive"] = interactive(p)
    p["quirks"] = quirks(p)
    p["sits"] = sits(p)
    p["chips"] = chips(p)
    return p


def resident(this_need: Optional[float], others: list, budget: Optional[int], reserve: float = 0.0) -> dict:
    """{co_resides_with, pivot_only}: `others` = [(name, need_bytes, weight_bytes)] of the host's other models.
    It co-resides with a model when both fit the budget together; pivot-only when the host has a big model
    (a quarter of the card or more) and it shares the card with none of them. None: no budget to say."""
    if not isinstance(budget, int) or budget <= 0 or not isinstance(this_need, (int, float)):
        return {"co_resides_with": [], "pivot_only": None}
    together = [n for n, need, _w in others if isinstance(need, (int, float)) and this_need + need + reserve <= budget]
    big = [n for n, _need, w in others if isinstance(w, (int, float)) and w >= budget / 4]
    pivot = bool(big) and not any(n in together for n in big)
    if this_need + reserve > budget:
        pivot = True
    return {"co_resides_with": together, "pivot_only": pivot}


def date_of(p: Optional[dict]) -> str:
    import time
    at = (p or {}).get("probed_at")
    return time.strftime("%Y-%m-%d", time.localtime(at)) if isinstance(at, (int, float)) else "never"


def summary_line(p: dict) -> str:
    """'tools yes · system honoured · instruction strict · json · no thinking · ids trusted · 187 tok/s'."""
    s = p.get("speed") or {}
    bits = [f"tools {p.get('tools')}", f"system {p.get('system_role')}", f"instruction {p.get('instruction')}",
            str(p.get("output")), "thinks" if p.get("reasoning") == "thinking" else "no thinking",
            f"ids {p.get('identifiers')}"]
    if s.get("tok_s"):
        bits.append(f"{s['tok_s']:g} tok/s")
    return " · ".join(bits)
