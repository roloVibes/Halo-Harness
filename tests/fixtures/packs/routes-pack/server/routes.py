"""The routes-pack fixture's routes (3.3.14.0 R1): `ping`, `page` (HTML with no CSP of its own), `styled` (HTML with
its own CSP and a header Studio drops), `value` (read from the sibling module server/value.py when asked), and a
module-level `unload()` that writes one line to the file `ROUTES_PACK_UNLOAD_FILE` names."""

import os


def handle(ctx, method, path, body, query):
    if path == "ping":
        return 200, {"ok": True, "pack": ctx.pack_id, "method": method, "query": dict(query or {})}
    if path == "page":
        return 200, "<!doctype html><p>a page</p><script>1</script>", "text/html; charset=utf-8"
    if path == "styled":
        return 200, b"<p>styled</p>", "text/html", {"Content-Security-Policy": "default-src 'self'", "X-Other": "no"}
    if path == "value":
        from . import value  # asked for here, as a pack's lazy import would be
        return 200, {"value": value.VALUE}
    return 404, {"error": f"no route {method} {path} in routes-pack"}


def unload():
    marker = os.environ.get("ROUTES_PACK_UNLOAD_FILE")
    if marker:
        with open(marker, "a", encoding="utf-8") as f:
            f.write("unloaded\n")
