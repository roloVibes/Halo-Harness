"""halo_harness.studio.start_api -- `/api/start`, Studio's "Start here" (Halo
3.1.1.0 R1). Same loopback / origin / token guard as every Studio route.

    GET  start           {fresh, dismissed, show, own_lineups, active_team, runs, starts, job, plan}
                         (start/fresh.py; `show`: the overlay comes up; `job`: start_job.current(); `plan`: the seven steps)
    POST start           202 {job}: `halo start --yes` as a background job, its steps streamed as `start` frames
                         on /api/events; 409 while one runs; 422 {error, reason: "no_provider"} with no model
    POST start/dismiss   {dismissed: true} -- "Just look around", remembered for this home
    POST start/stop      {stopping}
"""

from __future__ import annotations

import re

from halo_harness.start import fresh
from halo_harness.studio import start_job


def get_start(req):
    from halo_harness.start.steps import STEPS
    data = fresh.status(req.cwd, req.state_dir)
    data["job"] = start_job.current()
    data["plan"] = [{"step": n, "key": k, "title": title, "why": why, "state": "pending"}
                    for n, (k, title, why) in enumerate(STEPS, 1)]
    return 200, data


def _publisher(req):
    if req.server is None:
        return None
    from halo_harness.studio.events import bridge_for
    return bridge_for(req.server).publish_local


def post_start(req):
    if start_job.running():
        return 409, {"error": "the ten-minute start is already running", "job": start_job.current()}
    from halo_harness.start import fake
    if not fake.enabled():
        from halo_harness.start.provider import ready
        ok, text = ready()
        if not ok:
            return 422, {"error": text, "reason": "no_provider", "problems": [text]}
    return 202, {"job": start_job.start(req.state_dir, _publisher(req))}


def post_dismiss(req):
    fresh.dismiss(req.state_dir)
    return 200, {"dismissed": True}


def post_stop(req):
    return 200, {"stopping": start_job.stop()}


ROUTES = (("GET", r"^start$", get_start), ("POST", r"^start$", post_start),
          ("POST", r"^start/dismiss$", post_dismiss), ("POST", r"^start/stop$", post_stop))


def dispatch_start(req):
    for method, pattern, fn in ROUTES:
        if re.match(pattern, req.path) and method == req.method:
            return fn(req)
    if any(re.match(p, req.path) for _, p, _ in ROUTES):
        return 405, {"error": f"/api/{req.path} answers another method"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
