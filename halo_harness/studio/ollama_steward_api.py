"""halo_harness.studio.ollama_steward_api -- the Ollama steward's routes (Halo 3.3.4.0 R5; docs/MODELS-ollama-
steward.md "In Studio"), reached through studio/api.py's `_PREFIXES` (`ollama/`). The same loopback / origin / token
guard as every Studio route. Never a model call; never a write to a server.

    GET  ollama/steward        {status (job_state.status, `model` filled as `status` does), status_lines, current
                                (job.current: {where, frames} | null), notes (the last 24 h, newest last), last_note,
                                hub_note, mode, models (the local model refs), changes (in place), proposals}
    GET  ollama/hosts          studio/ollama_hosts_view.hosts_view: per host the card, the rollups, the models,
                               the profiles, the findings, the fit plan; the Hugging Face local servers
    GET  ollama/timeline?host=&since=1h   the ledger's lines per minute: {buckets [{t, calls, trims, cuts, errors,
                               p95_prompt}], bucket_s: 60, since_s, host}
    POST ollama/steward/apply {id} | {key, field, to, why?}   a finding's (or a proposal's) change, or a fit-plan
                               change -> {ok, change, say}; 409 {error} when the guards say no
    POST ollama/steward/dismiss {id}   a `dismissed` line: the finding stays quiet for 24 hours
    POST ollama/steward/undo   the newest change in place reverted -> {ok, change | null, say}
    POST ollama/steward/run    one steward.run() pass (its profile lock keeps it from racing the job)
"""

from __future__ import annotations

import time

NOTES = 40
MAX_SINCE_S = 86400.0


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def get_steward(req):
    from halo_harness.ollama_steward import job, job_state, notes, steward
    from halo_harness.ollama_steward.agent import choose_model, local_models
    state = req.state_dir
    st = job_state.status(state)
    if not st.get("running"):
        st["model"], st["model_why"] = choose_model(state_dir=state)
    last = notes.latest(state, stages=("note",)) or notes.latest(state, stages=("change", "finding"))
    journal = steward.read_journal(state)
    quiet = steward.dismissed(state, journal=journal)
    applied = {r.get("finding") for r in journal if r.get("kind") == "apply"}
    pending = [r for r in journal if r.get("kind") == "proposal" and r.get("id") not in quiet
               and r.get("id") not in applied]
    return 200, {"status": st, "status_lines": job_state.format_status(st, last_note=last),
                 "current": job.current(state), "notes": notes.read(state, since_s=86400.0)[-NOTES:],
                 "last_note": last, "hub_note": notes.hub_note(state), "mode": steward.mode(),
                 "models": [ref for ref, _size in local_models(state)], "changes": steward._in_place(journal)[-10:],
                 "proposals": pending[-20:]}


def get_hosts(req):
    from halo_harness.studio.ollama_hosts_view import hosts_view
    return 200, hosts_view(req.state_dir)


def get_timeline(req):
    from halo_harness.ollama_steward.ledger import parse_at, parse_since, read_calls
    from halo_harness.ollama_steward.traffic import percentile
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.studio.ollama_hosts_view import line_host, local_servers
    try:
        since_s = parse_since(str(req.query.get("since") or "1h")) or 3600.0
    except ValueError as e:
        return 422, {"error": str(e), "problems": [str(e)]}
    since_s = min(max(since_s, 60.0), MAX_SINCE_S)
    host = str(req.query.get("host") or "").strip()
    hosts, servers = resolve_ollama_hosts(), local_servers()
    now = time.time()
    start = int((now - since_s) // 60) * 60
    n = int((now - start) // 60) + 1
    rows = [{"t": start + 60 * i, "calls": 0, "trims": 0, "cuts": 0, "errors": 0, "_p": []} for i in range(n)]
    for x in read_calls(req.state_dir, since=since_s + 60):
        if host and line_host(x, hosts, servers).lower() != host.lower():
            continue
        i = int(((parse_at(x.get("at")) or 0) - start) // 60)
        if not 0 <= i < n or x.get("kind") == "calibrate":
            continue
        b = rows[i]
        b["calls"] += 1
        b["trims"] += int(bool(x.get("trimmed")))
        b["cuts"] += int(x.get("done_reason") == "length")
        b["errors"] += int(x.get("status") != 200)
        if x.get("status") == 200 and isinstance(x.get("prompt_eval_count"), int):
            b["_p"].append(x["prompt_eval_count"])
    for b in rows:
        b["p95_prompt"] = percentile(b.pop("_p"), 95)
    return 200, {"host": host, "since_s": since_s, "bucket_s": 60, "buckets": rows}


def _plan_change(state, body: dict):
    """A fit-plan option's change ({key, field, to}) through the same guards as a finding's."""
    import hashlib
    from halo_harness.ollama_steward import steward
    from halo_harness.ollama_steward.profiles import CHANGEABLE, all_profiles, split_key
    from halo_harness.providers.ollama import resolve_ollama_hosts
    key, field, to = str(body.get("key") or ""), str(body.get("field") or ""), body.get("to")
    host, model = split_key(key)
    hosts = resolve_ollama_hosts()
    if not host or not model or not any(h.name == host for h in hosts):
        return None, f"{key!r} is not <host>|<model> for a host configured here"
    if field not in CHANGEABLE or to is None or isinstance(to, bool):
        return None, f"field is one of {', '.join(CHANGEABLE)} with a value"
    if field in ("num_ctx", "num_predict", "tools_max"):
        try:
            to = int(to)
        except (TypeError, ValueError):
            return None, f"{field} takes a whole number, got {to!r}"
    raw = f"plan|{key}|{field}|{to}"
    f = {"id": f"plan-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:6]}", "rule": "plan", "key": key, "host": host,
         "model": model, "evidence": None, "plan": None,
         "proposal": {"field": field, "from": (all_profiles().get(key) or {}).get(field), "to": to,
                      "why": str(body.get("why") or "the fit plan's option")[:200]}}
    with steward.profile_lock(state):
        change, why = steward.check(state, f, hosts=hosts, now=time.time())
        if change is None:
            return None, why
        return steward.apply_change(state, f, change, mode_name="review"), ""


def post_apply(req):
    from halo_harness.ollama_steward import steward
    from halo_harness.studio.ollama_hosts_view import readers
    body = _body(req)
    fid = str(body.get("id") or "").strip()
    if fid:
        row, why = steward.apply_by_id(req.state_dir, fid, **readers())
    elif body.get("key") and body.get("field"):
        row, why = _plan_change(req.state_dir, body)
    else:
        return 422, {"error": "apply takes {id} or {key, field, to}", "problems": ["id: a finding's or a proposal's id"]}
    if row is None:
        return 409, {"error": why}
    return 200, {"ok": True, "change": row, "say": row.get("say")}


def post_dismiss(req):
    from halo_harness.ollama_steward import steward
    fid = str(_body(req).get("id") or "").strip()
    if not fid:
        return 422, {"error": "dismiss takes {id}", "problems": ["id: a finding's id"]}
    row = steward.dismiss(req.state_dir, fid)
    return 200, {"ok": True, "dismissed": fid, "say": row["say"]}


def post_undo(req):
    from halo_harness.ollama_steward import steward
    row = steward.undo_last(req.state_dir)
    return 200, {"ok": True, "change": row, "say": row["say"] if row else "nothing to undo: no steward change is in place"}


def post_run(req):
    from halo_harness.ollama_steward import steward
    from halo_harness.studio.ollama_hosts_view import readers
    said: list = []
    done = steward.run(req.state_dir, say=said.append, **readers())
    counts = {k: len(done[k]) for k in ("findings", "applied", "proposed", "rolled_back", "skipped")}
    return 200, {"ok": True, "mode": done["mode"], **counts, "says": said}


ROUTES = {"ollama/steward": ("GET", get_steward), "ollama/hosts": ("GET", get_hosts),
          "ollama/timeline": ("GET", get_timeline), "ollama/steward/apply": ("POST", post_apply),
          "ollama/steward/dismiss": ("POST", post_dismiss), "ollama/steward/undo": ("POST", post_undo),
          "ollama/steward/run": ("POST", post_run)}


def dispatch_ollama(req):
    hit = ROUTES.get(req.path)
    if hit is None:
        return 404, {"error": f"no route for {req.method} /api/{req.path}"}
    method, fn = hit
    return fn(req) if req.method == method else (405, {"error": "method not allowed"})
