"""halo_harness.studio.local_probe_api -- Halo 3.3.6.0 R1: Local's battery
routes (dispatched by studio/local_api.dispatch_local; docs/STUDIO-local.md).
Every answer carries `cli`, the `halo models probe` line that does the same,
and `cost`, the line said before the run.

    POST local/host/<name>/probe {model, force?}   a probe job (studio/local_probe_job.py; `probe` frames);
                                                   a host a fleet member serves: that member's own job
                                                   (fleet/control_models.py `ollama_probe`, under its
                                                   fleet.allow_control)
    GET  local/probes                              the jobs running and the last ended ones
    GET  local/profiles?host=                      every profile in the capability cache (that host's only
                                                   with ?host=), without the raw evidence
"""

from __future__ import annotations

import re
import urllib.parse

_PROBE = re.compile(r"^local/host/(?P<name>[^/]+)/probe$")


def cli(name: str, model: str, force: bool = False) -> str:
    return f"halo models probe {model} --host {name}" + (" --force" if force else "")


def post_probe(req, name: str):
    from halo_harness.providers.capability_battery import cost_line
    from halo_harness.studio import local_probe_job as J
    from halo_harness.studio.local_control_api import _forward, _pub, _refused, _target
    body = req.body if isinstance(req.body, dict) else {}
    model = str(body.get("model") or body.get("name") or "").strip()
    force = body.get("force") is True
    if not model:
        return 422, {"error": "probe takes {model}", "problems": ["model: the model to probe"]}
    host, ctl, here = _target(req, name)
    if ctl is None:
        return 404, {"error": f"no host named {name!r} here"}
    if not ctl.get("ok"):
        return _refused(ctl)
    extra = {"cli": cli(name, model, force), "cost": cost_line(model, name)}
    if here and host is not None:
        return 200, {**J.start(host, model, _pub(req), state_dir=req.state_dir, force=force), **extra}

    def send(more: dict):
        return _forward(req, ctl, "probe", {"model": model, "force": force, **more})
    code, view = J.start_remote(name, model, send, ctl.get("via") or "", _pub(req), member=ctl.get("member") or "")
    return code, {**view, **extra}


def get_profiles(req):
    from halo_harness.providers.ollama_capability import all_profiles
    from halo_harness.studio.local_probe_job import compact, current
    host = str(req.query.get("host") or "").strip()
    rows = [compact(p) for p in all_profiles(req.state_dir) if not host or p.get("host") == host
            or p.get("from_host") == host]
    return 200, {"profiles": rows, "probing": current()["jobs"]}


def dispatch_probe(req):
    """The answer for a route of this file, else None."""
    if req.path == "local/probes":
        from halo_harness.studio.local_probe_job import current
        return (200, current()) if req.method == "GET" else (405, {"error": "method not allowed"})
    if req.path == "local/profiles":
        return get_profiles(req) if req.method == "GET" else (405, {"error": "method not allowed"})
    m = _PROBE.match(req.path)
    if not m:
        return None
    if req.method != "POST":
        return 405, {"error": "method not allowed"}
    return post_probe(req, urllib.parse.unquote(m.group("name")))
