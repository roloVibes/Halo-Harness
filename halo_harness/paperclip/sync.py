"""halo_harness.paperclip.sync -- a Halo lineup as a Paperclip company (Halo
2.2.0 round C3). One Paperclip agent per lineup assignment, run through
Paperclip's `process` adapter as `halo paperclip-run`, with the reporting
lines from the lineup's `org.positions` (reports_to) when it has them and
every member reporting to `main` otherwise. Idempotent: an agent is matched
by the `halo_lineup` + `halo_slot` pair in its metadata, so a second sync
updates in place. `pull` goes the other way: the company's reporting lines
become the lineup's `org:` section.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from halo_harness.paperclip.client import Paperclip

# Paperclip's role enum (POST /api/companies/{id}/agents); Halo roles map onto it.
ROLE_MAP = {"main": "ceo", "subagent": "engineer", "reviewer": "qa", "researcher": "researcher",
            "judge": "qa", "custom": "general", "media": "designer"}
PROCESS_COMMAND = "halo"
PROCESS_ARGS = ["paperclip-run"]


def slot_of(entry: dict) -> str:
    return str(entry.get("as") or entry.get("role") or entry.get("agent") or "")


def agent_payload(lineup: str, entry: dict, bio: Optional[dict], cwd: Path, command: str = PROCESS_COMMAND) -> dict:
    slot = slot_of(entry)
    role = str(entry.get("role") or "subagent")
    desc = str((bio or {}).get("description") or "")
    limits = (bio or {}).get("limits") or {}
    budget = limits.get("max_budget_usd")
    payload = {
        "name": slot, "title": desc[:80] or slot, "role": ROLE_MAP.get(role, "general"),
        "adapterType": "process",
        "adapterConfig": {"command": command, "args": list(PROCESS_ARGS), "cwd": str(cwd)},
        "metadata": {"halo_lineup": lineup, "halo_slot": slot, "halo_agent": str(entry.get("agent") or ""), "halo_role": role},
    }
    if isinstance(budget, (int, float)) and budget > 0:
        payload["budgetMonthlyCents"] = int(round(float(budget) * 100))
    return payload


def reporting_lines(raw: dict) -> dict:
    """slot -> slot it reports to. From org.positions (title -> agent name is
    matched to a slot by agent), else everyone -> the main slot."""
    entries = [e for e in (raw.get("agents") or []) if isinstance(e, dict)]
    by_agent = {}
    main = ""
    for e in entries:
        by_agent.setdefault(str(e.get("agent") or ""), slot_of(e))
        if e.get("role") == "main" and not main:
            main = slot_of(e)
    lines: dict = {}
    org = raw.get("org") if isinstance(raw.get("org"), dict) else {}
    titles = {str(p.get("title")): by_agent.get(str(p.get("agent")), "") for p in (org.get("positions") or []) if isinstance(p, dict)}
    for p in (org.get("positions") or []):
        if isinstance(p, dict) and p.get("reports_to") and titles.get(str(p.get("title"))) and titles.get(str(p.get("reports_to"))):
            lines[titles[str(p["title"])]] = titles[str(p["reports_to"])]
    if not lines and main:
        for e in entries:
            if slot_of(e) != main:
                lines[slot_of(e)] = main
    return lines


def sync_lineup(client: Paperclip, company_id: str, lineup: str, *, cwd: Path, cwd_halo=None, state_dir=None,
                command: str = PROCESS_COMMAND, out=sys.stdout) -> list:
    """Create or update the company's agents from the lineup. Returns the
    agents (dicts) in lineup order."""
    from halo_harness.agents_yaml import resolve_agent_bio
    from halo_harness.teams_yaml import load_team_template_raw
    raw = load_team_template_raw(lineup, cwd=cwd_halo, state_dir=state_dir)
    if raw is None:
        raise ValueError(f"no lineup named {lineup!r}")
    entries = [e for e in (raw.get("agents") or []) if isinstance(e, dict)]
    existing = {}
    for a in client.agents(company_id):
        meta = a.get("metadata") if isinstance(a.get("metadata"), dict) else {}
        if meta.get("halo_lineup") == lineup and meta.get("halo_slot"):
            existing[meta["halo_slot"]] = a
    result = []
    for e in entries:
        bio = resolve_agent_bio(str(e.get("agent") or ""), cwd=cwd_halo, state_dir=state_dir) if e.get("agent") else None
        payload = agent_payload(lineup, e, bio, cwd, command)
        slot = payload["name"]
        if slot in existing:
            agent = client.update_agent(existing[slot]["id"], payload)
            print(f"  updated {slot} ({agent.get('id', '')[:8]})", file=out)
        else:
            agent = client.create_agent(company_id, payload)
            print(f"  created {slot} ({agent.get('id', '')[:8]})", file=out)
        existing[slot] = agent
        result.append(agent)
    lines = reporting_lines(raw)
    for slot, boss in lines.items():
        if slot in existing and boss in existing and existing[slot].get("reportsTo") != existing[boss]["id"]:
            existing[slot] = client.update_agent(existing[slot]["id"], {"reportsTo": existing[boss]["id"]})
            print(f"  {slot} reports to {boss}", file=out)
    return [existing[slot_of(e)] for e in entries if slot_of(e) in existing]


def pull_reporting_lines(client: Paperclip, company_id: str, lineup: str, *, cwd_halo=None, state_dir=None, project=False) -> dict:
    """Write the company's reporting lines into the lineup's org.positions."""
    from halo_harness.teams_yaml import load_team_template_raw, save_team_template
    raw = load_team_template_raw(lineup, cwd=cwd_halo, state_dir=state_dir)
    if raw is None:
        raise ValueError(f"no lineup named {lineup!r}")
    agents = client.agents(company_id)
    by_id = {a["id"]: a for a in agents}
    slot_by_id = {}
    for a in agents:
        meta = a.get("metadata") if isinstance(a.get("metadata"), dict) else {}
        if meta.get("halo_lineup") == lineup and meta.get("halo_slot"):
            slot_by_id[a["id"]] = (meta["halo_slot"], meta.get("halo_agent", ""))
    positions = []
    for aid, (slot, agent_name) in slot_by_id.items():
        pos = {"title": slot, "agent": agent_name or slot}
        boss = by_id.get(aid, {}).get("reportsTo")
        if boss in slot_by_id:
            pos["reports_to"] = slot_by_id[boss][0]
        positions.append(pos)
    clean = {k: v for k, v in raw.items() if not str(k).startswith("_")}
    clean["org"] = {**(clean.get("org") or {}), "positions": positions}
    ok, problems = save_team_template(lineup, clean, cwd=cwd_halo, state_dir=state_dir, project=project)
    if not ok:
        raise ValueError("; ".join(problems))
    return clean["org"]


def org_tree_lines(org: list, indent: int = 0) -> list:
    """`GET /companies/{id}/org` as indented text: name (role, status)."""
    lines = []
    for node in org or []:
        lines.append("  " * indent + f"{node.get('name')}  ({node.get('role')}, {node.get('status')})")
        lines.extend(org_tree_lines(node.get("reports") or [], indent + 1))
    return lines
