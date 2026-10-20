"""halo_harness.teams_tier_fields -- Halo 3.1.6.0 round R1: a tier's own
`model` and `trigger` (teams_tiers.py holds the stack and the spawn rule).

    tiers:
      - {name: top, members: [main]}
      - name: media
        members: [media, editor]
        model: or:google/gemini-3-flash        # or `default`: the session's model
        trigger: {on: file_change, paths: [assets/], prompt: "Cut the new clips"}

`model` is what the tier's members run on unless a card names its own model
or its bio pins a real one (`teams_yaml.member_model` holds the order).
`trigger` is ONE entry in the shapes a bio's `schedule` / `triggers` use
(`on: schedule` with `cron` or `every`; `on: file_change` with `paths`;
`on: event` with `name`; `on: message` with `from`), plus the `prompt` the
fired job starts with and an optional `model`. It starts the tier's lead
(its first member) as a background job under the team, and that lead may
spawn its own tier's other members and the next tier down
(agents_schedule.arm_session, teams_runtime.TeamControl.tier_gate).
"""

from __future__ import annotations

from typing import Optional

TRIGGER_KINDS = ("schedule", "file_change", "event", "message")
# The job a tier trigger fires carries this (the tier's name): its root
# session is that tier's lead, not the main agent (TeamControl.fired_tier).
FIRED_ENV = "HALO_TIER_FIRED"


def model_of(tier) -> "Optional[str]":
    """The tier's `model`, trimmed; None when it names none (or a bad value)."""
    model = tier.get("model") if isinstance(tier, dict) else None
    return model.strip() if isinstance(model, str) and model.strip() else None


def trigger_of(tier) -> "Optional[dict]":
    """A copy of the tier's `trigger` when its kind is one of TRIGGER_KINDS, else None."""
    trigger = tier.get("trigger") if isinstance(tier, dict) else None
    if not isinstance(trigger, dict) or trigger.get("on") not in TRIGGER_KINDS:
        return None
    return dict(trigger)


def _model_problems(where: str, model) -> "list[str]":
    if model is None:
        return []
    if not isinstance(model, str) or not model.strip():
        return [f'{where}: "model" must be a model ref (e.g. or:vendor/model) or default']
    return []


def _trigger_problems(where: str, trigger) -> "list[str]":
    """The bio validators' own lines (agents_yaml), worded for `trigger.<key>`."""
    if trigger is None:
        return []
    if not isinstance(trigger, dict) or trigger.get("on") not in TRIGGER_KINDS:
        return [f'{where}: "trigger.on" must be one of {", ".join(TRIGGER_KINDS)}']
    from halo_harness.agents_yaml import validate_schedule_section, validate_trigger_section
    if trigger["on"] == "schedule":
        body = {k: v for k, v in trigger.items() if k != "on"}
        return [f"{where}: " + line.replace('"schedule', '"trigger', 1) for line in validate_schedule_section(body)]
    lines = [line.replace('triggers[0]: "', '"trigger.', 1) for line in validate_trigger_section([trigger])]
    out = [f"{where}: {line}" for line in lines if not line.startswith('"trigger.prompt"')]
    prompt = trigger.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        out.append(f'{where}: "trigger.prompt" is required (what the tier\'s lead starts on)')
    if trigger.get("model") is not None and not isinstance(trigger.get("model"), str):
        out.append(f'{where}: "trigger.model" must be a string')
    return out


def tier_field_problems(where: str, tier: dict) -> "list[str]":
    """One plain line per problem in this tier's `model` and `trigger`."""
    return _model_problems(where, tier.get("model")) + _trigger_problems(where, tier.get("trigger"))


def trigger_text(trigger) -> str:
    """`every 30m`, `cron 0 9 * * 1`, `on file src/`, `on event turn_done`, `on message from worker`."""
    if not isinstance(trigger, dict):
        return ""
    kind = trigger.get("on")
    if kind == "schedule":
        return f"every {trigger['every']}" if trigger.get("every") is not None else f"cron {trigger.get('cron') or '?'}"
    if kind == "file_change":
        paths = trigger.get("paths") if isinstance(trigger.get("paths"), list) else []
        return "on file " + (", ".join(str(p) for p in paths) or "?")
    if kind == "event":
        return f"on event {trigger.get('name') or '?'}"
    if kind == "message":
        return f"on message from {trigger.get('from') or '?'}"
    return ""


def tier_line(tier: dict) -> str:
    """One `halo teams show` line: index, name, members, then each key it sets."""
    parts = [f"tier {tier['index']} {tier['name']}: {', '.join(tier['members']) or '(empty)'}"]
    if tier.get("implicit"):
        parts.append("implicit")
    if tier.get("max_parallel"):
        parts.append(f"max_parallel {tier['max_parallel']}")
    if tier.get("model"):
        parts.append(f"model {tier['model']}")
    if tier.get("trigger"):
        prompt = str(tier["trigger"].get("prompt") or "").strip().replace("\n", " ")
        parts.append(f"trigger {trigger_text(tier['trigger'])}" + (f" -> {prompt[:60]!r}" if prompt else ""))
    return "; ".join(parts)


def tier_lines(template) -> "list[str]":
    """`halo teams show`'s tiers block ([] for a lineup that declares none)."""
    from halo_harness.teams_tiers import declared, effective_tiers
    if not declared(template):
        return []
    return ["  tiers (a member spawns only into the next tier down):"] + [
        f"    {tier_line(t)}" for t in effective_tiers(template)]
