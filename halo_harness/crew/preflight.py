"""halo_harness.crew.preflight -- the run-start preflight on the map a run uses (Halo 3.0.7.0 R1's preflight; 3.6.0.0
R5b: on a map and its agents, where it was a lineup and its bios).

Before `halo orchestra run` (and its Studio route) starts, the map the goal names (its `lineup` field) is checked
for what would make its agents come back empty: a problem in the map (a missing agent, a circle), and an agent model id
its provider's catalog does not know (the silent-404 case `halo doctor --roles` finds after the fact). Each finding is
`{id, severity: "blocks"|"warns", text, fix}`; the entry points list every `blocks` finding with its fix and stop,
unless `--force` / `{"force": true}` says run anyway.

    run_problems(name, cwd, state_dir) -> [finding]
    blocking(findings) -> [finding]      refusal_text(findings, what, force) -> str      refusal_body(findings) -> dict
"""

from __future__ import annotations

from typing import Optional


def _finding(fid: str, severity: str, text: str, fix: str) -> dict:
    return {"id": fid, "severity": severity, "text": text, "fix": fix}


def run_problems(name: Optional[str] = None, *, cwd=None, state_dir=None) -> "list[dict]":
    from halo_harness.crew.checks import missing_model_provider
    from halo_harness.crew.compile import compile_map
    from halo_harness.crew import store
    if not name or store.find("map", name, cwd=cwd, state_dir=state_dir) is None:
        return []  # no map of that name: a goal naming an old lineup is not stopped here (its worker says it, --map)
    try:
        c = compile_map(name, cwd=cwd, state_dir=state_dir)
    except Exception:
        return []
    out = [_finding("map", "blocks", f"map {name}: {p}", f"halo maps show {name}; fix it in Studio (Agents -> 3 · Map)")
           for p in c.problems]
    catalogs: dict = {}
    for agent, spec in c.specs.items():
        provider = missing_model_provider(spec.model, catalogs=catalogs, state_dir=state_dir) if spec.model else None
        if provider is not None:
            out.append(_finding("dead-model", "blocks",
                                f"agent {agent}'s model {spec.model!r} is not in the {provider} catalog (it would 404 silently)",
                                f"pick a live model for {agent} (Studio, Agents -> 1 · Agents), or `halo models --refresh`"))
    return out


def blocking(problems: "list[dict]") -> "list[dict]":
    return [p for p in problems or [] if p.get("severity") == "blocks"]


def refusal_text(problems: "list[dict]", *, what: str = "the run", force: str = "--force") -> str:
    """The stop text: every `blocks` finding with its fix, then how to run anyway."""
    rows = blocking(problems)
    lines = [f"preflight: {len(rows)} problem(s) stop {what} before it starts:"]
    for p in rows:
        lines.append(f"  - {p['text']}")
        lines.append(f"    fix: {p['fix']}")
    lines.append(f"Fix them, or run anyway with {force}.")
    return "\n".join(lines)


def refusal_body(problems: "list[dict]", *, what: str = "the run") -> dict:
    """The 422 body Studio's run routes answer: `{error, problems, preflight}`."""
    return {"error": refusal_text(problems, what=what, force='{"force": true}'), "problems": list(problems),
            "preflight": True}
