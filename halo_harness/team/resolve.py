"""halo_harness.team.resolve -- what a team's stage runs with, shared by the
runner and the validator (Halo 3.0.8.0; 3.1.0.0 R2 cut it out of
spec_check.py): the members of a lineup tier (`tier_members`), a file or
folder block's files (`block_files`, capped, the ledger and .git left out)
and an orchestra stage's goal with its defaults filled in
(`goal_for_stage`). `_lineup` resolves a member's lineup once per cache.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.team import LEDGER_DIR
from halo_harness.team import spec as S

_FILES_CAP = 100


def _lineup(name: str, cwd, state_dir, cache: dict):
    if name not in cache:
        from halo_harness.teams_yaml import resolve_team_template
        try:
            cache[name] = resolve_team_template(name, cwd=cwd, state_dir=state_dir) if name else None
        except Exception:
            cache[name] = None
    return cache[name]


def tier_members(team: dict, tier: str, *, cwd=None, state_dir=None, cache=None) -> "list[str]":
    """Members whose role sits in their lineup's tier named `tier`."""
    from halo_harness.teams_tiers import effective_tiers
    cache = {} if cache is None else cache
    out = []
    for m in team["members"]:
        lineup = _lineup(m["lineup"], cwd, state_dir, cache)
        for t in effective_tiers(lineup) if lineup else []:
            if t["name"] == tier and m["role"] in t["members"]:
                out.append(m["name"])
    return out


def block_files(root: Path, block: dict, cap: int = _FILES_CAP) -> "list[str]":
    """Repo-relative files of a file or folder block (a git block: none)."""
    path = root / block["path"]
    if block["kind"] == "file":
        return [Path(block["path"]).as_posix()] if path.is_file() else []
    if block["kind"] != "folder" or not path.is_dir():
        return []
    out = []
    for p in sorted(path.rglob("*")):
        if p.is_file() and LEDGER_DIR not in p.parts and ".git" not in p.parts:
            out.append(p.relative_to(root).as_posix())
            if len(out) >= cap:
                break
    return out


def goal_for_stage(team: dict, stage: dict, root) -> dict:
    """An orchestra stage's goal with the defaults filled in: a STOP WHEN,
    the files of its write blocks, and the lead member's lineup."""
    goal = dict(stage.get("goal") or {}) if isinstance(stage.get("goal"), dict) else {}
    goal.setdefault("stop_when", "the team stops this stage")
    if not goal.get("files"):
        files = []
        for bid in stage.get("writes") or []:
            block = S.block_by_id(team, bid)
            files += block_files(Path(root), block) if block else []
        goal["files"] = files
    if not goal.get("lineup"):
        lead = S.member_by_name(team, stage.get("lead") or "") or (team["members"][0] if team["members"] else None)
        if lead and lead.get("lineup"):
            goal["lineup"] = lead["lineup"]
    return goal
