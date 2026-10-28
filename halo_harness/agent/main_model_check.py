"""halo_harness.agent.main_model_check -- Halo 3.3.5.0 R0b (d): the main
model picked cannot orchestrate here -- say so in one plain line, and offer
to keep it as the coder lane under a model that can.

    check(ref, *, state_dir, card=None, rows=None, prefer=()) -> None | {line, card, offer, offer_line}
    accept(offer, *, session=None, cwd=None, state_dir=None) -> (ok, lines)
    config_lines(ref, state_dir) -> [lines]   (`halo config set model`, `halo init --model`)

`check` is None when the card's `fit_for.orchestrator` holds. Otherwise
`line` says what the model is and what it cannot do as the main agent
("qwen3-coder:30b is a coding model with no tool calling on this server: it
can write and answer but cannot act; as the main agent it would not run
tools") and `offer` names the fix: a lineup (`local-coder`, or
`<model>-coder` for a cloud model) with the coder role pinned to this model,
main on the best orchestrator among the configured models (local first, then
cloud: the Auto pool's pick), reviewer / researcher / small on the `auto`
pool. `accept` writes it through the `halo teams apply` path
(`teams_cli_views.apply_lineup`); the caller then moves the session to the
orchestrator. Going ahead anyway always works: nothing is written then.
`offer` is None when no configured model can orchestrate either.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger("bridge")

LOCAL_PREFIXES = ("ol:", "hf:local/", "hf:mlx/", "local:")


def _is_local(ref: str) -> bool:
    return str(ref or "").startswith(LOCAL_PREFIXES)


def warning_line(card: dict) -> str:
    from halo_harness.providers.model_card_words import what_words
    name, what = card.get("name") or card.get("ref"), what_words(card)
    w = card.get("window") or {}
    if card.get("embedding_only"):
        return f"{name} is {what}: it turns text into vectors and does not chat; as the main agent it would not answer"
    if card.get("tools") == "none":
        return (f"{name} is {what} with no tool calling on this server: it can write and answer but cannot act; "
                "as the main agent it would not run tools")
    if isinstance(w.get("tokens"), int) and w["tokens"] < 32768:
        return (f"{name} is {what} with a {w['tokens']:,}-token window here ({w.get('source')}): as the main agent "
                "its tools and the conversation would not fit (an orchestrator needs 32,768)")
    why = (card.get("fit_why") or {}).get("orchestrator") or "it is not an orchestrator"
    return f"{name} is {what}: {why.split(': ', 1)[-1]}; as the main agent it would plan and delegate poorly"


def lineup_name(card: dict) -> str:
    if card.get("kind") != "cloud":
        return "local-coder"
    slug = re.sub(r"[^a-z0-9]+", "-", str(card.get("name") or "model").lower()).strip("-")[:40] or "model"
    return f"{slug}-coder"


def _rows(state_dir, rows) -> list:
    if rows is not None:
        return rows
    try:
        from halo_harness.studio.model import catalog_rows
        return catalog_rows(state_dir, cached=True)
    except Exception:
        log.debug("main_model_check: the catalog could not be read", exc_info=True)
        return []


def pick_orchestrator(state_dir, *, exclude: str = "", rows=None, prefer=()) -> "tuple[Optional[str], str]":
    """`(ref, why)`: the best `fit_for.orchestrator` model among the configured ones -- local first (a probed tool
    call, then the larger window, then the larger model), then cloud (`prefer` first, then the Auto pool's pick)."""
    from halo_harness.providers.model_card import card_of
    local, cloud = [], []
    for row in _rows(state_dir, rows):
        ref = str((row or {}).get("ref") or "")
        if not ref or ref == exclude or ref.startswith("("):
            continue
        is_local = _is_local(ref)
        try:
            card = card_of(ref, state_dir=state_dir, catalog=None if ref.startswith("ol:") else row)
        except Exception:
            continue
        if not card["fit_for"]["orchestrator"]:
            continue
        (local if is_local else cloud).append((card, row))
    if local:
        local.sort(key=lambda cr: (cr[0]["tools"] != "probed", -((cr[0]["window"] or {}).get("tokens") or 0),
                                   -(cr[0].get("params") or 0), cr[0]["ref"]))
        best = local[0][0]
        return best["ref"], f"the local model that can orchestrate here (tools {best['tools']}, window " \
                            f"{(best['window'] or {}).get('tokens') or 0:,})"
    refs = [c["ref"] for c, _r in cloud]
    for p in prefer or ():
        if p in refs:
            return p, "the model you were on, which can orchestrate"
    if not refs:
        return None, "no configured model can orchestrate here"
    try:
        from halo_harness.models_auto import load_rows, pick
        entries = {k: v for k, v in load_rows(state_dir).items() if k in refs}
        if entries:
            got = pick(state_dir, needs=["tools"], rows=entries, role="orchestrator")
            if got.ref in refs:
                return got.ref, f"the Auto pool's pick: {got.reason}"
    except Exception:
        log.debug("main_model_check: the Auto pick failed", exc_info=True)
    return sorted(refs)[0], "the first cloud model that can orchestrate (no best-at index yet)"


def offer_line(offer: Optional[dict]) -> str:
    if not offer:
        return "No configured model can orchestrate here; it runs as the main agent as it is."
    return (f"Keep it as the coder lane under {offer['orchestrator']} (lineup '{offer['lineup']}'), "
            "or go ahead anyway.")


def check(ref, *, state_dir, card: Optional[dict] = None, catalog=None, host=None, probe=None, rows=None,
          prefer=()) -> Optional[dict]:
    from halo_harness.providers.model_card import card_of
    if card is None:
        card = card_of(ref, state_dir=state_dir, catalog=catalog, host=host, probe=probe)
    if card.get("fit_for", {}).get("orchestrator", True):
        return None
    orch, why = pick_orchestrator(state_dir, exclude=card["ref"], rows=rows, prefer=prefer)
    name = lineup_name(card)
    offer = ({"lineup": name, "coder": card["ref"], "orchestrator": orch, "why": why,
              "command": f"halo teams apply {name} && halo config set model {orch}"} if orch else None)
    return {"line": warning_line(card), "card": card, "offer": offer, "offer_line": offer_line(offer)}


def lane_template(offer: dict) -> dict:
    coder, orch = offer["coder"], offer["orchestrator"]
    return {
        "description": f"{coder} as the coder lane under {orch} (written when {coder} was picked as the main model)",
        "version": "1.0", "tags": ["lane", "local" if _is_local(coder) else "cloud"],
        "about": (f"Main runs on {orch}, which plans, acts and delegates. Code work goes to the coder, {coder}; "
                  "review, research and small jobs go to the auto pool. You are in the lineup: do your task and hand "
                  "back the result."),
        "agents": [
            {"agent": "default-model", "role": "main", "models": {"preference": orch}},
            {"agent": "auto-coder", "role": "coder", "use_for": ["implement", "fix", "refactor", "code"],
             "models": {"preference": coder}},
            {"agent": "auto-reviewer", "role": "reviewer", "use_for": ["review", "audit"]},
            {"agent": "auto-researcher", "role": "researcher", "use_for": ["research", "investigate"]},
            {"agent": "auto-writer", "role": "small", "use_for": ["summarize", "draft"]},
        ],
        "delegation": {"mode": "by-skill", "max_parallel": 2, "max_depth": 2, "handoff": "summary", "forward_text": False},
        "routing": {"implement": "coder", "fix": "coder", "refactor": "coder", "code": "coder", "review": "reviewer",
                    "audit": "reviewer", "research": "researcher", "investigate": "researcher", "summarize": "small",
                    "draft": "small"},
        "budget": {"band": "mid"},
    }


def write_lane(offer: dict, *, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    """The lineup file only (not made active): `halo teams apply <name>` makes it active."""
    from halo_harness.teams_yaml import ensure_builtin_team_templates, save_team_template
    try:
        ensure_builtin_team_templates(state_dir=state_dir)
    except Exception:
        pass
    return save_team_template(offer["lineup"], lane_template(offer), cwd=cwd, state_dir=state_dir)


def accept(offer: dict, *, session=None, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    """Write the lineup and make it active (the `halo teams apply` path); `(ok, lines)`."""
    ok, problems = write_lane(offer, cwd=cwd, state_dir=state_dir)
    if not ok:
        return False, list(problems)
    from halo_harness.teams_apply_answer import apply_answer
    from halo_harness.teams_cli_views import apply_lineup
    ok, lines, notes = apply_lineup(offer["lineup"], cwd=cwd, state_dir=state_dir, session=session)
    if not ok:
        return False, list(lines)
    head, _details = apply_answer(offer["lineup"], notes)
    return True, [f"{head}: {offer['coder']} is the coder lane, {offer['orchestrator']} runs main"] + list(lines)


def config_lines(ref: str, state_dir) -> "list[str]":
    """What `halo config set model` and `halo init --model` print when the model cannot orchestrate: the line,
    and the lineup written (not active) with the command that makes it active."""
    try:
        got = check(ref, state_dir=state_dir)
    except Exception:
        log.debug("main_model_check: the check failed", exc_info=True)
        return []
    if got is None:
        return []
    out = [got["line"]]
    offer = got["offer"]
    if offer is None:
        return out + [got["offer_line"]]
    ok, problems = write_lane(offer, state_dir=state_dir)
    if not ok:
        return out + [f"the lineup could not be written: {'; '.join(problems)}"]
    return out + [f"To keep it as the coder lane under {offer['orchestrator']}: {offer['command']} "
                  f"(lineup '{offer['lineup']}' is written, not active)"]
