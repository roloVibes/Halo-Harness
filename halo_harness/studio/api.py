"""halo_harness.studio.api -- Studio's JSON routes (Halo 2.1.0 round B3; 3.6.0.0 R5: the lineup, layout, bio, validate,
yaml, state, session and tools routes went with Cast; agents, workflows and maps are studio/crew_api.py's).

Every handler takes a `Request` and returns `(status, body)`. The table here holds the model catalog's routes (models,
models/*: studio/models_api.py, model_card_api.py, roles_api.py), a pack canvas's layout and doctor/config; every other area is a prefix
(`_PREFIXES`: one `*_api.py` each).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

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
    owner: bool = False  # 3.4.1.2: the request carried the owner proof (studio/owner_proof.py `owner_only`)

    @property
    def project(self) -> bool:
        return self.query.get("scope") == "project"

def _problems(lines: list, status: int = 422):
    return status, {"error": lines[0] if lines else "invalid", "problems": list(lines)}


# -- canvas layouts (a pack's canvas: `<pack id>:<name>`, the design pack's artboards) -------------------------------

# 3.0.7.0 R3: design:<slug> too; 3.3.13.0 R2: <pack id>:<name> (the design pack keeps design:<project slug>)
_LAYOUT_NAME = re.compile(r"^((pc|[a-z][a-z0-9-]*):)?[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _layout_name_problem(name: str):
    return None if _LAYOUT_NAME.match(name) else _problems([f"{name!r} is not a valid layout name (<pack id>:<name>)"])


def get_layout(req: Request):
    return _layout_name_problem(req.params["name"]) or (200, M.legacy_layout_view(M.read_layout(req.state_dir, req.params["name"])))


def _layout_parts(body: dict):
    """`(positions, tiers)` from a layout body (`{positions}` or the {nodes, tiers} shape), or the 422 answer."""
    positions = body.get("positions")
    if positions is None and isinstance(body.get("nodes"), dict):  # 3.0.7.0 R1: the new {nodes, tiers} shape
        positions = body.get("nodes")
    if not isinstance(positions, dict):
        return _problems(["positions must be a mapping of node id -> {x, y}"])
    tiers = body.get("tiers")
    if tiers is not None and not isinstance(tiers, dict):
        return _problems(["tiers must be a mapping of tier name -> {collapsed: true|false}"])
    return positions, tiers


def put_layout(req: Request):
    bad = _layout_name_problem(req.params["name"])
    if bad:
        return bad
    parts = _layout_parts(req.body)
    if isinstance(parts[0], int):
        return parts
    M.write_layout(req.state_dir, req.params["name"], parts[0], tiers=parts[1])
    return 200, {"ok": True}


# -- models ---------------------------------------------------------------------------

def get_models(req: Request):
    return 200, M.model_rows(req.state_dir, req.cwd)  # 3.1.4.0 R4: the session's provider resolution


ROUTES: list = [("GET", r"^models$", get_models),  # the layout: a pack canvas's card places (studio/packlib scoped)
                ("GET", r"^layout/(?P<name>[^/]+)$", get_layout), ("PUT", r"^layout/(?P<name>[^/]+)$", put_layout)]

from .models_api import ROUTES as _MODELS_ROUTES  # noqa: E402  (3.0.4.0: models/status, models/refresh)
ROUTES[len(ROUTES):] = _MODELS_ROUTES
from .model_card_api import ROUTES as _CARD_ROUTES  # noqa: E402  (3.3.5.0 R0b: models/card, lane, effort, think)
ROUTES[len(ROUTES):] = _CARD_ROUTES
from .roles_api import ROUTES as _ROLES_ROUTES  # noqa: E402  (3.0.7.0 R2: gym, models/best-for)
ROUTES[len(ROUTES):] = _ROLES_ROUTES
from .doctor_config_api import ROUTES as _DOCTOR_CONFIG_ROUTES  # noqa: E402  (3.1.1.0 R2: doctor/config)
ROUTES[len(ROUTES):] = _DOCTOR_CONFIG_ROUTES

_PREFIXES = (("media", "halo_harness.studio.media_api", "dispatch_media"),
             ("sessions", "halo_harness.studio.sessions_api", "dispatch_sessions"),
             ("live", "halo_harness.studio.live_api", "dispatch_live"),  # 3.0.5.0 R2; 3.5.0.0: this machine's sessions live
             ("glossary", "halo_harness.studio.glossary_api", "dispatch_glossary"),  # 3.1.1.0 R1: docs/GLOSSARY.md
             ("field-help", "halo_harness.studio.field_help_api", "dispatch_field_help"),  # 3.1.1.0 R3: field_help.py
             ("focus", "halo_harness.studio.focus_api", "dispatch_focus"),  # 3.1.1.0 R3: `halo studio --edit` on a running one
             ("recall", "halo_harness.studio.recall_api", "dispatch_recall"),  # 3.1.2.0 R3: the recall box
             ("supervise", "halo_harness.studio.supervise_api", "dispatch_supervise"),  # 3.1.8.0 R1: the morning line
             ("pack", "halo_harness.studio.packs_studio_api", "dispatch_pack"),  # 3.2.0.0 R3: Studio contributions
             ("packs", "halo_harness.studio.packs_routes", "dispatch"),  # 3.3.13.0 R2: a pack's own routes (API 1.2)
             ("glance", "halo_harness.studio.glance_door", "dispatch_glance"),  # 3.4.1.0 R4
             ("crew", "halo_harness.studio.crew_api", "dispatch_crew"),  # 3.6.0.0 R1: the Agents tab (crew/ files, Try it)
             ("builder", "halo_harness.studio.builder_api", "dispatch_builder"),  # 3.6.0.0 R1: the builder box
             ("setup", "halo_harness.studio.setup_api", "dispatch_setup"),  # 3.3.0.0 R1: the Setup section
             ("settings", "halo_harness.studio.settings_api", "dispatch_settings"),  # 3.3.3.0 R2: the Settings section
             ("ollama", "halo_harness.studio.ollama_steward_api", "dispatch_ollama"),  # 3.3.4.0 R5: the steward's panel
             ("local", "halo_harness.studio.local_api", "dispatch_local"),  # 3.3.5.0 R1: the Local section
             ("studio", "halo_harness.studio.timings", "dispatch_studio"))  # 3.6.0.0 R14: GET studio/timings


def dispatch(req: Request):
    """Route `req` (path without the /api/ prefix) to its handler."""
    from halo_harness.studio.work_api import dispatch_work  # 3.1.2.0 R1: the shared unit view (docs/WORK.md)
    worked = dispatch_work(req)
    if worked is not None:
        return worked
    if req.path == "orchestra" or req.path.startswith("orchestra/"):  # 3.0.3.0: the Orchestra run console
        from halo_harness.studio.orchestra_api import dispatch_orchestra
        return dispatch_orchestra(req)
    for prefix, module, fn in _PREFIXES:  # 3.0.4.0: ComfyUI media, the live sessions
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
