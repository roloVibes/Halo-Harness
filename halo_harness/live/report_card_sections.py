"""halo_harness.live.report_card_sections -- two of the report card's sections (Halo 3.4.1.0 R3 "Time"; live/report_card.py
builds the rest): which model did what, and what this record cannot show, said in plain words rather than left blank
(docs/REPLAY.md "What a past moment can and cannot show" is the list). No model call.

    models_did(agents, figures) -> [{model, cost_usd, cost_share, time_share, agents: [{name, role, task}]}]
    cannot(p, facts, waits, money) -> [line, ...]
"""

from __future__ import annotations

NOT_RECORDED = "model not recorded"


def models_did(agents: list, fig: dict) -> list:
    """Each model and the agents that ran on it, the model that cost the most first (live/replay_facts.figures' order)."""
    by: dict = {}
    for a in agents:
        by.setdefault(str(a.get("model") or NOT_RECORDED), []).append(
            {"name": str(a.get("name") or a.get("agent_id") or "?"), "role": str(a.get("role") or ""), "task": str(a.get("task") or "")})
    shares = {m["model"]: m for m in fig.get("models") or []}
    order = [m for m in shares if m in by] + [m for m in by if m not in shares]
    return [{"model": m, "cost_usd": shares.get(m, {}).get("cost_usd"), "cost_share": shares.get(m, {}).get("cost_share"),
             "time_share": shares.get(m, {}).get("time_share"), "agents": by[m]} for m in order]


def cannot(p: dict, facts: dict, waits: list, money: dict) -> list:
    """What this record does not hold, each in one plain line (an empty section of the card is never left unexplained)."""
    from halo_harness.live.compare_text import bare
    out = []
    if p.get("kind") == "run":
        out.append("A goal run's record holds each lane's state changes (joined, writing, written, in review, merged, failed), "
                   "not each step a lane took.")
    if p.get("upgraded_from") is not None:
        out.append("This is an older file (the 3.0.5.0 to 3.4.0.0 shape): it holds the agents and their states, not the record's figures.")
    elif not facts:
        out.append("This file was saved before 3.4.1.0 R2: the tokens, the retries and the failed model calls are not in it; "
                   "each model's cost comes from its agents.")
    if "artefacts" not in facts:
        out.append("This record does not list the files the run wrote (a replay saved before 3.4.1.0 R3).")
    if facts and facts.get("tokens") is None:
        out.append("The tokens are not in this record" + (": not every lane's transcript is on this disk." if p.get("kind") == "run" else "."))
    if any(str(w.get("text") or "").startswith("a permission card (") for w in waits):
        out.append("A permission card's words are recorded from 3.4.1.0 on: an older card says only when it was answered and how.")
    if any(w.get("secs") is None and "answered" not in str(w.get("text") or "") for w in waits):
        out.append("How long some asks waited is not in the record (the answer's time was not kept).")
    unknown = ", ".join(bare(m) for m in money.get("unknown") or [])
    if not money.get("known") and money.get("total"):
        out.append(f"Halo could not price every call ({unknown or 'a model with no price'}): the cost is the priced part, with a +.")
    elif not money.get("known"):
        out.append(f"No call was priced ({unknown or 'no price recorded'}): the cost is unknown, not $0.")
    out.append("What only Live showed as it happened -- a tool's last output line, a thought's pieces as they streamed -- is not "
               "in the record.")
    return out
