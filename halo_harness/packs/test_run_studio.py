"""halo_harness.packs.test_run_studio -- `halo pack test`'s checks of the extension API 1.2 parts (Halo 3.3.13.0 R2):
a section's view, the pack's own Studio routes, and the pack's own test modules.

- `views`: each section's `view.bundle` is in the pack and reads as an ES module that exports `mount(el, api)`.
- `routes`: the routes module imports through the pack's folder (the package `halo_packs.<id>`, as Studio imports it)
  and `handle(ctx, "GET", "ping", {}, {})` answers in shape -- `(status, json)` or `(status, bytes | str, type[,
  headers])`, a status below 500 -- with a ctx like Studio's (the scratch home's folders, a `publish` that keeps the
  frames).
- `own_tests`: each `tests/test_*.py` of the pack runs as `python -m tests.<name>` from the pack's folder, in a fresh
  scratch home of its own, and passes on exit 0 (only when no `--kinds` narrows the run: they may take a while).
"""

from __future__ import annotations

import os
from halo_harness import subprocess_safe as subprocess
import sys
import tempfile
import types
from pathlib import Path

OWN_TIMEOUT_S = 600


def views(r) -> None:
    from halo_harness.packs.studio_rules import sections_of
    from halo_harness.packs.studio_view_rules import view_of
    for s in sections_of(r.manifest) if r.wants("studio") else []:
        src = view_of(s)
        if not src:
            continue
        path = r.root / src
        r.add("studio", src, f"section {s.get('id')}'s view has its module", path.is_file(), "the file is in the pack")
        if path.is_file():
            from halo_harness.packs.test_run_proc import es_module_lines
            lines = es_module_lines(path, r.timeout)
            r.add("studio", src, "the view is an ES module that exports mount(el, api)", not lines, "; ".join(lines))


def _shape(out) -> str:
    """'' when `out` is what handle answers; else what is wrong."""
    if not isinstance(out, tuple) or not 2 <= len(out) <= 4 or not isinstance(out[0], int):
        return f"it answered {type(out).__name__}; handle answers (status, json | bytes, content_type?)"
    if out[0] >= 500:
        return f"it answered {out[0]}: {out[1]!r}"[:300]
    if isinstance(out[1], (bytes, str)) and len(out) < 3:
        return "bytes or text need a content type: (status, body, content_type)"
    if not isinstance(out[1], (dict, list, bytes, str)):
        return f"the body is {type(out[1]).__name__}: a dict or a list (JSON), or bytes with a content type"
    return ""


def routes(r) -> None:
    from halo_harness.packs.studio_view_rules import routes_of
    rt = routes_of(r.manifest) if r.wants("studio") else {}
    if not rt:
        return
    import importlib
    from halo_harness.ext.files import data_dir
    from halo_harness.studio.packs_routes import ensure_package, unload
    rel, prefix = str(rt.get("module")), str(rt.get("prefix"))
    try:
        mod = importlib.import_module(ensure_package(r.pack.id, r.root) + "." + ".".join(Path(rel).with_suffix("").parts))
    except Exception as e:
        r.add("studio", rel, "the routes module imports through the pack's folder", False, f"{type(e).__name__}: {e}")
        unload(r.pack.id)
        return
    ok = callable(getattr(mod, "handle", None))
    r.add("studio", rel, "the routes module imports and has handle(ctx, method, path, body, query)", ok,
          "define handle(ctx, method, path, body, query) in it")
    if ok:
        frames: list = []
        ctx = types.SimpleNamespace(pack_id=r.pack.id, prefix=prefix, pack_root=r.root, data_dir=Path(data_dir(r.pack.id)),
                                    state_dir=r.home / ".halo", cwd=r.project, bridge=None,
                                    publish=lambda kind, data=None: frames.append((kind, data)) or True)
        try:
            why = _shape(mod.handle(ctx, "GET", "ping", {}, {}))
        except Exception as e:
            why = f"it raised {type(e).__name__}: {e}"
        r.add("studio", rel, f"GET /api/packs/{r.pack.id}/{prefix}/ping answers in shape", not why,
              why + " -- answer GET ping with (200, {\"ok\": true})" if why else "")
    unload(r.pack.id)
