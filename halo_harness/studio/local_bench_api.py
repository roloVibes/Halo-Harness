"""halo_harness.studio.local_bench_api -- Halo 3.3.6.0 R5: Local's bench routes (dispatched by
studio/local_api.dispatch_local; docs/STUDIO-local-routes.md). Every answer carries `cli`, the `halo local bench` line
that does the same, and `cost`, the line said before the run (local: time and a busy card, never dollars).

    GET  local/host/<name>/bench?model=&quick=   {jobs (that host's), cost, cli}: catch-up, and the cost line the
                                                 Bench button shows as its confirmation
    POST local/host/<name>/bench {model, quick?}  a bench job (studio/local_bench_job.py; `bench` frames); 409 with one
                                                 line while the host had a call in the last minute, a session uses it,
                                                 or another bench runs there; a host a fleet member serves: 409 (that
                                                 machine's own Studio benches it)
    GET  local/benches?host=                     per host every installed model and its speed card (stale marked),
                                                 the Benchmarks page's table, and the jobs
"""

from __future__ import annotations

import re
import urllib.parse

_BENCH = re.compile(r"^local/host/(?P<name>[^/]+)/bench$")


def cli(name: str, model: str, quick: bool = False) -> str:
    return f"halo local bench --host {name} --model {model}" + (" --quick" if quick else "")


def _truthy(v) -> bool:
    return v is True or str(v).lower() in ("1", "true", "yes", "on")


def _cost(host, model: str, quick: bool, state_dir) -> str:
    from halo_harness.providers.fit_meter import host_card_of
    from halo_harness.providers.local_bench import estimate
    try:
        return estimate(host, model, card=host_card_of(host), state_dir=state_dir, quick=quick)[1]
    except Exception:
        from halo_harness.providers.local_bench import cost_line
        return cost_line(host.name, 5)


def get_bench(req, name: str):
    from halo_harness.providers.ollama import resolve_ollama_host
    from halo_harness.studio.local_bench_job import current
    host = resolve_ollama_host(name)
    if host is None:
        return 404, {"error": f"no host named {name!r} here"}
    model, quick = str(req.query.get("model") or "").strip(), _truthy(req.query.get("quick"))
    out = {**current(name)}
    if model:
        out.update(cost=_cost(host, model, quick, req.state_dir), cli=cli(name, model, quick))
    return 200, out


def post_bench(req, name: str):
    from halo_harness.providers.local_bench_runs import busy
    from halo_harness.studio import local_bench_job as J
    from halo_harness.studio.local_control_api import _pub, _refused, _target
    body = req.body if isinstance(req.body, dict) else {}
    model = str(body.get("model") or body.get("name") or "").strip()
    quick = body.get("quick") is True
    if not model:
        return 422, {"error": "bench takes {model}", "problems": ["model: the model to bench"]}
    host, ctl, here = _target(req, name)
    if ctl is None or host is None:
        return 404, {"error": f"no host named {name!r} here"}
    if not ctl.get("ok"):
        return _refused(ctl)
    if not here:
        return 409, {"error": f"{name} is served by another machine: its own Studio benches it (halo local bench there)"}
    other = J.running_on(name)
    if other is not None and other.get("model") != model:
        return 409, {"error": f"a bench of {other['model']} runs on {name} now: one bench per card at a time"}
    why = busy(req.state_dir, name) if other is None else ""
    if why:
        return 409, {"error": why}
    from halo_harness.studio.ollama_hosts_view import card_of
    cost = _cost(host, model, quick, req.state_dir)
    view = J.start(host, model, _pub(req), state_dir=req.state_dir, quick=quick, cost=cost, card=card_of(host))
    return 200, {**view, "cost": cost, "cli": cli(name, model, quick)}


def get_benches(req):
    from halo_harness.ollama_steward.profiles import short_model
    from halo_harness.providers.local_bench_runs import _now_version, load, stale, view
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.studio import ollama_hosts_view as V
    from halo_harness.studio.local_bench_job import current
    want = str(req.query.get("host") or "").strip()
    hosts = []
    for h in resolve_ollama_hosts():
        if want and h.name != want:
            continue
        version, rows = _now_version(h.name), []
        for r in V.catalog_of(h).get("models") or []:
            if not isinstance(r, dict):
                continue
            m = short_model(r.get("model") or r.get("name"))
            sc = load(req.state_dir, h.name, m, r.get("digest")) or load(req.state_dir, h.name, m)
            rows.append({"model": m, "size": r.get("size"), "digest": r.get("digest"),
                         "card": view(sc, stale(sc, digest=r.get("digest"), version=version)) if sc else None})
        rows.sort(key=lambda x: (x["card"] is None, -int(x.get("size") or 0)))
        hosts.append({"name": h.name, "version": version, "models": rows})
    return 200, {"hosts": hosts, **current()}


def dispatch_bench(req):
    """The answer for a route of this file, else None."""
    if req.path == "local/benches":
        return get_benches(req) if req.method == "GET" else (405, {"error": "method not allowed"})
    m = _BENCH.match(req.path)
    if not m:
        return None
    name = urllib.parse.unquote(m.group("name"))
    if req.method == "GET":
        return get_bench(req, name)
    return post_bench(req, name) if req.method == "POST" else (405, {"error": "method not allowed"})
