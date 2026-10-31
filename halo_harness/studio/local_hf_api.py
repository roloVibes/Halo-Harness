"""halo_harness.studio.local_hf_api -- Halo 3.3.5.0 R5: Local -> Hugging Face's routes (prefix `local/`, dispatched
first by studio/local_api.dispatch_local; docs/STUDIO-local.md). Every answer that acts carries `cli`, the
`halo local` line that does the same. Never a model call; the hub is read only by a download (providers/
hf_download.py) and the servers are studio/local_server_api.py's.

    GET  local/hf/dirs?host=&window=      studio/local_hf_view.dirs: each model folder and what is on disk in it
    POST local/hf/download {repo, file?, dir?, accept}   the licence line first: 422 {licence, needs_accept} until
                                          `accept`; a gated repo without HF_TOKEN 422 {needs_token}; then a download
                                          job (studio/local_download_job.py), a second ask joins it
    POST local/download/<id>/cancel       stop it (the part file stays: downloading again resumes)
    GET  local/downloads                  the download jobs running and the last ended ones
    GET  local/hf/uses?path=              the uses card of a model on disk (studio/local_uses.py, `hf:local/<model>`)
    POST local/hf/delete {path, force?}   409 while a server Halo started serves it; 422 + the uses card when
                                          something names it (force: delete anyway); then its files go
    POST local/hf/dirs {path}             a folder added to huggingface.model_dirs (the `/local add` writer)
    POST local/hf/forget {path}           a folder taken off the list (nothing on disk is touched)
"""

from __future__ import annotations

import re
import shutil
import urllib.parse
from pathlib import Path

_CANCEL = re.compile(r"^local/download/(?P<id>[^/]+)/cancel$")
CODES = {"missing": 404, "no_file": 422, "bad_repo": 422, "gated": 422, "blocked": 502, "unreachable": 502, "http": 502}


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def _int(v):
    try:
        n = int(str(v).replace(",", "").strip())
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def dl_cli(repo: str, file: str = "", d: str = "", yes: bool = True) -> str:
    return " ".join(w for w in ("halo local download", repo, file, f"--dir {d}" if d else "", "--yes" if yes else "") if w)


def pick_dir(asked: str) -> "tuple[Path | None, str]":
    from halo_harness.providers.local_model_dirs import resolve_model_dirs
    dirs = resolve_model_dirs()
    if asked:
        want = Path(asked).expanduser().resolve()
        hit = next((d for d in dirs if d.resolve() == want), None)
        return (hit, "") if hit else (None, f"{want} is not a huggingface.model_dirs folder: Add folder first (halo local add {want})")
    hit = next((d for d in dirs if d.is_dir()), None)
    return (hit, "") if hit else (None, "no huggingface.model_dirs folder yet: Add folder first (halo local add <path>)")


def summary(plan: dict) -> dict:
    return {k: plan.get(k) for k in ("repo", "file", "kind", "quant", "total", "commit")} | {
        "files": [{"name": f["name"], "size": f["size"]} for f in plan.get("files") or []]}


def post_download(req):
    from halo_harness.models_library.hf_hub import token
    from halo_harness.providers.hf_download import HubError, prepare
    from halo_harness.studio import local_download_job as DJ
    from halo_harness.studio.local_api import _publish
    body = _body(req)
    repo, file = str(body.get("repo") or "").strip(), str(body.get("file") or "").strip()
    if not repo:
        return 422, {"error": "download takes {repo, file?, dir?, accept}", "problems": ["repo: <org>/<name>"]}
    d, why = pick_dir(str(body.get("dir") or "").strip())
    if d is None:
        return 422, {"error": why, "problems": [why], "cli": dl_cli(repo, file)}
    tok = token()
    try:
        plan = prepare(repo, file or None, token=tok)
    except HubError as e:
        return CODES.get(e.kind, 502), {"error": e.message, "kind": e.kind, "cli": dl_cli(repo, file, str(d))}
    lic, line = plan["licence"], dl_cli(repo, file, str(d))
    if plan["needs_token"] and not tok:
        say = lic["line"] + "; set HF_TOKEN first (Setup -> Providers -> Hugging Face)"
        return 422, {"error": say, "licence": lic, "needs_token": True, "plan": summary(plan), "cli": line}
    if body.get("accept") is not True:
        return 422, {"error": lic["line"], "licence": lic, "needs_accept": True, "plan": summary(plan), "dir": str(d),
                     "cli": line, "problems": [lic["line"]]}
    try:
        pub = _publish(req)
    except Exception:
        pub = None
    view = DJ.start(d, plan["repo"], file, pub, token=tok, plan=plan)
    return 200, {**view, "licence": lic, "plan": summary(plan), "cli": line}


def find(path: str):
    """The model on disk Local -> Hugging Face lists at `path` (its view row), or None."""
    from halo_harness.providers.local_model_dirs import resolve_model_dirs
    from halo_harness.studio.local_hf_view import models_in
    try:
        want = Path(path).expanduser().resolve()
    except (OSError, ValueError):
        return None
    for root in resolve_model_dirs():
        if root.is_dir():
            for r in models_in(root):
                if Path(r["path"]).resolve() == want:
                    return r
    return None


def _uses(raw: dict, req) -> dict:
    from halo_harness.studio.local_uses import uses_of
    return uses_of(f"hf:local/{raw['model']}", cwd=req.cwd, state_dir=req.state_dir, repo=raw.get("repo") or "")


def _serving(raw: dict, state_dir) -> list:
    from halo_harness.providers.local_server import servers
    return [s for s in servers(state_dir) if s.get("alive")
            and Path(str(s.get("model_path") or "")).resolve() == Path(raw["path"]).resolve()]


def remove(raw: dict) -> int:
    """Its files off the disk (a quant's shards; a hub repo whose snapshot holds no other model goes whole)."""
    from halo_harness.models_library.hf_hub import SHARD
    path = Path(raw["path"])
    freed = raw["size"]
    if raw["kind"] == "gguf":
        key = SHARD.sub(".gguf", path.name)
        for p in path.parent.glob("*.gguf"):
            if SHARD.sub(".gguf", p.name) == key:
                p.unlink()
    else:
        shutil.rmtree(path)
    if raw.get("hub"):
        repo_dir = next(p for p in path.parents if p.name.startswith("models--"))
        left = [p for p in (repo_dir / "snapshots").rglob("*") if p.suffix.lower() in (".gguf", ".safetensors")]
        if not left:
            shutil.rmtree(repo_dir, ignore_errors=True)
    return freed


def post_delete(req):
    body = _body(req)
    path, force = str(body.get("path") or "").strip(), body.get("force") is True
    if not path:
        return 422, {"error": "delete takes {path, force?}", "problems": ["path: the model's file or folder"]}
    raw = find(path)
    if raw is None:
        return 404, {"error": f"Local -> Hugging Face lists no model at {path}"}
    line = f"halo local rm {raw['path']}" + (" --force" if force else "")
    on = _serving(raw, req.state_dir)
    if on:
        s = on[0]
        return 409, {"error": f"{s['id']} serves it on port {s['port']}: stop it first (halo local stop {s['id']})",
                     "served": [{"id": x["id"], "port": x["port"]} for x in on], "cli": line}
    uses = _uses(raw, req)
    if uses["any"] and not force:
        return 422, {"error": uses["line"], "uses": uses, "problems": [uses["line"]], "cli": f"halo local rm {raw['path']} --force"}
    try:
        freed = remove(raw)
    except OSError as e:
        return 500, {"error": f"deleting {raw['path']} failed: {e}", "cli": line}
    from halo_harness.studio import local_hf_view
    from halo_harness.studio.local_pull_job import after_change
    local_hf_view.reset()
    after_change()
    return 200, {"ok": True, "say": f"deleted {raw['path']} ({freed / 2 ** 30:.2f} GiB freed)", "freed": freed, "uses": uses, "cli": line}


def get_uses(req):
    raw = find(str(req.query.get("path") or "").strip())
    if raw is None:
        return 404, {"error": "Local -> Hugging Face lists no model at that path"}
    u = _uses(raw, req)
    return 200, {"uses": u, "served": [{"id": s["id"], "port": s["port"]} for s in _serving(raw, req.state_dir)],
                 "cli": f"halo local rm {raw['path']}" + (" --force" if u["any"] else "")}


def post_folder(req, add: bool):
    from halo_harness.providers.local_model_dirs import add_model_dir, forget_model_dir
    from halo_harness.studio import local_hf_view
    path = str(_body(req).get("path") or "").strip()
    if not path:
        return 422, {"error": "takes {path}", "problems": ["path: a folder"]}
    ok, say = (add_model_dir if add else forget_model_dir)(path)
    local_hf_view.reset()
    line = f"halo local {'add' if add else 'forget'} {path}"
    return (200, {"ok": True, "say": f"{say} (huggingface.model_dirs)", "cli": line}) if ok else (422, {"error": say, "cli": line})


def get_dirs(req):
    from halo_harness.studio.local_hf_view import dirs
    return 200, dirs(req.state_dir, host=str(req.query.get("host") or "").strip(), window=_int(req.query.get("window")))


def get_downloads(req):
    from halo_harness.studio import local_download_job as DJ
    return 200, DJ.current()


ROUTES = {("GET", "local/hf/dirs"): get_dirs, ("POST", "local/hf/download"): post_download,
          ("GET", "local/downloads"): get_downloads, ("GET", "local/hf/uses"): get_uses,
          ("POST", "local/hf/delete"): post_delete, ("POST", "local/hf/dirs"): lambda r: post_folder(r, True),
          ("POST", "local/hf/forget"): lambda r: post_folder(r, False)}


def dispatch_hf(req):
    """The answer for a route of this file or of studio/local_server_api.py, else None."""
    from halo_harness.studio.local_server_api import dispatch_servers
    got = dispatch_servers(req)
    if got is not None:
        return got
    fn = ROUTES.get((req.method, req.path))
    if fn is not None:
        return fn(req)
    m = _CANCEL.match(req.path)
    if m:
        if req.method != "POST":
            return 405, {"error": "method not allowed"}
        from halo_harness.studio import local_download_job as DJ
        got = DJ.cancel(urllib.parse.unquote(m.group("id")))
        return (200, {**got, "cancelling": not got["done"]}) if got else (404, {"error": "no such download job"})
    if any(p == req.path for _m, p in ROUTES):
        return 405, {"error": "method not allowed"}
    return None
