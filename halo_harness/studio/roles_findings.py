"""halo_harness.studio.roles_findings -- Studio's Problems panel (Halo
3.0.7.0 round R2): every finding about a lineup as it stands in the editor,
saved or not, grouped by severity.

`findings_for(raw, ...)` merges, in this order:
  - the validator's lines (`teams_yaml.validate_team_template`), all `blocks`
    (the same lines that make Save answer 422);
  - the run-start preflight on the edited mapping
    (`lineup_preflight.template_problems`): a model id its catalog does not
    know, a dead fallback, a bio with `tools.allow: []`, aliases left out of
    every tier (its tier and missing-bio lines are the validator's already);
  - three tiers or more with `delegation.max_depth` too low to reach the
    bottom tier (R1's hand-back, finding 3);
  - each card's own problems and warnings from the graph (no model resolves,
    an alias used twice, a model on a removed cc:/cx: route, not one main).

Each finding is `{id, severity: "blocks"|"warns", text, fix, node}`; `node`
is the graph card it is about (Studio selects it on a click), or "". 3.3.6.0
R2: a gap (a role with no model, or on a local model that fails its gate)
also carries `find: {role, preset}`: Problems' "Find a model" opens Local ->
Library with the role's preset.
"""

from __future__ import annotations

import re

_AGENT_LINE = re.compile(r"^agents\[(\d+)\]")
_PREFLIGHT_KEEP = ("dead-model:", "dead-fallback:", "empty-tools:", "tiers:unplaced")


def resolve_raw(raw: dict, *, cwd=None, state_dir=None) -> dict:
    """The edited mapping with its `extends` parent merged in, the way
    `teams_yaml.resolve_team_template` merges a saved file."""
    from halo_harness import teams_yaml as T
    parent_name = raw.get("extends")
    if not (isinstance(parent_name, str) and parent_name.strip()):
        return dict(raw)
    parent = T.resolve_team_template(parent_name.strip(), cwd=cwd, state_dir=state_dir) or {}
    out = {**parent, **raw}
    for section in T.TOP_SECTIONS:
        out[section] = T._merge_section(parent.get(section), raw.get(section))
    out["agents"] = raw.get("agents") if raw.get("agents") is not None else parent.get("agents")
    return out


def _node_for_alias(graph: dict, alias: str) -> str:
    for n in graph.get("nodes") or []:
        if alias and (n.get("alias") == alias or (not n.get("alias") and n.get("role") == alias)):
            return n["id"]
    return ""


def _node_for_index(graph: dict, i: int) -> str:
    for n in graph.get("nodes") or []:
        if n.get("index") == i:
            return n["id"]
    return ""


def _depth_finding(resolved: dict) -> "list[dict]":
    tiers = resolved.get("tiers") if isinstance(resolved.get("tiers"), list) else []
    if len(tiers) < 3:
        return []
    deleg = resolved.get("delegation") if isinstance(resolved.get("delegation"), dict) else {}
    depth = deleg.get("max_depth")
    need = len(tiers) - 1
    if isinstance(depth, int) and not isinstance(depth, bool) and depth >= need:
        return []
    have = depth if isinstance(depth, int) and not isinstance(depth, bool) else 1
    return [{"id": "tiers:depth", "severity": "warns",
             "text": f"{len(tiers)} tiers need delegation.max_depth {need} to reach the bottom tier; it is {have}, "
                     f"so tier {need} never gets work",
             "fix": f"set delegation.max_depth: {need} (docs/ROLES.md, \"Tiers\")", "node": ""}]


def _pivot_findings(resolved: dict, cwd, state_dir) -> "list[dict]":
    try:
        from halo_harness import teams_yaml as T
        from halo_harness.providers.placement_apply import lineup_pivots
        table, _notes = T.resolve_role_table(resolved, cwd=cwd, state_dir=state_dir)
        return [{"id": f"pivot:{i}", "severity": "warns", "text": p["line"],
                 "fix": "keep one of them resident (keep_alive -1) and run the other's steps together, or move one "
                        "to another host", "node": ""} for i, p in enumerate(lineup_pivots(table, state_dir))]
    except Exception:
        return []


def _gap_findings(resolved: dict, cwd, state_dir) -> "list[dict]":
    try:
        from halo_harness import teams_yaml as T
        from halo_harness.models_library.role_gaps import gaps
        table, _notes = T.resolve_role_table(resolved, cwd=cwd, state_dir=state_dir)
        roles = [e.get("as") or e.get("role") for e in resolved.get("agents") or [] if isinstance(e, dict)]
        return [{"id": f"gap:{g['role']}", "severity": "warns", "text": g["why"], "fix": f"find a model for this role ({g['cli']})",
                 "node": "", "find": {"role": g["role"], "preset": g["preset"]}} for g in gaps(table, state_dir, roles)]
    except Exception:
        return []


def findings_for(raw: dict, *, problems: "list[str]", graph: dict, cwd=None, state_dir=None) -> "list[dict]":
    out: "list[dict]" = []
    for i, line in enumerate(problems or []):
        m = _AGENT_LINE.match(line)
        out.append({"id": f"validate:{i}", "severity": "blocks", "text": line, "fix": "",
                    "node": _node_for_index(graph, int(m.group(1))) if m else ""})
    resolved = raw
    try:
        resolved = resolve_raw(raw, cwd=cwd, state_dir=state_dir)
        from halo_harness.lineup_preflight import template_problems
        for f in template_problems(resolved, cwd=cwd, state_dir=state_dir):
            fid = str(f.get("id") or "")
            if not fid.startswith(_PREFLIGHT_KEEP):
                continue
            alias = fid.split(":", 1)[1] if ":" in fid else ""
            out.append({**f, "node": _node_for_alias(graph, alias) if fid.startswith("dead-") else ""})
    except Exception as e:  # the panel says so instead of failing the whole validate call
        out.append({"id": "preflight-error", "severity": "warns", "text": f"the preflight could not finish: {e}",
                    "fix": "run `halo teams validate` on the lineup", "node": ""})
    out.extend(_depth_finding(resolved))
    out.extend(_pivot_findings(resolved, cwd, state_dir))  # 3.3.6.0 R1: a lineup that is a pivot schedule
    out.extend(_gap_findings(resolved, cwd, state_dir))  # 3.3.6.0 R2: find a model for this role
    seen = {f["text"] for f in out}
    for n in graph.get("nodes") or []:
        for sev, key in (("warns", "problems"), ("warns", "warnings")):
            for text in n.get(key) or []:
                line = f"`{n.get('alias') or n.get('role')}`: {text}"
                once = "have role main" in text  # the graph puts this one on every card: list it once
                if line in seen or (once and text in seen):
                    continue
                seen.update((line, text) if once else (line,))
                out.append({"id": f"card:{n['id']}:{len(out)}", "severity": sev, "text": line, "fix": "", "node": n["id"]})
    return out
