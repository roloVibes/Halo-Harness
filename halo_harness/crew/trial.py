"""halo_harness.crew.trial -- Try it for an agent (Halo 3.6.0.0 R1; docs/STUDIO-builder.md "Try it").

    estimate(raw, state_dir)            {usd, line}: what one typical task costs on its model, said BEFORE the run
    start(raw, request, cwd, state_dir, publish) -> record    runs the agent once, as it stands (saved or not)
    stop(try_id)  get(try_id, state_dir)  seen(try_id, state_dir)  recent(state_dir)

A run is a real agent: `halo -p` as that agent (crew/trial_run.py) in a throwaway copy of the project, its careful
mode honoured, removed when it ends. Its record lives in <state>/crew/.try/<id>.json -- {id, agent, model, request,
state: running | done | stopped | failed, where, reply, used {tool: n}, denied, cost_usd, turns, seconds, now, seen}
-- and each change is published on Studio's feed (`crew` frames). A run that ends while the person is not looking at
it (`seen` is not set) is an Attention row (live/crew_attention.py) until the tab shows it or it is set aside.
"""

from __future__ import annotations

import json
import re
import secrets
import threading
import time
from typing import Callable, Optional

from halo_harness.crew import store, trial_run

TYPICAL_IN, TYPICAL_OUT = 20000, 2000
RUNNING: dict = {}
_LOCK = threading.Lock()


def _folder(state_dir):
    return store.state_dir_of(state_dir) / "crew" / ".try"


def _save(rec: dict, state_dir) -> None:
    store.write_text(_folder(state_dir) / f"{rec['id']}.json", json.dumps(rec, ensure_ascii=False))


def get(try_id: str, state_dir=None) -> Optional[dict]:
    if not re.match(r"^t[0-9a-f]{10}$", str(try_id or "")):
        return None
    try:
        return json.loads((_folder(state_dir) / f"{try_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def recent(state_dir=None, within_s: float = 86400.0) -> list:
    out = []
    try:
        files = sorted(_folder(state_dir).glob("t*.json"))
    except OSError:
        return out
    for p in files:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if time.time() - float(rec.get("started") or 0) < within_s:
            out.append(rec)
    return out


def model_for(raw: dict, request: str, state_dir) -> "tuple[str, str]":
    """(the ref the run uses, one line on why); auto picks per task as a session would."""
    model = str(raw.get("model") or "auto")
    if model != "auto":
        return model, model
    from halo_harness.checks.provider import default_model
    main = default_model()
    try:
        from halo_harness.models_auto import pick
        got = pick(store.state_dir_of(state_dir), needs=raw.get("needs") or [], task_text=request, main_ref=main)
        if got.ref:
            return got.ref, f"Auto picked {got.ref}: {got.reason}"
    except Exception:
        pass
    return main, f"Auto: {main or 'your main model'} (no pick)"


def estimate(raw: dict, state_dir=None) -> dict:
    model = str(raw.get("model") or "auto")
    if model == "auto":
        return {"usd": None, "line": "Auto picks the model when it runs: the cost shows after the run"}
    try:
        from halo_harness.checks.run import call_price
        words = call_price(model, TYPICAL_IN, TYPICAL_OUT)
    except Exception:
        words = f"price unknown for {model}"
    m = re.search(r"\$([0-9.]+)", words)
    usd = float(m.group(1)) if m else (0.0 if words.startswith("free") else None)
    return {"usd": usd, "line": f"one typical task (~{TYPICAL_IN // 1000}k in, ~{TYPICAL_OUT // 1000}k out): {words}"}


def _public(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k not in ("cmd",)}


def start(raw: dict, request: str, *, cwd, state_dir=None, publish: Optional[Callable] = None) -> dict:
    tid = "t" + secrets.token_hex(5)
    rec = {"id": tid, "agent": str(raw.get("name")), "request": request, "state": "running", "started": time.time(),
           "ended": None, "where": "", "reply": "", "used": {}, "denied": [], "cost_usd": None, "turns": None,
           "seconds": None, "now": "starting", "seen": False, "error": "", "estimate": estimate(raw, state_dir)}
    rec["model"], rec["model_line"] = model_for(raw, request, state_dir)
    _save(rec, state_dir)
    th = threading.Thread(target=_run, args=(rec, raw, request, cwd, state_dir, publish), name=f"crew-try-{tid}", daemon=True)
    th.start()
    return _public(rec)


def _emit(rec: dict, state_dir, publish) -> None:
    _save(rec, state_dir)
    if publish is not None:
        try:
            publish({"session_id": "studio", "event": "crew", "data": {"try": _public(rec)}})
        except Exception:
            pass


def _run(rec: dict, raw: dict, request: str, cwd, state_dir, publish) -> None:
    copy, repo = None, None
    try:
        copy, rec["where"], repo = trial_run.throwaway(cwd)
        proc = trial_run.spawn(trial_run.command(raw, request, rec["model"]), copy)
        with _LOCK:
            RUNNING[rec["id"]] = (proc, rec)
        rec["now"] = "running"
        _emit(rec, state_dir, publish)
        for line in proc.stdout:
            if trial_run.read(line, rec):
                _emit(rec, state_dir, publish)
        err = proc.stderr.read() if proc.stderr else ""
        code = proc.wait()
        stopped = rec.get("state") == "stopping"
        rec["state"] = "stopped" if stopped else ("done" if code == 0 and not rec.get("is_error") else "failed")
        if rec["state"] == "failed" and not rec["reply"]:
            rec["error"] = " ".join(err.split())[-600:] or f"halo -p ended with {code}"
    except Exception as e:
        rec["state"], rec["error"] = "failed", f"{type(e).__name__}: {e}"
    finally:
        with _LOCK:
            RUNNING.pop(rec["id"], None)
        if copy is not None:
            trial_run.drop(copy, repo)
        rec["ended"] = time.time()
        rec["seconds"] = round(rec["ended"] - rec["started"], 1)
        rec["now"] = ""
        _emit(rec, state_dir, publish)


def stop(try_id: str, state_dir=None) -> dict:
    with _LOCK:
        got = RUNNING.get(try_id)
    if got is None:
        return {"ok": False, "error": "that run is not running"}
    proc, rec = got
    rec["state"] = "stopping"
    trial_run.kill(proc)
    return {"ok": True}


def seen(try_id: str, state_dir=None) -> dict:
    rec = get(try_id, state_dir)
    if rec is None:
        return {"ok": False, "error": "no such run"}
    if rec.get("state") != "running" and not rec.get("seen"):
        rec["seen"] = True
        _save(rec, state_dir)
    return {"ok": True, "seen": bool(rec.get("seen"))}
