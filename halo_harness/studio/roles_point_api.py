"""halo_harness.studio.roles_point_api -- Halo 3.3.7.0 R4: "point the role at it" (ollama_steward/dead_tag.point).

    POST roles/<role>/point {to}    roles.<role> in config.json -> `to` (its effort kept): the role write and nothing
                                    else -- nothing is pulled, nothing loads; {ok, line, from, to}
The dead-tag line (a role on a deleted tag, its nearest equivalent) and the roster adviser's point suggestions send it.
"""

from __future__ import annotations

from .api import Request


def post_point(req: Request):
    from halo_harness.ollama_steward.dead_tag import point
    from halo_harness.roles import is_role_name_syntax
    role = str(req.params.get("role") or "")
    to = str((req.body or {}).get("to") or "").strip() if isinstance(req.body, dict) else ""
    if not is_role_name_syntax(role):
        return 422, {"error": f"{role!r} is not a role name", "problems": [role]}
    if not to:
        return 422, {"error": "point takes {to: <model ref>}", "problems": ["to"]}
    got = point(role, to)
    return (200 if got["ok"] else 422), (got if got["ok"] else {"error": got["line"], **got})


ROUTES: list = [("POST", r"^roles/(?P<role>[a-z][a-z0-9_]*)/point$", post_point)]
