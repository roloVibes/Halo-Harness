"""halo_harness.studio.paperclip_api -- Studio's Org mode backend (Halo 2.2.0
round C4): `/api/pc/status`, `/api/pc/install` and a proxy for everything
else under `/api/pc/<path>` -> the Paperclip instance's `/api/<path>` with
the board token from ~/.halo/paperclip.json added server-side (the page
never sees it). Same loopback / origin / token guard as every Studio route
(server.py runs it before dispatch).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
from pathlib import Path

from halo_harness.paperclip.client import DEFAULT_URL, Paperclip, PaperclipError, load_config

_INSTALL: dict = {"running": False, "log": [], "code": None}


def _client(state_dir) -> Paperclip:
    cfg = load_config(Path(state_dir))
    return Paperclip(str(cfg.get("base_url") or DEFAULT_URL), str(cfg.get("token") or ""), timeout=20)


def installed_locally() -> bool:
    return (Path.home() / ".paperclip" / "instances").is_dir()


def status(req):
    cfg = load_config(Path(req.state_dir))
    client = _client(req.state_dir)
    out = {"installed": installed_locally(), "base_url": client.base_url, "token": bool(client.token),
           "company_id": cfg.get("company_id") or "", "reachable": False, "version": "", "companies": [],
           "node": shutil.which("node") is not None, "install": {"running": _INSTALL["running"], "code": _INSTALL["code"]}}
    try:
        h = client.health()
        out["reachable"] = h.get("status") == "ok"
        out["version"] = h.get("version", "")
        out["mode"] = h.get("deploymentMode", "")
        out["companies"] = [{"id": c.get("id"), "name": c.get("name"), "status": c.get("status")} for c in client.companies()]
    except PaperclipError as e:
        out["error"] = e.message
    return 200, out


def _run_install() -> None:
    _INSTALL.update(running=True, log=[], code=None)
    npx = shutil.which("npx") or "npx"
    cmd = [npx, "--yes", "--registry", "https://registry.npmjs.org", "paperclipai@latest", "onboard", "--yes"]
    _INSTALL["log"].append("$ " + " ".join(cmd))
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace",
                                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        for line in proc.stdout:  # type: ignore[union-attr]
            _INSTALL["log"].append(line.rstrip("\n"))
            if len(_INSTALL["log"]) > 400:
                del _INSTALL["log"][:100]
            if "Server startup recovery complete" in line or "startup recovery complete" in line:
                _INSTALL["code"] = 0  # the server keeps running in the foreground: that is the success line
        proc.wait()
        if _INSTALL["code"] is None:
            _INSTALL["code"] = proc.returncode
    except OSError as e:
        _INSTALL["log"].append(f"cannot run npx: {e}")
        _INSTALL["code"] = 1
    finally:
        _INSTALL["running"] = False


def install(req):
    if req.method == "GET":
        return 200, {"running": _INSTALL["running"], "code": _INSTALL["code"], "log": _INSTALL["log"][-200:]}
    if _INSTALL["running"]:
        return 409, {"error": "an install is already running"}
    if shutil.which("node") is None:
        return 422, {"error": "Paperclip needs Node.js 24 or newer; install Node first", "problems": ["node not found on PATH"]}
    client = _client(req.state_dir)
    if client.reachable():  # a reachable instance (local or linked) means there is nothing to install
        return 409, {"error": f"Paperclip is already running at {client.base_url}"}
    threading.Thread(target=_run_install, name="halo-paperclip-install", daemon=True).start()
    return 202, {"running": True}


def link(req):
    """POST {company_id?, base_url?, token?}: remember the company Studio shows."""
    from halo_harness.paperclip.client import save_config
    cfg = load_config(Path(req.state_dir))
    for key in ("company_id", "base_url", "token"):
        if key in req.body:
            cfg[key] = str(req.body.get(key) or "")
    save_config(cfg, Path(req.state_dir))
    return 200, {k: (bool(v) if k == "token" else v) for k, v in cfg.items()}


def sync(req):
    """POST {lineup, company_id?, new?, cwd?}: lineup -> company (C3)."""
    from halo_harness.paperclip.sync import org_tree_lines, sync_lineup
    import io
    client = _client(req.state_dir)
    try:
        cid = str(req.body.get("company_id") or "")
        if req.body.get("new"):
            cid = client.create_company(str(req.body["new"]), f"Halo lineup {req.body.get('lineup')}")["id"]
        if not cid:
            return 422, {"error": "company_id or new is required"}
        out = io.StringIO()
        agents = sync_lineup(client, cid, str(req.body.get("lineup") or ""), cwd=Path(req.body.get("cwd") or req.cwd), cwd_halo=req.cwd,
                             state_dir=req.state_dir, out=out)
        return 200, {"company_id": cid, "agents": len(agents), "log": out.getvalue().splitlines(), "org": org_tree_lines(client.org(cid))}
    except (ValueError, PaperclipError) as e:
        return 422, {"error": str(e), "problems": [str(e)]}


def pull(req):
    from halo_harness.paperclip.sync import pull_reporting_lines
    client = _client(req.state_dir)
    try:
        org = pull_reporting_lines(client, str(req.body.get("company_id") or ""), str(req.body.get("lineup") or ""),
                                   cwd_halo=req.cwd, state_dir=req.state_dir, project=bool(req.body.get("project")))
        return 200, {"org": org}
    except (ValueError, PaperclipError) as e:
        return 422, {"error": str(e), "problems": [str(e)]}


def proxy(req):
    """Everything else: forward to Paperclip with the board token."""
    client = _client(req.state_dir)
    path = req.path[len("pc/"):]
    try:
        data = client.request(req.method, path, req.body if req.method in ("POST", "PUT", "PATCH") else None, req.query or None)
        return 200, data if data is not None else {}
    except PaperclipError as e:
        return (502 if e.status == 0 else e.status), {"error": e.message}


def dispatch_pc(req):
    sub = req.path[len("pc/"):]
    if sub == "status" and req.method == "GET":
        return status(req)
    if sub == "install" and req.method in ("GET", "POST"):
        return install(req)
    if sub == "link" and req.method == "POST":
        return link(req)
    if sub == "sync" and req.method == "POST":
        return sync(req)
    if sub == "pull" and req.method == "POST":
        return pull(req)
    return proxy(req)
