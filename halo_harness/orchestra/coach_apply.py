"""halo_harness.orchestra.coach_apply -- a coach card's Apply (Halo 3.1.3.0 R1):
the change the card names, written through the writers Studio's editors use.

* a bio field (`models.preference`, `tools.allow`, `tools.deny`,
  `context.prompt_notes`: the note goes after the bio's own notes, once):
  `agents_yaml.save_agent_bio`, in the scope the bio was found in (a shipped
  bio gets a user copy);
* a lineup role's model (`roles.<role>`: that role's `models.preference`):
  `teams_yaml.save_team_template`, in the lineup's own scope;
* a plan job's field (`job-<n>.after`, `job-<n>.drop`): the run's plan draft,
  `orchestra.plan.write_draft` (the plan editor's own save; the run already
  ran, so the draft is the plan the next run starts from).

`preview(...)` is the confirm card: `{id, target, name, field, value, file,
exists, before, after, diff}` and writes nothing. `apply(...)` writes, reads
the file back and records the change (orchestra/coach_record.py, which also
holds Undo). A change that cannot be made raises ApplyError with the reason.

3.1.6.0 R2: a writer takes several fields of its one file at once (`fields`:
[[field, value], ...]), and a lineup's `agents.<bio>.use_for` (that entry's
routing words); a probe card's `overlay` target (several files) is previewed
and applied by orchestra/coach_probe_card.py through these writers.

3.1.6.0 R3: every Apply (a card's change, a probe card's group) then becomes
one entry of the improvement library (orchestra/coach_library.py); the
returned row carries its id as `entry`.
"""

from __future__ import annotations

import copy
import difflib
import json
import time
from pathlib import Path

from halo_harness.orchestra import coach_record as R


class ApplyError(ValueError):
    pass


def _yaml(payload: dict) -> str:
    import yaml
    return yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, allow_unicode=True)


def set_path(raw: dict, field: str, value) -> None:
    keys = field.split(".")
    cur = raw
    for k in keys[:-1]:
        if not isinstance(cur.get(k), dict):
            cur[k] = {}
        cur = cur[k]
    old = cur.get(keys[-1])
    if field.endswith("prompt_notes") and isinstance(old, str) and old.strip() and isinstance(value, str):
        value = old if value in old else f"{old.rstrip()}\n{value}"
    cur[keys[-1]] = value


def pairs(a: dict) -> list:
    """3.1.6.0 R2: the (field, value) pairs one write sets: `a["fields"]` (a probe card's change, every field of one
    file at once), else the one `field` = `value`."""
    return [tuple(p) for p in a.get("fields") or []] or [(a["field"], a["value"])]


def _bio(a: dict, cwd, state_dir) -> dict:
    from halo_harness import agents_yaml as A
    raw = A.load_agent_bio_raw(a["name"], cwd=cwd, state_dir=state_dir)
    if raw is None:
        raise ApplyError(f"no bio named {a['name']!r} here")
    project = raw.get("_source") == "project"
    raw = {k: copy.deepcopy(v) for k, v in raw.items() if not k.startswith("_")}
    raw["name"] = a["name"]
    for field, value in pairs(a):
        set_path(raw, field, value)
    problems = A.validate_agent_bio(raw, name=a["name"], cwd=cwd, state_dir=state_dir)
    if problems:
        raise ApplyError(f"bio {a['name']}: {problems[0]}")
    path = (A.project_agents_dir(cwd) if project else A.user_agents_dir(state_dir)) / f"{a['name']}.yaml"
    write = lambda: A.save_agent_bio(a["name"], raw, cwd=cwd, state_dir=state_dir, project=project)  # noqa: E731
    return {"file": path, "render": _yaml(dict(raw, name=a["name"])), "write": write}


def _lineup(a: dict, cwd, state_dir) -> dict:
    from halo_harness import teams_yaml as T
    name = a.get("name") or ""
    if not name:
        from halo_harness.theme import get_config_value
        name = str(get_config_value("team", "") or "")
    if not name:
        raise ApplyError("the run names no lineup and none is active: give the role its model in Studio's Roles")
    raw = T.load_team_template_raw(name, cwd=cwd, state_dir=state_dir)
    if raw is None:
        raise ApplyError(f"no lineup named {name!r} here")
    project = raw.get("_source") == "project"
    raw = {k: copy.deepcopy(v) for k, v in raw.items() if not k.startswith("_") and k != "roles"}
    raw["name"] = name
    for field, value in pairs(a):  # roles.<role>: that role's model; 3.1.6.0 R2 agents.<bio>.use_for: that entry's words
        agents = [e for e in raw.get("agents") or [] if isinstance(e, dict)]
        if field.startswith("agents.") and field.endswith(".use_for"):
            bio = field[len("agents."):-len(".use_for")]
            entry = next((e for e in agents if e.get("agent") == bio), None)
            if entry is None:
                raise ApplyError(f"lineup {name} has no entry for bio {bio}: add it in Studio's Roles")
            entry["use_for"] = list(value or [])
            continue
        role = field.replace("roles.", "", 1)
        entry = next((e for e in agents if role in (e.get("as"), e.get("role"))), None)
        if entry is None:
            raise ApplyError(f"lineup {name} has no {role} role: give one the model {value} in Studio's Roles")
        set_path(entry, "models.preference", value)
    problems = T.validate_team_template(raw, name=name, cwd=cwd, state_dir=state_dir)
    if problems:
        raise ApplyError(f"lineup {name}: {problems[0]}")
    path = (T.project_teams_dir(cwd) if project else T.user_teams_dir(state_dir)) / f"{name}.yaml"
    write = lambda: T.save_team_template(name, raw, cwd=cwd, state_dir=state_dir, project=project)  # noqa: E731
    return {"file": path, "render": _yaml(dict(raw, name=name)), "write": write, "name": name}


def _plan(a: dict, run_dir: Path) -> dict:
    from halo_harness.orchestra import plan as P
    jobs = copy.deepcopy(P.current_jobs(run_dir))
    for field, value in pairs(a):
        job, key = (field.split(".", 1) + [""])[:2]
        if not any(str(j.get("id")) == job for j in jobs):
            raise ApplyError(f"the plan of run {run_dir.name} has no {job}")
        if key == "drop":
            jobs = [dict(j, after=[x for x in j.get("after") or [] if x != job]) for j in jobs if str(j.get("id")) != job]
        else:
            jobs = [dict(j, after=list(value or [])) if str(j.get("id")) == job else j for j in jobs]
    render = json.dumps({"jobs": jobs, "ts": round(time.time(), 3)}, indent=2, ensure_ascii=False, default=str) + "\n"

    def write():
        P.write_draft(run_dir, jobs)
        return True, []
    return {"file": Path(run_dir) / P.DRAFT, "render": render, "write": write}


def _change(s: dict, run_dir, cwd, state_dir) -> dict:
    a = s.get("apply")
    if not a:
        raise ApplyError(f"{s['id']} names no change to apply: change it by hand")
    if a.get("target") == "bio":
        return _bio(a, cwd, state_dir)
    if a.get("target") == "lineup":
        return _lineup(a, cwd, state_dir)
    if a.get("target") == "plan":
        return _plan(a, Path(run_dir))
    raise ApplyError(f"{s['id']}: no writer for target {a.get('target')!r}")


def diff(before: str, after: str, file) -> list:
    return [line.rstrip("\r\n") for line in difflib.unified_diff(
        before.replace("\r\n", "\n").splitlines(True), after.replace("\r\n", "\n").splitlines(True),
        fromfile=f"{Path(file).name} (now)", tofile=f"{Path(file).name} (after Apply)", n=2)]


def find(result: dict, sid: str) -> dict:
    s = next((x for x in result.get("suggestions") or [] if x.get("id") == sid), None)
    if s is None:
        ids = ", ".join(x["id"] for x in result.get("suggestions") or []) or "none"
        raise ApplyError(f"no suggestion {sid!r} on this run's card (its ids: {ids})")
    return s


def _overlay(s: dict) -> bool:
    return (s.get("apply") or {}).get("target") == "overlay"  # 3.1.6.0 R2: a probe card (orchestra/coach_probe_card.py)


def preview(result: dict, sid: str, run_dir, *, cwd=None, state_dir=None) -> dict:
    s = find(result, sid)
    if _overlay(s):
        from halo_harness.orchestra.coach_probe_card import preview as overlay_preview
        return overlay_preview(result, s, run_dir, cwd=cwd, state_dir=state_dir)
    ch = _change(s, run_dir, cwd, state_dir)
    before = R.text_of(ch["file"])
    a = s["apply"]
    return {"id": sid, "target": a["target"], "name": ch.get("name") or a.get("name"), "field": a["field"],
            "value": a["value"], "file": str(ch["file"]), "exists": before is not None, "before": before or "",
            "after": ch["render"], "diff": diff(before or "", ch["render"], ch["file"])}


def _library(result: dict, s: dict, run_dir, applied: dict, cwd, state_dir) -> dict:
    """3.1.6.0 R3: every Apply becomes a library entry (orchestra/coach_library.py; `entry` is its id); a failed
    entry is `entry_error` and never undoes the Apply."""
    from halo_harness.orchestra.coach_library import born
    try:
        applied["entry"] = born(result, s, run_dir, applied, cwd=cwd, state_dir=state_dir)
    except Exception as e:
        applied.update(entry=None, entry_error=f"{type(e).__name__}: {e}"[:300])
    return applied


def apply(result: dict, sid: str, run_dir, *, cwd=None, state_dir=None) -> dict:
    s = find(result, sid)
    if _overlay(s):
        from halo_harness.orchestra.coach_probe_card import apply as overlay_apply
        return _library(result, s, run_dir, overlay_apply(result, s, run_dir, cwd=cwd, state_dir=state_dir), cwd, state_dir)
    ch = _change(s, run_dir, cwd, state_dir)
    before = R.text_of(ch["file"])
    ok, problems = ch["write"]()
    if not ok:
        raise ApplyError(problems[0] if problems else f"could not write {ch['file']}")
    after = R.text_of(ch["file"]) or ""
    a = s["apply"]
    row = R.append({"op": "apply", "apply_id": R.new_id(), "id": sid, "run": result.get("run"),
                    "run_dir": str(Path(run_dir).resolve()), "kind": result.get("kind"), "target": a["target"],
                    "name": ch.get("name") or a.get("name"), "field": a["field"], "value": a["value"],
                    "file": str(ch["file"]), "existed": before is not None, "before": before or "", "after": after,
                    "ts": round(time.time(), 3)}, state_dir)
    return _library(result, s, run_dir, dict(row, diff=diff(before or "", after, ch["file"])), cwd, state_dir)
