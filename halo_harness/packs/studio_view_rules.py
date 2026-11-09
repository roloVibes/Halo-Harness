"""halo_harness.packs.studio_view_rules -- the two Studio contributions of extension API 1.2 (Halo 3.3.13.0 R2,
docs/EXTENSION_API.md "Studio contributions"): a section drawn whole by one bundle, and the pack's own API routes.

    contributes.studio.sections[].view: {bundle: studio/page.js}    # mount(el, api): el is the section's whole page
    contributes.studio.routes: {module: server/routes.py, prefix: design}

The meaning, checked with the manifest (packs/studio_rules.py calls `check`), one line each:

- a view's `bundle` is an ES module (`.js` / `.mjs`) inside the pack's folder; it runs the pack's script, so it needs
  the `studio-script` permission requested; a section with a view draws its page itself, so it lists no panels;
- the routes' `module` is a `.py` file inside the pack's folder, its `prefix` a word (`^[a-z][a-z0-9-]*$`, the
  `/api/packs/<id>/<prefix>/` it answers under); it runs the pack's Python inside Studio's server, so it needs the
  `studio-routes` permission requested.

    view_of(section)         # the view's bundle path, or ""
    view_sections(manifest)  # the ids of the sections with a view
    routes_of(manifest)      # {module, prefix} or {}
"""

from __future__ import annotations

import re
from pathlib import Path

ROUTES = "studio-routes"
PREFIX_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def view_of(section) -> str:
    view = section.get("view") if isinstance(section, dict) else None
    src = view.get("bundle") if isinstance(view, dict) else None
    return src if isinstance(src, str) else ""


def view_sections(manifest) -> "list[str]":
    from halo_harness.packs.studio_rules import sections_of
    return [str(s.get("id")) for s in sections_of(manifest) if s.get("view") is not None]


def routes_of(manifest) -> dict:
    from halo_harness.packs.studio_rules import studio_of
    r = studio_of(manifest).get("routes")
    return r if isinstance(r, dict) else {}


def doctor_rows(pack) -> "list[dict]":
    """The routes module's last failure (studio/packs_routes.py keeps it in the pack's data folder) as a doctor row."""
    if not routes_of(pack.manifest):
        return []
    import json
    from halo_harness.ext.files import data_dir
    path = Path(data_dir(pack.id)) / ".studio-routes.json"
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [{"severity": "warns", "check": "studio-routes", "path": path,
             "text": f"{pack.id}: its Studio routes failed at {got.get('at')}: {got.get('error')}",
             "fix": "fix the routes module; Studio imports it again on its next request"}] if isinstance(got, dict) else []


def _inside(root, rel: str) -> str:
    """'' when `rel` is a file inside the pack's folder; else the problem's words."""
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or rel.startswith(("/", "\\")) or ":" in p.as_posix().split("/")[0]:
        return "is outside the pack's folder (a path inside it)"
    if root is None:
        return ""
    base = Path(root).resolve()
    target = (base / p).resolve()
    if base not in target.parents:
        return "is outside the pack's folder"
    return "" if target.is_file() else "is not in the pack"


def check(L, manifest, root) -> None:
    from halo_harness.packs import studio_rules as R
    asked = R._list(manifest, "permissions")
    for i, s in enumerate(R._list(R.studio_of(manifest), "sections")):
        if not isinstance(s, dict) or s.get("view") is None:
            continue
        key = f"contributes.studio.sections[{i}].view"
        src = view_of(s)
        if not src.strip():
            L.add(key, ": {bundle: <a .js or .mjs file of the pack>} (the module that draws the section's page)", "view")
            continue
        if Path(src).suffix.lower() not in R.SUFFIXES["bundle"]:
            L.add(f"{key}.bundle", f" {src!r}: a view's bundle is a .js or .mjs file", "bundle", src)
        elif _inside(root, src):
            L.add(f"{key}.bundle", f" {src!r} {_inside(root, src)}", "bundle", src)
        if R.SCRIPT not in asked:
            L.add(key, f": a view runs the pack's script, which needs the {R.SCRIPT!r} permission in pack.yaml's "
                  "permissions (you grant it with halo pack enable <id> --grant studio-script)", "view")
        if R._list(s, "panels"):
            L.add(f"contributes.studio.sections[{i}].panels", ": a section with a view draws its page itself; "
                  "its panels would never show (take them out, or drop the view)", "panels")
    routes = R.studio_of(manifest).get("routes")
    if routes is None:
        return
    if not isinstance(routes, dict):
        L.add("contributes.studio.routes", ": {module: <a .py file of the pack>, prefix: <word>}", "routes")
        return
    mod, prefix = routes.get("module"), routes.get("prefix")
    if not isinstance(mod, str) or not mod.endswith(".py"):
        L.add("contributes.studio.routes.module", f" {mod!r}: the routes module is a .py file of the pack", "module", mod)
    elif _inside(root, mod):
        L.add("contributes.studio.routes.module", f" {mod!r} {_inside(root, mod)}", "module", mod)
    if not isinstance(prefix, str) or not PREFIX_RE.match(prefix):
        L.add("contributes.studio.routes.prefix", f" {prefix!r} is not a word (lower-case letters, digits and -): "
              "the routes answer under /api/packs/<id>/<prefix>/", "prefix", prefix)
    if ROUTES not in asked:
        L.add("contributes.studio.routes", f": the routes run the pack's Python inside Studio's server, which needs the "
              f"{ROUTES!r} permission in pack.yaml's permissions (you grant it with halo pack enable <id> --grant "
              f"{ROUTES})", "routes")
