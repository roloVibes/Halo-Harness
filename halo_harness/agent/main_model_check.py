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
tools") and `offer` names the fix: keep this model as the coder of a plain
session (config `roles.coder`: the starter's coder card runs on it, and the
words implement / fix / refactor / code still route there), main on the best
orchestrator among the configured models (local first, then cloud: the Auto
pool's pick), the other cards on `auto` -- what 3.5's `local-coder` lane
lineup did (3.6.0.0 R5c: a plain session's role, where R5b wrote a map).
`accept` writes `roles.coder` (and turns roles on); a map you put in use is
taken out of use, as applying the lane lineup replaced the lineup in force,
and the line says how to bring it back. The caller then moves the session to
the orchestrator. Going ahead anyway always works: nothing is written then.
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
    """The offer's short name (`local-coder`, `<model>-coder` for a cloud model): what the UI and the lines call it."""
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
    return f"Keep it as the coder lane under {offer['orchestrator']} (roles.coder), or go ahead anyway."


def check(ref, *, state_dir, card: Optional[dict] = None, catalog=None, host=None, probe=None, rows=None,
          prefer=()) -> Optional[dict]:
    from halo_harness.providers.model_card import card_of
    if card is None:
        card = card_of(ref, state_dir=state_dir, catalog=catalog, host=host, probe=probe)
    if card.get("fit_for", {}).get("orchestrator", True):
        return None
    orch, why = pick_orchestrator(state_dir, exclude=card["ref"], rows=rows, prefer=prefer)
    name = lineup_name(card)
    offer = ({"lineup": name, "role": "coder", "coder": card["ref"], "orchestrator": orch, "why": why,
              "command": f"halo roles point coder {card['ref']} && halo config set model {orch}"} if orch else None)
    return {"line": warning_line(card), "card": card, "offer": offer, "offer_line": offer_line(offer)}


def accept(offer: dict, *, session=None, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    """`roles.coder` = the model and roles on, a map in use taken out of use (`halo maps use <name>` brings it back);
    this session's coder follows at once. `(ok, lines)`; the caller moves main to the orchestrator."""
    from halo_harness.roles import (assign_role, configured_role_table, role_value_parts, roles_mode_enabled,
                                    set_roles_enabled)
    from halo_harness.theme import get_config_value, set_config_value
    try:  # 3.6.0.0 R5c (the judge's S-c): what the answer replaces and switches back on, named in it
        before = {k: role_value_parts(v)[0] for k, v in configured_role_table().items()}
    except Exception:
        before = {}
    ok, problems = assign_role("coder", offer["coder"])
    if not ok:
        return False, list(problems) or [f"roles.coder could not be set to {offer['coder']}"]
    tail = []
    try:
        if not roles_mode_enabled():
            set_roles_enabled(True)
            from halo_harness.crew.in_use import read_roles
            read = read_roles()
            parked = [f"{k} on {v}" for k, v in sorted(before.items()) if k != "coder" and k in read and v]
            tail.append("roles are on again (they were off: one model for everything)"
                        + (f"; your roles run again: {', '.join(parked)}" if parked else ""))
        named = get_config_value("crew.map", default=None)
        if isinstance(named, str) and named.strip():
            set_config_value("crew.map", None)
            tail.append(f"map {named.strip()} is no longer in use (halo maps use {named.strip()} brings it back)")
    except OSError as e:
        return False, [f"could not write the config: {e}"]
    runtime = getattr(session, "agent_runtime", None)  # this session's coder follows at once
    if runtime is not None and isinstance(getattr(runtime, "role_table", None), dict):
        runtime.role_table["coder"] = offer["coder"]
    was = before.get("coder")
    was = f" (was {was})" if was and was != offer["coder"] else ""
    return True, [f"roles.coder = {offer['coder']}{was}: new sessions hand code work to it, "
                  f"{offer['orchestrator']} runs main"] + tail


def config_lines(ref: str, state_dir) -> "list[str]":
    """What `halo config set model` and `halo init --model` print when the model cannot orchestrate: the line, and the
    command that keeps it as the coder (nothing is written)."""
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
    return out + [f"To keep it as the coder under {offer['orchestrator']}: {offer['command']}"]
