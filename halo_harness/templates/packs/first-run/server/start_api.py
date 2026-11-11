"""The first-run pack's Studio routes (Halo 3.1.1.0 R1 as studio/start_api.py; the pack's since 3.4.0.0 B), under
`/api/packs/first-run/start/...` behind Studio's token (server/routes.py hands them here):

    GET  start           {fresh, dismissed, show, own_lineups, active_team, runs, starts, job, plan, card, no_provider, auto}
                         (first_run/fresh.py; `job`: start_job.current(); `plan`: the seven steps; `card`: the card lines
                         shown above Run; `no_provider`: nothing for a run to run on yet; `auto`: the line shown in place of
                         Run on the Auto lineup, "" with a custom one)
    POST start           202 {job}: `halo start --yes` as a background job, its steps published as `start` frames on the
                         live feed (the pack's panel hears them through api.on); 409 while one runs; 422 {error, reason:
                         "no_provider" | "auto_lineup" | "no_lineup" | "no_coder"}
    POST dismiss         {dismissed: true} -- "Just look around", remembered for this home
    POST stop            {stopping}
"""

from __future__ import annotations

from ..first_run import fresh
from . import start_job


def _auto_line() -> str:
    from ..first_run.auto_gate import AUTO_LINE, offers_start
    return "" if offers_start() else AUTO_LINE


def get_start(ctx) -> "tuple[int, dict]":
    from halo_harness.ext import core as _core
    from ..first_run import fake
    from ..first_run.card import card_lines
    from ..first_run.steps import STEPS
    data = fresh.status(ctx.cwd, ctx.state_dir)
    data["job"] = start_job.current()
    data["no_provider"] = not _core.get("checks.provider", "ready")()[0]
    data["auto"] = _auto_line()
    data["plan"] = [{"step": n, "key": k, "title": title, "why": why, "state": "pending"}
                    for n, (k, title, why) in enumerate(STEPS, 1)]
    try:
        data["card"] = card_lines(state_dir=ctx.state_dir, cwd=ctx.cwd, fake=fake.enabled())
    except Exception as e:  # the panel still opens; the card says why it is short
        data["card"] = [f"the card could not be read: {type(e).__name__}: {e}"]
    return 200, data


def post_start(ctx) -> "tuple[int, dict]":
    from halo_harness.ext import core as _core
    from ..first_run import fake
    from ..first_run.auto_gate import AUTO_LINE, REASON
    from ..first_run.lineup import ready
    if start_job.running():
        return 409, {"error": "the guided first run is already running", "job": start_job.current()}
    if _auto_line():  # 3.3.15.0 R5: the guided first run belongs to a custom lineup
        return 422, {"error": AUTO_LINE, "reason": REASON, "problems": [AUTO_LINE]}
    line, reason = ready(state_dir=ctx.state_dir, cwd=ctx.cwd)  # 3.3.15.0 R7: the active lineup must take the lanes
    if line:
        return 422, {"error": line, "reason": reason, "problems": [line]}
    if not fake.enabled():
        ok, text = _core.get("checks.provider", "ready")()
        if not ok:
            return 422, {"error": text, "reason": "no_provider", "problems": [text]}

    def publish(frame: dict) -> None:
        ctx.publish("start", frame.get("data") or {})
    return 202, {"job": start_job.start(ctx.state_dir, publish)}


def post_dismiss(ctx) -> "tuple[int, dict]":
    fresh.dismiss(ctx.state_dir)
    return 200, {"dismissed": True}


def post_stop(ctx) -> "tuple[int, dict]":
    return 200, {"stopping": start_job.stop()}


ROUTES = {("GET", "start"): get_start, ("POST", "start"): post_start, ("POST", "dismiss"): post_dismiss,
          ("POST", "stop"): post_stop}
