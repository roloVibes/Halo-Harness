"""__NAME__'s own Studio routes (docs/EXTENSION_API.md "A pack's own routes"). Studio imports this module through the
pack's folder once the owner grants studio-routes, and answers `/api/packs/__ID__/__ID__/<path>` with `handle`, behind
its token like every route. `ctx` carries the pack's folder (`pack_root`), its data folder (`data_dir`), Halo's
(`state_dir`), Studio's project (`cwd`) and `publish(kind, data)`: a live frame the pack's page hears with
`api.on(kind, cb)`. Answer `(status, a dict or a list)` for JSON, or `(status, bytes, content_type)` for a file.
"""

import json

from halo_harness.ext import write_private


def handle(ctx, method, path, body, query):
    if method == "GET" and path == "ping":
        return 200, {"ok": True, "pack": ctx.pack_id}
    if method == "POST" and path == "note":
        text = str((body or {}).get("text") or "").strip()
        if not text:
            return 422, {"error": "say what the note is: {\"text\": \"...\"}"}
        lines = write_private(ctx.pack_id, "last-note.json", json.dumps({"text": text}) + "\n")
        if lines:
            return 500, {"error": lines[0]}
        ctx.publish("note", {"text": text})
        return 200, {"ok": True}
    return 404, {"error": f"no route {method} {path} in __ID__"}
