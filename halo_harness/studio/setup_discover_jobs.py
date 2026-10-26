"""halo_harness.studio.setup_discover_jobs -- the two background jobs behind
Setup's Ollama card (Halo 3.3.0.0 R5; the routes are studio/setup_discover_api.py):
the network scan and the measuring of found models, one of each at a time,
and the rows Find and Scan answered in this Studio (what Add picks from).

Each job publishes its frames on Studio's live feed (studio/events.py
`publish_local`) as

    {"event": "setup", "session_id": "setup:<kind>:<job>",
     "data": {job, kind: "scan" | "measure", state: running | done | stopped, elapsed, ...}}

a scan every second while it sweeps (`rows: []`, `note`: "scanning <subnet>")
and once at the end (`rows`, `note`, `notes`); a measure before and after each
model (`host`, `model`, `index`, `total`, `line`, `lines` so far) and a summary
(`summary`, `results`). `latest(kind)` is the newest frame (the GET catch-up).
A stop ends the waiting at once (a scan) or after the model in hand (a measure);
the sweep itself always ends inside its 10 s cap.
"""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_found: dict = {}  # url_key -> Found: every row Find and Scan answered in this Studio
_jobs: dict = {"scan": None, "measure": None}


def remember(rows) -> None:
    from halo_harness.providers.ollama_discover import url_key
    with _lock:
        for r in rows:
            _found[url_key(r.url)] = r


def found() -> list:
    with _lock:
        return list(_found.values())


def found_dicts() -> list:
    return [r.as_dict() for r in found()]


def forget() -> None:
    """Drop the remembered rows and the jobs (the tests' fresh start)."""
    with _lock:
        _found.clear()
        _jobs.update(scan=None, measure=None)


def alive(kind: str) -> bool:
    job = _jobs.get(kind) or {}
    return any(t is not None and t.is_alive() for t in (job.get("thread"), job.get("worker")))


def latest(kind: str) -> dict:
    with _lock:
        job = _jobs.get(kind)
        frame = dict(job["frame"]) if job else {"job": None, "kind": kind, "state": "idle"}
    frame["running"] = alive(kind)
    return frame


def stop(kind: str) -> bool:
    with _lock:
        job = _jobs.get(kind)
    if job and alive(kind):
        job["stopped"] = True
        return True
    return False


def _new_job(kind: str, publish, **first) -> dict:
    job = {"id": time.strftime("%Y%m%d-%H%M%S"), "kind": kind, "t0": time.monotonic(), "stopped": False,
           "thread": None, "worker": None, "publish": publish, "note": ""}
    job["frame"] = {"job": job["id"], "kind": kind, "state": "running", "elapsed": 0.0, **first}
    return job


def _send(job: dict, **data) -> None:
    frame = {"job": job["id"], "kind": job["kind"], "elapsed": round(time.monotonic() - job["t0"], 1), **data}
    with _lock:
        job["frame"] = frame
    if job["publish"] is None:
        return
    try:
        job["publish"]({"session_id": f"setup:{job['kind']}:{job['id']}", "event": "setup", "data": frame,
                        "ts": time.time()})
    except Exception:
        pass


def _start(job: dict, body) -> dict:
    job["thread"] = threading.Thread(target=body, name=f"halo-setup-{job['kind']}-{job['id']}", daemon=True)
    with _lock:
        _jobs[job["kind"]] = job
    job["thread"].start()
    return latest(job["kind"])


# -- the network scan ------------------------------------------------------------

def lan_rows(env, on_progress):
    """The network scope (the seam the tests replace with a blocking stub)."""
    from halo_harness.providers.ollama_discover import discover
    return discover("lan", env=env, on_progress=on_progress)


def _scan_note(rows) -> str:
    if rows.notes:
        return "; ".join(rows.notes)
    n = len(rows)
    return f"found {n} Ollama server{'' if n == 1 else 's'} on the network" if n else "no Ollama server answered on the network"


def start_scan(env, publish) -> dict:
    """Start the scan (the caller checked none runs); its first frame."""
    job = _new_job("scan", publish, rows=[], note="starting the scan")
    got: dict = {}

    def progress(text: str) -> None:
        job["note"] = str(text).rstrip(" .")

    def work() -> None:
        try:
            got["rows"] = lan_rows(env, progress)
        except Exception as e:  # one line, never a traceback
            got["error"] = f"the scan stopped: {type(e).__name__}: {e}"

    def body() -> None:
        job["worker"] = threading.Thread(target=work, name=f"halo-setup-sweep-{job['id']}", daemon=True)
        job["worker"].start()
        while job["worker"].is_alive() and not job["stopped"]:
            _send(job, state="running", rows=[], note=job["note"] or "starting the scan")
            job["worker"].join(1.0)
        rows = got.get("rows")
        if job["stopped"]:
            _send(job, state="stopped", rows=[], note="stopped: nothing was listed or added")
        elif rows is None:
            _send(job, state="done", rows=[], note=got.get("error") or "the scan returned nothing", notes=[])
        else:
            remember(rows)
            _send(job, state="done", rows=[r.as_dict() for r in rows], note=_scan_note(rows), notes=list(rows.notes))

    return _start(job, body)


# -- measuring the found models --------------------------------------------------

def plan_models(names: list, refs: list) -> dict:
    """{host name: [models]} from `refs`: `ol:<model>@<host>` or `<model>@<host>` for that host, a bare model for each."""
    plan: dict = {n: [] for n in names}
    for ref in refs:
        bare = ref[3:] if ref.startswith("ol:") else ref
        model, host = bare.rpartition("@")[::2] if "@" in bare else (bare, "")
        for name in [n for n in names if not host or n.lower() == host.lower()]:
            if model and model not in plan[name]:
                plan[name].append(model)
    return plan


def _summary(results: list, hosts: int, seconds: float) -> str:
    from halo_harness.providers.ollama_discover_measure import duration_text
    fits = sum(1 for r in results if r.get("outcome") == "fits")
    dnf = sum(1 for r in results if r.get("outcome") == "does_not_fit")
    n = len(results)
    return (f"{n} model{'' if n == 1 else 's'} measured on {hosts} host{'' if hosts == 1 else 's'} in {duration_text(seconds)}: "
            f"{fits} fit, {dnf} do not fit fully in GPU memory, {n - fits - dnf} not recorded")


def _models_of(host) -> list:
    from halo_harness.providers.ollama import get_catalog
    try:
        rows = get_catalog(host).get("models") or []
    except Exception:
        rows = []
    return [m.get("model") or m.get("name") for m in rows if isinstance(m, dict) and (m.get("model") or m.get("name"))]


def _measure_run(job: dict, hosts: list, plan: dict, timeout, state_dir) -> None:
    """One `measure_models` call per model (a frame before and after each), then the summary frame."""
    from halo_harness.providers.ollama_discover_measure import measure_models
    results, lines, todo = [], [], []
    for h in hosts:
        todo.extend((h, m) for m in (plan.get(h.name) or _models_of(h)))
    for i, (h, model) in enumerate(todo, 1):
        if job["stopped"]:
            break
        step = {"host": h.name, "model": model, "index": i, "total": len(todo)}
        _send(job, state="running", lines=list(lines), line=f"measuring {model} on {h.name} ...", **step)
        try:
            rec = measure_models(h, [model], timeout=timeout, state_dir=state_dir)[0]
        except Exception as e:  # measure_models never raises; a stub or a broken host still gets its line
            rec = {"host": h.name, "model": model, "outcome": "error", "line": f"{model} on {h.name}: {type(e).__name__}: {e}"}
        results.append(rec)
        lines.append(rec["line"])
        _send(job, state="running", lines=list(lines), line=rec["line"], outcome=rec.get("outcome"), **step)
    names = ", ".join(h.name for h in hosts)
    summary = _summary(results, len(hosts), time.monotonic() - job["t0"]) if todo else f"no model to measure on {names}"
    _send(job, state="stopped" if job["stopped"] else "done", lines=lines, line=summary, summary=summary,
          results=[{k: r.get(k) for k in ("host", "model", "outcome", "max_full_gpu_ctx", "seconds")} for r in results])


def start_measure(hosts: list, plan: dict, timeout, state_dir, publish) -> dict:
    """Start measuring (the caller checked none runs); its first frame."""
    job = _new_job("measure", publish, lines=[], line="reading the models of " + ", ".join(h.name for h in hosts))
    return _start(job, lambda: _measure_run(job, hosts, plan, timeout, state_dir))
