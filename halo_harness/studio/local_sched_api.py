"""halo_harness.studio.local_sched_api -- Halo 3.3.7.0 R3: the scheduler's routes (dispatched by
studio/local_api.dispatch_local; docs/STUDIO-local.md "Scheduling").

    GET  local/sched?lineup=<name>        the lineup's swap preview (local_sched/preview.py: the warm set per card, the
                                          swaps a pass, the hygiene lines) and the last Warm run's rows
    POST local/warm {lineup, dry?}        pre-warm its warm set (local_warm_cli.warm_lineup) in the background; GET
                                          local/sched shows the rows as they land
    GET  local/warm-set?host=<name>       the active lineup's warm set on that host: the Hosts card's line
    GET  local/place?lineup=<name>        where each lane's model should run (local_sched/place.solve)
    POST local/place {lineup}             write host_for on each moved lane's profile (Halo-side only)
    GET  local/loads?session=<id>         the session's loading tax (local_sched/loads.tally): the Cost panel

No route loads a model except POST local/warm; nothing changes a server setting.
"""

from __future__ import annotations

import threading

_RUNS: dict = {}  # lineup -> {running, rows, line}
_LOCK = threading.Lock()


def _lineup(req) -> str:
    body = req.body if isinstance(req.body, dict) else {}
    name = str(req.query.get("lineup") or body.get("lineup") or "").strip()
    if not name:
        from halo_harness.teams_runtime import active_team_name
        try:
            name = active_team_name(None) or ""
        except Exception:
            name = ""
    return name


def _slim(pv: dict) -> dict:
    keep = ("model", "lanes", "window", "window_from", "gb", "why", "load_s", "load_from", "warm_now", "never")
    hosts = [{**{k: ws.get(k) for k in ("host", "budget", "usable", "used", "swaps", "swap_s", "line", "helper")},
              **{part: [{k: m.get(k) for k in keep} for m in ws.get(part) or []] for part in ("warm", "pivots", "unknown")}}
             for ws in pv.get("hosts") or []]
    return {**{k: pv.get(k) for k in ("lineup", "swaps", "swap_s", "cards", "lines", "hygiene", "declared")},
            "hosts": hosts, "local": bool(pv.get("lanes"))}


def get_sched(req):
    from halo_harness.local_sched.preview import preview
    name = _lineup(req)
    if not name:
        return 422, {"error": "sched takes ?lineup=<name> (no lineup is in force)"}
    out = _slim(preview(name))
    with _LOCK:
        out["warm_run"] = dict(_RUNS.get(name) or {})
    return 200, out


def post_warm(req):
    from halo_harness.local_warm_cli import warm_lineup
    name = _lineup(req)
    if not name:
        return 422, {"error": "warm takes {lineup}"}
    dry = bool((req.body or {}).get("dry")) if isinstance(req.body, dict) else False
    with _LOCK:
        if (_RUNS.get(name) or {}).get("running"):
            return 409, {"error": f"a Warm of {name} is already running"}
        _RUNS[name] = {"running": True, "rows": [], "line": f"warming {name} ..."}

    def say(line: str) -> None:
        with _LOCK:
            _RUNS[name]["rows"].append(line.strip())

    def work() -> None:
        try:
            got = warm_lineup(name, dry=dry, say=say)
            line = got["line"]
        except Exception as e:  # the row says it; Studio shows the line
            line = f"halo local warm {name}: {type(e).__name__}: {e}"
        with _LOCK:
            _RUNS[name].update(running=False, line=line)
    threading.Thread(target=work, name=f"halo-warm-{name}", daemon=True).start()
    return 200, {"ok": True, "say": f"warming {name}'s warm set", "lineup": name}


def get_warm_set(req):
    from halo_harness.local_sched.preview import preview
    from halo_harness.local_sched.reserve import budget_line  # 3.3.7.0 R5: "1.2 GB reserved for ...; ... free for tasks"
    host = str(req.query.get("host") or "").strip()
    name = _lineup(req)
    held = budget_line(host, state_dir=req.state_dir) if host else ""
    if not host or not name:
        return 200, {"line": "", "host": host, "lineup": name, "claims_line": held}
    pv = preview(name)
    ws = next((w for w in pv.get("hosts") or [] if w.get("host") == host), None)
    return 200, {"host": host, "lineup": name, "line": (ws or {}).get("line") or "",
                 "swaps": (ws or {}).get("swaps") or 0, "claims_line": held}


def get_place(req):
    from halo_harness.local_place_cli import place_lineup
    got = place_lineup(_lineup(req) or None)
    return 200, {"lineup": got["lineup"], "line": got["line"], "rows": got["rows"], "local": bool(got["lanes"])}


def post_place(req):
    from halo_harness.local_place_cli import place_lineup
    from halo_harness.local_sched.place import apply
    plan = place_lineup(_lineup(req) or None)
    return 200, {"ok": True, "lineup": plan["lineup"], "written": apply(plan), "rows": plan["rows"]}


def get_loads(req):
    from halo_harness.local_sched.loads import tally
    from halo_harness.safe_id import is_safe_session_id
    sid = str(req.query.get("session") or "").strip()
    if not sid or not is_safe_session_id(sid):
        return 422, {"error": "loads takes ?session=<id>"}
    from halo_harness.local_sched.reserve import all_lines  # 3.3.7.0 R5: the reservations beside the loading tax
    return 200, {**tally(req.state_dir, sid), "claims": all_lines(req.state_dir)}


ROUTES = {("GET", "local/sched"): get_sched, ("POST", "local/warm"): post_warm, ("GET", "local/warm-set"): get_warm_set,
          ("GET", "local/place"): get_place, ("POST", "local/place"): post_place, ("GET", "local/loads"): get_loads}
PATHS = {p for _m, p in ROUTES}


def dispatch_sched(req):
    """The answer for a route of this file, else None."""
    if req.path not in PATHS:
        return None
    fn = ROUTES.get((req.method, req.path))
    return fn(req) if fn else (405, {"error": "method not allowed"})
