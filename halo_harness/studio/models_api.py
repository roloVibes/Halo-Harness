"""Studio: why the model catalog is empty, and a Refresh that fills it.

3.0.4.0 (owner, live on the Kali VM): the bio form's model dropdown showed
only "(none) / Type a ref..." because no provider had a cached catalog in
that state dir, and the page said nothing about it. `GET models/status`
explains the catalog per provider; `POST models/refresh` re-pulls every
enabled provider's catalog, then returns the new row count. Nothing here
writes anything but the providers' own cache files (and the refresh record,
models_refresh.py), exactly as `halo models --refresh` and the keys step do.

3.0.7.0 R1: `POST models/test {ref}` sends the one-token probe
(model_probe.py) and answers `{ok, latency_ms, error, cost_line, ref, reply}`.

3.1.4.0 R4 (the owner, live on Kali: the session ran on Databricks while
this route said "No provider is set up"): every route here resolves the
providers with `catalog_env(req.cwd)`, the env a session resolves with (the
env file, the shell, the settings.json `env` chain), never a bare copy of
os.environ. Refresh asks every provider at once, time-boxed, one outcome line
each (models_refresh.py); status names every provider it looked at and why
it listed nothing (`looked_at`), and when the last refresh ran. `GET
models/fallback` is what the select offers beside the live catalog
(models_fallback.py); `GET models/resolve` is models_resolve.py.
"""
from __future__ import annotations

from .api import Request


def _env(req: Request) -> dict:
    from .catalog_env import catalog_env
    return catalog_env(req.cwd)


def _rows(req: Request) -> list:
    from . import model as M
    return M.model_rows(req.state_dir, req.cwd)


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


def looked_at(rows: list, providers: list, record) -> list:
    """`[{name, label, ok, line}]`: every provider looked at, what it lists or why it lists nothing."""
    outcomes = (record or {}).get("outcomes") or []
    by = {}
    for o in outcomes:
        by.setdefault(o.get("provider"), []).append(o)
    counts: dict = {}
    for r in rows:
        counts[r.get("provider")] = counts.get(r.get("provider"), 0) + 1
    out = []
    for p in providers:
        name, label, n = p["name"], p["label"], counts.get(p["name"], 0)
        failed = [o for o in by.get(name, []) if not o.get("ok")]
        if n:
            line, ok = f"{n} models listed", True
        elif failed:
            line, ok = "listing failed: " + failed[0]["line"], False
        elif p["enabled"]:
            line, ok = "on, no list cached yet: press Refresh", False
        elif "disabled" in p["status"]:
            line, ok = f"turned off by you (halo providers enable {name})", False
        elif p["credentials"]:
            line, ok = f"a key is here but the provider is off: halo providers enable {name}", False
        elif name.endswith("_subscription"):
            line, ok = "not logged in on this machine", False
        else:
            line, ok = "not configured: no key in the env file, the shell or settings.json", False
        out.append({"name": name, "label": label, "ok": ok, "line": line})
    hosts = by.get("ollama", [])
    if counts.get("ollama"):
        out.append({"name": "ollama", "label": "Ollama", "ok": True, "line": f"{counts['ollama']} models listed"})
    for o in hosts:
        if not o.get("ok"):
            out.append({"name": "ollama", "label": o["name"], "ok": False, "line": o["line"]})
    if not hosts and not counts.get("ollama"):
        out.append({"name": "ollama", "label": "Ollama", "ok": False, "line": "no model listed yet: Refresh asks every ollama.hosts entry"})
    return out


def _reason(rows: list, seen: list) -> str:
    if rows:
        return ""
    return "No model list here yet. Looked at: " + "; ".join(f"{s['label']}: {s['line']}" for s in seen) + "."


def get_models_status(req: Request):
    from .models_refresh import last
    env = _env(req)
    rows = _rows(req)
    providers = _providers(env)
    record = last(req.state_dir)
    seen = looked_at(rows, providers, record)
    return 200, {"rows": len(rows), "providers": providers, "reason": _reason(rows, seen), "looked_at": seen,
                 "refreshed_at": (record or {}).get("at"), "outcomes": (record or {}).get("outcomes") or []}


def post_models_refresh(req: Request):
    """Ask every provider at once (each time-boxed); the new count, one line per provider, and when.
    `?no_probe=1` asks the keyed catalogs only (no local host)."""
    from . import models_refresh as MR
    env = _env(req)
    record = MR.refresh(req.state_dir, env, local=not req.query.get("no_probe"))
    rows = _rows(req)
    seen = looked_at(rows, _providers(env), record)
    lines = [f"{o['name']}: {o['line']}" for o in record["outcomes"]]
    return 200, {"rows": len(rows), "attempts": lines, "outcomes": record["outcomes"], "refreshed_at": record["at"],
                 "box_s": record["box_s"], "reason": _reason(rows, seen), "looked_at": seen}


def get_models_fallback(req: Request):
    from .models_fallback import fallback_rows
    return 200, fallback_rows(req.state_dir, req.cwd, {r["ref"] for r in _rows(req)}, _env(req))


def post_models_test(req: Request):
    """3.0.7.0 R1 ("Test this model"): `{ref}` -> `{ok, latency_ms, error,
    cost_line, ref, reply}`, a one-token round trip (model_probe.py, 20 s)."""
    ref = str((req.body or {}).get("ref") or "").strip()
    if not ref:
        return 422, {"error": 'say which model: {"ref": "or:vendor/model"}', "problems": ["ref is required"]}
    from halo_harness.model_probe import probe_model
    return 200, probe_model(ref, state_dir=req.state_dir)


from .models_resolve import get_models_resolve  # noqa: E402  (3.1.4.0 R4)

ROUTES: list = [
    ("GET", r"^models/status$", get_models_status),
    ("GET", r"^models/resolve$", get_models_resolve),
    ("GET", r"^models/fallback$", get_models_fallback),
    ("POST", r"^models/refresh$", post_models_refresh),
    ("POST", r"^models/test$", post_models_test),
]
