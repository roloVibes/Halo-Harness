"""halo_harness.studio.field_help_api -- `GET /api/field-help` (Halo 3.1.1.0 R3):
the one plain line per field that Studio's bio form and lineup inspector show
under each control. The lines are `halo_harness/field_help.py`'s, the same
the TUI's read-only bio and lineup views show: Studio serves them, the bundle
carries no copy.

    GET field-help   {identity, bio, lineup_sections, lineup_fields, assignment}
"""

from __future__ import annotations


def dispatch_field_help(req):
    if req.path != "field-help":
        return 404, {"error": f"no route for {req.method} /api/{req.path}"}
    if req.method != "GET":
        return 405, {"error": "/api/field-help answers GET"}
    from halo_harness.field_help import as_json
    return 200, as_json()
