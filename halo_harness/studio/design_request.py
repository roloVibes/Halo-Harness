"""halo_harness.studio.design_request -- the request lookups every Design
route shares (Halo 3.0.1.0 round D3; 3.1.0.0 R2 cut it out of
design_api_io.py): the 422 answer, the project and artboard a request names,
and the pins and history rows as the page receives them (numbers stay
numbers, whatever a file on disk holds).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from halo_harness.design.store import Project

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _bad(lines, status: int = 422):
    lines = [lines] if isinstance(lines, str) else list(lines)
    return status, {"error": lines[0], "problems": lines}


def _num(v, default=0.0):
    """A finite number from a file-derived value, else `default` (a string never reaches the page's markup)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")):
        return default
    return v


def clean_comments(rows) -> list:
    """Pins as the page receives them: x, y and version are always numbers."""
    out = []
    for c in rows if isinstance(rows, list) else []:
        if isinstance(c, dict):
            out.append({**c, "x": _num(c.get("x")), "y": _num(c.get("y")), "version": int(_num(c.get("version"), 0))})
    return out


def clean_history(rows) -> list:
    """History rows as the page receives them: tool_calls is a number or absent, elapsed and cost are numbers or null."""
    out = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        r = dict(r)
        if "tool_calls" in r:
            r["tool_calls"] = int(_num(r["tool_calls"], 0)) if _num(r["tool_calls"], None) is not None else None
        for k in ("elapsed", "cost"):
            if k in r:
                r[k] = _num(r[k], None)
        out.append(r)
    return out


def _project(req):
    slug = req.params.get("slug", "")
    p = Project.open(slug, state_dir=req.state_dir) if _SLUG.match(slug) else None
    return p, ((404, {"error": f"no design project named {slug!r}"}) if p is None else None)


def _artboard(req, p):
    aid = str(req.body.get("artboard") or req.params.get("aid") or "")
    hit = next((a for a in p.artboards() if a["id"] == aid), None)
    return hit, (None if hit else (404, {"error": f"no artboard {aid!r} in {p.slug}"}))


def _json_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
