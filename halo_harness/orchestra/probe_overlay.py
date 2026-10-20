"""halo_harness.orchestra.probe_overlay -- a candidate overlay delivered to a
probe run's workers (Halo 3.1.6.0 R2; orchestra/probe_runs.py runs them).

Two ways in, both per lane, both written when the lane's worker starts
(`adapters.spawn_worker(..., team=, cwd_overlay=writer(...))`):

* the lane worktree's project scope, which the worker resolves nearest-first
  (agents_yaml / teams_yaml: `<cwd>/.halo/agents`, `<cwd>/.halo/teams`):
      .halo/.gitignore          `*` (the run commits the worktree with `git add -A`; a file git
                                already tracks is marked skip-worktree instead)
      .halo/agents/<bio>.yaml   each bio the overlay changes, resolved, with its fields set
      .halo/teams/<lineup>.yaml the goal's lineup with the overlay's models and use_for words
  plus `--team <lineup>` on the worker's argv, so what the worker starts under
  the lineup (its sub-agents) composes those bios;
* the worker session itself (a `halo -p` main session does not compose its
  own bio's notes, only a sub-agent's): `--append-system-prompt` with the
  lane's notes, `--max-turns`, `--allowedTools`, `--disallowedTools`.

The lane's model goes through the approved plan (the job's `model`).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Callable

from halo_harness.orchestra.coach_probe_schema import for_bio, joined

IGNORE = "# The coach's probe overlay: never committed.\n*\n"


def _dump(data: dict) -> str:
    import yaml
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)


def _set(raw: dict, dotted: str, value) -> None:
    cur = raw
    keys = dotted.split(".")
    for k in keys[:-1]:
        if not isinstance(cur.get(k), dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = joined(cur.get(keys[-1]), value) if keys[-1] == "prompt_notes" else value


BIO_FIELDS = {"prompt_notes": "context.prompt_notes", "model": "models.preference", "effort": "models.effort",
              "max_iterations": "limits.max_iterations"}


def bio_fields(part: dict) -> list:
    """[(dotted bio field, value)] for one overlay part (`tools` as tools.allow / tools.deny)."""
    out = [(BIO_FIELDS[k], v) for k, v in part.items() if k in BIO_FIELDS]
    for k in ("allow", "deny"):
        if k in (part.get("tools") or {}):
            out.append((f"tools.{k}", part["tools"][k]))
    return out


def lane_bios(f: dict) -> list:
    """The bios the run's workers ran as (the lanes', else the lineup's worker role)."""
    bios = sorted({l["bio"] for l in f.get("lanes") or [] if l.get("bio")})
    return bios or ([f["worker_bio"]] if f.get("worker_bio") else [])


def scope_files(overlay: dict, f: dict) -> dict:
    """{path relative to a worktree: text} of the overlay's project scope (only the .gitignore when it changes nothing)."""
    from halo_harness.agents_yaml import resolve_agent_bio
    files = {".halo/.gitignore": IGNORE}
    names = set(lane_bios(f)) | set((overlay.get("bios") or {}))
    if f.get("lead_bio") and overlay.get("lead"):
        names.add(f["lead_bio"])
    for name in sorted(names):
        part = dict(for_bio(overlay, name))
        if name == f.get("lead_bio") and name not in lane_bios(f):
            part = dict(overlay.get("lead") or {})
        fields = bio_fields(part)
        bio = resolve_agent_bio(name, cwd=f["cwd"], state_dir=f.get("state_dir")) if fields else None
        if not bio:
            continue
        raw = {k: copy.deepcopy(v) for k, v in bio.items() if not str(k).startswith("_") and k != "extends"}
        raw["name"] = name
        for dotted, value in fields:
            _set(raw, dotted, value)
        files[f".halo/agents/{name}.yaml"] = _dump(raw)
    lineup = lineup_text(overlay, f)
    if lineup:
        files[f".halo/teams/{f['lineup']}.yaml"] = lineup
    return files


def lineup_text(overlay: dict, f: dict) -> str:
    """The goal's lineup with the overlay's models (an entry's own model wins over its bio's) and use_for words."""
    raw = f.get("lineup_raw") or {}
    if not f.get("lineup") or not raw:
        return ""
    raw = {k: copy.deepcopy(v) for k, v in raw.items() if not str(k).startswith("_") and k != "roles"}
    for e in raw.get("agents") or []:
        if not isinstance(e, dict):
            continue
        role, bio = e.get("as") or e.get("role"), str(e.get("agent") or "")
        part = dict(overlay.get("lead") or {}) if role == f.get("lead_role") else for_bio(overlay, bio)
        if part.get("model"):
            _set(e, "models.preference", part["model"])
        if part.get("effort"):
            _set(e, "models.effort", part["effort"])
        words = ((overlay.get("bios") or {}).get(bio) or {}).get("use_for")
        if words:
            e["use_for"] = list(words)
    raw["name"] = f["lineup"]
    return _dump(raw)


def flags(overlay: dict, bio: str) -> list:
    """The worker flags that carry the lane's part of the overlay to the worker session itself."""
    part = for_bio(overlay, bio)
    out = []
    if part.get("prompt_notes"):
        out += ["--append-system-prompt", "Notes for this run (the coach's probe):\n" + part["prompt_notes"]]
    if part.get("max_iterations"):
        out += ["--max-turns", str(int(part["max_iterations"]))]
    tools = part.get("tools") or {}
    if tools.get("allow"):
        out += ["--allowedTools", ",".join(tools["allow"])]
    if tools.get("deny"):
        out += ["--disallowedTools", ",".join(tools["deny"])]
    return out


def _tracked(worktree: Path, rel: str) -> bool:
    from halo_harness.orchestra import gitops
    return gitops.git(["ls-files", "--error-unmatch", "--", rel], worktree).returncode == 0


def write_scope(worktree, files: dict) -> list:
    """Write the scope into one worktree; a file git tracks is marked skip-worktree so the run never commits it."""
    from halo_harness.orchestra import gitops
    worktree, written = Path(worktree), []
    for rel, text in files.items():
        path = worktree / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        if _tracked(worktree, rel):
            gitops.git(["update-index", "--skip-worktree", "--", rel], worktree)
        written.append(rel)
    return written


def writer(overlay: dict, f: dict, seen: "dict | None" = None) -> Callable:
    """`cwd_overlay(lane)` for adapters.spawn_worker: the scope written into the lane's worktree, the worker flags
    answered. `seen` (optional) keeps {lane: {files, flags}} for the probe's record."""
    files = scope_files(overlay, f)
    by_lane = {l["n"]: l.get("bio") or "" for l in f.get("lanes") or []}

    def cwd_overlay(lane) -> list:
        bio = str(getattr(lane.job, "bio", "") or by_lane.get(lane.n) or f.get("worker_bio") or "")
        written = write_scope(lane.worktree, files)
        out = flags(overlay, bio)
        if seen is not None:
            seen[lane.n] = {"files": written, "flags": out, "bio": bio}
        return out
    return cwd_overlay
