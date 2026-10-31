"""halo_harness.ollama_steward.job_state -- Halo 3.3.4.0 R4: the steward
job's lock and its status file.

- `acquire(state_dir, where)`: the OS lock on `<state>/ollama/steward-job.lock`
  (filelock's primitive, held on an open handle for the job's life: one job per
  state dir across every process); a second one does not start and names the holder.
- `<state>/ollama/steward-job.json` (`update`, `read`): {pid, where ("studio" | "host" (3.3.7.0 R1) |
  "hub" | "watch"), machine, since, running, model, model_why, last_run {at,
  mode, findings, applied, proposed, rolled_back}, last_note {at, line}, idle,
  error, stopped}.
- `status(state_dir)`: that file with `running` checked against the lock (a
  job that died leaves the file but not the lock); `format_status` prints it
  for `halo ollama steward status`.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

LOCK_FILE = "steward-job.lock"
STATE_FILE = "steward-job.json"


def _dir(state_dir) -> Path:
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir)


_TRIES = 10  # Windows: a read or a replace can meet the other thread's replace for a moment


def read(state_dir) -> dict:
    path = _dir(state_dir) / STATE_FILE
    for i in range(_TRIES):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            time.sleep(0.02 * (i + 1))
    return {}


def update(state_dir, **fields) -> dict:
    from halo_harness.filelock import file_lock
    path = _dir(state_dir) / STATE_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(path, timeout=1.0):
            data = {**read(state_dir), **fields}
            tmp = path.with_suffix(f".{os.getpid()}.tmp")
            tmp.write_text(json.dumps(data, default=str), encoding="utf-8")
            for i in range(_TRIES):
                try:
                    os.replace(tmp, path)
                    break
                except PermissionError:
                    time.sleep(0.02 * (i + 1))
    except OSError:
        return {}
    return data


def _when(t) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) if isinstance(t, (int, float)) else "?"


def holder_line(st: dict) -> str:
    return (f"the steward job already runs for this state dir: {st.get('where') or '?'} (pid {st.get('pid') or '?'} "
            f"on {st.get('machine') or 'this machine'}) since {_when(st.get('since'))}")


def acquire(state_dir, *, where: str):
    """(the open lock handle, "") or (None, who holds it)."""
    from halo_harness.filelock import _try_lock
    path = _dir(state_dir) / LOCK_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(path, "a+b")
    except OSError as e:
        return None, f"the steward job's lock could not be opened ({e})"
    if not _try_lock(fh):
        fh.close()
        return None, holder_line(read(state_dir))
    update(state_dir, pid=os.getpid(), where=where, machine=_machine(), since=time.time(), running=True,
           stopped=None, error=None)
    return fh, ""


def release(state_dir, fh) -> None:
    from halo_harness.filelock import _unlock
    update(state_dir, running=False, stopped=time.time())
    try:
        _unlock(fh)
        fh.close()
    except OSError:
        pass


def lock_held(state_dir) -> bool:
    from halo_harness.filelock import _try_lock, _unlock
    path = _dir(state_dir) / LOCK_FILE
    if not path.exists():
        return False
    try:
        with open(path, "a+b") as fh:
            if _try_lock(fh):
                _unlock(fh)
                return False
            return True
    except OSError:
        return False


def _machine() -> str:
    try:
        from halo_harness.ollama_steward.ledger import this_machine
        return this_machine() or "this machine"
    except Exception:
        return "this machine"


def status(state_dir) -> dict:
    st = read(state_dir)
    return {**st, "running": bool(st.get("running")) and lock_held(state_dir)}


def format_status(st: dict, *, last_note: Optional[dict] = None) -> "list[str]":
    from halo_harness.ollama_steward.agent import NO_MODEL
    if st.get("running"):
        out = [f"steward job: running in {st.get('where')} (pid {st.get('pid')} on {st.get('machine') or 'this machine'})"
               f" since {_when(st.get('since'))}"]
    else:
        out = ["steward job: not running (it starts with Studio, the fleet hub or `halo host`; `halo ollama steward --watch` runs "
               "it here)" + (f"; the last one stopped {_when(st.get('stopped'))}" if st.get("stopped") else "")]
    run = st.get("last_run") or {}
    if run:
        out.append(f"  last run {_when(run.get('at'))} ({run.get('mode')}): {run.get('findings', 0)} findings, "
                   f"{run.get('applied', 0)} applied, {run.get('proposed', 0)} proposed, "
                   f"{run.get('rolled_back', 0)} rolled back")
    elif st.get("running"):
        out.append("  no run yet: it runs every ollama.steward.every_s while calls flow, or on a server alert")
    if st.get("idle"):
        out.append(f"  idle: {st['idle']}")
    model = st.get("model")
    out.append(f"  model: {model} ({st.get('model_why')})" if model else f"  {st.get('model_why') or NO_MODEL}")
    note = last_note or {}
    if note:
        out.append(f"  last note {note.get('at')}: {note.get('say')}" + (f" ({note['cost']})" if note.get("cost") else ""))
    if st.get("error"):
        out.append(f"  last error: {st['error']}")
    return out


# ---- what a pass reads ------------------------------------------------------------------------

def last_call_at(state_dir) -> Optional[float]:
    """The `at` of the ledger's newest line (its last 16 KB read), or None."""
    from halo_harness.ollama_steward.ledger import parse_at, traffic_path
    try:
        with open(traffic_path(state_dir), "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 16384))
            tail = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    for raw in reversed(tail):
        try:
            t = parse_at(json.loads(raw).get("at"))
        except (ValueError, AttributeError):
            continue
        if t is not None:
            return t
    return None


def noted_findings(state_dir, now: float, *, since_s: float = 86400.0) -> set:
    from halo_harness.ollama_steward import notes
    return {(r.get("data") or {}).get("finding") for r in notes.read(state_dir, stage="finding", since_s=since_s,
                                                                      now=now)} - {None}


def readers() -> dict:
    from halo_harness.ollama_steward.cli_steward import _readers
    return _readers()


def served_host():
    """The configured Ollama host this machine serves (its log is here), or None."""
    try:
        from halo_harness.fleet.ollama_share import served_here
        from halo_harness.providers.ollama import resolve_ollama_hosts
        return next((h for h in resolve_ollama_hosts() if served_here(h.url)), None)
    except Exception:
        return None


def default_watch(state_dir, host, stop, *, on_event=None) -> None:
    from halo_harness.ollama_steward import server_log
    try:
        server_log.watch(state_dir, host, stop, on_event=on_event)
    except Exception:
        pass
