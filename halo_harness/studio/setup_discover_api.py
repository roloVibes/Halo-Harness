"""halo_harness.studio.setup_discover_api -- Find, Scan, Add and Measure in
Setup's Ollama card (Halo 3.3.0.0 R5; docs/STUDIO-setup.md "Find, Scan, Add,
Measure"): what `halo ollama discover [--lan] [--add] [--calibrate]` does, from
the page. Same loopback / origin / token guard as every Studio route.

    POST setup/ollama/find                 this machine's doors at once (about 4 s): {rows, notes, ports}
    POST setup/ollama/scan                 202 {job}: the network sweep (10 s cap) as a background job; 409 while one runs
    GET  setup/ollama/scan                 the latest scan frame (catch-up after a reload)
    POST setup/ollama/scan/stop            {stopping}: the page stops waiting; the sweep ends inside its cap
    POST setup/ollama/add {names | urls}   add_hosts over the rows Find / Scan listed -> {...state, lines, added, rows}
    POST setup/ollama/measure {hosts, models?, timeout?}
                                           202 {job}: one calibration per model of those hosts; 409 while one runs
    GET  setup/ollama/measure              the latest measure frame
    POST setup/ollama/measure/stop         {stopping}: ends after the model in hand

The jobs and their `setup` frames are studio/setup_discover_jobs.py. A row
is a found server `{url, name, version, models, configured, where}`
(providers/ollama_discover.py); Add never repoints a host and the first host
stays the default; Measure runs `run_calibration` with its own budget
(`timeout` overrides it per step) and records what settles in
`~/.halo/ollama-fit.json`. Under `BRIDGE_TEST_NO_BACKGROUND_NET=1` the scan
answers its one note and no rows, and Find asks only loopback on the ports
`ollama.discover.ports` names.
"""

from __future__ import annotations

from halo_harness.studio import setup_discover_jobs as J


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def _strings(value) -> list:
    return [str(v).strip() for v in value if str(v).strip()] if isinstance(value, list) else []


def _refused(lines: list):
    return 422, {"error": lines[0] if lines else "not done", "problems": list(lines)}


def _env(req):
    try:
        from halo_harness.studio.catalog_env import catalog_env
        return catalog_env(req.cwd)
    except Exception:
        return None


def _publisher(req):
    if req.server is None:
        return None
    from halo_harness.studio.events import bridge_for
    return bridge_for(req.server).publish_local


def post_find(req):
    from halo_harness.providers.ollama_discover import discover, discover_ports
    rows = discover("local", env=_env(req))
    J.remember(rows)
    return 200, {"rows": [r.as_dict() for r in rows], "notes": list(rows.notes), "ports": list(discover_ports())}


def post_scan(req):
    if J.alive("scan"):
        return 409, {"error": "a network scan is running (it ends inside its 10 s cap)", "job": J.latest("scan")}
    return 202, {"job": J.start_scan(_env(req), _publisher(req))}


def post_add(req):
    from halo_harness.providers.ollama_discover import add_hosts, reset_discover_cache, url_key
    from halo_harness.studio.setup_providers_api import _answer
    from halo_harness.studio.setup_providers_state import _config_list
    body = _body(req)
    names, urls = {n.lower() for n in _strings(body.get("names"))}, _strings(body.get("urls"))
    if not names and not urls:
        return _refused(["say which servers to add: names or urls (the rows Find or Scan listed)"])
    keys = {url_key(u) for u in urls}
    chosen = [r for r in J.found() if r.name.lower() in names or url_key(r.url) in keys]
    seen = {r.name.lower() for r in chosen} | {url_key(r.url) for r in chosen}
    missing = [n for n in sorted(names) if n not in seen] + [u for u in urls if url_key(u) not in seen]
    problems = [f"{m}: not found by Find or Scan in this Studio (Find again, or add it by hand above)" for m in missing]
    if not chosen:
        return _refused(problems)
    before = {str(h.get("name")) for h in _config_list("ollama.hosts")}
    lines = add_hosts(chosen) or ["nothing new to add: every server ticked is already in ollama.hosts"]
    hosts = _config_list("ollama.hosts")
    added = [str(h.get("name")) for h in hosts if str(h.get("name")) not in before]
    by_key = {url_key(str(h.get("url") or "")): str(h.get("name")) for h in hosts}
    for r in J.found():  # what the table shows next: the rows now in ollama.hosts are configured, under their names
        if url_key(r.url) in by_key:
            r.configured, r.name = True, by_key[url_key(r.url)]
    reset_discover_cache()
    code, answer = _answer(req, lines + problems)
    return code, {**answer, "added": added, "rows": J.found_dicts()}


def post_measure(req):
    from halo_harness.providers.ollama import resolve_ollama_hosts
    body = _body(req)
    wanted = _strings(body.get("hosts"))
    if not wanted:
        return _refused(["say which hosts to measure: hosts: [names] (ollama.hosts entries)"])
    known = {h.name.lower(): h for h in resolve_ollama_hosts()}
    unknown = [n for n in wanted if n.lower() not in known]
    if unknown:
        return _refused([f"no Ollama host named {n!r} in ollama.hosts" for n in unknown])
    timeout = body.get("timeout")
    if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0):
        return _refused(["timeout: a positive number of seconds (leave it out for the calibration's own budget)"])
    if J.alive("measure"):
        return 409, {"error": "a measurement is running", "job": J.latest("measure")}
    hosts = [known[n.lower()] for n in dict.fromkeys(wanted)]
    plan = J.plan_models([h.name for h in hosts], _strings(body.get("models")))
    return 202, {"job": J.start_measure(hosts, plan, float(timeout) if timeout else None, req.state_dir, _publisher(req))}


ROUTES = {("POST", "setup/ollama/find"): post_find,
          ("POST", "setup/ollama/scan"): post_scan,
          ("GET", "setup/ollama/scan"): lambda req: (200, J.latest("scan")),
          ("POST", "setup/ollama/scan/stop"): lambda req: (200, {"stopping": J.stop("scan")}),
          ("POST", "setup/ollama/add"): post_add,
          ("POST", "setup/ollama/measure"): post_measure,
          ("GET", "setup/ollama/measure"): lambda req: (200, J.latest("measure")),
          ("POST", "setup/ollama/measure/stop"): lambda req: (200, {"stopping": J.stop("measure")})}


def dispatch_setup_discover(req):
    """The answer for one of these routes, or None when the path is not one of them."""
    fn = ROUTES.get((req.method, req.path))
    if fn is not None:
        return fn(req)
    return (405, {"error": "method not allowed"}) if any(p == req.path for _m, p in ROUTES) else None


def discover_block() -> dict:
    """What `GET setup/state` carries for the card: the ports Find asks, the subnets Scan adds, the latest jobs."""
    from halo_harness.providers.ollama_discover import discover_ports, discover_subnets
    return {"ports": list(discover_ports()), "subnets": discover_subnets(), "scan": J.latest("scan"),
            "measure": J.latest("measure")}
