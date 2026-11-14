"""halo_harness.studio.replays_api -- Studio's `replays/*` routes (Halo 3.4.1.0 R1 "Time"): save a session's replay
as one file, list and open saved ones, take one in from another machine, and film a clip of a range. Core: they read
this machine's sessions and `<state>/replays/` only, with the fleet pack on or off. docs/REPLAY.md.

    GET  replays                          {dir, replays: [row]}  newest first (live/replay_file.row)
    GET  replays/plan?session=<sid>[&lineup=] | ?run=<run-id>   what Save would write, nothing written: {id, path, bytes, includes}
    POST replays/save  {session, lineup?, id?} | {run, id?}       {ok, id, path, bytes, includes, row}; `id`: the plan's
                                          (3.4.1.1: the file is written under the name the dialog showed)
    GET  replays/compare?a=<ref>&b=<ref>[&split=<s>]   two runs side by side (live/compare.py), nothing written;
                                          ref: session:<id> | run:<id> | file:<id>; the same ref twice splits it at `split`
    GET  replays/report?ref=<ref>         3.4.1.0 R3: the run report card (live/report_card.py) -> {card, markdown}; ref as
                                          compare's; a mission's report is the fleet pack's (422); nothing written
    POST replays/import {text}                  a file chosen in History: checked, kept under replays/ -> {ok, id, path, row}
    GET  replays/<id>                     the file's payload (format halo-replay, version 1)
    GET  replays/<id>/clip?from&to&speed  what Export a clip would film and write, nothing written
    POST replays/<id>/clip {from, to, speed}    films it (headless Chrome on this Studio) -> {ok, path, name, bytes, ...}
    GET  replays/clips/<name>             the clip's bytes (image/webp or image/gif, attachment)
"""

from __future__ import annotations

import json
import re


def _live_states(req, sid: str) -> dict:
    try:
        from halo_harness.studio.live_handoff_api import _find
        _v, _h, s, _local = _find(req, "local", sid)
    except Exception:
        return {}
    return {str(a.get("agent_id")): a.get("state") for a in (s or {}).get("agents") or []
            if a.get("state") in ("running", "waiting", "paused", "queued")}


def _build(req, sid: str, lineup, run: str = ""):
    """A session's replay, or (3.4.1.0 R2) a goal run's of the repo Studio's folder is in."""
    from halo_harness.live import replay_file, replay_run
    try:
        if run:
            run_dir = replay_run.find(req.cwd, run)
            if run_dir is None:
                return None, (404, {"error": f"no goal run {run!r} in this repo"})
            return replay_run.build_run(req.state_dir, run_dir), None
        return replay_file.build(req.state_dir, sid, lineup=lineup or None, cwd=req.cwd, live_states=_live_states(req, sid)), None
    except replay_file.ReplayError as e:
        return None, (404, {"error": str(e)})


def get_list(req):
    from halo_harness.live import replay_file
    return 200, {"dir": str(replay_file.replays_dir(req.state_dir)), "replays": replay_file.saved(req.state_dir)}


def get_plan(req):
    from halo_harness.live import replay_file
    sid, run = str(req.query.get("session") or "").strip(), str(req.query.get("run") or "").strip()
    if not sid and not run:
        return 422, {"error": "name the session or the goal run: ?session=<id> or ?run=<id>", "problems": []}
    p, err = _build(req, sid, req.query.get("lineup"), run)
    if err:
        return err
    path = replay_file.replays_dir(req.state_dir) / f"{p['id']}{replay_file.SUFFIX}"
    return 200, {"id": p["id"], "path": str(path), "bytes": len(json.dumps(p, separators=(",", ":")).encode("utf-8")),
                 "includes": p["includes"]}


def post_save(req):
    from halo_harness.live import replay_file
    body = req.body if isinstance(req.body, dict) else {}
    sid, run = str(body.get("session") or "").strip(), str(body.get("run") or "").strip()
    if not sid and not run:
        return 422, {"error": "name the session or the goal run: {session: <id>} or {run: <id>}", "problems": []}
    p, err = _build(req, sid, body.get("lineup"), run)
    if err:
        return err
    shown = str(body.get("id") or "")  # 3.4.1.1 (53): the name the dialog showed (its plan's), not a second stamp
    if shown.startswith(f"{sid or run}-") and replay_file._ID.match(shown) and replay_file.path_for(req.state_dir, shown) is None:
        p["id"] = shown
    path = replay_file.save(req.state_dir, p)
    return 200, {"ok": True, "id": p["id"], "path": str(path), "bytes": path.stat().st_size, "includes": p["includes"],
                 "row": replay_file.row(p, path)}


def post_import(req):
    from halo_harness.live import replay_file
    body = req.body if isinstance(req.body, dict) else {}
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        return 422, {"error": "send the file's text: {text: ...}", "problems": []}
    if len(text) > replay_file.MAX_BYTES:
        return 413, {"error": f"a replay is at most {replay_file.MAX_BYTES} bytes"}
    try:
        p = replay_file.parse(text)
        path = replay_file.save(req.state_dir, p)
    except replay_file.ReplayError as e:
        return 422, {"error": str(e), "problems": []}
    return 200, {"ok": True, "id": p["id"], "path": str(path), "row": replay_file.row(p, path), "includes": p.get("includes") or []}


def get_one(req):
    from halo_harness.live import replay_file
    path = replay_file.path_for(req.state_dir, req.params["rid"])
    if path is None:
        return 404, {"error": f"no saved replay {req.params['rid']!r}"}
    try:
        return 200, replay_file.load(path)
    except replay_file.ReplayError as e:
        return 422, {"error": str(e)}


def get_compare(req):
    from halo_harness.live import compare
    a, b = str(req.query.get("a") or "").strip(), str(req.query.get("b") or "").strip()
    if not a or not b:
        return 422, {"error": "name two runs: ?a=<ref>&b=<ref> (session:<id>, run:<id> or file:<id>)", "problems": []}
    try:
        pa = compare.resolve(req.state_dir, a, cwd=req.cwd)
        pb = pa if b == a else compare.resolve(req.state_dir, b, cwd=req.cwd)
    except compare.CompareError as e:
        return 404, {"error": str(e)}
    return 200, compare.compare(pa, pb, split=_num(req.query.get("split")), same=a == b)


def get_report(req):
    from halo_harness.live import compare, report_card
    from halo_harness.live.report_card_text import markdown
    ref = str(req.query.get("ref") or "").strip()
    if not ref:
        return 422, {"error": "name the run: ?ref=session:<id> | run:<id> | file:<id>", "problems": []}
    try:
        p, from_file = report_card.resolve(req.state_dir, ref, cwd=req.cwd)
    except compare.CompareError as e:
        return 404, {"error": str(e)}
    c = report_card.card(p, ref, from_file)
    return 200, {"card": c, "markdown": markdown(c)}


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def get_clip_plan(req):
    from halo_harness.live import replay_clip, replay_file
    rid = req.params["rid"]
    path = replay_file.path_for(req.state_dir, rid)
    if path is None:
        return 404, {"error": f"no saved replay {rid!r}"}
    q = req.query or {}
    try:
        p = replay_clip.plan(replay_file.load(path), _num(q.get("from")), _num(q.get("to")), _num(q.get("speed")))
    except (replay_clip.ClipError, replay_file.ReplayError) as e:
        return 422, {"error": str(e)}
    enc = replay_clip.encoder()  # 3.4.1.0 R6: the plan needs no Pillow; `pillow` / `needs` say whether Export can encode
    p.pop("times", None)
    out = replay_file.replays_dir(req.state_dir) / "clips" / f"{rid}-{int(p['from'])}-{int(p['to'])}.{enc['format']}"
    from halo_harness.live.clip_chrome import find_chrome
    return 200, {**p, **enc, "path": str(out), "chrome": bool(find_chrome())}


def post_clip(req):
    from halo_harness.live import replay_clip, replay_file
    body = req.body if isinstance(req.body, dict) else {}
    try:  # 3.4.1.2 (SERVERS-5): filmed through a throwaway read-only Studio; this Studio's token never enters its Chrome
        got = replay_clip.clip(req.state_dir, req.params["rid"], _num(body.get("from")), _num(body.get("to")),
                               _num(body.get("speed")), cwd=req.cwd)
    except (replay_clip.ClipError, replay_file.ReplayError, TimeoutError, RuntimeError) as e:
        return 422, {"error": str(e)}
    return 200, {**got, "url": f"replays/clips/{got['name']}"}


def get_clip_file(req):
    from halo_harness.live import replay_file
    from halo_harness.studio.raw_body import RawBody
    name = req.params["name"]
    path = replay_file.replays_dir(req.state_dir) / "clips" / name
    if not path.is_file():
        return 404, {"error": f"no clip {name!r}"}
    kind = "image/webp" if name.endswith(".webp") else "image/gif"
    return 200, RawBody(path.read_bytes(), kind, {"Content-Disposition": f'attachment; filename="{name}"'})


_RID = r"(?P<rid>[A-Za-z0-9_.-]{1,120})"
ROUTES = [("GET", r"^replays$", get_list), ("GET", r"^replays/plan$", get_plan), ("GET", r"^replays/compare$", get_compare),
          ("GET", r"^replays/report$", get_report), ("POST", r"^replays/save$", post_save),
          ("POST", r"^replays/import$", post_import),
          ("GET", r"^replays/clips/(?P<name>[A-Za-z0-9_.-]+\.(?:webp|gif))$", get_clip_file),
          ("GET", rf"^replays/{_RID}/clip$", get_clip_plan), ("POST", rf"^replays/{_RID}/clip$", post_clip),
          ("GET", rf"^replays/{_RID}$", get_one)]


def dispatch_replays(req):
    for method, pattern, fn in ROUTES:
        m = re.match(pattern, req.path)
        if m and method == req.method:
            req.params = dict(m.groupdict())
            return fn(req)
    if any(re.match(p, req.path) for _, p, _ in ROUTES):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
