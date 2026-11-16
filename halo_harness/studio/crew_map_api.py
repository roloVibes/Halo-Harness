"""halo_harness.studio.crew_map_api -- the Map tab's routes (Halo 3.6.0.0 R3; docs/STUDIO-map.md).

    GET  crew/maps                     {maps: [{name, scope, in_use, boxes, lines, problems}], in_use, source}: one row
                                       per name, nearest first (a trusted project's map, then yours, then the starters)
    GET  crew/map/<name>[?scope=]      {map, scope, path, writable, in_use, problems, boxes: {id: {kind, names, ...}},
                                       agents[], workflows[]}: the map and what each box holds (an agent's model and
                                       what it does, a workflow's steps), the compile's problem lines
    PUT  crew/map/<name> {map}         save it (a new name makes a new map; a starter is saved as yours under its name;
                                       a trusted project's stays the project's): {undo_id, map, problems: []}; 422 with
                                       the problem lines (a line that would make a circle is named); 409 while locked
                                       is the page's own rule, not the route's
    POST crew/map/<name>/use {on}      config `crew.map` -- what new sessions run on (off: the starter map); {undo_id, in_use}
    DELETE crew/map/<name>             delete yours (a starter or the project's: 409)

Every write goes through crew/changes.py (the before-image kept: the builder's Undo, `POST builder/undo`, puts it back)
and is owner-only.
"""

from __future__ import annotations

from halo_harness.crew import changes, store
from halo_harness.crew.compile import compile_raw, in_use
from halo_harness.crew.formats import MAP, map_problems
from halo_harness.studio.owner_proof import owner_only

_NAME = r"(?P<name>[a-z][a-z0-9-]{0,47})"


def _rows(req) -> list:
    seen, out = set(), []
    used = in_use(None, req.cwd)[0]
    for r in store.rows("map", cwd=req.cwd, state_dir=req.state_dir):
        if r["name"] in seen:
            continue
        seen.add(r["name"])
        out.append({"name": r["name"], "scope": r["_scope"], "in_use": r["name"] == used, "problems": r["_problems"],
                    "boxes": len(r.get("boxes") or []), "lines": len(r.get("lines") or [])})
    return out


def get_maps(req):
    name, source = in_use(None, req.cwd)
    return 200, {"maps": _rows(req), "rows": _rows(req), "in_use": name, "source": source}


def _box_facts(c, raw: dict, req) -> dict:
    out = {}
    for bid, box in c.boxes.items():
        facts = []
        for n in box["names"]:
            got = store.load(box["kind"], n, cwd=req.cwd, state_dir=req.state_dir) or {}
            if box["kind"] == "agent":
                facts.append({"name": n, "model": got.get("model"), "does": got.get("does"), "careful": got.get("careful"),
                              "uses": got.get("uses") or [], "missing": not got})
            else:
                facts.append({"name": n, "for": got.get("for"), "missing": not got,
                              "steps": [{"name": s.get("name"), "agents": s.get("agents") or []} for s in got.get("steps") or [] if isinstance(s, dict)]})
        out[bid] = {"kind": box["kind"], "names": box["names"], "facts": facts}
    return out


def _one(req, name: str, scope: str = ""):
    got = store.load("map", name, cwd=req.cwd, state_dir=req.state_dir, scope=scope)
    if got is None:
        return None
    raw = store.clean(got)
    c = compile_raw(raw, name=name, cwd=req.cwd, state_dir=req.state_dir)
    main = store.load("agent", c.main.get("agent") or "main", cwd=req.cwd, state_dir=req.state_dir) or {}
    return {"map": raw, "scope": got["_scope"], "path": got["_path"], "writable": True, "in_use": in_use(None, req.cwd)[0] == name,
            "problems": c.problems, "boxes": _box_facts(c, raw, req),
            "main": {"agent": c.main.get("agent"), "model": main.get("model"), "does": main.get("does")}}


def get_map(req):
    got = _one(req, req.params["name"], str((req.query or {}).get("scope") or ""))
    return (200, got) if got else (404, {"error": f"no map named {req.params['name']!r}"})


def put_map(req):
    name = req.params["name"]
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
    said = (f"New sessions run on {name}; a running session keeps its own" if on else "New sessions run on no map (as before maps)")
    return 200, {"undo_id": undo_id, "in_use": in_use(None, req.cwd)[0], "said": f"{said}{'; ' + moved if moved else ''}."}


def delete_map(req):
    name = req.params["name"]
    got = store.find("map", name, cwd=req.cwd, state_dir=req.state_dir, scope="yours")
    if got is None:
        return 409, {"error": f"{name} is not one of your maps (a starter or this project's stays)"}
    undo_id = changes.write_all({got[0]: None}, state_dir=req.state_dir)
    return 200, {"undo_id": undo_id}


ROUTES: list = [
    ("GET", r"^crew/maps$", get_maps),
    ("GET", rf"^crew/map/{_NAME}$", get_map),
    ("PUT", rf"^crew/map/{_NAME}$", owner_only(put_map)),
    ("POST", rf"^crew/map/{_NAME}/use$", owner_only(post_use)),
    ("DELETE", rf"^crew/map/{_NAME}$", owner_only(delete_map)),
]
