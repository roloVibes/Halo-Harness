"""halo_harness.studio.api -- Studio's JSON routes (Halo 2.1.0 round B3).

Every handler takes a `Request` and returns `(status, body)`. Writes
validate through `teams_yaml` / `agents_yaml` first and answer 422 with the
validator's own lines; shipped (template-scope) files are read-only and
answer 409 with "duplicate to edit". Scope is `?scope=user|project`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from halo_harness import agents_yaml as A
from halo_harness import teams_yaml as T
from halo_harness.studio import model as M


@dataclass
class Request:
    method: str
    path: str
    query: dict
    body: dict
    cwd: Path
    state_dir: Path
    params: dict = field(default_factory=dict)
    server: object = None  # 3.0.3.0: the HTTP server (its live-feed bridge), None outside one

    @property
    def project(self) -> bool:
        return self.query.get("scope") == "project"


def _active_team() -> str:
    from halo_harness.theme import get_config_value
    return str(get_config_value("team", "") or "")


def _problems(lines: list, status: int = 422):
    return status, {"error": lines[0] if lines else "invalid", "problems": list(lines)}


# -- state ---------------------------------------------------------------------

def get_state(req: Request):
    from halo_harness import __version__
    from halo_harness.roles import roles_mode_enabled
    from halo_harness.theme import get_config_value
    return 200, {"version": __version__, "active_team": _active_team(), "roles_enabled": bool(roles_mode_enabled()),
                 "default_model": str(get_config_value("model", "") or ""), "cwd": str(req.cwd),
                 "state_dir": str(req.state_dir), "shipped_lineups": T.list_bundled_team_templates(),
                 "shipped_bios": A.list_bundled_agent_templates(), "top_sections": list(T.TOP_SECTIONS)}


# -- lineups --------------------------------------------------------------------

def get_lineups(req: Request):
    active = _active_team()
    names = T.list_team_templates(cwd=req.cwd, state_dir=req.state_dir)
    rows = [M.lineup_summary(n, cwd=req.cwd, state_dir=req.state_dir, active=active) for n in names]
    return 200, [r for r in rows if r]


def get_lineup(req: Request):
    data = M.lineup_payload(req.params["name"], cwd=req.cwd, state_dir=req.state_dir, active=_active_team())
    if data is None:
        return 404, {"error": f"no lineup named {req.params['name']!r}"}
    from .roles_findings import findings_for  # 3.0.7.0 R2: the Problems panel's list on open
    data["findings"] = findings_for(data["raw"], problems=data["problems"], graph=data["graph"], cwd=req.cwd, state_dir=req.state_dir)
    data["layout"] = M.legacy_layout_view(M.read_layout(req.state_dir, req.params["name"]))
    return 200, data


def _incoming(req: Request):
    if "yaml" in req.body:
        try:
            return M.from_yaml(str(req.body.get("yaml") or ""))
        except Exception as e:  # yaml errors carry their own message
            return _problems([f"YAML: {e}"])
    raw = req.body.get("raw")
    if not isinstance(raw, dict):
        return _problems(["the body needs a 'raw' mapping or a 'yaml' string"])
    return raw


def put_lineup(req: Request):
    name = req.params["name"]
    raw = _incoming(req)
    if isinstance(raw, tuple):
        return raw
    found = T.find_team_template_path(name, cwd=req.cwd, state_dir=req.state_dir)
    if found and found[1] == "template" and not req.query.get("duplicate"):
        return 409, {"error": f"{name} is a shipped lineup: duplicate to edit", "problems": []}
    raw = M.clean(raw)
    raw["name"] = name
    problems = T.validate_team_template(raw, name=name, cwd=req.cwd, state_dir=req.state_dir)
    if problems:
        return _problems(problems)
    ok, saved = T.save_team_template(name, raw, cwd=req.cwd, state_dir=req.state_dir, project=req.project)
    if not ok:
        return _problems(saved or ["save failed"], 500)
    return get_lineup(req)


def post_lineup(req: Request):
    name = str(req.body.get("name") or "").strip()
    if not T.is_valid_team_name(name):
        return _problems([f"{name!r} is not a valid lineup name (letters, digits, - and _)"])
    ok, problems = T.new_team_template_from_template(name, req.body.get("from") or None, cwd=req.cwd,
                                                     state_dir=req.state_dir, project=req.project)
    if not ok:
        return _problems(problems or ["could not create the lineup"])
    req.params["name"] = name
    status, data = get_lineup(req)
    return (201 if status == 200 else status), data


def delete_lineup(req: Request):
    name = req.params["name"]
    if not T.is_valid_team_name(name):
        return _problems([f"{name!r} is not a valid lineup name (letters, digits, - and _)"])
    found = T.find_team_template_path(name, cwd=req.cwd, state_dir=req.state_dir)
    if found and found[1] == "template":
        return 409, {"error": "a shipped lineup cannot be deleted"}
    return (200, {"ok": True}) if T.delete_team_template(name, cwd=req.cwd, state_dir=req.state_dir, project=req.project) else (404, {"error": "not found"})


def apply_lineup(req: Request):
    name = req.params["name"]
    ok, problems, notes = T.apply_team_template(name, cwd=req.cwd, state_dir=req.state_dir)
    if not ok:
        return _problems(problems or ["apply failed"])
    from halo_harness.roles import set_roles_enabled
    set_roles_enabled(True)
    return 200, {"ok": True, "notes": list(notes), "active_team": _active_team()}


_LAYOUT_NAME = re.compile(r"^((pc|design):)?[A-Za-z0-9][A-Za-z0-9_.-]*$")  # 3.0.7.0 R3: design:<slug> too


def _layout_name_problem(name: str):
    return None if _LAYOUT_NAME.match(name) else _problems([f"{name!r} is not a valid layout name (a lineup name, pc:<company id> or design:<project slug>)"])


def get_layout(req: Request):
    return _layout_name_problem(req.params["name"]) or (200, M.legacy_layout_view(M.read_layout(req.state_dir, req.params["name"])))


def put_layout(req: Request):
    bad = _layout_name_problem(req.params["name"])
    if bad:
        return bad
    positions = req.body.get("positions")
    if positions is None and isinstance(req.body.get("nodes"), dict):  # 3.0.7.0 R1: the new {nodes, tiers} shape
        positions = req.body.get("nodes")
    if not isinstance(positions, dict):
        return _problems(["positions must be a mapping of node id -> {x, y}"])
    tiers = req.body.get("tiers")
    if tiers is not None and not isinstance(tiers, dict):
        return _problems(["tiers must be a mapping of tier name -> {collapsed: true|false}"])
    M.write_layout(req.state_dir, req.params["name"], positions, tiers=tiers)
    return 200, {"ok": True}


# -- bios -------------------------------------------------------------------------

def get_bios(req: Request):
    rows = [M.bio_summary(n, cwd=req.cwd, state_dir=req.state_dir) for n in A.list_agent_bios(cwd=req.cwd, state_dir=req.state_dir)]
    return 200, [r for r in rows if r]


def get_bio(req: Request):
    data = M.bio_payload(req.params["name"], cwd=req.cwd, state_dir=req.state_dir)
    return (200, data) if data else (404, {"error": f"no agent bio named {req.params['name']!r}"})


def put_bio(req: Request):
    name = req.params["name"]
    raw = _incoming(req)
    if isinstance(raw, tuple):
        return raw
    found = A.find_agent_bio_path(name, cwd=req.cwd, state_dir=req.state_dir)
    if found and found[1] == "template" and not req.query.get("duplicate"):
        return 409, {"error": f"{name} is a shipped bio: duplicate to edit", "problems": []}
    raw = M.clean(raw)
    raw["name"] = name
    problems = A.validate_agent_bio(raw, name=name, cwd=req.cwd, state_dir=req.state_dir)
    if problems:
        return _problems(problems)
    ok, saved = A.save_agent_bio(name, raw, cwd=req.cwd, state_dir=req.state_dir, project=req.project)
    if not ok:
        return _problems(saved or ["save failed"], 500)
    return get_bio(req)


def post_bio(req: Request):
    name = str(req.body.get("name") or "").strip()
    if not A.is_valid_agent_name(name):
        return _problems([f"{name!r} is not a valid agent name (letters, digits, - and _)"])
    ok, problems = A.new_agent_bio_from_template(name, req.body.get("from") or None, cwd=req.cwd,
                                                 state_dir=req.state_dir, project=req.project)
    if not ok:
        return _problems(problems or ["could not create the bio"])
    req.params["name"] = name
    status, data = get_bio(req)
    return (201 if status == 200 else status), data


def delete_bio(req: Request):
    if not A.is_valid_agent_name(req.params["name"]):
        return _problems([f"{req.params['name']!r} is not a valid bio name (letters, digits, - and _)"])
    found = A.find_agent_bio_path(req.params["name"], cwd=req.cwd, state_dir=req.state_dir)
    if found and found[1] == "template":
        return 409, {"error": "a shipped bio cannot be deleted"}
    return (200, {"ok": True}) if A.delete_agent_bio(req.params["name"], cwd=req.cwd, state_dir=req.state_dir, project=req.project) else (404, {"error": "not found"})


# -- models, validation, yaml, session ----------------------------------------------

def get_models(req: Request):
    return 200, M.model_rows(req.state_dir)


def post_validate(req: Request):
    raw = _incoming(req)
    if isinstance(raw, tuple):
        return raw
    raw = M.clean(raw)
    name = str(req.body.get("name") or raw.get("name") or "")
    if req.body.get("kind") == "bio":
        return 200, {"problems": A.validate_agent_bio(raw, name=name or None, cwd=req.cwd, state_dir=req.state_dir)}
    problems = T.validate_team_template(raw, name=name or None, cwd=req.cwd, state_dir=req.state_dir)
    from .roles_findings import findings_for, resolve_raw  # 3.0.7.0 R2: the Problems panel's list
    graph = M.graph_for(resolve_raw(raw, cwd=req.cwd, state_dir=req.state_dir), cwd=req.cwd, state_dir=req.state_dir)
    return 200, {"problems": problems, "graph": graph,
                 "findings": findings_for(raw, problems=problems, graph=graph, cwd=req.cwd, state_dir=req.state_dir)}


def post_yaml(req: Request):
    if "yaml" in req.body:
        try:
            return 200, {"raw": M.from_yaml(str(req.body.get("yaml") or ""))}
        except Exception as e:
            return _problems([f"YAML: {e}"])
    return 200, {"yaml": M.to_yaml(req.body.get("raw") or {})}


def get_session(req: Request):
    return 200, M.session_payload(req.state_dir)


def get_tools(req: Request):
    """The real registry's names (`tools.registry.known_tool_names`)."""
    from halo_harness.tools.registry import known_tool_names
    return 200, known_tool_names()


ROUTES: list = [
    ("GET", r"^state$", get_state),
    ("GET", r"^lineups$", get_lineups), ("POST", r"^lineup$", post_lineup),
    ("GET", r"^lineup/(?P<name>[^/]+)$", get_lineup), ("PUT", r"^lineup/(?P<name>[^/]+)$", put_lineup),
    ("DELETE", r"^lineup/(?P<name>[^/]+)$", delete_lineup), ("POST", r"^lineup/(?P<name>[^/]+)/apply$", apply_lineup),
    ("GET", r"^layout/(?P<name>[^/]+)$", get_layout), ("PUT", r"^layout/(?P<name>[^/]+)$", put_layout),
    ("GET", r"^bios$", get_bios), ("POST", r"^bio$", post_bio),
    ("GET", r"^bio/(?P<name>[^/]+)$", get_bio), ("PUT", r"^bio/(?P<name>[^/]+)$", put_bio), ("DELETE", r"^bio/(?P<name>[^/]+)$", delete_bio),
    ("GET", r"^models$", get_models), ("POST", r"^validate$", post_validate), ("POST", r"^yaml$", post_yaml),
    ("GET", r"^session$", get_session), ("GET", r"^tools$", get_tools),
]

from .models_api import ROUTES as _MODELS_ROUTES  # noqa: E402  (3.0.4.0: models/status, models/refresh)
ROUTES[len(ROUTES):] = _MODELS_ROUTES
from .roles_api import ROUTES as _ROLES_ROUTES  # noqa: E402  (3.0.7.0 R2: gym, models/best-for)
ROUTES[len(ROUTES):] = _ROLES_ROUTES
from .doctor_config_api import ROUTES as _DOCTOR_CONFIG_ROUTES  # noqa: E402  (3.1.1.0 R2: doctor/config)
ROUTES[len(ROUTES):] = _DOCTOR_CONFIG_ROUTES


_PREFIXES = (("flow", "halo_harness.studio.flow_api", "dispatch_flow"),
             ("media", "halo_harness.studio.media_api", "dispatch_media"),
             ("sessions", "halo_harness.studio.sessions_api", "dispatch_sessions"),
             ("fleet", "halo_harness.studio.fleet_hub_api", "dispatch_fleet"),  # 3.0.5.0 R2: the hub's view
             ("team", "halo_harness.studio.team_api", "dispatch_team"))  # 3.0.8.0 R1: the Team (docs/TEAM.md)


def dispatch(req: Request):
    """Route `req` (path without the /api/ prefix) to its handler."""
    from halo_harness.studio.coach_api import dispatch_coach  # 3.0.9.0 R3: the post-run coach's four routes
    coached = dispatch_coach(req)
    if coached is not None:
        return coached
    if req.path == "pc" or req.path.startswith("pc/"):  # 2.2.0: Org mode (Paperclip) routes
        from halo_harness.studio.paperclip_api import dispatch_pc
        return dispatch_pc(req)
    if req.path == "design" or req.path.startswith("design/"):  # 3.0.1.0: Design mode routes
        from halo_harness.studio.design_api import dispatch_design
        return dispatch_design(req)
    if req.path == "orchestra" or req.path.startswith("orchestra/"):  # 3.0.3.0: the Orchestra run console
        from halo_harness.studio.orchestra_api import dispatch_orchestra
        return dispatch_orchestra(req)
    for prefix, module, fn in _PREFIXES:  # 3.0.4.0: flows, ComfyUI media, the live sessions
        if req.path == prefix or req.path.startswith(prefix + "/"):
            import importlib
            return getattr(importlib.import_module(module), fn)(req)
    for method, pattern, fn in ROUTES:
        m = re.match(pattern, req.path)
        if m and method == req.method:
            req.params = {k: v for k, v in m.groupdict().items()}
            return fn(req)
    if any(re.match(p, req.path) for _, p, _ in ROUTES):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
