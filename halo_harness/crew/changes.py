"""halo_harness.crew.changes -- a change set: preview, apply, undo (Halo 3.6.0.0 R1; docs/STUDIO-builder.md).

A builder tool never writes. It answers rows, one per thing that would change:

    {id, kind: create | change | remove | fill, target: "agent:<name>", summary, widen, ticked, op}

`widen` is True for a row that lets an agent do more than before: a tool beyond reading (change files, run commands,
the web, a skill, a connected tool), a less careful mode, a higher (or no) money cap, `offline` turned off. Such a row
starts unticked (`ticked: False`), and `apply` writes only the ids the person sent back ticked -- so a description, a
pasted document or the model's own reply can never tick one. `fill` rows write nothing: the page puts their text into
the form (instructions drafted for an agent that is not saved yet).

3.6.0.0 R2: a row may target `workflow:<name>` (crew/tools_flow.py): its step ops (crew/changes_steps.py) never widen
-- what a workflow's agents may do is in each agent's own file, and its own rows say it.

`apply(rows, ids)` writes every ticked row's target file under <state>/crew/ after checking each result with
crew/formats.py (nothing is written when one fails) and keeps the before-image of every touched file in
<state>/crew/.undo/<undo_id>.json (the last KEEP); `undo(undo_id)` puts each file back exactly as it was.
"""

from __future__ import annotations

import copy
import json
import secrets
import time
from pathlib import Path

from halo_harness.crew import store
from halo_harness.crew.formats import CAREFUL, PROBLEMS

KEEP = 20
NARROW_USES = ("read",)
USE_WORDS = {"read": "Read files", "edit": "Change files", "bash": "Run commands", "web": "The web"}


def use_word(u: str) -> str:
    if u in USE_WORDS:
        return USE_WORDS[u]
    kind, _, name = u.partition(":")
    return f"Skill: {name}" if kind == "skill" else f"Connected tool: {name}"


def careful_rank(v) -> int:
    return CAREFUL.index(v) if v in CAREFUL else 0


def row(kind: str, target: str, summary: str, op: dict, widen: bool = False) -> dict:
    return {"id": "c" + secrets.token_hex(4), "kind": kind, "target": target, "summary": summary,
            "widen": bool(widen), "ticked": not widen, "op": op}


def widens(op: dict, before: dict) -> bool:
    """True when `op` lets the agent do more than `before` (its file now; {} for a new agent)."""
    o, more = op.get("op"), before.get("more") or {}
    if o == "add_use":
        return op["use"] not in NARROW_USES and op["use"] not in (before.get("uses") or [])
    if o == "set" and op["field"] == "careful":
        return careful_rank(op["value"]) > careful_rank(before.get("careful", CAREFUL[0]))
    if o == "more" and op["field"] == "max_usd":
        had = more.get("max_usd")
        return isinstance(had, (int, float)) and (op["value"] is None or op["value"] > had)
    if o == "more" and op["field"] == "offline":
        return bool(more.get("offline")) and not op["value"]
    return False


def public(rows: list) -> list:
    """What the page gets: everything but the op's full body (a create's `before` / `after` stay)."""
    out = []
    for r in rows:
        p = {k: v for k, v in r.items() if k != "op"}
        if r["op"].get("op") == "fill":
            p["fill"] = {"field": r["op"]["field"], "value": r["op"]["value"]}
        if str(r["op"].get("op")).startswith(("step_", "map_")):  # R2: a ghost step in the form; R3: a ghost box or line
            p["ghost"] = {k: v for k, v in r["op"].items() if k != "op"} | {"op": r["op"]["op"]}
        if r["target"].startswith("map:") and r["op"].get("op") in ("create", "copy"):
            p["ghost"] = {"op": "map_create", "body": r["op"]["body"]}
        if r["target"].startswith("agent:") and r["op"].get("op") in ("create", "copy"):
            p["body"] = r["op"]["body"]  # the proposal card's "make it" fills the agent form with it
        out.append(p)
    return out


def _apply_op(body, op: dict):
    o = op.get("op")
    if o in ("create", "copy"):
        return copy.deepcopy(op["body"])
    if body is None or o == "remove":
        return None
    body = copy.deepcopy(body)
    if o == "set":
        if op["value"] in (None, "", []):
            body.pop(op["field"], None)
        else:
            body[op["field"]] = op["value"]
    elif o == "add_use":
        body["uses"] = list(body.get("uses") or []) + ([op["use"]] if op["use"] not in (body.get("uses") or []) else [])
    elif o == "drop_use":
        body["uses"] = [u for u in body.get("uses") or [] if u != op["use"]]
    elif o == "more":
        more = dict(body.get("more") or {})
        if op["value"] is None:
            more.pop(op["field"], None)
        else:
            more[op["field"]] = op["value"]
        body["more"] = more
    elif o.startswith("step_"):
        from halo_harness.crew.changes_steps import apply_step
        body = apply_step(body, op)
    elif o.startswith("map_"):  # 3.6.0.0 R3: boxes and lines (crew/changes_map.py)
        from halo_harness.crew.changes_map import apply_map
        body = apply_map(body, op)
    return body


def plan(rows: list, ids, *, cwd=None, state_dir=None) -> "tuple[dict, list, list, list]":
    """({path: new text or None}, skipped lines, problems, fills) for the ticked rows, nothing written."""
    ticked = [r for r in rows if r["id"] in set(ids or [])]
    targets: dict = {}
    skipped, problems, fills = [], [], []
    for r in ticked:
        if r["op"].get("op") == "fill":
            fills.append({"target": r["target"], "field": r["op"]["field"], "value": r["op"]["value"]})
            continue
        if r["op"].get("op") == "use":  # 3.6.0.0 R3: map_use writes config.json's crew.map (crew/changes_map.py)
            from halo_harness.crew.changes_map import config_path, config_text
            from halo_harness.theme import CorruptConfigError
            try:
                out_use = (config_path(), config_text(r["op"].get("value")))
            except CorruptConfigError as e:  # 3.6.0.0 fx: a problem, never {} written over the file
                problems.append(str(e))
                continue
            targets[out_use[0]] = ["config", "crew.map", out_use[1], True]
            continue
        kind, name = r["target"].split(":", 1)
        path = store.path_for(kind, name, cwd=cwd, state_dir=state_dir)
        if path not in targets:
            targets[path] = [kind, name, store.read(path) if path.is_file() else None, False]
        t = targets[path]
        if t[2] is None and r["op"].get("op") not in ("create", "copy"):
            skipped.append(f"{r['summary']} (skipped: {name} is not one of your {kind}s; tick the line that makes it)")
            continue
        t[2] = _apply_op(t[2], r["op"])
        t[3] = True
    out: dict = {}
    for path, (kind, name, body, touched) in targets.items():
        if not touched:
            continue
        if kind == "config":
            out[path] = body
            continue
        if body is not None:
            bad = PROBLEMS[kind](store.clean(body), name=name) if kind in PROBLEMS else []
            problems += [f"{name}: {p}" for p in bad]
        out[path] = None if body is None else store.dump(body)
    return out, skipped, problems, fills


def _write(path: Path, text) -> None:
    """A crew file through store.write_text; config.json (map_use) as Halo writes it, 0600."""
    from halo_harness.crew.changes_map import config_path, write_config
    if Path(path).resolve() == config_path().resolve():
        write_config(text)
    else:
        store.write_text(path, text)


def _undo_dir(state_dir) -> Path:
    return store.state_dir_of(state_dir) / "crew" / ".undo"


def apply(rows: list, ids, *, cwd=None, state_dir=None, texts: "dict | None" = None) -> dict:
    """Write the ticked rows. {ok, undo_id, wrote [path], removed [path], skipped, problems, filled}. `texts`, when a
    dict is passed, is filled {str(path): the validated text written} (3.6.0.15 U4: the Builder puts an agent it wrote
    into its running session with no disk read); the answer's keys never change (Studio's builder/apply returns it)."""
    writes, skipped, problems, fills = plan(rows, ids, cwd=cwd, state_dir=state_dir)
    if problems:
        return {"ok": False, "undo_id": "", "wrote": [], "removed": [], "skipped": skipped, "problems": problems, "filled": []}
    undo_id = write_all(writes, state_dir=state_dir)
    if texts is not None:
        texts.update({str(p): t for p, t in writes.items() if t is not None})
    return {"ok": True, "undo_id": undo_id, "wrote": [str(p) for p, t in writes.items() if t is not None],
            "removed": [str(p) for p, t in writes.items() if t is None], "skipped": skipped, "problems": [], "filled": fills}


def write_all(writes: dict, *, state_dir=None) -> str:
    """Write {path: text | None}, keeping every before-image under one undo id (also the Map tab's own edits)."""
    before = []
    for path in writes:
        try:
            before.append({"path": str(path), "before": path.read_text(encoding="utf-8") if path.is_file() else None})
        except OSError:
            before.append({"path": str(path), "before": None})
    undo_id = ""
    if writes:
        undo_id = time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
        folder = _undo_dir(state_dir)
        store.write_text(folder / f"{undo_id}.json", json.dumps({"at": time.time(), "files": before}, ensure_ascii=False))
        for old in sorted(folder.glob("*.json"))[:-KEEP]:
            store.write_text(old, None)
    for path, text in writes.items():
        _write(path, text)
    return undo_id


def _undoable(path: Path, crew: Path) -> bool:
    """A crew file (yours, or a trusted project's .halo/crew/<kind>/<name>.yaml) or config.json (map_use)."""
    from halo_harness.crew.changes_map import config_path
    p = path.resolve()
    return crew in p.parents or p == config_path().resolve() or \
        (p.parent.name in store.KINDS.values() and p.parent.parent.name == "crew" and p.parent.parent.parent.name == ".halo")


def undo(undo_id: str, *, state_dir=None) -> dict:
    """Every file the apply touched, back as it was (a file it made is removed). {ok, restored [path], removed [path]}
    (`removed`: those of `restored` the apply had made, now gone) or {ok: False, error}."""
    if not undo_id or not all(c.isalnum() or c == "-" for c in undo_id):
        return {"ok": False, "error": "no such change to undo"}
    rec_path = _undo_dir(state_dir) / f"{undo_id}.json"
    try:
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ok": False, "error": f"no change {undo_id} to undo (the last {KEEP} are kept)"}
    crew = (store.state_dir_of(state_dir) / "crew").resolve()
    restored, removed = [], []
    for f in rec.get("files") or []:
        path = Path(f["path"])
        if not _undoable(path, crew):
            continue
        _write(path, f.get("before"))
        restored.append(str(path))
        if f.get("before") is None:
            removed.append(str(path))
    store.write_text(rec_path, None)
    return {"ok": True, "restored": restored, "removed": removed}
