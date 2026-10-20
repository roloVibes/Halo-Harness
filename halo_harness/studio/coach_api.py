"""halo_harness.studio.coach_api -- the post-run coach's Studio routes (Halo
3.0.9.0 round R3; orchestra/coach.py). studio/api.py's `dispatch` sends
these paths here before the section dispatchers:

    GET orchestra/<run>/coach        an Orchestra run of Studio's repo
    GET fleet/missions/<id>/coach    a mission in this harness's missions folder
    GET team/coach?run=              a team run of Studio's repo (the latest when run is empty)

Each answers the coach's result `{run, kind, suggestions, evidence, model,
computed, source_mtime, cached}` (each suggestion with its `paragraph`,
`paragraph_error` and `applied` state), computed once and kept in
`<run>/coach.json` until a run file it reads is newer (coach.cached).

3.1.3.0 R1, the same paths plus a verb, POST only (team: `?run=` too):

    POST <coach path>/ask    {id, refresh?}   the lead's paragraph -> {id, paragraph, error, model, role, cached}
    POST <coach path>/apply  {id, confirm?}   confirm false: the confirm card {preview} (nothing written);
                                              confirm true: write it -> {preview, applied: <the record row>}
    POST <coach path>/undo   {apply_id}       put the file back -> {ok, message, apply_id}; 409 with the reason

404 for an unknown run, 405 for another method, 422 when the change cannot be made.

3.1.6.0 R2, an Orchestra run only (orchestra/coach_probe.py):

    POST orchestra/<run>/coach/probe {k?, confirm?}   confirm false: {estimate: {runs, cap_usd, total_usd, line, ...},
                                                      running} (nothing runs); confirm true: 202 {started, estimate}, the
                                                      probe on a thread (studio/coach_probe_job.py); 409 while one runs;
                                                      422 for a mission, a team run or a run with no report

The orchestra coach's GET answer carries `probe` (its status, with `live`: a
probe of the run runs in this Studio) and, once one ended, the probe's card first.

3.1.6.0 R3, the improvement library (orchestra/coach_library.py): every GET
answer carries `library` (the entries the coach cites for the run),
`library_line` and each suggestion's `library_hits`, and

    POST coach/library/<entry>/forget                  deletes the entry's folder -> {ok, entry, message}; 404 unknown
"""

from __future__ import annotations

import re
from pathlib import Path

_RUN = r"[A-Za-z0-9_-]+"
_VERB = r"(?:/(?P<verb>ask|apply|undo|probe))?$"
PATTERNS = (("orchestra", rf"^orchestra/(?P<run>{_RUN})/coach{_VERB}"),
            ("mission", rf"^fleet/missions/(?P<run>m-\d{{8}}-[0-9a-f]{{4}})/coach{_VERB}"), ("team", rf"^team/coach{_VERB}"))
LIBRARY = r"^coach/library/(?P<entry>e-\d{8}-[0-9a-f]{4})/forget$"


def _orchestra_dir(req, ref):
    from halo_harness.studio import orchestra_model as OM
    return OM.find_run(OM.repo_of(req.cwd), ref)


def _mission_dir(req, ref):
    from halo_harness.fleet import mission_store as S
    folder = S.folder(req.state_dir, ref)
    return folder if (folder / "mission.json").is_file() else None


def _team_dir(req, ref):
    from halo_harness.team import board as BD
    from halo_harness.team.spec import team_root
    return BD.find_run(team_root(req.cwd), ref or None)


FINDERS = {"orchestra": _orchestra_dir, "mission": _mission_dir, "team": _team_dir}
WHAT = {"orchestra": "Orchestra run", "mission": "mission", "team": "team run"}


def match(path: str):
    for kind, pattern in PATTERNS:
        m = re.match(pattern, path)
        if m:
            return kind, m.groupdict().get("run"), m.groupdict().get("verb")
    return None


def _cwd_of(kind: str, run_dir, req):
    if kind == "orchestra":
        from halo_harness.orchestra.goal import repo_root_of
        return repo_root_of(run_dir)
    return req.cwd


def _publisher(req):
    if getattr(req, "server", None) is None:
        return None
    from halo_harness.studio.events import bridge_for
    return bridge_for(req.server).publish_local


def _probe(kind: str, run_dir, body: dict, cwd, req):
    """3.1.6.0 R2: the probe's cost line, or its start on a thread."""
    from halo_harness.orchestra import coach_probe as CP
    if kind != "orchestra" or not (Path(run_dir) / "report.json").is_file():
        return 422, {"error": "a probe runs an Orchestra run's goal again: it takes an Orchestra run that has its report"}
    k = body.get("k") if isinstance(body.get("k"), int) and not isinstance(body.get("k"), bool) else None
    est = CP.estimate(run_dir, k)
    if not body.get("confirm"):
        return 200, {"estimate": est, "running": CP.live(run_dir)}
    if CP.live(run_dir):
        return 409, {"error": f"a probe of run {Path(run_dir).name} is running", "estimate": est}
    from halo_harness.studio import coach_probe_job
    started = coach_probe_job.start(run_dir, k=est["k"], cwd=cwd, state_dir=req.state_dir, publish=_publisher(req))
    return (202 if started else 409), {"started": started, "estimate": est}


def _verb(verb: str, kind: str, run_dir, result: dict, req):
    body = req.body if isinstance(req.body, dict) else {}
    cwd = _cwd_of(kind, run_dir, req)
    if verb == "probe":
        return _probe(kind, run_dir, body, cwd, req)
    if verb == "ask":
        from halo_harness.orchestra.coach_ask import ask
        return 200, ask(run_dir, result, str(body.get("id") or ""), refresh=bool(body.get("refresh")), cwd=cwd,
                        state_dir=req.state_dir)
    if verb == "undo":
        from halo_harness.orchestra.coach_record import undo
        ok, message, rec = undo(str(body.get("apply_id") or "") or None, req.state_dir)
        return (200 if ok else 409), {"ok": ok, "message": message, "error": "" if ok else message,
                                      "apply_id": (rec or {}).get("apply_id")}
    from halo_harness.orchestra import coach_apply as CA
    try:
        p = CA.preview(result, str(body.get("id") or ""), run_dir, cwd=cwd, state_dir=req.state_dir)
        if not body.get("confirm"):
            return 200, {"preview": p, "applied": None}
        return 200, {"preview": p, "applied": CA.apply(result, p["id"], run_dir, cwd=cwd, state_dir=req.state_dir)}
    except CA.ApplyError as e:
        return 422, {"error": str(e)}


def _library(req, entry: str):
    """3.1.6.0 R3: `POST coach/library/<entry>/forget` deletes that entry's folder (orchestra/coach_library.py)."""
    if req.method != "POST":
        return 405, {"error": "method not allowed"}
    from halo_harness.orchestra.coach_library import forget
    if not forget(entry, req.state_dir):
        return 404, {"error": f"no library entry {entry!r}"}
    return 200, {"ok": True, "entry": entry, "message": f"forgot {entry}: its folder is deleted"}


def dispatch_coach(req):
    """The coach's answer for `req`, or None when the path is not a coach route."""
    lib = re.match(LIBRARY, req.path)
    if lib:
        return _library(req, lib.group("entry"))
    hit = match(req.path)
    if hit is None:
        return None
    kind, ref, verb = hit
    if req.method != ("POST" if verb else "GET"):
        return 405, {"error": "method not allowed"}
    if kind == "team":
        ref = str(req.query.get("run") or "")
    run_dir = FINDERS[kind](req, ref)
    if run_dir is None or not Path(run_dir).is_dir():
        return 404, {"error": f"no {WHAT[kind]} {ref!r}" if ref else f"no {WHAT[kind]} yet"}
    from halo_harness.orchestra.coach import cached
    try:
        result = cached(run_dir, state_dir=req.state_dir)
    except ValueError as e:
        return 404, {"error": str(e)}
    if kind == "orchestra":
        from halo_harness.orchestra.coach_probe import live
        result = dict(result, probe=dict(result.get("probe") or {}, live=live(run_dir)))
    return _verb(verb, kind, run_dir, result, req) if verb else (200, result)
