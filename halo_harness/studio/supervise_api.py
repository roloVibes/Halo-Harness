"""halo_harness.studio.supervise_api -- `/api/supervise/summary`, the Session
landing's morning line (Halo 3.1.8.0 R1). Read only; the same loopback +
token guard as every Studio route (studio/api.py dispatches it).

    GET supervise/summary   {running, pid, state, goals: {queued, running, done, parked},
                             done, waiting, cost_usd, line}

`line` is "N goals done, M waiting on you, $X" when a supervisor's pulse is
live, else "". The Session section shows it when the pulse is live; the
decisions that wait are the Attention queue's `goal_*` rows.
"""

from __future__ import annotations

import re


def get_summary(req):
    from halo_harness.supervise import history, pulse
    state_dir = req.state_dir
    p = pulse.read(state_dir)
    summ = history.summary(state_dir)
    line = ""
    if p["running"]:
        done, waiting, cost = summ["done"], summ["waiting"], summ["cost_usd"]
        line = (f"{done} goal{'' if done == 1 else 's'} done, "
                f"{waiting} waiting on you, ${cost:.2f}")
    return 200, {"running": p["running"], "pid": p["pid"], "state": p["state"], "goals": p.get("goals") or {},
                 "done": summ["done"], "waiting": summ["waiting"], "cost_usd": summ["cost_usd"], "line": line}


ROUTES = [("GET", r"^supervise/summary$", get_summary)]


def dispatch_supervise(req):
    for method, pattern, fn in ROUTES:
        if method == req.method and re.match(pattern, req.path):
            return fn(req)
    return None
