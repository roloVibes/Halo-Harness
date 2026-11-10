"""halo_harness.ollama_steward.rules_prompt -- Halo 3.3.16.1 "the local prompt diet": `prompt-heavy`.

Halo's own part of a request -- its system text, the memory and topic index it carries, the tool
schemas (the ledger line's `composition`, agent/prompt_composition.ledger_fields) -- is more than half of
the window the newest call to the model went out at: the conversation gets the rest. One next step, the
first that applies:

    the lean profile is off (`prompt.lean`)      -> turn it on (`halo config set prompt.lean auto`)
    the window can grow (the cap is larger)      -> a bigger window: Halo's part half of it at most (num_ctx)
    otherwise                                    -> the core tools only (tools_max)
"""

from __future__ import annotations

from halo_harness.ollama_steward.rules import finding, hint, proposal

HEAVY = 0.5
OWN = ("system", "memory", "topic_index", "tools_schema")


def own_part(line: dict) -> int:
    comp = line.get("composition") or {}
    return sum(int(comp.get(k) or 0) for k in OWN if isinstance(comp.get(k), (int, float)))


def _pow2_ceil(n: int) -> int:
    p = 1
    while p < n:
        p *= 2
    return p


def _lean_off() -> bool:
    try:
        from halo_harness.agent.prompt_lean import knobs
        return knobs()["lean"] == "off"
    except Exception:
        return False


def prompt_heavy(g: dict, ctx: dict) -> list:
    calls = [x for x in g["stats"]["native"] if isinstance(x.get("num_ctx_sent"), int) and x["num_ctx_sent"] > 0
             and own_part(x) > 0]
    if not calls:
        return []
    last = calls[-1]
    own, window = own_part(last), last["num_ctx_sent"]
    share = own / window
    if share <= HEAVY:
        return []
    nums = {"own": own, "window": window, "share": round(share, 2)}
    text = f"Halo's own prompt is {share:.0%} of {g['model']}'s window ({own:,} of {window:,} tokens): "
    cap = g.get("cap")
    if _lean_off():
        return [finding("prompt-heavy", g, "warn", text + "turn the lean profile on", calls=[last], numbers=nums,
                        server_hint=hint(None, "halo config set prompt.lean auto",
                                         "the short tool descriptions and system text a local model gets"))]
    if cap and cap > window:
        to = min(cap, _pow2_ceil(2 * own + 1))
        return [finding("prompt-heavy", g, "warn", text + f"a bigger window ({to:,})", calls=[last], numbers=nums,
                        proposal=proposal("num_ctx", g["profile"].get("num_ctx"), to,
                                          f"Halo's own {own:,} tokens at most half the window"))]
    from halo_harness.providers.ollama_fit import CORE_TOOL_NAMES
    to = len(CORE_TOOL_NAMES)
    cur = g["profile"].get("tools_max")
    if cur and cur <= to:
        return [finding("prompt-heavy", g, "warn", text + "the window is at its cap and the tools at the core set: "
                        "a model with a bigger window", calls=[last], numbers=nums)]
    return [finding("prompt-heavy", g, "warn", text + f"offer the {to} core tools (the rest by ToolSearch)",
                    calls=[last], numbers=nums,
                    proposal=proposal("tools_max", cur, to, "the core tools; the rest stay reachable through ToolSearch"))]


RULES = [prompt_heavy]
