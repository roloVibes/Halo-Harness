"""halo_harness.studio.packs_routes -- a pack's own Studio API routes (Halo 3.3.13.0 R2, extension API 1.2;
docs/EXTENSION_API.md "A pack's own routes").

A pack that declares `contributes.studio.routes: {module: server/routes.py, prefix: design}` and is granted
`studio-routes` answers under `/api/packs/<id>/<prefix>/...`, behind Studio's token like every route:

    handle(ctx, method, path, body, query) -> (status, json)              # a dict or a list
                                            | (status, bytes | str, content_type[, headers])

`path` is what follows the prefix (`projects`, `x/turn/7`). `ctx` carries `pack_id`, `prefix`, `pack_root`,
`data_dir` (the pack's data folder), `state_dir` (Halo's), `cwd` (Studio's project), `publish(kind, data)` (a
`pack_live` frame on the live feed: the pack's bundle hears it through `api.on(kind)`, nothing keeps it) and
`bridge` (Studio's live-feed bridge). Raw bytes keep the route's own `Content-Security-Policy` (and a
`Content-Disposition`); every other header is dropped. The module is imported through the pack's own folder as the
package `halo_packs.<id>` (a relative import reaches the pack's other modules), once, and again when the file
changes; a pack that is disabled, removed or no longer granted is unloaded on its next request. `MAX_BODY = <bytes>`
in the module raises the request body limit for this pack's prefix (the server's 4 MB otherwise; at most 64 MB).
A module that fails to import, or a `handle` that raises, answers 500 with one line, kept in the pack's data folder
(`.studio-routes.json`) for `halo pack doctor` to show.
"""

from __future__ import annotations

import importlib
import json
import sys
import threading
import time
import types
from pathlib import Path

PKG = "halo_packs"
DEFAULT_MAX, HARD_MAX = 4_000_000, 64_000_000
ERRORS = ".studio-routes.json"
PASSED_HEADERS = ("Content-Security-Policy", "Content-Disposition")
_lock = threading.RLock()
_loaded: dict = {}  # pack id -> {"root", "stamp", "module"}


def _safe(pack_id: str) -> str:
    return pack_id.replace("-", "_")


def unload(pack_id: str) -> None:
    """Forget the pack's routes module and every module imported through its folder."""
    name = f"{PKG}.{_safe(pack_id)}"
    with _lock:
        _loaded.pop(pack_id, None)
        for mod in [m for m in sys.modules if m == name or m.startswith(name + ".")]:
            sys.modules.pop(mod, None)


def ensure_package(pack_id: str, root) -> str:
    """The package `halo_packs.<id>` over the pack's folder `root` (made, or the one already there for that folder)."""
    if PKG not in sys.modules:
        top = types.ModuleType(PKG)
        top.__path__ = []  # type: ignore[attr-defined]
        sys.modules[PKG] = top
    name, where = f"{PKG}.{_safe(pack_id)}", str(Path(root).resolve())
    have = sys.modules.get(name)
    if have is not None and list(getattr(have, "__path__", [])) == [where]:
        return name
    unload(pack_id)
    pkg = types.ModuleType(name)
    pkg.__path__ = [where]  # type: ignore[attr-defined]
    pkg.__file__ = str(Path(where) / "pack.yaml")
    sys.modules[name] = pkg
    return name


def note_error(pack_id: str, line: str) -> None:
    """Keep the route's last failure in the pack's data folder (the doctor's row); never raises."""
    try:
        from halo_harness.ext.files import data_dir
        d = Path(data_dir(pack_id))
        d.mkdir(parents=True, exist_ok=True)
        (d / ERRORS).write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "error": line}) + "\n",
                                encoding="utf-8")
    except Exception:
        pass


def _clear_error(pack_id: str) -> None:
    try:
        from halo_harness.ext.files import data_dir
        (Path(data_dir(pack_id)) / ERRORS).unlink(missing_ok=True)
    except Exception:
        pass


def load(pack) -> "tuple[object, str]":
    """`(module, '')`, or `(None, the line)` when the routes module does not import or has no handle()."""
    from halo_harness.packs.studio_view_rules import routes_of
    rel = str(routes_of(pack.manifest).get("module") or "")
    path = Path(pack.root) / rel
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        return None, f"{pack.id}: {rel} is not in the pack"
    root = str(Path(pack.root).resolve())
    with _lock:
        have = _loaded.get(pack.id)
        if have and have["root"] == root and have["stamp"] == stamp:
            return have["module"], ""
        if have:  # the file changed, or the pack moved: import it afresh
            unload(pack.id)
        name = ensure_package(pack.id, root) + "." + ".".join(Path(rel).with_suffix("").parts)
        try:
            mod = importlib.import_module(name)
        except Exception as e:  # the pack's own code: its failure is a line, never Studio's
            unload(pack.id)
            return None, f"{pack.id}: {rel} does not import: {type(e).__name__}: {e}"
        if not callable(getattr(mod, "handle", None)):
            unload(pack.id)
            return None, f"{pack.id}: {rel} has no handle(ctx, method, path, body, query)"
        _loaded[pack.id] = {"root": root, "stamp": stamp, "module": mod}
        _clear_error(pack.id)
        return mod, ""


def drop_inactive() -> None:
    """A pack was turned off, removed or had a grant taken back (packs/grants.py `changed`): unload its routes now;
    the routes of the packs still on keep their module (and the work it holds, a running turn)."""
    for pack_id, have in list(_loaded.items()):
        try:
            find(pack_id, have.get("prefix", ""), cwd=have.get("cwd"), state_dir=have.get("state_dir"))
        except Exception:
            unload(pack_id)


def _split(path: str) -> "tuple[str, str, str]":
    """`packs/<id>/<prefix>/<rest>` -> (id, prefix, rest)."""
    parts = path.split("/", 3)
    return (parts[1] if len(parts) > 1 else "", parts[2] if len(parts) > 2 else "", parts[3] if len(parts) > 3 else "")


def find(pack_id: str, prefix: str, *, cwd, state_dir) -> "tuple[object, int, str]":
    """`(pack, 200, '')` when the pack runs here, declares this prefix and is granted studio-routes."""
    from halo_harness.packs import state as S
    from halo_harness.packs.studio_registry import active_pack
    from halo_harness.packs.studio_view_rules import ROUTES, routes_of
    pack = active_pack(pack_id, cwd=cwd, state_dir=state_dir) if pack_id else None
    if pack is None:
        unload(pack_id)
        return None, 404, f"no pack {pack_id!r} runs here (halo pack list)"
    if str(routes_of(pack.manifest).get("prefix") or "") != prefix:
        return None, 404, f"{pack.id} declares no routes under {prefix!r}"
    if ROUTES not in S.granted(pack.id, S.load(state_dir)):
        unload(pack.id)
        return None, 403, f"{pack.id}'s routes run once you grant it: halo pack enable {pack.id} --grant {ROUTES}"
    return pack, 200, ""


def max_body(url_path: str, server) -> int:
    """The body limit for a request to `url_path` (`/api/packs/...`): the module's MAX_BODY, else 4 MB."""
    pack_id, prefix, _rest = _split(url_path[len("/api/"):])
    try:
        pack, status, _why = find(pack_id, prefix, cwd=server.cwd, state_dir=server.state_dir)
        mod = load(pack)[0] if status == 200 else None
        n = getattr(mod, "MAX_BODY", None)
        return max(0, min(HARD_MAX, int(n))) if isinstance(n, int) and not isinstance(n, bool) else DEFAULT_MAX
    except Exception:
        return DEFAULT_MAX


def _ctx(pack, prefix: str, req):
    from halo_harness.ext.files import data_dir

    def publish(kind: str, data=None) -> bool:
        if req.server is None:
            return False
        from halo_harness.studio.events import bridge_for
        bridge_for(req.server).publish_local({"event": "pack_live", "data": {"pack": pack.id, "kind": str(kind), "data": data}})
        return True

    bridge = None
    if req.server is not None:
        from halo_harness.studio.events import bridge_for
        bridge = bridge_for(req.server)
    return types.SimpleNamespace(pack_id=pack.id, prefix=prefix, pack_root=Path(pack.root), data_dir=Path(data_dir(pack.id)),
                                 state_dir=Path(req.state_dir), cwd=Path(req.cwd), publish=publish, bridge=bridge)


def _answer(pack_id: str, out):
    from halo_harness.studio.raw_body import RawBody
    if not isinstance(out, tuple) or not 2 <= len(out) <= 4 or not isinstance(out[0], int):
        line = f"{pack_id}: handle answered {type(out).__name__}; it answers (status, json | bytes, content_type?)"
        note_error(pack_id, line)
        return 500, {"error": line}
    status, body = out[0], out[1]
    if isinstance(body, (bytes, str)) and len(out) >= 3:
        data = body.encode("utf-8") if isinstance(body, str) else body
        heads = out[3] if len(out) == 4 and isinstance(out[3], dict) else {}
        return status, RawBody(data, str(out[2]), {k: str(v) for k, v in heads.items() if k in PASSED_HEADERS})
    return status, body


def dispatch(req):
    """`/api/packs/<id>/<prefix>/<rest>` to the pack's handle()."""
    pack_id, prefix, rest = _split(req.path)
    pack, status, why = find(pack_id, prefix, cwd=req.cwd, state_dir=req.state_dir)
    if pack is None:
        return status, {"error": why}
    mod, why = load(pack)
    if mod is None:
        note_error(pack.id, why)
        return 500, {"error": why}
    _loaded.get(pack.id, {}).update(prefix=prefix, cwd=req.cwd, state_dir=req.state_dir)  # drop_inactive's lookup
    try:
        query = {k: v for k, v in (req.query or {}).items() if k != "t"}  # the token a GET may carry is Studio's
        out = mod.handle(_ctx(pack, prefix, req), req.method, rest, req.body, query)
    except Exception as e:
        line = f"{pack.id}: {req.method} {prefix}/{rest} raised {type(e).__name__}: {e}"
        note_error(pack.id, line)
        return 500, {"error": line}
    return _answer(pack.id, out)
