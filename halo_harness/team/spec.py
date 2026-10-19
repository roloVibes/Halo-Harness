"""halo_harness.team.spec -- the team file: where it lives, how it loads.

    <repo>/.halo/team.yaml                     the repo's team (wins)
    ~/.halo/teams/<project>.team.yaml          a team kept outside the repo
                                               (<project> = the repo folder's name)

`<repo>` is the git work tree holding the current folder, else the folder
itself. `load_team(cwd, state_dir)` answers the normalised team (every
default filled in, plus `path`, `source` and `root`) or None when there is
no team file; a file that is not YAML or not a mapping raises ValueError
with a plain message. `validate_team(doc, *, cwd, state_dir)` lists every
problem as one sentence (team/validate.py). `halo team init` writes the
repo file from `templates/team/team.yaml`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

BLOCK_KINDS = ("file", "folder", "git")
CLAIM_MODES = ("section", "file", "none")
STAGE_KINDS = ("agent", "orchestra")
REMOVED_STAGE_KINDS = {"flow": "3.1.4.0"}  # a kind that is gone: validation names the release
GATES = ("required", "optional", "none")
TRIGGER_KINDS = ("manual", "block_change", "stage_done")
BRIEF_ID = "brief"
DEFAULT_SETTLE_S = 20
SUFFIX = ".team.yaml"
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "team" / "team.yaml"


def team_root(cwd=None) -> Path:
    """The git work tree holding `cwd` (the folder itself outside git)."""
    base = Path(cwd if cwd is not None else Path.cwd()).resolve()
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(base), capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=10,
                             stdin=subprocess.DEVNULL)
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    return base


def repo_team_path(root) -> Path:
    return Path(root) / ".halo" / "team.yaml"


def user_team_path(root, state_dir=None) -> Path:
    from halo_harness.config.paths import bridge_home
    base = Path(state_dir) if state_dir is not None else bridge_home()
    return base / "teams" / f"{Path(root).name}{SUFFIX}"


def find_team_file(cwd=None, state_dir=None) -> "Optional[tuple[Path, str, Path]]":
    """`(path, source, root)` with source `repo` or `user`; None when neither exists."""
    root = team_root(cwd)
    for path, source in ((repo_team_path(root), "repo"), (user_team_path(root, state_dir), "user")):
        if path.is_file():
            return path, source, root
    return None


def parse_yaml(text: str, where: str = "the team file") -> dict:
    import yaml
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f"{where} is not valid YAML: {e}") from None
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"{where} is a mapping with name, brief, members, blocks and workflow")
    return data


def _list(value) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return list(value) if isinstance(value, (list, tuple)) else [value]


def default_claims(kind: str) -> str:
    return "file" if kind == "git" else "section"


def parse_trigger(raw) -> "tuple[str, str]":
    """`("manual", "")`, `("block_change", "<block>")` or `("stage_done", "<stage>")`;
    an unknown kind comes back as given (the validator names it)."""
    text = str(raw or "manual").strip()
    kind, _, target = text.partition(":")
    return kind.strip(), target.strip()


def normalize(doc: dict) -> dict:
    """Every key the runner and Studio read, with its default. Unknown keys
    stay out; the raw values are kept where they do not fit, for the validator."""
    doc = doc if isinstance(doc, dict) else {}
    members = []
    for m in _list(doc.get("members")):
        m = m if isinstance(m, dict) else {"name": m}
        members.append({"name": str(m.get("name") or ""), "lineup": str(m.get("lineup") or ""),
                        "role": str(m.get("role") or "main"), "harness": _harness(m.get("harness"))})
    blocks = []
    for b in _list(doc.get("blocks")):
        b = b if isinstance(b, dict) else {"id": b}
        kind = str(b.get("kind") or "folder")
        blocks.append({"id": str(b.get("id") or ""), "kind": kind, "path": str(b.get("path") or ""),
                       "claims": str(b.get("claims") or default_claims(kind))})
    wf = doc.get("workflow") if isinstance(doc.get("workflow"), dict) else {}
    stages = []
    for s in _list(wf.get("stages")):
        s = s if isinstance(s, dict) else {"id": s}
        kind = str(s.get("kind") or "agent")
        names = [str(x) for x in _list(s.get("members"))]
        settle = s.get("settle_s", DEFAULT_SETTLE_S)
        stages.append({"id": str(s.get("id") or ""), "kind": kind, "members": names,
                       "reads": [str(x) for x in _list(s.get("reads"))],
                       "writes": [str(x) for x in _list(s.get("writes"))],
                       "trigger": str(s.get("trigger") or "manual"), "lead": str(s.get("lead") or ""),
                       "gate": str(s.get("gate") or "none"),
                       "acceptance": s.get("acceptance") if isinstance(s.get("acceptance"), dict) else None,
                       "settle_s": settle, "goal": s.get("goal") if kind == "orchestra" else None,
                       "prompt": str(s.get("prompt") or ""), "budget_usd": s.get("budget_usd"),
                       "harness": _harness(s.get("harness")) if kind == "orchestra" else None})
    return {"name": str(doc.get("name") or ""), "brief": str(doc.get("brief") or ""), "members": members,
            "blocks": blocks, "workflow": {"stages": stages}, "budget_usd": doc.get("budget_usd")}


def _harness(raw) -> Optional[str]:
    """A fleet member's name, or None for this harness (`here`, `local` or nothing)."""
    return str(raw) if raw not in (None, "", "here", "local") else None


def load_file(path) -> dict:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"cannot read {path}: {e}") from None
    return parse_yaml(text, str(path))


def load_team(cwd=None, state_dir=None) -> Optional[dict]:
    """The normalised team with `path`, `source` and `root`, or None (no team file)."""
    found = find_team_file(cwd, state_dir)
    if found is None:
        return None
    path, source, root = found
    team = normalize(load_file(path))
    team.update(path=str(path), source=source, root=str(root))
    if not team["name"]:
        team["name"] = root.name
    return team


def stage_by_id(team: dict, sid: str) -> Optional[dict]:
    return next((s for s in team["workflow"]["stages"] if s["id"] == sid), None)


def block_by_id(team: dict, bid: str) -> Optional[dict]:
    return next((b for b in team["blocks"] if b["id"] == bid), None)


def member_by_name(team: dict, name: str) -> Optional[dict]:
    return next((m for m in team["members"] if m["name"] == name), None)


def stage_members(team: dict, stage: dict, *, cwd=None, state_dir=None) -> "list[str]":
    """The member names a stage runs: each entry a member name, else every
    member whose `role` is that alias, else every member whose role sits in
    the lineup tier of that name. An agent stage with none listed runs the first member."""
    from halo_harness.team.resolve import tier_members
    out: "list[str]" = []
    for entry in stage.get("members") or []:
        if member_by_name(team, entry):
            hits = [entry]
        else:
            hits = [m["name"] for m in team["members"] if m["role"] == entry]
            hits = hits or tier_members(team, entry, cwd=cwd, state_dir=state_dir)
        out += [h for h in hits if h not in out]
    if not out and stage.get("kind") == "agent" and team["members"]:
        out = [team["members"][0]["name"]]
    return out


def stage_lead(team: dict, stage: dict, members: "list[str]") -> str:
    return stage.get("lead") or (members[0] if members else "")


def validate_team(doc, *, cwd=None, state_dir=None, preflight: bool = True) -> "list[str]":
    from halo_harness.team.validate import validate_team as _validate
    return _validate(doc, cwd=cwd, state_dir=state_dir, preflight=preflight)


def template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")
