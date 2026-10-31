"""halo_harness.ollama_steward.probe_new -- Halo 3.3.6.0 R1: the steward's
job (ollama_steward/job.py) runs the battery (providers/capability_battery.py)
on a model of the host this machine serves that has no profile for its
digest and the server's Ollama version: a newly pulled or newly seen model,
or one whose digest or Ollama version changed since its profile.

    maybe(job, now) -> the model it started on, or None

Only when `ollama.steward.probe_new` is on (the default), the card is idle
(no call in the ledger for IDLE_S: never while a session's call is in
flight), no probe of this job runs already, and the job holds its lock (it
runs inside the job). One model per pass; its frames go out as the job's
`finding` lines ("probed <model>: <where it sits>").
"""

from __future__ import annotations

import threading
from typing import Optional

IDLE_S = 180.0
CHECK_S = 300.0  # how often an idle job asks the host what it has
_running = threading.Event()


def enabled() -> bool:
    from halo_harness.ollama_steward.agent import _cfg
    return _cfg("ollama.steward.probe_new", True) is not False


def due(state_dir, host, *, client=None) -> list:
    """The host's chat models with no fresh profile (a changed digest or Ollama version counts)."""
    from halo_harness.providers.capability_battery import HostClient
    from halo_harness.providers.ollama_capability import load_profile
    c = client or HostClient(host)
    version = (c.call("GET", "/api/version", timeout=10.0) or {}).get("version")
    tags = c.call("GET", "/api/tags", timeout=15.0) or {}
    out = []
    for r in tags.get("models") or []:
        if not isinstance(r, dict) or not r.get("digest"):
            continue
        name = r.get("model") or r.get("name")
        family = str(((r.get("details") or {}).get("family")) or "")
        if "embed" in str(name).lower() or family.endswith("bert"):
            continue
        if load_profile(state_dir, r["digest"], host.name, ollama_version=version) is None:
            out.append(name)
    return out


def maybe(job, now: float, *, client=None, runner=None) -> Optional[str]:
    from halo_harness.ollama_steward import job_state
    from halo_harness.providers.capability_battery import test_guard
    if not enabled() or _running.is_set() or job.lock is None:
        return None
    if now - float(getattr(job, "_probe_checked", 0.0) or 0.0) < CHECK_S:
        return None
    job._probe_checked = now
    last = job_state.last_call_at(job.state_dir)
    if last is not None and now - last < IDLE_S:
        return None
    host = job.host if job.host is not None else job_state.served_host()
    if host is None or test_guard(host):
        return None
    try:
        names = due(job.state_dir, host, client=client)
    except Exception:
        return None
    if not names:
        return None
    model = names[0]
    _running.set()

    def body() -> None:
        from halo_harness.providers.capability_battery import run
        from halo_harness.providers.fit_meter import host_card_of
        try:
            p = (runner or run)(host, model, card=host_card_of(host, read=True), state_dir=job.state_dir,
                                client=client)
            if p.get("ok"):
                job.emit("finding", f"probed {model} on {host.name}: {p.get('sits')}"
                                    f"{' · agentic-ready' if p.get('agentic_ready') else ''}"
                                    f" ({', '.join(p.get('quirks') or [])[:160] or 'no quirks'})",
                         {"probe": model, "host": host.name, "sits": p.get("sits")})
        except Exception:
            pass
        finally:
            _running.clear()

    threading.Thread(target=body, name="halo-steward-probe", daemon=True).start()
    return model
