"""halo_harness.studio.local_guard_api -- Halo 3.3.7.0 R4: the guards' and the refresh's reads for Local -> Hosts, the
traffic view and the Steward page (dispatched by studio/local_api.dispatch_local; docs/STUDIO-local.md).

    GET local/idle?host=<name>    {hosts: [{host, line, busy, idle_s, foreign [...], foreign_line, refresh_line,
                                   last_line, via}]}: through the paired halo host that serves it (its GET idle and
                                   GET refresh), else this machine's own reads (ollama_steward/idle.py, host/refresh.py)
    GET local/refresh             {line, last_line, review, settings, plan}: this machine's refresh (the Steward page)
    POST roles/<role>/point {to}  is studio/roles_point_api.py
Read-only: one /api/ps per host; nothing loads.
"""

from __future__ import annotations


def _hosts(name: str = "") -> list:
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.providers.ollama_guard import skip_default
    try:
        hs = [h for h in resolve_ollama_hosts() if not skip_default(h)]
    except Exception:
        hs = []
    return [h for h in hs if not name or h.name == name]


def _via_host(h) -> "dict | None":
    from halo_harness.ollama_steward.host_client import HostError, _addr_port, _usable, for_host
    try:
        c = for_host(h)
    except Exception:
        return None
    if not _usable(c):
        return None
    served = c.served_name(_addr_port(h.url)[1]) or h.name
    try:
        idle = next((r for r in c.get("idle").get("hosts") or [] if r.get("host") == served), None) or {}
        ref = c.get("refresh")
    except (HostError, OSError, AttributeError):
        return None
    return {**{k: idle.get(k) for k in ("line", "busy", "idle_s", "foreign", "foreign_line")}, "host": h.name,
            "refresh_line": ref.get("line"), "last_line": ref.get("last_line"), "via": "host"}


def _here(state_dir, h) -> dict:
    from halo_harness.fleet.ollama_share import served_here
    from halo_harness.ollama_steward.idle import idle_since
    got = idle_since(state_dir, h)
    out = {"host": h.name, **{k: got[k] for k in ("line", "busy", "idle_s", "foreign", "foreign_line")}, "via": "local",
           "refresh_line": "", "last_line": ""}
    if served_here(h.url):
        from halo_harness.host.refresh import status
        st = status(state_dir, [h])
        out.update(refresh_line=st["line"], last_line=st["last_line"])
    else:
        out["refresh_line"] = (f"no halo host serves {h.name}: run `halo host serve` there for the off-hours refresh, "
                               "or `halo local refresh` on that machine")
    return out


def get_idle(req):
    name = str(req.query.get("host") or "").strip()
    rows = []
    for h in _hosts(name):
        try:
            rows.append(_via_host(h) or _here(req.state_dir, h))
        except Exception as e:
            rows.append({"host": h.name, "line": f"{h.name}: not read ({type(e).__name__})", "foreign": [],
                         "foreign_line": "", "refresh_line": "", "last_line": "", "via": "local"})
    return 200, {"hosts": rows}


def get_refresh(req):
    from halo_harness.host.refresh import status
    st = status(req.state_dir)
    return 200, {k: st[k] for k in ("line", "last_line", "review", "settings", "plan")}


ROUTES = {("GET", "local/idle"): get_idle, ("GET", "local/refresh"): get_refresh}
PATHS = {p for _m, p in ROUTES}


def dispatch_guard(req):
    if req.path not in PATHS:
        return None
    fn = ROUTES.get((req.method, req.path))
    return fn(req) if fn else (405, {"error": "method not allowed"})
