"""halo_harness.crew.agents_doctor -- `halo doctor --agents` on agent files and the map in use (Halo 3.6.0.0 R5b; it
checked bios and the active lineup before).

    shape_problems(cwd) -> [line]       every agent file of yours, the project's and a pack's with its problems
    map_problems(cwd) -> [line]         the map in use: its own problems, and each agent model id its provider's
                                        catalog does not know (it would 404 silently)
    run_checks(cwd, call_fn) -> [(name, ok, message)]   each agent's `more.check` (ask / expect) on one real call:
                                        its own model, or the default model for `auto`; "no check" when it has none
"""

from __future__ import annotations

from typing import Callable, Optional


def shape_problems(*, cwd=None, state_dir=None) -> "list[str]":
    from halo_harness.crew import store
    out: "list[str]" = []
    for r in store.rows("agent", cwd=cwd, state_dir=state_dir):
        if r["_scope"] != "starter":
            out += [f"{r['name']} ({r['_scope']}): {p}" for p in r["_problems"]]
    return out


def map_problems(*, cwd=None, state_dir=None) -> "list[str]":
    from halo_harness.crew.checks import missing_model_provider
    from halo_harness.crew.compile import compile_map
    from halo_harness.crew.in_use import map_name
    name = map_name(cwd)
    if not name:
        return []
    c = compile_map(name, cwd=cwd, state_dir=state_dir)
    out = list(c.problems)
    catalogs: dict = {}
    for agent, spec in c.specs.items():
        provider = missing_model_provider(spec.model, catalogs=catalogs, state_dir=state_dir) if spec.model else None
        if provider is not None:
            out.append(f"agent {agent}'s model {spec.model!r} is not in the {provider} catalog: its hand-offs would come "
                       "back empty (pick a live model in Studio, Agents -> 1 · Agents)")
    return out


def run_checks(*, cwd=None, state_dir=None, call_fn: "Optional[Callable[[str, str], str]]" = None,
               default_model: Optional[str] = None) -> "list[tuple[str, bool, str]]":
    from halo_harness.crew.checks import call_once, check_expectation
    from halo_harness.crew.in_use import agent, agent_names, main_model
    out: "list[tuple[str, bool, str]]" = []
    for name in agent_names(cwd=cwd, state_dir=state_dir):
        got = agent(name, cwd=cwd, state_dir=state_dir) or {}
        check = got.get("acceptance") or {}
        if not check.get("prompt"):
            out.append((name, True, "no acceptance block"))
            continue
        ref = (got.get("models") or {}).get("preference")
        ref = ref if ref and ref not in ("auto", "measured", "default") else (default_model or main_model())
        if not ref:
            out.append((name, False, "no model of its own and no default model -- nothing to call"))
            continue
        try:
            text = (call_fn or call_once)(ref, check["prompt"])
        except Exception as e:
            out.append((name, False, f"call failed: {type(e).__name__}: {e}"))
            continue
        ok = check_expectation(text, check.get("expect"))
        snippet = (text or "")[:120].replace("\n", " ")
        out.append((name, ok, f"ok ({ref}): {snippet!r}" if ok else f"FAILED ({ref}): got {snippet!r}"))
    return out
