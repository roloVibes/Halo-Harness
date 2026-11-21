"""halo_harness.studio.crew_map_api -- the Map tab's routes (Halo 3.6.0.0 R3; docs/STUDIO-map.md).

    GET  crew/maps                     {maps: [{name, scope, in_use, boxes, lines, problems}], in_use, source, next}: one
                                       row per name, nearest first (a trusted project's map, then yours, then the
                                       starters); `next` (3.6.0.2 R50, F4) is config `crew.map`, null when unset
    GET  crew/map/<name>[?scope=]      {map, scope, path, writable, in_use, next, problems, boxes: {id: {kind, names, ...}},
                                       agents[], workflows[]}: the map and what each box holds (an agent's model and
                                       what it does, a workflow's steps), the compile's problem lines
         [&path=][&soft=1]             3.6.0.2 R50: with `path`, THAT file only -- and only when it is the file the store
                                       reads for `<name>` in that scope (a trusted project's `.halo/crew/maps`, in any
                                       folder; yours; a starter; an enabled pack's), never another file of the name.
                                       Not there: 404, or with soft=1 200 {removed: true, map, scope, path}; there but
                                       not readable here: 404, or soft 200 {unreadable: true, map, scope, path} (T12).
                                       A path outside every maps folder is never looked at: 404, soft {unreadable}.
                                       No path and no map of the name (a just-built map Session reads by name, R28):
                                       404, or soft 200 {removed: true, map, scope, path: ""}
    PUT  crew/map/<name> {map}         save it (a new name makes a new map; a starter is saved as yours under its name;
                                       a trusted project's stays the project's): {undo_id, map, problems: []}; 422 with
                                       the problem lines (a line that would make a circle is named); 409 while locked
                                       is the page's own rule, not the route's
    POST crew/map/<name>/use {on}      config `crew.map` -- what new sessions run on (off: Auto, the default); {undo_id, in_use}
    DELETE crew/map/<name>             delete yours (a starter or the project's: 409)

Every write goes through crew/changes.py (the before-image kept: the builder's Undo, `POST builder/undo`, puts it back)
and is owner-only.
"""

from __future__ import annotations

import os
from pathlib import Path

from halo_harness.crew import changes, store
from halo_harness.crew.compile import DEFAULT_MAP, compile_raw, in_use
from halo_harness.crew.formats import MAP, map_problems
from halo_harness.studio.owner_proof import owner_only

_NAME = r"(?P<name>[a-z][a-z0-9-]{0,47})"


def _rows(req) -> list:
    seen, out = set(), []
    used = in_use(None, req.cwd)[0]
    for r in store.rows("map", cwd=req.cwd, state_dir=req.state_dir):
        auto = store.is_auto(r["name"])  # 3.6.0.5 A4: his old auto/starter file is listed beside Auto, never in use
        key = (r["name"], r["_scope"] == "starter") if auto else r["name"]
        if key in seen:
            continue
        seen.add(key)
        on = store.row_in_use(r["name"], r["_scope"], used)  # 3.6.0.5 A4: one row, ONE answer (GET crew/maps and map/<name>)
        out.append({"name": r["name"], "scope": r["_scope"], "in_use": on, "problems": r["_problems"],
                    "boxes": len(r.get("boxes") or []), "lines": len(r.get("lines") or [])})
    return out


def _next():
    """3.6.0.2 R50 (F4): the map new sessions use -- config `crew.map`, None when unset (`in_use` says the starter)."""
    try:
        from halo_harness.crew.map_facts import next_map
        return next_map()[0]
    except Exception:
        return None


def _next_none() -> bool:
    """The status row's `map_next_none` for the Start view and Empty (crew/map_facts.py `_none_next`, one source)."""
    try:
        from halo_harness.crew.map_facts import _none_next
        return _none_next()
    except Exception:
        return False


def get_maps(req):
    name, source = in_use(None, req.cwd)
    nxt = _next()  # next_none: new sessions start with no map (roles off, crew.map unset), not "the default"
    return 200, {"maps": _rows(req), "rows": _rows(req), "in_use": name, "source": source, "next": nxt,
                 "next_none": nxt is None and _next_none()}


def _box_facts(c, raw: dict, req, cwd=None) -> dict:
    out = {}
    for bid, box in c.boxes.items():
        facts = []
        for n in box["names"]:
            got = store.load(box["kind"], n, cwd=req.cwd if cwd is None else cwd, state_dir=req.state_dir) or {}
            if box["kind"] == "agent":
                facts.append({"name": n, "model": got.get("model"), "does": got.get("does"), "careful": got.get("careful"),
                              "uses": got.get("uses") or [], "missing": not got})
            else:
                facts.append({"name": n, "for": got.get("for"), "missing": not got,
                              "steps": [{"name": s.get("name"), "agents": s.get("agents") or []} for s in got.get("steps") or [] if isinstance(s, dict)]})
        out[bid] = {"kind": box["kind"], "names": box["names"], "facts": facts}
    return out


def _sigs(path, main: str, boxes: dict, cwd, state_dir) -> dict:
    """3.6.0.9 V: `sig`, the hash of the map's file as read (studio/files_live.py), and `deps`, the hash of each agent
    and workflow file whose facts this answer bakes in (`agent:<name>` / `workflow:<name>`), so a page re-reads the map
    when one of THOSE changes on disk, and only then. A hand-written step whose `agents` is not a list of names (a
    format problem `problems` already lists) adds no dep: only a non-empty string is a name."""
    from halo_harness.studio.files_live import file_sig, sig
    pairs = [("agent", main)]
    for b in boxes.values():
        pairs += [(b["kind"], n) for n in b["names"]]
        for f in b["facts"]:
            for s in f.get("steps") or []:
                got = s.get("agents")
                pairs += [("agent", a) for a in (got if isinstance(got, list) else [])]
    names = {(k, n) for k, n in pairs if isinstance(n, str) and n}
    return {"sig": file_sig(path), "deps": {f"{k}:{n}": sig(k, n, cwd, state_dir) for k, n in sorted(names)}}


def _answer(req, name: str, got: dict, cwd) -> dict:
    raw = store.clean(got)
    c = compile_raw(raw, name=name, cwd=cwd, state_dir=req.state_dir)
    main = store.load("agent", c.main.get("agent") or "main", cwd=cwd, state_dir=req.state_dir) or {}
    boxes = _box_facts(c, raw, req, cwd)
    out = {"map": raw, "scope": got["_scope"], "path": got["_path"], "writable": True,
           "in_use": store.row_in_use(name, got["_scope"], in_use(None, req.cwd)[0]),
           "next": _next(), "problems": c.problems, "boxes": boxes,
           "main": {"agent": c.main.get("agent"), "model": main.get("model"), "does": main.get("does")},
           **_sigs(got["_path"], c.main.get("agent") or "main", boxes, cwd, req.state_dir)}
    if got["_scope"] == "starter" and store.is_auto(raw.get("name")):
        # 3.6.0.5 A22 (M1's {names}): the agents a NEW session on Auto gets now, the seven that ship with Halo first
        from halo_harness.config.agents_md import discover_agents
        from halo_harness.crew.compile import compile_map
        from halo_harness.crew.map_session import agents
        out["hand_to"] = list(agents(discover_agents(cwd), compile_map(DEFAULT_MAP, cwd=cwd, state_dir=req.state_dir))[0])
    return out


def _one(req, name: str, scope: str = ""):
    got = store.load("map", name, cwd=req.cwd, state_dir=req.state_dir, scope=scope)
    return None if got is None else _answer(req, name, got, req.cwd)


def _same(a, b) -> bool:
    return os.path.normcase(os.path.realpath(str(a))) == os.path.normcase(os.path.realpath(str(b)))


def _key(p) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(str(p))))


def _in_maps_folder(req, path: str) -> bool:
    """3.6.0.2 R50 (P2 batch 8): `path` names a file in a folder maps live in -- yours, the starters', an enabled pack's,
    the `.halo/crew/maps` of a project Studio knows (whose trust `_at_path` then asks). Decided from the text of `path`
    alone (no file-system call names it or a folder above it), so a page holding Studio's token cannot ask through the
    soft read whether an arbitrary file or folder exists."""
    if not path or not os.path.isabs(path):
        return False
    folder = _key(os.path.dirname(os.path.normpath(path)))
    known = [store.state_dir_of(req.state_dir) / "crew" / "maps", store.SHIPPED / "maps"]
    known += [os.path.dirname(str(b["_path"])) for b in store.pack_items("map", cwd=req.cwd, state_dir=req.state_dir).values()
              if isinstance(b, dict) and b.get("_path")]
    if any(folder in (_key(k), _key(os.path.realpath(str(k)))) for k in known):
        return True
    up = Path(os.path.normpath(path)).parents
    if len(up) < 4 or [x.name for x in up[:3]] != ["maps", "crew", ".halo"]:
        return False
    # batch 8 repair: a project's folder only when Studio knows that project -- its own folder, a live session's, a
    # history line's. Asking whether any named folder is trusted walks it and its parents for `.git`, an oracle again.
    from halo_harness.peers.projects import _history_roots, _registry_roots
    home = store.state_dir_of(req.state_dir)
    roots = [str(req.cwd)] + _registry_roots(home) + _history_roots(home)
    homes = {k for r in roots for t in (Path(r), store.repo_of(r)) for k in (_key(t), _key(os.path.realpath(str(t))))}
    return _key(up[3]) in homes


def _at_path(req, name: str, scope: str, path: str):
    """3.6.0.2 R50: ("found", map, cwd) when `path` is the very file the store reads for `name` in `scope` (any scope
    when none is given) -- a project's from that project's folder (trusted now), yours, a starter, an enabled pack's;
    ("bad", None, None) when that file is there but cannot be read; (None, None, None) when it is not such a file."""
    real = Path(os.path.realpath(path))
    for sc in ("project", "yours", "starter", "pack"):
        if scope and sc != scope:
            continue
        cwd = req.cwd
        if sc == "project":  # <repo>/.halo/crew/maps/<name>.yaml: read as a session in <repo> reads it
            if [x.name for x in real.parents[:3]] != ["maps", "crew", ".halo"] or len(real.parents) < 4:
                continue
            cwd = real.parents[3]
        found = store.find("map", name, cwd=cwd, state_dir=req.state_dir, scope=sc)
        if found is None or found[1] != sc or not _same(found[0], path):
            continue
        got = store.load("map", name, cwd=cwd, state_dir=req.state_dir, scope=sc)
        return ("found", {**got, "_path": str(path)}, cwd) if got is not None else ("bad", None, None)
    return None, None, None


def get_map(req):
    name, q = req.params["name"], (req.query or {})
    scope, path = str(q.get("scope") or ""), str(q.get("path") or "")
    soft = str(q.get("soft") or "") in ("1", "true")  # the page's read (R28): calm; never another file of the name
    if not path:
        got = _one(req, name, scope)
        if got:
            return 200, got
        # 3.6.0.2 R28: Session reads a just-built map by name (its frame names no file); gone, asked softly, is calm
        return (200, {"removed": True, "map": name, "scope": scope, "path": ""}) if soft else (404, {"error": f"no map named {name!r}"})
    allowed = _in_maps_folder(req, path)  # batch 8: any other path is never looked at
    how, got, cwd = _at_path(req, name, scope, path) if allowed else (None, None, None)
    if how == "found":
        return 200, _answer(req, name, got, cwd)
    if soft:
        gone = allowed and how is None and not os.path.lexists(path)
        return 200, {("removed" if gone else "unreadable"): True, "map": name, "scope": scope, "path": path}
    return 404, {"error": f"no map named {name!r} at {path}"}


def put_map(req):
    name = req.params["name"]
    bad = store.default_name_refusal(name)  # 3.6.0.5 A6 (W16): never a map of his under a default's name
    if bad:
        return 422, {"error": bad, "problems": [bad]}
    raw = (req.body or {}).get("map")
    if not isinstance(raw, dict):
        return 400, {"error": "the body needs the map ('map')"}
    raw = store.clean({**raw, "format": MAP, "name": name})
    raw.setdefault("main", {"agent": "main"})
    bad = map_problems(raw, name=name)
    if bad:
        return 422, {"error": bad[0], "problems": bad}
    got = store.find("map", name, cwd=req.cwd, state_dir=req.state_dir)
    project = bool(got and got[1] == "project")
    path = store.path_for("map", name, cwd=req.cwd, state_dir=req.state_dir, project=project)
    undo_id = changes.write_all({path: store.dump(raw)}, state_dir=req.state_dir)
    return 200, {"undo_id": undo_id, **(_one(req, name) or {}), "problems": []}


def post_use(req):
    name = req.params["name"]
    on = bool((req.body or {}).get("on", True))
    if on and store.find("map", name, cwd=req.cwd, state_dir=req.state_dir) is None:
        return 404, {"error": f"no map named {name!r}"}
    from halo_harness.crew.changes_map import ONE_MODEL, config_path, config_text
    now = in_use(None, req.cwd)[0]
    value = name if on else (None if now == name else (now or ONE_MODEL))  # off: no map in use stays no map
    from halo_harness.theme import CorruptConfigError
    try:
        text = config_text(value)
    except CorruptConfigError as e:  # 3.6.0.0 fx: never {} written over a config.json that does not parse
        return 422, {"error": str(e)}
    from halo_harness.crew.map_session import start_modes, starts_said
    before = start_modes(req.cwd, req.state_dir)
    undo_id = changes.write_all({config_path(): text}, state_dir=req.state_dir)
    # 3.6.0.1: the person's own switch asks nothing, but its receipt says when the mode new sessions start in changes
    # (jf-mapuse: here and in a folder that is no trusted project -- crew.map is global)
    moved = starts_said(before, start_modes(req.cwd, req.state_dir))
    # 3.6.0.5 A21 (W18): off with none set is Auto; roles off (no map for new sessions) keeps the true words
    after, src = in_use(None, req.cwd)
    from halo_harness.crew.map_facts import BACK_TO_AUTO
    said = (f"New sessions run on {name}; a running session keeps its own" if on
            else f"{name} was not in use; new sessions still run on {after}"  # 3.6.0.5: off for a map not in use
            if src == "config" and after != name
            else BACK_TO_AUTO
            if src == "default" else "New sessions run on no map (as before maps)")
    return 200, {"undo_id": undo_id, "in_use": in_use(None, req.cwd)[0], "said": f"{said}{'; ' + moved if moved else ''}."}


def delete_map(req):
    name = req.params["name"]
    got = store.find("map", name, cwd=req.cwd, state_dir=req.state_dir, scope="yours")
    if got is None:
        return 409, {"error": f"{name} is not one of your maps (one that ships with Halo or this project's stays)"}
    undo_id = changes.write_all({got[0]: None}, state_dir=req.state_dir)
    return 200, {"undo_id": undo_id}


ROUTES: list = [
    ("GET", r"^crew/maps$", get_maps),
    ("GET", rf"^crew/map/{_NAME}$", get_map),
    ("PUT", rf"^crew/map/{_NAME}$", owner_only(put_map)),
    ("POST", rf"^crew/map/{_NAME}/use$", owner_only(post_use)),
    ("DELETE", rf"^crew/map/{_NAME}$", owner_only(delete_map)),
]
