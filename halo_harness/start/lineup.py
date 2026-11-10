"""halo_harness.start.lineup -- step 1 of `halo start`: the lineup the guided first run rehearses
(Halo 3.1.1.0 R1; 3.3.15.0 R7: your lineup, never a copy).

`pick(explicit)` is the lineup the run uses: the one `--lineup <name>` names, else the active one (`team` in
config.json, the one the Team step applied). Nothing is copied or written: the run reads the lineup as it is.
On the Auto lineup (or none) it raises LineupError with auto_gate.AUTO_LINE; a name with no lineup behind it
raises `missing_line(name)`.

`parts(name)` is who plays what, from the lineup's own cards and `teams_yaml.resolve_role_table`:

    {name, lead: card, lanes: [card per lane], coders: [card], cards: [card], short: str}
    card: {card, role, bio, instances, model}   model: the ref the card pins ('' = the session model)

The lead is the `main` card (else the first one). A card that writes code -- a coder-like role or alias
(`LANE_ROLES`), or a card used for implement / fix (`LANE_USES`) -- takes lanes, as many as its instances;
the sample needs SAMPLE_LANES (one per function of basket.py). Fewer lane slots: the sample runs in that many
lanes and `short` says so in one line; none at all: `no_coder_line(name)`, and the start ends before it writes
anything. `card_rows(name)` is one row per card for the step's table.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from halo_harness import teams_yaml as T

SAMPLE_LANES = 5
LANE_ROLES = ("coder", "subagent", "subagent_default", "implementer", "worker", "developer", "builder", "fixer")
LANE_USES = ("implement", "fix", "patch", "feature", "refactor", "code", "build")


class LineupError(ValueError):
    pass


def missing_line(name: str) -> str:
    return f"no lineup named {name}; `halo teams` lists them"


def no_coder_line(name: str) -> str:
    return (f"{name} has no card that writes code (a coder, implementer or subagent role, or a card used for implement "
            "or fix), so it cannot take the sample's lanes: add one in Agents -> Cast (halo studio --mode agents) or name "
            "another lineup with --lineup")


def exists(name: str, *, state_dir=None, cwd=None) -> bool:
    if T.find_team_template_path(name, cwd=cwd, state_dir=state_dir) is not None:
        return True
    try:  # a shipped lineup not yet copied on this home: every lineup surface does this first
        T.ensure_builtin_team_templates(state_dir=state_dir)
    except Exception:
        return False
    return T.find_team_template_path(name, cwd=cwd, state_dir=state_dir) is not None


def pick(explicit: Optional[str] = None, *, state_dir=None, cwd=None) -> str:
    """The lineup the start runs (see the module docstring); LineupError with the one line when there is none."""
    name = (explicit or "").strip()
    if not name:
        from halo_harness.start.auto_gate import AUTO_LINE, lineup_now, on_auto
        if on_auto():
            raise LineupError(AUTO_LINE)
        name = str(lineup_now()[0] or "")
    if not exists(name, state_dir=state_dir, cwd=cwd):
        raise LineupError(missing_line(name))
    return name


def ready(explicit: Optional[str] = None, *, state_dir=None, cwd=None) -> "tuple[str, str]":
    """`('', '')` when the lineup the start rehearses can take the sample; else `(the one line, reason)`, reason
    `auto_lineup` | `no_lineup` | `no_coder`. Every door asks this before it writes anything."""
    from halo_harness.start.auto_gate import AUTO_LINE, REASON
    try:
        name = pick(explicit, state_dir=state_dir, cwd=cwd)
    except LineupError as e:
        return str(e), REASON if str(e) == AUTO_LINE else "no_lineup"
    return ("", "") if parts(name, state_dir=state_dir, cwd=cwd)["lanes"] else (no_coder_line(name), "no_coder")


def _ref(value) -> str:
    from halo_harness.roles import role_value_parts
    ref = role_value_parts(value)[0]
    return "" if not ref or ref in ("default", "auto") else str(ref)


def _cards(name: str, state_dir, cwd) -> "list[dict]":
    template = T.resolve_team_template(name, cwd=cwd, state_dir=state_dir) or {}
    table, _notes = T.resolve_role_table(template, cwd=cwd, state_dir=state_dir)
    out = []
    for e in template.get("agents") or []:
        if isinstance(e, dict) and e.get("role"):
            key = str(e.get("as") or e["role"])
            uses = e.get("use_for") if isinstance(e.get("use_for"), list) else []
            try:
                n = max(1, int(e.get("instances") or 1))
            except (TypeError, ValueError):
                n = 1
            out.append({"card": key, "role": str(e["role"]), "bio": str(e.get("agent") or ""), "instances": n,
                        "model": _ref(table.get(key)), "uses": [str(u) for u in uses]})
    return out


def writes_code(card: dict) -> bool:
    return (card["role"] in LANE_ROLES or card["card"] in LANE_ROLES or "implementer" in card["bio"]
            or "coder" in card["bio"] or any(u in LANE_USES for u in card.get("uses") or []))


def parts(name: str, *, state_dir=None, cwd=None, lanes: int = SAMPLE_LANES) -> dict:
    """Who plays the lead and each of the sample's lanes (see the module docstring)."""
    cards = _cards(name, state_dir, cwd)
    lead = next((c for c in cards if c["role"] == "main"), cards[0] if cards else None)
    coders = [c for c in cards if c is not lead and writes_code(c)]
    slots, left = [], {id(c): c["instances"] for c in coders}
    while len(slots) < lanes and any(left.values()):  # round robin over the coder cards, each up to its instances
        for c in coders:
            if left[id(c)] and len(slots) < lanes:
                slots.append(c)
                left[id(c)] -= 1
    short = ""
    if coders and len(slots) < lanes:
        who = ", ".join(f"{c['card']} x{c['instances']}" for c in coders)
        short = (f"{name} has {len(slots)} lane slot(s) for code ({who}): the sample runs in {len(slots)} lane(s) "
                 f"instead of {lanes}, the functions shared between them")
    return {"name": name, "lead": lead, "lanes": slots, "coders": coders, "cards": cards, "short": short}


def shown(card: Optional[dict], model: str = "") -> str:
    """`<card> (<bio>) on <model>`; `model` stands in for a card that pins none."""
    if not card:
        return f"the session model ({model})" if model else "the session model"
    ref = card.get("model") or model or "the session model"
    return f"{card['card']} ({card['bio'] or 'no bio'}) on {ref}"


def who_lines(p: dict) -> "list[str]":
    """The lineup in two lines: the lead, then the lanes (one entry per card with its lane count)."""
    counts: "dict[str, int]" = {}
    for c in p["lanes"]:
        counts[c["card"]] = counts.get(c["card"], 0) + 1
    by_card = {c["card"]: c for c in p["lanes"]}
    lanes = "; ".join(f"{shown(by_card[k])} x{n}" for k, n in counts.items()) or "none"
    return [f"lineup {p['name']}: the lead is {shown(p['lead'])}",
            f"lineup {p['name']}: {len(p['lanes'])} lane(s): {lanes}"]


def card_rows(name: str, *, state_dir=None, cwd=None) -> "list[dict]":
    """One row per card of `name`: `{tier, card, role, bio, instances}`, in tier order."""
    from halo_harness.teams_tiers import effective_tiers
    template = T.resolve_team_template(name, cwd=cwd, state_dir=state_dir) or {}
    entries = {}
    for e in template.get("agents") or []:
        if isinstance(e, dict) and e.get("role"):
            entries.setdefault(str(e.get("as") or e["role"]), e)
    rows = []
    for tier in effective_tiers(template):
        for key in tier["members"]:
            e = entries.get(key) or {}
            rows.append({"tier": tier["name"], "card": key, "role": str(e.get("role") or ""),
                         "bio": str(e.get("agent") or ""), "instances": int(e.get("instances") or 1)})
    return rows


def card_table(rows: "list[dict]") -> "list[str]":
    """The rows as fixed-width text lines with a header."""
    head = f"{'tier':<10} {'card':<12} {'role':<12} {'bio':<18} n"
    lines = [head, "-" * len(head)]
    for r in rows:
        lines.append(f"{r['tier'][:10]:<10} {r['card'][:12]:<12} {r['role'][:12]:<12} {r['bio'][:18]:<18} {r['instances']}")
    return lines


def lineup_path(name: str, *, state_dir=None, cwd=None) -> Optional[Path]:
    found = T.find_team_template_path(name, cwd=cwd, state_dir=state_dir)
    return found[0] if found else None
