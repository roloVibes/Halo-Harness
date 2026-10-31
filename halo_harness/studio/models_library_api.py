"""halo_harness.studio.models_library_api -- Halo 3.3.5.0 R2: the routes of Local -> Library (docs/STUDIO-local.md
"Library"), reached through studio/local_api.dispatch_local (prefix `local/`). The same guard as every Studio
route; never a model call. 3.3.5.0 R3: each row says `installed` -- the hosts whose catalog has it (`pull_target`:
what Pull asks for, a library name or `hf.co/<repo>:<quant>`); Pull itself is studio/local_control_api.py.

    GET  local/library?source=ollama|hf|all&q=&host=&window=&fits=1&intent=&family=&quant=&cap=&max_gb=&license=&page=
         -> {rows: [row + card view + fit + intent], total, page, pages, cached_at, sources {ollama: "live" |
            "snapshot <date>", hf: "live" | "fixtures"}, notes, host, hosts, window, intents, snapshot}
    GET  local/library/<source>/<id>?host=&window=   one model's tags (Ollama) or files (a hub repo), each with its fit
    POST local/library/refresh                       the cache dropped: the next read is live

models_library/browse.py does the work (`halo models browse` prints the same rows).
"""

from __future__ import annotations

import re
import urllib.parse

_DETAIL = re.compile(r"^local/library/(?P<source>ollama|hf)/(?P<id>.+)$")


def _int(v):
    try:
        n = int(str(v).replace(",", "").strip())
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _float(v):
    try:
        n = float(str(v).strip())
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _q(req, key: str) -> str:
    return str(req.query.get(key) or "").strip()


def pull_target(row: dict) -> str:
    line = str(row.get("pull_line") or "")
    return line[len("ollama pull "):].strip() if line.startswith("ollama pull ") else ""


def mark_installed(answer: dict) -> dict:
    """Each row's `pull_target` and `installed` [host names]: read from the catalogs the Hosts page reads."""
    from halo_harness.providers.ollama import ollama_names_match, resolve_ollama_hosts
    from halo_harness.providers.ollama_guard import skip_default
    from halo_harness.studio.ollama_hosts_view import catalog_of
    have = []
    for h in resolve_ollama_hosts():
        if not skip_default(h):
            have.append((h.name, [str(r.get("model") or r.get("name") or "") for r in catalog_of(h).get("models") or []
                                  if isinstance(r, dict)]))
    for row in answer.get("rows") or []:
        target = pull_target(row)
        row["pull_target"] = target
        row["installed"] = [n for n, names in have if target and any(ollama_names_match(target, m) for m in names)]
    from halo_harness.studio.local_hf_view import mark_on_disk  # 3.3.5.0 R5: a hub row's "on disk in <folder>"
    mark_on_disk(answer.get("rows") or [])
    return answer


def get_library(req):
    from halo_harness.models_library.browse import library
    return 200, mark_installed(library(req.state_dir, source=_q(req, "source") or "all", q=_q(req, "q"), host=_q(req, "host"),
                        window=_int(req.query.get("window")), fits=_q(req, "fits") in ("1", "true", "yes"),
                        intent=_q(req, "intent"), family=_q(req, "family"), quant=_q(req, "quant"), cap=_q(req, "cap"),
                        max_gb=_float(req.query.get("max_gb")), license=_q(req, "license"),
                        page=_int(req.query.get("page")) or 1))


def get_detail(req, source: str, model_id: str):
    from halo_harness.models_library.browse import detail
    if not model_id:
        return 422, {"error": "which model: local/library/<source>/<id>", "problems": ["id: the model or the repo"]}
    return 200, mark_installed(detail(req.state_dir, source, model_id, host=_q(req, "host"), window=_int(req.query.get("window"))))


def post_refresh(req):
    from halo_harness.models_library.browse import refresh
    return 200, refresh(req.state_dir)


ROUTES = {("GET", "local/library"): get_library, ("POST", "local/library/refresh"): post_refresh}


def dispatch_library(req):
    """The answer for a `local/library*` path, or None for any other path."""
    if not req.path.startswith("local/library"):
        return None
    fn = ROUTES.get((req.method, req.path))
    if fn is not None:
        return fn(req)
    m = _DETAIL.match(req.path)
    if m and req.path != "local/library/refresh":
        if req.method != "GET":
            return 405, {"error": "method not allowed"}
        return get_detail(req, m.group("source"), urllib.parse.unquote(m.group("id")))
    if any(p == req.path for _m, p in ROUTES):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
