"""halo_harness.models_auto_spawn -- the `auto` pick at a sub-agent's spawn
(Halo 3.1.9.0 R2, "the Auto lineup").

`agent/subagent.py` builds a child's model through ONE order
(`config/agents_md.resolve_agent_model`: the call's own `model`, a `--role`
override, the agent file's `model:`, the role table -- where a lineup's tier
model sits above an `auto` bio -- then the env / settings fallbacks and the
parent's model). When that order reaches `auto`, it calls the `resolver`
built here: the member's needs (its lineup card's `models.needs`, else its
bio's), the words naming it (its alias and its bio's kind), the lineup's
`budget.band`, the task text and the spawning session's model go to
`models_auto.pick`, and the Pick lands in `holder["pick"]`. A pick whose ref
does not parse here (a provider turned off) falls back to the spawning
session's model, with the reason saying so.

`record(child, pick)` puts the choice where it is seen: `child.model_reason`
(the agent row's `model_reason`, so Studio's card pill, the Inspector's Live
tab and the Session Live column's spawn line show it) and the child's first
transcript note, `auto: <model> -- <reason>`.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.models_auto import BANDS, DEFAULT_BAND, Pick, pick


def member_needs(team_control, role_name: Optional[str]) -> "tuple[list, str]":
    """`(needs, words)` for the lineup member `role_name` (a role or alias):
    the card's `models.needs` override, else its bio's; the words are the
    alias, the card's role and the bio's kind ("planner planner planner")."""
    entry = team_control.assignment_for(role_name) if team_control is not None and role_name else None
    bio = (team_control.bio_for(role_name) or {}) if entry else {}
    over = entry.get("models") if isinstance((entry or {}).get("models"), dict) else {}
    models = bio.get("models") if isinstance(bio.get("models"), dict) else {}
    needs = over.get("needs") if isinstance(over.get("needs"), list) else models.get("needs")
    words = " ".join(str(w) for w in (role_name, (entry or {}).get("role"), bio.get("kind")) if w)
    return [str(n) for n in needs] if isinstance(needs, list) else [], words


def band_of(team_control) -> str:
    band = (getattr(team_control, "budget", None) or {}).get("band") if team_control is not None else None
    return band if band in BANDS else DEFAULT_BAND


def resolver(*, runtime, role_name: Optional[str], task_text: str, holder: dict, routes=None):
    """The `auto_pick` callable for one spawn: returns the picked ref, or
    None when main's model runs it (the Pick says why either way)."""
    def _pick() -> Optional[str]:
        parent = getattr(runtime, "parent", None)
        main_ref = str(getattr(getattr(parent, "model_ref", None), "raw", "") or "")
        team_control = getattr(runtime, "team_control", None)
        try:
            needs, words = member_needs(team_control, role_name)
            chosen = pick(getattr(parent, "state_dir", None), needs=needs, task_text=task_text or "",
                          band=band_of(team_control), main_ref=main_ref, role=words)
        except Exception as e:
            chosen = Pick(main_ref, f"the pick failed ({type(e).__name__}); using main's", [], [], True)
        if not chosen.fallback and chosen.ref != main_ref:
            try:
                from halo_harness.model import parse_model_ref
                parse_model_ref(chosen.ref, routes)
            except Exception:
                chosen.fall_back(main_ref, f"{chosen.ref} does not resolve here")
        holder["pick"] = chosen
        return None if chosen.fallback else chosen.ref
    return _pick


def pool_words(template: dict, entry: dict, *, cwd=None, state_dir=None) -> str:
    """`halo teams show`: " -- model picked at spawn (needs: reasoning; band
    mid)" for a card whose model is `auto`, else ""."""
    from halo_harness.agents_yaml import resolve_agent_bio
    from halo_harness.teams_yaml import member_model
    from halo_harness.models_auto import is_auto
    if not is_auto(member_model(template, entry, cwd=cwd, state_dir=state_dir)[0]):
        return ""
    bio = resolve_agent_bio(str(entry.get("agent") or ""), cwd=cwd, state_dir=state_dir) or {}
    over = entry.get("models") if isinstance(entry.get("models"), dict) else {}
    needs = over.get("needs") if isinstance(over.get("needs"), list) else (bio.get("models") or {}).get("needs")
    band = ((template.get("budget") or {}) if isinstance(template.get("budget"), dict) else {}).get("band")
    what = ", ".join(str(n) for n in needs) if needs else (
        "the task's modality, vision when it names none" if bio.get("kind") == "media" or entry.get("as") == "media"
        else "none of its own, so cheap and fast")
    return f" -- model picked at spawn (needs: {what}; band {band if band in BANDS else DEFAULT_BAND})"


def record(child, chosen: Optional[Pick], ran_on: Optional[str] = None) -> Optional[str]:
    """The child carries the pick's reason; its transcript opens with the
    pick's line. `ran_on`: the model the child was built on -- when it is not
    the pick (the ref failed to resolve after all), the reason says so.
    Returns the reason (None when no pick was made)."""
    if chosen is None:
        return None
    if ran_on and not chosen.fallback and chosen.ref != ran_on:
        chosen.fall_back(ran_on, f"{chosen.ref} did not resolve")
    child.model_reason = chosen.reason
    try:
        child.log.append_meta(fleet_note=chosen.line())
    except Exception:
        pass
    return chosen.reason
