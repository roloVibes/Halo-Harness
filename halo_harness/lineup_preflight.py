"""halo_harness.lineup_preflight -- Halo 3.0.7.0 round R1: the run-start
preflight (the OpenFlow port in plans/ROADMAP.md, "Into 3.0.7.0").

Before `halo orchestra run`, `halo flow run` (and their Studio routes) and a
mission run start, the lineup they run under is checked for what would make
members come back empty: a model id its provider's catalog does not know
(the silent-404 case `halo doctor --roles` finds after the fact), an
assignment naming a bio that does not exist, a bio whose `tools.allow` is
an empty list (it may call no tool), and a `tiers` problem. Each finding
is `{id, severity: "blocks"|"warns", text, fix}`; the entry points list
every `blocks` finding with its fix and stop, unless `--force` /
`{"force": true}` says run anyway.

The module is named `lineup_preflight` because `halo_harness/preflight.py`
is the 2.0.7 lane-canary preflight (`halo preflight`); that module
re-exports `lineup_problems` so both spellings work.
"""

from __future__ import annotations

from typing import Optional


def _finding(fid: str, severity: str, text: str, fix: str) -> dict:
    return {"id": fid, "severity": severity, "text": text, "fix": fix}


def _resolve(name: "Optional[str]", *, cwd, state_dir) -> "tuple[Optional[str], Optional[dict]]":
    from halo_harness.teams_yaml import resolve_team_template
    if not name:
        from halo_harness.teams_runtime import active_team_name
        name = active_team_name()
    if not name:
        return None, None
    try:
        return name, resolve_team_template(name, cwd=cwd, state_dir=state_dir)
    except Exception:
        return name, None


def _models(entry: dict, bio: dict) -> "tuple[Optional[str], Optional[str]]":
    over = entry.get("models") if isinstance(entry.get("models"), dict) else {}
    own = bio.get("models") if isinstance(bio.get("models"), dict) else {}
    return over.get("preference") or own.get("preference"), over.get("fallback") or own.get("fallback")


def lineup_problems(team_or_lineup_name: "Optional[str]" = None, *, cwd=None, state_dir=None) -> "list[dict]":
    """Every preflight finding for the named lineup (the active team when
    the name is empty; [] when there is none). Never raises."""
    try:
        return _lineup_problems(team_or_lineup_name, cwd=cwd, state_dir=state_dir)
    except Exception as e:  # a preflight never takes a run start down
        return [_finding("preflight-error", "warns", f"the preflight could not finish: {type(e).__name__}: {e}",
                         "run `halo teams validate` on the lineup")]


def _lineup_problems(name, *, cwd, state_dir) -> "list[dict]":
    from halo_harness.agents_doctor import missing_model_provider
    from halo_harness.agents_yaml import resolve_agent_bio
    from halo_harness.teams_tiers import tier_warnings, validate_tiers
    lineup, template = _resolve(name, cwd=cwd, state_dir=state_dir)
    if lineup is None:
        return []
    if template is None:
        return [_finding("lineup-missing", "blocks", f"lineup `{lineup}` does not resolve (no such file, or its "
                         f"`extends` chain is broken)", "`halo teams` lists the lineups; name one that exists")]
    out: "list[dict]" = []
    catalogs: dict = {}
    bios: "dict[str, Optional[dict]]" = {}
    for entry in template.get("agents") or []:
        if not isinstance(entry, dict) or not entry.get("agent"):
            continue
        alias, bio_name = entry.get("as") or entry.get("role") or "?", str(entry["agent"])
        if bio_name not in bios:
            bios[bio_name] = resolve_agent_bio(bio_name, cwd=cwd, state_dir=state_dir)
        bio = bios[bio_name]
        if bio is None:
            out.append(_finding(f"missing-bio:{alias}", "blocks",
                                f"`{alias}` names bio `{bio_name}`, which does not exist",
                                f"create it (`halo agents new {bio_name}`) or point `{alias}` at an existing bio"))
            continue
        pref, fallback = _models(entry, bio)
        for ref, kind, severity in ((pref, "model", "blocks"), (fallback, "fallback", "warns")):
            provider = missing_model_provider(ref, catalogs=catalogs, state_dir=state_dir)
            if provider is not None:
                out.append(_finding(
                    f"dead-{kind}:{alias}", severity,
                    f"`{alias}` (bio `{bio_name}`) names {kind} `{ref}`, which is not in the {provider} catalog: "
                    f"requests for it 404 and the member comes back empty",
                    f"pick a live id for bio `{bio_name}` (`halo agents edit {bio_name}`, or the lineup's models "
                    f"override), or `halo models --refresh` if the catalog is stale"))
    for bio_name, bio in bios.items():
        tools = (bio or {}).get("tools")
        if isinstance(tools, dict) and isinstance(tools.get("allow"), list) and not tools["allow"]:
            users = [str(e.get("as") or e.get("role")) for e in template.get("agents") or []
                     if isinstance(e, dict) and e.get("agent") == bio_name]
            out.append(_finding(f"empty-tools:{bio_name}", "blocks",
                                f"bio `{bio_name}` (used by {', '.join(f'`{u}`' for u in users)}) has "
                                f"`tools.allow: []`: it may call no tool",
                                f"list the tools it calls under `tools.allow`, or remove the key to use the "
                                f"defaults (`halo agents edit {bio_name}`)"))
    org = template.get("org") if isinstance(template.get("org"), dict) else {}
    for p in org.get("positions") or []:
        if isinstance(p, dict) and p.get("agent") and resolve_agent_bio(str(p["agent"]), cwd=cwd,
                                                                        state_dir=state_dir) is None:
            title = p.get("title") or "?"
            out.append(_finding(f"missing-bio:org:{title}", "blocks",
                                f"org position `{title}` names bio `{p['agent']}`, which does not exist",
                                f"create it (`halo agents new {p['agent']}`) or point the position at an existing bio"))
    for i, line in enumerate(validate_tiers(template.get("tiers"), template.get("agents") or [])):
        out.append(_finding(f"tiers:{i}", "blocks", line, "fix the `tiers` section (docs/ROLES.md, \"Tiers\")"))
    for line in tier_warnings(template):
        out.append(_finding("tiers:unplaced", "warns", line[len("warning: "):],
                            "add each alias to a tier, or leave it in the implicit last tier"))
    return out


def flow_problems(spec: dict, *, cwd=None, state_dir=None) -> "list[dict]":
    """The preflight for a flow: every lineup its `roles` steps use."""
    seen: "list[str]" = []
    for step in (spec or {}).get("steps") or []:
        if not isinstance(step, dict):
            continue
        uses = str(step.get("uses") or "")
        if step.get("kind") == "roles" and uses.startswith("lineup:") and uses[7:] not in seen:
            seen.append(uses[7:])
    out: "list[dict]" = []
    for name in seen:
        for f in lineup_problems(name, cwd=cwd, state_dir=state_dir):
            out.append({**f, "id": f"{name}/{f['id']}", "text": f"lineup `{name}`: {f['text']}"})
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
