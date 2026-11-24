"""halo_harness.agent.prompt_diet -- Halo 3.3.16.1 "the local prompt diet": the lean tool block
(`prompt_lean.cap_tools` calls `diet`; docs/MODELS-prompt-diet.md).

    ALIASES                           {alias: canonical}: one tool under two names goes on the wire once
    aliases_once(tools)               the alias left out wherever its canonical is in the list
    lean_shell(platform)              the one shell a lean Windows session offers (`prompt.shell`)
    tools_budget(window)              the lean tool block's tokens: 2,200 to 16,384, 4,500 under 65,536 (a set-up
                                      copilot_ask rides on top of the 4,500 one, 3.6.0.19 LM: `ON_TOP`)
    call_window(session)              the window the next call gets (a one-shot: the window it asks; an `ol:`
                                      model: its resolved num_ctx)
    workflow_needed(session)          an enabled square covers something this model does not take
    diet(session, tools, task, cap)   (kept, dropped names): the order, the budget, the lean descriptions
    by_name_line(dropped)             the one system line naming what was left out (ToolSearch loads it)

The order the cap and the budget fill: the core tools (`ollama_fit.CORE_TOOL_NAMES`, the session's one
shell in Bash's place), then what the session's lineup needs (Workflow only when a square is enabled
for this lineup and the model lacks something a square covers), then `AFTER_NEEDS` (copilot_ask, 3.3.17.0:
registered only once Copilot is set up, so asked for), then the built-ins in the registry's
order, then the rest (MCP tools) by relevance to the task. `BY_NAME_UNDER` (3.6.0.6 W: Browser) names a tool
offered by name only in a window of that size or less, whatever room is left. A tool left out stays callable by name and
ToolSearch shows its schema, exactly as a deferred tool. The kept tools go out lean
(`tools/lean_descriptions.py`) and in the catalog's own order (a stable prefix).
"""

from __future__ import annotations

import sys
from typing import Optional

ALIASES = {"Task": "Agent"}
LEAN_TOOLS_BUDGET = ((16385, 2200), (65536, 4500))  # (below, tokens): 16,384 and under; under 65,536
SHELLS = ("Bash", "PowerShell")
AFTER_NEEDS = ("copilot_ask",)  # offered only once set up (tools/copilot_ask.py): right after the lineup's needs
# 3.6.0.6 W: offered by name only in a window of this size or less (the smallest lean block never grows for it)
BY_NAME_UNDER = {"Browser": 16384}
# 3.6.0.10 MW batch 4: a top session's own built-in (headless.py registers it): ranked as the LAST of the built-ins, before
# the tools of packs and MCP servers, and counted with them where the cap is the built-ins' count (prompt_lean.tools_cap)
LAST_BUILTINS = ("Builder",)
# 3.6.0.19 LM (the coordinator's ruling: neither the Builder nor copilot_ask gives way): copilot_ask, once set up, rides
# on top of this budget (the 4,500 one: over 16,384, under 65,536) and is not counted in the cap there
ON_TOP, ON_TOP_OF = ("copilot_ask",), 4500


def tools_budget(window: Optional[int]) -> Optional[int]:
    """The lean tool block's token budget for `window` (None: no budget, a window of 65,536 or more)."""
    if not isinstance(window, int) or window <= 0:
        from halo_harness.providers.ollama import REMOTE_UNKNOWN_DEFAULT_NUM_CTX
        window = REMOTE_UNKNOWN_DEFAULT_NUM_CTX
    for below, budget in LEAN_TOOLS_BUDGET:
        if window < below:
            return budget
    return None


def _name(t) -> Optional[str]:
    return t.get("name") if isinstance(t, dict) else None


def aliases_once(tools: list) -> list:
    names = {_name(t) for t in tools}
    return [t for t in tools if ALIASES.get(_name(t)) not in names]


def lean_shell(platform: Optional[str] = None) -> Optional[str]:
    """Windows: the shell `prompt.shell` names (`auto`: Bash when Git Bash is found, else PowerShell);
    None elsewhere (PowerShell is a Windows tool, Bash the only shell)."""
    if (platform or sys.platform) != "win32":
        return None
    from halo_harness.theme import get_config_value
    try:
        v = str(get_config_value("prompt.shell", default="auto") or "auto").lower()
    except Exception:
        v = "auto"
    if v in ("bash", "powershell"):
        return "Bash" if v == "bash" else "PowerShell"
    try:
        from halo_harness.config.paths import git_bash
        return "Bash" if git_bash() else "PowerShell"
    except Exception:
        return "Bash"


def call_window(session) -> Optional[int]:
    """The window the next call gets: a one-shot's ask (3.6.0.12 OS: the window its request is shaped for,
    agent/ollama_window_truth.start_window; 3.6.0.19 LM: a session's spill cap held from its first call), a measure's
    own window, an `ol:` model's resolved num_ctx (what
    `_build_ollama_body_for_ref` starts from), else the model profile's context."""
    model = getattr(getattr(session, "model_ref", None), "raw", None)
    for attr in ("_shape_window", "_measure_window"):
        w = getattr(session, attr, None)
        if attr == "_shape_window" and getattr(session, "_shape_model", None) != model:
            continue  # the block a one-shot started with is its model's (a switch starts over)
        if isinstance(w, int) and w > 0:
            return w
    ref = getattr(session, "model_ref", None)
    if getattr(getattr(session, "route", None), "dialect", None) == "ollama" and ref is not None:
        try:
            from halo_harness.providers.ollama_hw import resolve_context_decision
            n = resolve_context_decision(ref, getattr(getattr(session, "settings", None), "effective_env", None)).num_ctx
            if isinstance(n, int) and n > 0:
                return n
        except Exception:
            pass
    from halo_harness.agent.prompt_lean import window_of
    return window_of(session)


def workflow_needed(session) -> bool:
    """A square is enabled for this lineup and the model lacks something a square covers (a read it does
    not take, or an ask -- a plan, a review, research -- no model reads)."""
    try:
        from halo_harness.workflows.registry import enabled_squares
        from halo_harness.workflows.router import READS, model_takes
        tool = getattr(getattr(session, "tool_registry", None), "get", lambda _n: None)("Workflow")
        squares = enabled_squares(getattr(tool, "lineup", None))
        if not squares:
            return False
        from halo_harness.workflows.when_store import rules_for
        from halo_harness.workflows.when_tool import has_reach
        if has_reach(rules_for(getattr(tool, "lineup", None))):  # 3.3.16.3: an `always` or a words rule
            return True
        covers = {str(c) for w in squares for c in (getattr(w.contract, "covers", None) or ())}
        if covers - set(READS) - {"media"}:
            return True
        reads = (covers & set(READS)) | (set(READS) if "media" in covers else set())
        ref = getattr(getattr(session, "model_ref", None), "raw", "") or ""
        takes = set(model_takes(ref, getattr(session, "state_dir", None)))
        return any(r not in takes for r in reads)
    except Exception:
        return False


def wire_tokens(defn: dict) -> int:
    """One tool's tokens as it goes on the wire (`{"type": "function", ...}`, chars / 3.5)."""
    from halo_harness.agent.prompt_composition import tokens_of
    from halo_harness.providers.request import anthropic_tool_to_openai
    try:
        return tokens_of(anthropic_tool_to_openai(defn))
    except Exception:
        return tokens_of(defn)


def _bands(session, tools: list, task: str, shell: Optional[str]) -> dict:
    from halo_harness.agent.prompt_lean import _builtin_names, relevance
    from halo_harness.providers.ollama_fit import CORE_TOOL_NAMES
    core = set(CORE_TOOL_NAMES) | ({shell} if shell else set())
    needs = {"Workflow"} if workflow_needed(session) else set()
    builtin = _builtin_names()
    order = {n: i for i, n in enumerate(builtin)}
    rank = {}
    for i, t in enumerate(tools):
        n = _name(t)
        if n in core:
            rank[id(t)] = (0, 0.0, i)
        elif n in needs:
            rank[id(t)] = (1, 0.0, i)
        elif n in AFTER_NEEDS:
            rank[id(t)] = (1, 1.0, i)
        elif n == "Workflow":
            rank[id(t)] = (4, 0.0, i)  # no square this model needs: last
        elif n in order:
            rank[id(t)] = (2, 0.0, order[n])
        elif n in LAST_BUILTINS:
            rank[id(t)] = (2, 0.0, len(order) + LAST_BUILTINS.index(n))
        else:
            rank[id(t)] = (3, -relevance(t, task), i)
    return rank


def _rides(t, budget: Optional[int], used: int) -> bool:
    """3.6.0.19 LM: a set-up Copilot's `copilot_ask` rides ON TOP of the 4,500 budget (a window over 16,384 and under
    65,536): the budget there is 4,500 plus its own size, so every other tool is in or out as in a home without it."""
    return _name(t) in ON_TOP and budget == ON_TOP_OF and used <= budget


def diet(session, tools: list, task: str = "", cap: Optional[int] = None, *,
         platform: Optional[str] = None) -> "tuple[list, list]":
    """(the tools sent, lean and in the catalog's order; the names left out) -- see the module docstring."""
    from halo_harness.tools.lean_descriptions import lean_definition
    tools = aliases_once([t for t in tools or [] if isinstance(t, dict)])
    shell = lean_shell(platform or getattr(session, "_measure_platform", None))
    names = {_name(t) for t in tools}
    dropped: list = []
    if shell and all(s in names for s in SHELLS):
        other = next(s for s in SHELLS if s != shell)
        dropped.append(other)
        tools = [t for t in tools if _name(t) != other]
    window = call_window(session)
    small = [n for n, at in BY_NAME_UNDER.items() if n in names and isinstance(window, int) and 0 < window <= at]
    rank = _bands(session, tools, task, shell)
    budget = tools_budget(window)
    keep, used, riders = set(), 0, 0
    for t in sorted(tools, key=lambda t: rank[id(t)]):
        cost = wire_tokens(lean_definition(t))
        first = rank[id(t)][0] == 0
        rides = _rides(t, budget, used)
        if (cap is not None and len(keep) - riders >= cap) or (budget is not None and not first and not rides
                                                                and used + cost > budget) or _name(t) in small:
            continue
        keep.add(id(t))
        if rides:  # 3.6.0.19 LM: on top of the budget and the cap; every other tool as in a home without it
            riders += 1
            continue
        used += cost
    out = [lean_definition(t) for t in tools if id(t) in keep]
    dropped += [_name(t) for t in tools if id(t) not in keep]
    return out, dropped


def by_name_line(dropped: list) -> str:
    names = [n for n in dropped if n]
    more = f" and {len(names) - 40} more" if len(names) > 40 else ""
    return ("Other tools you can call by name (their schemas are left out to fit your window; ToolSearch "
            "\"select:<name>\" shows one): " + ", ".join(names[:40]) + more + ".")
