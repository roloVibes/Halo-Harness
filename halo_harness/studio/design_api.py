"""halo_harness.studio.design_api -- Studio's Design mode backend (Halo
3.0.1.0 round D3): `/api/design/...` over `halo_harness.design` (projects,
artboards, turns, comments, knobs, direct text edits, versions, the design
system, exports, the handoff). Same loopback / origin / token guard as every
Studio route. `RUNNER` replaces the turn's subprocess (tests set it);
`REGISTERED` pins the craft apps a turn may use (None = the user's config).
"""

from __future__ import annotations

import re

from halo_harness.design import controls as C
from halo_harness.design.store import Project
from halo_harness.studio import design_api_turns as turns
from halo_harness.studio.design_api_io import _artboard, _bad, _project, export, handoff, put_system, restore, sync, versions

RUNNER = None
REGISTERED = None


def list_projects(req):
    return 200, {"projects": Project.list(state_dir=req.state_dir)}


def new_project(req):
    name = str(req.body.get("name") or "").strip()
    if not name:
        return _bad("a project needs a name")
    p = Project.create(name, model=str(req.body.get("model") or ""), state_dir=req.state_dir)
    return 201, {"slug": p.slug}


def get_models(req):
    from halo_harness.capabilities import best_for
    from halo_harness.studio import model as M
    return 200, best_for(M.model_rows(req.state_dir), "design", limit=12)


def get_project(req):
    p, err = _project(req)
    if err:
        return err
    p.discover_artboards()
    return 200, {"slug": p.slug, "meta": p.meta(), "artboards": p.artboards(), "comments": p.comments(), "system": p.system(),
                 "history": p.history(), "live_turn": turns.live_turn(p.slug)}


def run(req):
    p, err = _project(req)
    if err:
        return err
    prompt = str(req.body.get("prompt") or "").strip()
    if not prompt:
        return _bad("write what to design first")
    try:
        budget = float(req.body["budget"]) if req.body.get("budget") not in (None, "") else None
    except (TypeError, ValueError):
        return _bad("budget is a number of US dollars")
    turn = turns.start(p, prompt, model=str(req.body.get("model") or ""), budget=budget, runner=RUNNER, registered=REGISTERED)
    if turn is None:
        return 409, {"error": "this project already has a turn running: wait for it to finish", "turn": turns.live_turn(p.slug)}
    return 200, {"turn": turn["id"]}


def get_turn(req):
    r = turns.poll(req.params["slug"], req.params["tid"], int(req.query.get("since") or 0))
    return (200, r) if r else (404, {"error": "no such turn"})


def comment(req):
    p, err = _project(req)
    if err:
        return err
    a, err = _artboard(req, p)
    if err:
        return err
    text = str(req.body.get("text") or "").strip()
    if not text:
        return _bad("a comment needs text")
    c = p.add_comment(a["id"], text, x=float(req.body.get("x") or 0), y=float(req.body.get("y") or 0),
                      path=str(req.body.get("path") or ""), version=a["latest"])
    return 201, c


def resolve(req):
    p, err = _project(req)
    if err:
        return err
    ids = req.body.get("ids")
    if not isinstance(ids, list):
        return _bad("ids is a list of comment ids")
    return 200, {"resolved": p.resolve_comments([str(i) for i in ids])}


def control(req):
    p, err = _project(req)
    if err:
        return err
    a, err = _artboard(req, p)
    if err:
        return err
    knob = next((c for c in a["controls"] if c.get("name") == req.body.get("name")), None)
    if knob is None:
        return _bad(f"{a['id']} has no knob named {req.body.get('name')!r}")
    target = str(knob.get("target") or "")
    if not target.startswith("css:"):
        p.set_control(a["id"], knob["name"], req.body.get("value"))
        return 202, {"queued": True}
    page = p.artboard_dir(a["id"]) / "index.html"
    if not page.is_file():
        return _bad(f"{a['id']} has no index.html for {target} to change")
    html = page.read_text(encoding="utf-8")
    try:
        value = C.css_value(html, target[4:], req.body.get("value"), str(knob.get("unit") or ""))
        page.write_text(C.apply_css_control(html, target[4:], value), encoding="utf-8")
    except ValueError as e:
        return _bad(str(e))
    p.set_control(a["id"], knob["name"], req.body.get("value"))
    return 200, {"value": value, "versions": p.snapshot(note=f"knob {knob['name']}")}


_EDIT_SCRIPT = re.compile(r"<!--halo-edit-->.*?<!--/halo-edit-->", re.S)
_EDITABLE = re.compile(r"(<body\b[^>]*?)\s+contenteditable=[\"']?true[\"']?", re.I)


def text_edit(req):
    p, err = _project(req)
    if err:
        return err
    a, err = _artboard(req, p)
    if err:
        return err
    html = req.body.get("html")
    if not isinstance(html, str) or "<" not in html:
        return _bad("html is the edited page")
    html = _EDITABLE.sub(r"\1", _EDIT_SCRIPT.sub("", html))
    if not html.lstrip().lower().startswith("<!doctype"):
        html = "<!doctype html>\n" + html
    page = p.artboard_dir(a["id"]) / "index.html"
    page.write_text(html, encoding="utf-8")
    return 200, {"versions": p.snapshot(note="direct edit")}


_S = r"^(?P<slug>[^/]+)"
ROUTES = [
    ("GET", r"^projects$", list_projects), ("POST", r"^projects$", new_project), ("GET", r"^models$", get_models),
    ("GET", _S + r"$", get_project), ("POST", _S + r"/run$", run), ("GET", _S + r"/turn/(?P<tid>[^/]+)$", get_turn),
    ("POST", _S + r"/comment$", comment), ("POST", _S + r"/comments/resolve$", resolve), ("POST", _S + r"/control$", control),
    ("POST", _S + r"/text-edit$", text_edit), ("PUT", _S + r"/system$", put_system),
    ("GET", _S + r"/artboard/(?P<aid>[^/]+)/versions$", versions), ("POST", _S + r"/artboard/(?P<aid>[^/]+)/restore$", restore),
    ("POST", _S + r"/sync$", sync), ("POST", _S + r"/export$", export), ("POST", _S + r"/handoff$", handoff),
]


def dispatch_design(req):
    rest = req.path[len("design/"):] if req.path.startswith("design/") else ""
    for method, pattern, fn in ROUTES:
        m = re.match(pattern, rest)
        if m and method == req.method:
            req.params = m.groupdict()
            return fn(req)
    if any(re.match(p, rest) for _, p, _ in ROUTES):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
