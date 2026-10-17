"""halo_harness.team.spec_check -- `validate_team`: every problem in a team
file as one plain sentence ([] = valid). `spec.validate_team` is the public
name; this module also holds the two helpers the runner shares with it
(`tier_members`, `goal_for_stage`).

Checked: unique member, block and stage ids; each member's lineup resolves
and its `role` is an alias there; block kinds, claim modes and paths (inside
the repo; an existing path has the block's kind, a missing one can be
created; a git block sits in a git tree); stage kinds, members (a member, an
alias or a tier), lead, reads/writes (block ids; `brief` is always
readable), gates, triggers (`stage_done:` an earlier stage, `block_change:`
a declared block) and no trigger cycle (a stage whose own writes, or a
later stage's, start it again); an orchestra stage's goal; a flow stage's
flow loads; and, with `preflight`, the lineup preflight's `blocks` findings
for every member that runs here.
"""

from __future__ import annotations

import re
from pathlib import Path

from halo_harness.team import LEDGER_DIR
from halo_harness.team import spec as S

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
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


def _inside(root: Path, rel: str) -> bool:
    p = rel.replace("\\", "/")
    if p.startswith("/") or (len(p) > 1 and p[1] == ":") or ".." in p.split("/"):
        return False
    try:
        (root / rel).resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


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


def _check_members(team, cwd, state_dir, cache) -> list:
    out, seen = [], set()
    from halo_harness.teams_tiers import assignment_keys
    if not team["members"]:
        out.append("members: list at least one member (name, lineup, role, harness)")
    for i, m in enumerate(team["members"]):
        name = m["name"]
        if not _ID.match(name):
            out.append(f"members[{i}]: name {name!r} is letters, digits, - and _")
        elif name in seen:
            out.append(f"member `{name}` is listed twice")
        seen.add(name)
        if not m["lineup"]:
            out.append(f"member `{name}`: name its lineup (`halo teams` lists them)")
            continue
        lineup = _lineup(m["lineup"], cwd, state_dir, cache)
        if lineup is None:
            out.append(f"member `{name}`: lineup `{m['lineup']}` does not exist (`halo teams` lists them)")
        elif m["role"] not in assignment_keys(lineup.get("agents")):
            out.append(f"member `{name}`: lineup `{m['lineup']}` has no alias `{m['role']}` "
                       f"(aliases: {', '.join(assignment_keys(lineup.get('agents'))) or 'none'})")
    return out


def _check_blocks(team, root: Path) -> list:
    out, seen = [], set()
    for i, b in enumerate(team["blocks"]):
        bid = b["id"]
        if not _ID.match(bid):
            out.append(f"blocks[{i}]: id {bid!r} is letters, digits, - and _")
        elif bid == S.BRIEF_ID:
            out.append("block id `brief` is taken: the brief is always readable as `brief`")
        elif bid in seen:
            out.append(f"block `{bid}` is declared twice")
        seen.add(bid)
        if b["kind"] not in S.BLOCK_KINDS:
            out.append(f"block `{bid}`: kind is file, folder or git, got {b['kind']!r}")
        if b["claims"] not in S.CLAIM_MODES:
            out.append(f"block `{bid}`: claims is section, file or none, got {b['claims']!r}")
        if not b["path"]:
            out.append(f"block `{bid}`: give its path (relative to {root})")
            continue
        if not _inside(root, b["path"]):
            out.append(f"block `{bid}`: path {b['path']!r} must be relative to the repo and inside it")
            continue
        path = root / b["path"]
        if b["kind"] == "file" and path.exists() and not path.is_file():
            out.append(f"block `{bid}`: {b['path']} is a folder; a file block names one file")
        elif b["kind"] in ("folder", "git") and path.exists() and not path.is_dir():
            out.append(f"block `{bid}`: {b['path']} is a file; a {b['kind']} block names a folder")
        elif b["kind"] == "git" and not (path.is_dir() and _in_git(path)):
            out.append(f"block `{bid}`: {b['path']} is not inside a git work tree")
        elif not path.exists():
            parent = next((p for p in [path.parent, *path.parent.parents] if p.exists()), None)
            if parent is None or not parent.is_dir():
                out.append(f"block `{bid}`: {b['path']} cannot be created here")
    return out


def _in_git(path: Path) -> bool:
    from halo_harness.worktree import repo_root
    try:
        return repo_root(path) is not None
    except Exception:
        return False


def validate_team(doc, *, cwd=None, state_dir=None, preflight: bool = True) -> "list[str]":
    from halo_harness.team.spec_stages import check_stages
    if not isinstance(doc, dict):
        return ["the team file is a mapping with name, brief, members, blocks and workflow"]
    team = S.normalize(doc)
    root = Path(doc.get("root") or S.team_root(cwd))
    cache: dict = {}
    out = []
    if team["name"] and not _ID.match(team["name"]):
        out.append(f"name {team['name']!r} is letters, digits, - and _")
    if not team["brief"]:
        out.append("brief: name the one file every agent reads first (for example docs/BRIEF.md)")
    elif not _inside(root, team["brief"]):
        out.append(f"brief {team['brief']!r} must be a file inside the repo")
    elif not (root / team["brief"]).is_file():
        out.append(f"brief {team['brief']} does not exist yet: write it (halo team init makes a starter)")
    out += _check_members(team, cwd, state_dir, cache)
    out += _check_blocks(team, root)
    out += check_stages(team, root, cwd=cwd, state_dir=state_dir, cache=cache)
    if preflight:
        out += preflight_lines(team, cwd=cwd, state_dir=state_dir, cache=cache)
    return out


def preflight_findings(team: dict, *, cwd=None, state_dir=None, cache=None) -> "list[dict]":
    """The lineup preflight for every member that runs here, ids and texts
    prefixed by the member (`writer/dead-model:main`)."""
    from halo_harness.lineup_preflight import lineup_problems
    cache = {} if cache is None else cache
    out, seen = [], set()
    for m in team["members"]:
        if m.get("harness") or not m["lineup"] or _lineup(m["lineup"], cwd, state_dir, cache) is None:
            continue
        if m["lineup"] in seen:
            continue
        seen.add(m["lineup"])
        for f in lineup_problems(m["lineup"], cwd=cwd, state_dir=state_dir):
            out.append({**f, "id": f"{m['name']}/{f['id']}",
                        "text": f"member `{m['name']}` (lineup `{m['lineup']}`): {f['text']}"})
    return out


def preflight_lines(team: dict, *, cwd=None, state_dir=None, cache=None) -> "list[str]":
    from halo_harness.lineup_preflight import blocking
    return [f"preflight: {f['text']} -- fix: {f['fix']}"
            for f in blocking(preflight_findings(team, cwd=cwd, state_dir=state_dir, cache=cache))]
