"""halo_harness.packs.clone -- a pack's bio or lineup copied into your folder
(Halo 3.2.0.0 R2: Studio's Roles "Clone" and "Customize").

The copy is the pack's file as Halo reads it (the pack's own bio and lineup
names qualified, so `extends: reviewer` reads `extends: doc-review--reviewer`
and a lineup's members stay the pack's bios), named without the `<id>--`
(`doc-review--reviewer` -> `reviewer`), with one line more:
`from_pack: doc-review@1.0.0`. It goes to `~/.halo/agents/` or
`~/.halo/teams/` (the project's `.halo/` with `project=True`). A file of
yours with that name is never written over without `replace=True` -- the
caller asks first (Studio's confirm) -- so there is no path that writes into
a file of yours unasked. A name Halo ships (the `reviewer` bio) asks the
same way: your copy would take the shipped one's place everywhere.

    clone("bio", "doc-review--reviewer", cwd=..., state_dir=...)
      -> {"ok": True, "name": "reviewer", "path": ..., "from_pack": "doc-review@1.0.0"}
      -> {"ok": False, "exists": True, "name": "reviewer", "path": ..., "error": "..."}   # ask, then replace=True
      -> {"ok": False, "error": "...", "problems": [...]}
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from halo_harness.packs import names as N

KINDS = ("bio", "lineup")


def _modules(kind: str):
    from halo_harness import agents_yaml as A
    from halo_harness import teams_yaml as T
    if kind == "bio":
        return A.find_agent_bio_path, A.load_agent_bio_raw, A.save_agent_bio, A.project_agents_dir, A.user_agents_dir
    return T.find_team_template_path, T.load_team_template_raw, T.save_team_template, T.project_teams_dir, T.user_teams_dir


def _shipped(kind: str, name: str) -> Path:
    from halo_harness import agents_yaml as A
    from halo_harness import teams_yaml as T
    folder = A.bundled_agent_templates_dir() if kind == "bio" else T.bundled_team_templates_dir()
    return Path(folder) / f"{name}.yaml"


def target_name(name: str) -> str:
    """The name the copy takes: the pack's own name, `<id>--` dropped."""
    return N.unqualify(name)[1]


def clone(kind: str, name: str, *, as_name: Optional[str] = None, project: bool = False, replace: bool = False,
          cwd=None, state_dir=None) -> dict:
    if kind not in KINDS:
        return {"ok": False, "error": f"clone takes a bio or a lineup, not {kind!r}", "problems": []}
    find, load, save, project_dir, user_dir = _modules(kind)
    found = find(name, cwd=cwd, state_dir=state_dir)
    pack_id = N.pack_of_source(found[1]) if found else None
    if not pack_id:
        where = f"a {N.scope_label(found[1])} {kind}" if found else "not found"
        return {"ok": False, "error": f"{name} is not a pack's {kind} ({where}): Duplicate copies one of yours",
                "problems": []}
    new = (as_name or target_name(name)).strip()
    if not N.is_valid_name(new):
        return {"ok": False, "error": f"{new!r} is not a valid {kind} name (letters, digits, - and _)", "problems": []}
    path = Path(project_dir(cwd) if project else user_dir(state_dir)) / f"{new}.yaml"
    if path.is_file() and not replace:
        return {"ok": False, "exists": True, "shipped": False, "name": new, "path": str(path),
                "error": f"a {kind} named {new} is already yours ({path.name}): replace it, or pick another name"}
    if _shipped(kind, new).is_file() and not replace:
        user = "a lineup names it" if kind == "bio" else "you apply it"
        return {"ok": False, "exists": True, "shipped": True, "name": new, "path": str(path),
                "error": f"Halo ships a {kind} named {new}: your copy would take its place wherever {user}; "
                         "pick another name, or keep this one"}
    from halo_harness.packs.registry import snapshot
    pack = snapshot(cwd=cwd, state_dir=state_dir).pack(pack_id)
    data = {k: v for k, v in (load(name, cwd=cwd, state_dir=state_dir) or {}).items() if not k.startswith("_")}
    data["from_pack"] = f"{pack_id}@{pack.version if pack is not None else '?'}"
    data["name"] = new
    existed = path.is_file()
    ok, problems = save(new, data, cwd=cwd, state_dir=state_dir, project=project)
    if not ok:
        return {"ok": False, "error": problems[0] if problems else "the copy was not saved", "problems": problems}
    return {"ok": True, "name": new, "path": str(path), "from_pack": data["from_pack"], "replaced": existed}
