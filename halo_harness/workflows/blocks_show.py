"""halo_harness.workflows.blocks_show -- a lineup's blocks in lines (Halo 3.3.16.3): its squares, each with its "when"
(workflows/when.py), then its declared tiers with their purpose and the words that reach them (`routing`, a card's
`use_for`). `halo blocks list | show`, `halo teams show` (packs/lineup_run.workflow_lines) print them.

    lineup_blocks(lineup=None, repo) -> {lineup, blocks: [{name, kind, when, detail: [line]}], lines: [line]}
    block_lines(template) -> [line]     `halo teams show`'s "  block ..." lines for a resolved lineup
"""

from __future__ import annotations

from pathlib import Path


def _tier_words(raw: dict, members: list) -> "list[str]":
    routing = raw.get("routing") if isinstance(raw.get("routing"), dict) else {}
    words = [str(w) for w, alias in routing.items() if alias in members]
    for e in raw.get("agents") or []:
        if isinstance(e, dict) and (e.get("as") or e.get("role")) in members:
            words += [str(w) for w in e.get("use_for") or [] if str(w) not in words]
    return list(dict.fromkeys(words))


def _who(c) -> str:
    if c.lineup_name():
        return f"lineup {c.lineup_name()}"
    members = (c.lineup or {}).get("members") if isinstance(c.lineup, dict) else None
    names = [c.lead()[0]] + [str(m.get("bio") if isinstance(m, dict) else m) for m in members or []]
    return ", ".join(n for n in names if n)


def _squares(lineup, repo) -> list:
    from halo_harness.workflows import registry
    from halo_harness.workflows import when as W
    from halo_harness.workflows.when_store import rules_for
    try:
        rules = rules_for(lineup, cwd=repo)
        squares = registry.enabled_squares(lineup, cwd=repo)
    except Exception:
        return []
    out = []
    for wf in squares:
        rule, c = rules.get(wf.ref), wf.contract
        label = W.label(rule, c.covers)
        who = _who(c)
        out.append({"name": wf.ref, "kind": "square", "when": label,
                    "line": f"block {wf.ref} (square): {W.when_line(rule, c.covers)}" + (f"; inside: {who}" if who else ""),
                    "detail": [f"{wf.ref} (square block): {c.does or '-'}", f"  when      {label}",
                               f"            {W.sentence(rule, wf.ref, c.covers)}", f"  inside    {who or 'the session lineup'}",
                               f"  costs     {c.costs()}", f"  limits    {c.limits_chip()}", f"  file      {wf.path}"]})
    return out


def _tiers(raw: dict) -> list:
    from halo_harness.teams_tiers import effective_tiers
    out = []
    for t in effective_tiers(raw) if isinstance(raw, dict) else []:
        if t.get("implicit"):
            continue
        words = _tier_words(raw, list(t.get("members") or []))
        when = ("the task says " + ", ".join(words[:8])) if words else "main delegates to it"
        purpose = t.get("purpose") or "no purpose line"
        out.append({"name": t["name"], "kind": "tier", "when": when,
                    "line": f"block {t['name']} (tier {t['index']}): {purpose}; when {when}",
                    "detail": [f"{t['name']} (tier {t['index']} block): {purpose}", f"  when      {when}",
                               f"  inside    {', '.join(t.get('members') or []) or '-'}"]})
    return out


def lineup_blocks(lineup, repo: Path) -> dict:
    from halo_harness.teams_yaml import resolve_team_template
    from halo_harness.workflows import registry
    lineup = lineup if lineup is not None else registry.active_lineup() or "auto"
    raw = resolve_team_template(str(lineup), cwd=repo) or {}
    blocks = _squares(lineup, repo) + _tiers(raw)
    return {"lineup": lineup, "blocks": blocks, "lines": [b["line"] for b in blocks] or ["no blocks"]}


def block_lines(template) -> "list[str]":
    name = template.get("name") if isinstance(template, dict) else None
    if not isinstance(name, str) or not name or template.get("_pack"):
        return []
    return [f"  {b['line']}" for b in _squares(name, Path.cwd())]
