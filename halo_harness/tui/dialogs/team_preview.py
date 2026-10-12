"""halo_harness.tui.dialogs.team_preview -- Halo 2.1.0 round B1: the plain
words and the plain-text preview tree of a lineup, shared by the wizard's
Team step, the Summary step and (round B2) `halo teams preview` / `/teams`.

Pure functions, no Textual import at module level, no markup in any
string -- every caller decides how to colour it. A lineup preview is one
tree, `role -> agent -> model`, with the model's price and context window
when the cached catalog knows them, the lineup's own `about:` text, the
`lineup_editor.lineup_warnings` lines and ONE cost line. The cost line
never reads as free by accident: a model with no known price is named
("price unknown for <model>"), never left blank."""

from __future__ import annotations

import textwrap
from typing import Optional

ONE_MODEL_ID = "@one-model"
ONE_MODEL_LABEL = "One model for everything"
HEADER_TEXT = ("Halo runs one model for everything unless you pick a lineup. A lineup gives each job "
               "(planning, coding, reviewing, research) its own agent and model.")
#: A "typical turn" for the cost line: tokens in / tokens out per role call.
TURN_TOKENS_IN = 20_000
TURN_TOKENS_OUT = 2_000


def default_model_label(default_model: str = "") -> str:
    if default_model and default_model.strip():
        return default_model
    from halo_harness.theme import get_config_value
    current = get_config_value("model", default=None)
    return current if isinstance(current, str) and current.strip() else "the session model"


def one_model_sentence(default_model: str = "") -> str:
    return (f"Halo uses {default_model_label(default_model)} for everything. The main agent still spawns "
            f"sub-agents when a job is big, hands surveys and mechanical steps to cheaper models on its own, "
            f"and still asks you questions when it needs to.")


def catalog_by_ref() -> dict:
    """`{ref: row}` from the already-cached catalog files -- no network,
    `{}` on any failure."""
    try:
        from halo_harness.config.paths import bridge_home
        from halo_harness.providers.model_enumeration import build_model_rows
        return {r.get("ref"): r for r in build_model_rows(bridge_home()) if isinstance(r, dict) and r.get("ref")}
    except Exception:
        return {}


def _ref_of(value) -> str:
    if isinstance(value, dict):
        value = value.get("model")
    return value if isinstance(value, str) else ""


def _price(row, key):
    v = (row or {}).get(key)
    try:
        return float(v) if v is not None and not isinstance(v, bool) and float(v) >= 0 else None
    except (TypeError, ValueError):
        return None


def cost_hint(table: dict, *, models_by_ref: "Optional[dict]" = None) -> str:
    """One line: "Roughly $X per turn at these prices" -- the average, over
    the table's roles, of one typical turn (20k tokens in, 2k out) on that
    role's model -- when EVERY model has a price; otherwise
    "price unknown for <model>[, <model>]" naming each unpriced model."""
    refs = [_ref_of(v) for v in (table or {}).values()]
    refs = [r for r in refs if r]
    if not refs:
        return "price unknown for the session model (no model is pinned by this lineup)"
    rows = catalog_by_ref() if models_by_ref is None else models_by_ref
    costs, unknown = [], []
    for ref in refs:
        row = rows.get(ref)
        pin, pout = _price(row, "price_in_per_m"), _price(row, "price_out_per_m")
        if pin is None or pout is None:
            shown = "the session default model" if ref == "default" else ref
            if shown not in unknown:
                unknown.append(shown)
            continue
        costs.append((TURN_TOKENS_IN * pin + TURN_TOKENS_OUT * pout) / 1_000_000)
    if unknown:
        return "price unknown for " + ", ".join(unknown)
    return f"Roughly ${sum(costs) / len(costs):.2f} per turn at these prices"


def _model_detail(ref: str, rows: dict) -> str:
    from halo_harness.model_display import format_price_per_m, format_token_count
    row = rows.get(ref)
    if not row:
        return ref
    bits = [ref]
    price = format_price_per_m(row.get("price_in_per_m"))
    if price:
        bits.append(f"{price} in")
    ctx = format_token_count(row.get("context_tokens"))
    if ctx:
        bits.append(f"ctx {ctx}")
    return "  ".join(bits)


def _tree_lines(template: dict, table: dict, rows: dict, cwd, state_dir) -> "list[str]":
    from halo_harness.agents_yaml import resolve_agent_bio
    out = []
    for e in template.get("agents") or []:
        if not isinstance(e, dict) or not e.get("role"):
            continue
        key = e.get("as") or e["role"]
        label = e["role"] if key == e["role"] else f"{e['role']} ({key})"
        agent = e.get("agent") or "(no agent)"
        ref = _ref_of(table.get(key))
        if not ref and e.get("agent") and resolve_agent_bio(e["agent"], cwd=cwd, state_dir=state_dir) is None:
            model = "agent not found"
        else:
            model = "the session default model" if ref == "default" else (
                _model_detail(ref, rows) if ref else "the session model")
        out.append(f"{label} -> {agent} -> {model}")
    return out


def _wrap(lines: "list[str]", width: int) -> "list[str]":
    out: "list[str]" = []
    for line in lines:
        out.extend(textwrap.wrap(line, max(width, 20), subsequent_indent="    ", break_on_hyphens=False) or [""])
    return out


def preview_lines(name: str, *, cwd=None, state_dir=None, width: int = 80, default_model: str = "",
                  models_by_ref: "Optional[dict]" = None) -> "list[str]":
    """The preview of lineup `name` as plain text lines (`ONE_MODEL_ID` gives
    the "One model for everything" sentence). Never raises."""
    if name == ONE_MODEL_ID:
        return _wrap([ONE_MODEL_LABEL + ":", one_model_sentence(default_model)], width)
    from halo_harness.teams_yaml import resolve_role_table, resolve_team_template
    template = resolve_team_template(name, cwd=cwd, state_dir=state_dir)
    if template is None:
        return _wrap([f"{name}: no such lineup (or it failed validation)."], width)
    rows = catalog_by_ref() if models_by_ref is None else models_by_ref
    table, notes = resolve_role_table(template, cwd=cwd, state_dir=state_dir)
    lines = [f"{name}" + (f" -- {template['description']}" if template.get("description") else "")]
    if template.get("about"):
        lines.append(str(template["about"]).strip())
    lines.append("")
    lines.extend(_tree_lines(template, table, rows, cwd, state_dir))
    lines.extend(f"note: {n}" for n in notes)
    try:
        from halo_harness.tui.dialogs.lineup_editor import lineup_warnings
        lines.extend(f"warning: {w}" for w in lineup_warnings(template.get("agents") or [], cwd=cwd,
                                                              state_dir=state_dir))
    except Exception:
        pass
    lines.extend(["", cost_hint(table, models_by_ref=rows)])
    return _wrap(lines, width)


def applied_summary_lines(*, cwd=None, state_dir=None, default_model: str = "") -> "list[str]":
    """What the Summary step prints: the lineup in force, by name, one line
    per resolved role -- or "One model for everything: <model>"."""
    from halo_harness.roles import roles_mode_enabled
    from halo_harness.theme import get_config_value
    team = get_config_value("team", default=None)
    if not roles_mode_enabled():
        return [f"{ONE_MODEL_LABEL}: {default_model_label(default_model)}"]
    if not (isinstance(team, str) and team):
        return ["Lineup: none applied yet (roles follow the role table already configured, if any)."]
    from halo_harness.teams_yaml import resolve_role_table, resolve_team_template
    template = resolve_team_template(team, cwd=cwd, state_dir=state_dir)
    if template is None:
        return [f"Lineup: {team} (could not be resolved)"]
    table, _notes = resolve_role_table(template, cwd=cwd, state_dir=state_dir)
    out = [f"Lineup: {team}"]
    for role, value in table.items():
        out.append(f"  {role}: {_ref_of(value) or '?'}")
    return out
