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
tools") and `offer` names the fix: a map (`local-coder`, or
`<model>-coder` for a cloud model) with a coder agent on this model, main on
the best orchestrator among the configured models (local first, then cloud:
the Auto pool's pick), the starter reviewer / researcher / writer on `auto`
(3.6.0.0 R5b: a map and two agents, where it was a lineup). `accept` writes
them and puts the map in use (`halo maps use`); the caller then moves the
session to the orchestrator. Going ahead anyway always works: nothing is written then.
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
    return (f"Keep it as the coder under {offer['orchestrator']} (map '{offer['lineup']}'), "
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
              "command": f"halo maps use {name} && halo config set model {orch}"} if orch else None)
    return {"line": warning_line(card), "card": card, "offer": offer, "offer_line": offer_line(offer)}


def lane_files(offer: dict) -> "tuple[dict, dict]":
    """3.6.0.0 R5b: the offer as files -- ({agent name: agent/1 body}, the map/1 body): main on the orchestrator, a
    coder agent on the picked model, and lines from main to it and to the starter reviewer, researcher and writer
    (their models picked per task)."""
    coder, orch, name = offer["coder"], offer["orchestrator"], offer["lineup"]
    agents = {
        f"{name}-main": {"format": "agent/1", "name": f"{name}-main", "does": f"Main on {orch}: plans, acts and hands code work to {name}-coder.",
                         "instructions": (f"You run on {orch}, which plans, acts and delegates. Hand code work to {name}-coder "
                                          f"({coder}); review, research and writing go to the reviewer, researcher and writer."),
                         "model": orch, "uses": ["read", "edit", "bash", "web"], "careful": "ask-changes"},
        f"{name}-coder": {"format": "agent/1", "name": f"{name}-coder",
                          "does": f"Makes the change the task describes on {coder}, runs the tests that cover it and says what changed.",
                          "model": coder, "uses": ["read", "edit", "bash"], "careful": "ask-changes"},
    }
    boxes = [{"id": "coder", "agent": f"{name}-coder"}, {"id": "reviewer", "agent": "reviewer"},
             {"id": "researcher", "agent": "researcher"}, {"id": "writer", "agent": "writer"}]
    body = {"format": "map/1", "name": name, "boxes": boxes,
            "lines": [{"from": "main", "to": b["id"], "when": "main-decides"} for b in boxes],
            "main": {"agent": f"{name}-main"}}
    return agents, body


def write_lane(offer: dict, *, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    """The map and its two agents in your crew folder (not put in use): `halo maps use <name>` does that."""
    from halo_harness.crew import store
    from halo_harness.crew.formats import PROBLEMS
    agents, body = lane_files(offer)
    problems = [p for n, a in agents.items() for p in PROBLEMS["agent"](a, name=n)] + PROBLEMS["map"](body, name=offer["lineup"])
    if problems:
        return False, problems
    try:
        for n, a in agents.items():
            store.write_text(store.path_for("agent", n, state_dir=state_dir), store.dump(a))
        store.write_text(store.path_for("map", offer["lineup"], state_dir=state_dir), store.dump(body))
    except OSError as e:
        return False, [f"could not write: {e}"]
    return True, []


def accept(offer: dict, *, session=None, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    """Write the map and put it in use (config `crew.map`, as `halo maps use`); `(ok, lines)`."""
    ok, problems = write_lane(offer, cwd=cwd, state_dir=state_dir)
    if not ok:
        return False, list(problems)
    from halo_harness.crew.changes_map import config_text, write_config
    try:
        write_config(config_text(offer["lineup"]))
    except OSError as e:
        return False, [f"could not put the map in use: {e}"]
    runtime = getattr(session, "agent_runtime", None)  # this session's coder follows at once (new sessions: the map)
    if runtime is not None and isinstance(getattr(runtime, "role_table", None), dict):
        runtime.role_table["coder"] = offer["coder"]
    return True, [f"map {offer['lineup']} is in use for new sessions: {offer['coder']} is the coder, "
                  f"{offer['orchestrator']} runs main"]


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
        return out + [f"the map could not be written: {'; '.join(problems)}"]
    return out + [f"To keep it as the coder under {offer['orchestrator']}: {offer['command']} "
                  f"(map '{offer['lineup']}' is written, not in use)"]
