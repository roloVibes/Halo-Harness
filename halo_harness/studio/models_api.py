"""Studio: why the model catalog is empty, and a Refresh that fills it.

3.0.4.0 (owner, live on the Kali VM): the bio form's model dropdown showed
only "(none) / Type a ref..." because no provider had a cached catalog in
that state dir, and the page said nothing about it. `GET models/status`
explains the catalog per provider; `POST models/refresh` re-pulls every
enabled provider's catalog (and probes logins when a provider is detected
but has no rows yet), then returns the new row count. Nothing here writes
anything but the providers' own cache files, exactly as `halo models
--refresh` and the wizard's keys step already do.
"""
from __future__ import annotations

import os
from pathlib import Path

from .api import Request


def _env(state_dir: Path) -> dict:
    from halo_harness.providers.config import load_provider_env_files
    load_provider_env_files()
    return dict(os.environ)


def _rows(state_dir: Path) -> list:
    from . import model as M
    return M.model_rows(state_dir)


def _providers(env: dict) -> list:
    try:
        from halo_harness.providers_cli import provider_rows
        rows = provider_rows(env=env)
    except Exception:
        rows = []
    out = []
    for r in rows:
        out.append({
            "name": r.get("name", ""), "label": r.get("label", r.get("name", "")),
            "enabled": bool(r.get("enabled")), "credentials": bool(r.get("credentials")),
            "status": str(r.get("status") or ""), "model_count": r.get("model_count"),
        })
    return out


def _reason(rows: list, providers: list) -> str:
    if rows:
        return ""
    enabled = [p for p in providers if p["enabled"]]
    detected = [p for p in providers if p["credentials"] and not p["enabled"]]
    if not enabled and not detected:
        return ("No provider is set up in this Halo home yet: Studio lists the models each enabled "
                "provider has cached. Run `halo init` (the keys step) or `halo providers enable <name>` "
                "with a key in the environment, then press Refresh.")
    if detected and not enabled:
        names = ", ".join(p["label"] for p in detected)
        return f"{names}: detected but not enabled. Run `halo providers enable <name>`, then press Refresh."
    names = ", ".join(p["label"] for p in enabled)
    return f"{names} enabled but no catalog cached yet. Press Refresh to pull the model list."


def get_models_status(req: Request):
    env = _env(req.state_dir)
    rows = _rows(req.state_dir)
    providers = _providers(env)
    return 200, {"rows": len(rows), "providers": providers, "reason": _reason(rows, providers)}


def post_models_refresh(req: Request):
    """Force-refresh every enabled provider's catalog; when none is enabled
    but one is detected, run the bounded live enumeration (it probes logins
    and writes each provider's cache). Returns the new count and one line
    per attempt."""
    from halo_harness.providers.catalog_refresh import refresh_all_enabled_catalogs
    env = _env(req.state_dir)
    results = []
    try:
        results = refresh_all_enabled_catalogs(req.state_dir, env=env, force=True)
    except Exception as e:  # never take Studio down over one catalog
        results = [{"name": "catalogs", "attempted": True, "ok": False, "count": None, "error": str(e)}]
    rows = _rows(req.state_dir)
    providers = _providers(env)
    if not rows and any(p["credentials"] for p in providers) and not req.query.get("no_probe"):
        try:
            from halo_harness.providers.model_enumeration import enumerate_live
            enumerate_live(req.state_dir, env=env)
            rows = _rows(req.state_dir)
        except Exception as e:
            results.append({"name": "live probe", "attempted": True, "ok": False, "count": None, "error": str(e)})
    lines = []
    for r in results:
        if not r.get("attempted"):
            continue
        state = "skipped" if r.get("ok") is None else ("ok" if r.get("ok") else "failed")
        n = r.get("count")
        lines.append(f"{r.get('name')}: {state}" + (f", {n} model(s)" if isinstance(n, int) else "") + (f" ({r['error']})" if r.get("error") else ""))
    return 200, {"rows": len(rows), "attempts": lines, "reason": _reason(rows, providers)}


ROUTES: list = [
    ("GET", r"^models/status$", get_models_status),
    ("POST", r"^models/refresh$", post_models_refresh),
]
