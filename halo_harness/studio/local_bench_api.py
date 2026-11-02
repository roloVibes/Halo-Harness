"""halo_harness.studio.local_bench_api -- Halo 3.3.6.0 R5: Local's bench routes (dispatched by
studio/local_api.dispatch_local; docs/STUDIO-local-routes.md). Every answer carries `cli`, the `halo local bench` line
that does the same, and `cost`, the line said before the run (local: time and a busy card, never dollars).

    GET  local/host/<name>/bench?model=&quick=   {jobs (that host's), cost, cli, via?, offer?}: catch-up, and the cost
                                                 line the Bench button shows as its confirmation (3.3.8.1: with the
                                                 link's tail and the offer line over the LAN)
    POST local/host/<name>/bench {model, quick?}  a bench job (studio/local_bench_job.py; `bench` frames); 409 with one
                                                 line while the host had a call in the last minute, a session uses it,
                                                 or another bench runs there; 3.3.7.0 R2: a host a paired halo host
                                                 serves (with `control`): the host runs it (control/bench), its frames
                                                 come here (without it: 409, the grant line); 3.3.8.1: any other host
                                                 this machine does not serve (no paired halo host on it): it runs
                                                 over the LAN from here, `via` "over the LAN from <here>", the card
                                                 labelled with the link, `offer` the way to a card without it
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


def _cost(host, model: str, quick: bool, state_dir, label: str = "") -> str:
    from halo_harness.providers.fit_meter import host_card_of
    from halo_harness.providers.local_bench import estimate
    try:
        return estimate(host, model, card=host_card_of(host), state_dir=state_dir, quick=quick, label=label)[1]
    except Exception:
        from halo_harness.providers.local_bench import cost_line
        return cost_line(host.name, 5, label)


def _lan(req, host, ctl: dict, here: bool):
    """3.3.8.1: the LAN fields when the bench runs directly from here (no host path takes it), else None."""
    if here or ctl.get("via") == "host":  # a paired halo host serves it: its path (or its grant line), unchanged
        return None
    from halo_harness.providers.local_bench_link import from_where, link_line, over_lan
    return over_lan(host, req.state_dir) or {"over_lan": True, "measured_from": from_where(req.state_dir),
                                             "link": {"rtt_ms": None, "kind": None, "line": link_line(None, None)},
                                             "label": ""}


def _offer(host, lan) -> dict:
    from halo_harness.providers.local_bench_link import offer_line
    return {"via": f"over the LAN from {lan['measured_from']}", "offer": offer_line(host.url, host.name, bench=True)}


def get_bench(req, name: str):
    from halo_harness.studio.local_bench_job import current
    from halo_harness.studio.local_control_api import _target
    model, quick = str(req.query.get("model") or "").strip(), _truthy(req.query.get("quick"))
    host, ctl, here = _target(req, name) if model else (None, None, True)
    if model and (host is None or ctl is None):
        return 404, {"error": f"no host named {name!r} here"}
    out = {**current(name)}
    if model:
        lan = _lan(req, host, ctl, here)
        out.update(cost=_cost(host, model, quick, req.state_dir, (lan or {}).get("label") or ""), cli=cli(name, model, quick),
                   **(_offer(host, lan) if lan else {}))
    elif not _known(name):
        return 404, {"error": f"no host named {name!r} here"}
    return 200, out


def _known(name: str) -> bool:
    from halo_harness.providers.ollama import resolve_ollama_host
    return resolve_ollama_host(name) is not None


def post_bench(req, name: str):
    from halo_harness.providers.local_bench_runs import busy
    from halo_harness.studio import local_bench_job as J
    from halo_harness.studio.local_control_api import _pub, _target
    body = req.body if isinstance(req.body, dict) else {}
    model = str(body.get("model") or body.get("name") or "").strip()
    quick = body.get("quick") is True
    if not model:
        return 422, {"error": "bench takes {model}", "problems": ["model: the model to bench"]}
    host, ctl, here = _target(req, name)
    if ctl is None or host is None:
        return 404, {"error": f"no host named {name!r} here" if ctl is None else ctl.get("why") or "no address here"}
    if not here and ctl.get("ok") and ctl.get("via") == "host":  # 3.3.7.0 R2: the bench runs on the host (control/bench)
        from halo_harness.studio.local_host_acts import send, waiter
        code, ans = send(ctl, "bench", {"model": model, "quick": quick})
        if code != 200 or not ans.get("job"):
            return (code if code >= 400 else 409), {"error": ans.get("error") or ans.get("line") or "the host did not start it"}
        view = J.start(host, model, _pub(req), state_dir=req.state_dir, quick=quick, cost=ans.get("say") or "",
                       runner=waiter(ctl, ans["job"], save_card_as=name))
        return 200, {**view, "via": ctl.get("via_line"), "host_job": ans["job"], "cli": cli(name, model, quick)}
    if not here and ctl.get("via") == "host":  # paired, without `control`: the host's grant line (Request control)
        from halo_harness.studio.local_control_api import _refused
        return _refused(ctl)
    lan = _lan(req, host, ctl, here)  # 3.3.8.1: no host path takes it -- the bench runs over the LAN from here
    other = J.running_on(name)
    if other is not None and other.get("model") != model:
        return 409, {"error": f"a bench of {other['model']} runs on {name} now: one bench per card at a time"}
    why = busy(req.state_dir, name) if other is None else ""
    if why:
        return 409, {"error": why}
    from halo_harness.studio.ollama_hosts_view import card_of
    cost = _cost(host, model, quick, req.state_dir, (lan or {}).get("label") or "")
    runner = None
    if lan:
        from halo_harness.providers.local_bench import bench as run_bench

        def runner(h, m, **kw):
            return run_bench(h, m, lan=lan, **kw)
    view = J.start(host, model, _pub(req), state_dir=req.state_dir, quick=quick, cost=cost, card=card_of(host), runner=runner)
    return 200, {**view, "cost": cost, "cli": cli(name, model, quick), **(_offer(host, lan) if lan else {})}


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
