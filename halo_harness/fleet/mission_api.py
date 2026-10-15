"""halo_harness.fleet.mission_api -- every mission action, one function each,
`(status, body)` (Halo 3.0.6.0 "Fleet Missions" round R7). Studio's routes
(studio/fleet_mission_api.py), the hub port's loopback `local/mission` route
(`admin`, for a `halo fleet serve` in another process) and `halo fleet
mission` without either (this harness alone) all call these. `Ctx` carries
the home, the hub (or None), how frames are published and who acts.

`LEAD` and `JUDGE` (None: the real model calls through the provider layer)
are what tests replace with fakes.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from halo_harness.fleet import journal
from halo_harness.fleet import mission as M
from halo_harness.fleet import mission_plan as P
from halo_harness.fleet import mission_run as R
from halo_harness.fleet import mission_store as S
from halo_harness.fleet.mission_dispatch import Dispatch

LEAD: Optional[Callable] = None
JUDGE: Optional[Callable] = None


class Ctx:
    def __init__(self, home, hub=None, publish: Optional[Callable] = None, by: str = "", cwd=None) -> None:
        self.home, self.hub, self.by, self.cwd = home, hub, by, cwd
        self.publish = publish or (hub.state.publish if hub is not None else None)
        self.dispatch = Dispatch(home, hub)
        if hub is not None and not getattr(hub.state, "mission_sink", False):  # members' claim refusals reach the log
            hub.state.mission_sink = True
            hub.state.sinks.append(lambda f, h=home: _claim_sink(h, f, hub.state.publish))

    def hub_info(self) -> dict:
        from halo_harness.fleet.identity import fleet_name, harness
        if self.hub is not None:
            return {"id": self.hub.state.identity.get("id"), "name": self.hub.state.name}
        return {"id": harness(self.home)["id"], "name": fleet_name(self.home)}


def _claim_sink(home, f: dict, publish) -> None:
    data = f.get("data") if isinstance(f, dict) and isinstance(f.get("data"), dict) else {}
    if f.get("event") == "fleet" and data.get("action") == "mission_claim":
        R.note_claim(home, f, publish)


def _err(e: M.MissionError) -> "tuple[int, dict]":
    return e.status, {"error": str(e), "problems": []}


def _view(ctx: Ctx, mid: str) -> dict:
    doc = S.need(ctx.home, mid)
    return {"mission": doc, "plan": P.load_plan(ctx.home, mid), "summary": M.summary(doc),
            "running": R.get(ctx.home, mid) is not None}


def _frame(ctx: Ctx, mid: str, state: str, **extra) -> None:
    R.frame(ctx.publish, ctx.hub_info().get("id"), {"id": mid, "state": state, **extra})


def _journal(ctx: Ctx, kind: str, mid: str, **fields) -> None:
    info = ctx.hub_info()
    journal.append(ctx.home, kind, harness=info.get("id"), harness_name=info.get("name"), mission=mid, by=ctx.by or None, **fields)


def list_missions(ctx: Ctx) -> "tuple[int, dict]":
    return 200, {"missions": [M.summary(d) for d in reversed(S.all_docs(ctx.home))], "at": time.time(),
                 "root_shared": M.shared_dir(ctx.home) is not None}


def _plan(ctx: Ctx, mid: str) -> dict:
    view = ctx.dispatch.view()
    plan = P.plan(ctx.home, mid, ctx.dispatch.entries(view), call_model=LEAD, load=Dispatch.load(view), by=ctx.by)
    _journal(ctx, "mission_planned", mid, parts=len(plan["parts"]))
    _frame(ctx, mid, "planned")
    return plan


def create(ctx: Ctx, body: dict) -> "tuple[int, dict]":
    goal = " ".join(str(body.get("goal") or "").split())
    if not goal:
        return 422, {"error": "a mission needs a goal: one or more sentences", "problems": ["goal"]}
    try:
        budget = float(body["budget_usd"]) if body.get("budget_usd") not in (None, "") else None
    except (TypeError, ValueError):
        return 422, {"error": "budget_usd is a number of dollars", "problems": ["budget_usd"]}
    repo, root = None, None
    if body.get("repo", True) is not False and ctx.cwd is not None:
        from halo_harness.remote import fleet_identity as FI
        proj = FI.project(ctx.cwd, refresh=True)
        if proj.get("repo"):
            from halo_harness.orchestra import gitops
            root = proj["root"]
            repo = {"name": proj["repo"], "base": gitops.head(root), "branch": proj.get("branch")}
    mid = M.new_id()
    doc = M.new_doc(mid=mid, goal=goal, constraints=str(body.get("constraints") or "").strip(), prefer=M.names(body.get("prefer")),
                    budget_usd=budget, test=str(body.get("test") or "").strip(), hub=ctx.hub_info(), repo=repo,
                    shared=M.shared_dir(ctx.home) is not None, by=ctx.by)
    S.create(ctx.home, doc)
    if root:
        S.set_local(ctx.home, mid, repo_root=str(root))
    _frame(ctx, mid, "drafted")
    try:
        _plan(ctx, mid)
    except M.MissionError as e:
        status, out = _err(e)
        return status, {**out, "id": mid, **_view(ctx, mid)}
    return 200, _view(ctx, mid)


def get(ctx: Ctx, mid: str) -> "tuple[int, dict]":
    try:
        return 200, _view(ctx, mid)
    except M.MissionError as e:
        return _err(e)


def replan(ctx: Ctx, mid: str) -> "tuple[int, dict]":
    try:
        _plan(ctx, mid)
        return 200, _view(ctx, mid)
    except M.MissionError as e:
        return _err(e)


def edit_part(ctx: Ctx, mid: str, pid: str, body: dict) -> "tuple[int, dict]":
    try:
        view = ctx.dispatch.view()
        P.edit(ctx.home, mid, pid, ctx.dispatch.entries(view), harness=str(body.get("harness") or "") or None,
               drop=body.get("drop") is True, load=Dispatch.load(view), by=ctx.by)
        _frame(ctx, mid, "planned", part=str(pid))
        return 200, _view(ctx, mid)
    except M.MissionError as e:
        return _err(e)


def approve(ctx: Ctx, mid: str) -> "tuple[int, dict]":
    from halo_harness.fleet.mission_plan_check import ready
    try:
        doc = S.need(ctx.home, mid)
        if doc["state"] == "approved":
            return 200, _view(ctx, mid)
        problems = ready(P.load_plan(ctx.home, mid))
        if doc["state"] != "planned" or problems:
            return 409, {"error": f"mission {mid} is {doc['state']}" if not problems else "; ".join(problems),
                         "problems": problems}

        def apply(d: dict) -> None:
            M.move(d, "approved", "approved", ctx.by)
            d["approved_by"] = ctx.by or None
            M.decide(d, "approved the plan", ctx.by)
        S.update(ctx.home, mid, apply)
        _journal(ctx, "mission_approved", mid)
        _frame(ctx, mid, "approved")
        return 200, _view(ctx, mid)
    except M.MissionError as e:
        return _err(e)


def run(ctx: Ctx, mid: str) -> "tuple[int, dict]":
    """Approve (when planned), then run; a running mission's runner is picked up again."""
    try:
        doc = S.need(ctx.home, mid)
        if doc["state"] == "planned":
            status, out = approve(ctx, mid)
            if status != 200:
                return status, out
        elif doc["state"] not in ("approved", "running"):
            return 409, {"error": f"mission {mid} is {doc['state']}; only an approved mission runs", "problems": []}
        if S.need(ctx.home, mid)["state"] == "approved":
            S.update(ctx.home, mid, lambda d: M.move(d, "running", "run", ctx.by))
            S.log(ctx.home, mid, "running", by=ctx.by or None)
            _journal(ctx, "mission_run", mid)
            _frame(ctx, mid, "running")
        R.ensure(ctx.home, mid, ctx.dispatch, publish=ctx.publish, judge=JUDGE, by=ctx.by)
        return 200, _view(ctx, mid)
    except M.MissionError as e:
        return _err(e)


def stop(ctx: Ctx, mid: str, reason: str = "") -> "tuple[int, dict]":
    reason = " ".join(str(reason or "").split())[:300] or f"stopped by {ctx.by or 'the owner'}"
    try:
        doc = S.need(ctx.home, mid)
        if doc["state"] in M.FINAL:
            return 409, {"error": f"mission {mid} is already {doc['state']}", "problems": []}
        S.update(ctx.home, mid, lambda d: M.decide(d, f"stopped the mission: {reason}", ctx.by))
        runner = R.get(ctx.home, mid)
        if runner is not None:
            runner.request_stop(reason)
            runner.join(30.0)
        else:
            if doc["state"] in ("running", "merging"):
                for pid, ps in doc["parts"].items():
                    if ps.get("state") in M.PART_LIVE:
                        ctx.dispatch.stop(doc, pid, ps, reason)
            R.Runner(ctx.home, mid, ctx.dispatch, publish=ctx.publish, by=ctx.by)._end("stopped", reason)
        return 200, _view(ctx, mid)
    except M.MissionError as e:
        return _err(e)


def report(ctx: Ctx, mid: str) -> "tuple[int, dict]":
    from halo_harness.fleet import mission_report
    try:
        doc = S.need(ctx.home, mid)
        plan = P.load_plan(ctx.home, mid) or {}
        rep = mission_report.build(ctx.home, doc, plan)
        return 200, {"report": rep, "markdown": mission_report.markdown(rep), "final": doc["state"] in M.FINAL}
    except M.MissionError as e:
        return _err(e)


def files(ctx: Ctx, mid: str, path: str = "") -> "tuple[int, dict]":
    """Text files of the mission folder (the UI): a listing, or one file's text (confined like mission_files)."""
    try:
        base = S.folder(ctx.home, mid)
        S.need(ctx.home, mid)
        if not path:
            return 200, {"mission": mid, "files": S.files(base)}
        target = S.confine(base, path)
        if not target.is_file():
            return 404, {"error": f"no file {path} in mission {mid}"}
        raw = target.read_bytes()[:2_000_000]
        if b"\x00" in raw[:8192]:
            return 415, {"error": f"{path} is not a text file", "size": target.stat().st_size}
        return 200, {"mission": mid, "path": S.clean_rel(path), "size": target.stat().st_size,
                     "text": raw.decode("utf-8", errors="replace"), "truncated": target.stat().st_size > len(raw)}
    except S.PathRefused as e:
        return 400, {"error": str(e)}
    except M.MissionError as e:
        return _err(e)


def admin(home, hub, body: dict) -> "tuple[int, dict]":
    """The hub port's `local/mission` route: `{op, id?, part?, ...}` from this machine's `halo fleet mission`."""
    from halo_harness.fleet.identity import fleet_name
    ctx = Ctx(home, hub, by=str(body.get("by") or fleet_name(home)), cwd=body.get("cwd"))
    op, mid = str(body.get("op") or ""), str(body.get("id") or "")
    table = {"list": lambda: list_missions(ctx), "new": lambda: create(ctx, body), "get": lambda: get(ctx, mid),
             "plan": lambda: replan(ctx, mid), "edit": lambda: edit_part(ctx, mid, str(body.get("part") or ""), body),
             "approve": lambda: approve(ctx, mid), "run": lambda: run(ctx, mid),
             "stop": lambda: stop(ctx, mid, str(body.get("reason") or "")), "report": lambda: report(ctx, mid),
             "files": lambda: files(ctx, mid, str(body.get("path") or ""))}
    fn = table.get(op)
    return fn() if fn else (400, {"error": f"op is one of {', '.join(table)}, got {op!r}"})
