"""The design pack's server/api.py (was halo_harness.studio.design_api) -- the Design section's backend (Halo
3.0.1.0 round D3; the design pack since 3.3.13.0 R2): the pack's routes (`/api/packs/design/design/...`, routes.py)
over the projects (store.py): artboards, turns, comments, knobs, direct text edits, versions, the design system,
exports, the handoff; 3.0.7.0 R3: artboard rename / delete, cancel a turn, every turn on the live feed (the pack's
`pack_live` frames of kind `turn`); 3.1.4.0 R4: the project's model, `PUT <slug>/model`. Behind Studio's token
like every route. `RUNNER` replaces the turn's subprocess (tests set it); `REGISTERED` pins the craft apps a turn
may use (None = the user's config).

The routes of one artboard are artboards_api.py, the assets folder assets_api.py, variants and the critique
critique_api.py, the design system system_api.py, exports and the handoff export_api.py; the shared lookups are
request.py and the live turns turns.py.
"""

from __future__ import annotations

import re

from . import controls as C
from .store import Project
from . import artboards_api as artboards
from . import assets_api as assets
from . import critique_api as critiques
from . import turns as turns
from .export_api import export, handoff
from .request import _artboard, _bad, _project, clean_comments, clean_history
from .system_api import put_system, sync

RUNNER = None
REGISTERED = None


def list_projects(req):
    return 200, {"projects": Project.list(state_dir=req.state_dir)}


def new_project(req):
    name = str(req.body.get("name") or "").strip()
    if not name:
        return _bad("a project needs a name")
    from halo_harness.ext import get_config  # the pack's settings: the model a new project starts with
    model = str(req.body.get("model") or get_config("design", "model", "") or "")
    p = Project.create(name, model=model, state_dir=req.state_dir)
    return 201, {"slug": p.slug}


def put_model(req):
    """3.1.4.0 R4: `PUT <slug>/model {model}` -- the project's model (the
    Projects panel's model select); empty: the default model."""
    p, err = _project(req)
    if err:
        return err
    model = req.body.get("model")
    if model is not None and not isinstance(model, str):
        return _bad("model is a model ref, or empty for the default model")
    meta = p._meta_for_write()
    meta["model"] = str(model or "").strip()
    p.save_meta(meta)
    return 200, {"slug": p.slug, "model": meta["model"]}


def get_models(req):
    from halo_harness.ext import host
    if str(req.query.get("media") or "") in ("1", "true"):
        # the ComfyUI media models (cached inventory, by what each produces): a group of their own in the chooser
        return 200, {"media": host.media_models("all")}
    return 200, host.models("design", cwd=getattr(req, "cwd", None), limit=12)


def get_project(req):
    p, err = _project(req)
    if err:
        return err
    p.discover_artboards()
    return 200, {"slug": p.slug, "meta": p.meta(), "artboards": p.artboards(), "comments": clean_comments(p.comments()), "system": p.system(),
                 "history": clean_history(p.history()), "live_turn": turns.live_turn(p.slug)}


def run(req):
    p, err = _project(req)
    if err:
        return err
    prompt = str(req.body.get("prompt") or "").strip()
    if not prompt:
        return _bad("write what to design first")
    prompt, err = critiques.variants_of(prompt, req.body)
    if err:
        return err
    from halo_harness.ext import get_config  # the pack's settings: a turn's cap when the request names none
    try:
        budget = float(req.body["budget"]) if req.body.get("budget") not in (None, "") else None
        budget = budget if budget is not None else (float(get_config("design", "budget_usd", 0) or 0) or None)
    except (TypeError, ValueError):
        return _bad("budget is a number of US dollars")
    turn = turns.start(p, prompt, model=str(req.body.get("model") or ""), budget=budget, runner=RUNNER, registered=REGISTERED,
                       publish=feed_of(req))
    if turn is None:
        return 409, {"error": "this project already has a turn running: wait for it to finish", "turn": turns.live_turn(p.slug)}
    return 200, {"turn": turn["id"]}


def feed_of(req):
    """A turn step onto the live feed: the pack's `pack_live` frame of kind `turn`, its data the step (None without
    a feed: the poll still works)."""
    publish = getattr(req, "publish", None)
    if publish is None:
        return None
    return lambda frame: publish("turn", frame.get("data"))


def get_turn(req):
    r = turns.poll(req.params["slug"], req.params["tid"], int(req.query.get("since") or 0))
    return (200, r) if r else (404, {"error": "no such turn"})


def turn_cancel(req):
    """POST turn/<tid>/cancel: stop the running turn."""
    return turns.cancel(req.params["slug"], req.params["tid"])


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
    ("POST", _S + r"/text-edit$", text_edit), ("PUT", _S + r"/system$", put_system), ("PUT", _S + r"/model$", put_model),
    ("GET", _S + r"/artboard/(?P<aid>[^/]+)/versions$", artboards.versions),
    ("POST", _S + r"/artboard/(?P<aid>[^/]+)/restore$", artboards.restore),
    ("POST", _S + r"/critique$", critiques.critique), ("GET", _S + r"/artboard/(?P<aid>[^/]+)/contrast$", artboards.contrast),
    ("GET", _S + r"/assets$", assets.assets_list), ("POST", _S + r"/assets$", assets.assets_post),
    ("POST", _S + r"/sync$", sync), ("POST", _S + r"/export$", export), ("POST", _S + r"/handoff$", handoff),
    ("POST", _S + r"/artboard/(?P<aid>[^/]+)/rename$", artboards.artboard_rename),
    ("DELETE", _S + r"/artboard/(?P<aid>[^/]+)$", artboards.artboard_delete),
    ("POST", _S + r"/turn/(?P<tid>[^/]+)/cancel$", turn_cancel),
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
