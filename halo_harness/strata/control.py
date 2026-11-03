"""halo_harness.strata.control -- a Strata server Halo started, after `strata launch` returned (Halo 3.3.9.2;
docs/MODELS-strata.md "Serve").

`strata launch ... --yes --no-tui` downloads nothing Halo did not see planned, starts the server under Strata's own
supervisor, prints the addresses and returns; the server keeps running (docs/TERMINAL_LAUNCH.md). Its own lines go to
Strata's state folder, not to Halo's launch log: the runtime's `<state>/runtime/<profile>.server.log` (strata_control/
runtime.py) beside the `<state>/launch/<name>.engine.log` the launch prints as "Engine log" (strata_cli/launch/cmd.py).
From the source, unverified against a live run.

    status_rows(prefix) -> [{name, profile, state, port, url, host, config}] | None   `strata launch --status --output json`
    stop_row(e, *, state_dir) -> {ok, id, say}   `strata launch --stop --preset <the launch serving its port>`, then the
        registry row and the `strata` entry go
    alive(e) -> bool   its port answers /health as Strata, or the `strata launch` process is still starting it
    server_log_for(engine_log, profile) -> Path | None   the server log beside the engine log the launch printed
    settle(state_dir, rows=None) -> [row]   a row whose `strata launch` has returned: the server's own log in place of
        the launch log (the steward reads it), the pid cleared (Strata's supervisor owns the server), ready from /health
Halo never changes a Strata setting and never restarts a server: only the stop the user asks for.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from halo_harness.strata import KEY_ENV, NAME, SERVICE

_ENGINE_LOG = re.compile(r"^\s*Engine log\s+(\S.*?)\s{2,}\(follow it", re.M)
_SERVING = "Strata is serving."


def status_rows(prefix) -> Optional[list]:
    from halo_harness.strata.requirements import _run
    if not prefix:
        return None
    rc, out = _run(list(prefix) + ["launch", "--status", "--output", "json"])
    try:
        got = json.loads(out.strip().splitlines()[-1]) if rc == 0 and out.strip() else None
    except (ValueError, IndexError):
        got = None
    rows = got.get("running") if isinstance(got, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else None


def health(port, timeout: float = 1.0) -> dict:
    from halo_harness.providers.local_server_cmd import get
    code, body = get(f"http://127.0.0.1:{int(port)}/health", timeout=timeout)
    ok = code == 200 and isinstance(body, dict) and str(body.get("service") or "").lower() == SERVICE
    return {"ok": ok, "loaded": ok and body.get("loaded", True) is not False, "body": body if ok else None}


def alive(e: dict) -> bool:
    from halo_harness.bg_run import pid_alive
    if isinstance(e.get("pid"), int) and pid_alive(e["pid"]):
        return True
    return bool(e.get("port")) and health(e["port"], timeout=0.5)["ok"]


def server_log_for(engine_log, profile) -> Optional[Path]:
    if not engine_log or not profile:
        return None
    p = Path(str(engine_log)).expanduser()
    return p.parent.parent / "runtime" / f"{profile}.server.log"


def _launch_text(e: dict) -> str:
    try:
        return Path(e.get("launch_log") or e.get("log") or "").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _model_id(e: dict) -> Optional[str]:
    from halo_harness.providers.huggingface_local_probe import _probe_get
    from halo_harness.strata.launch import key
    got = _probe_get(f"http://127.0.0.1:{int(e['port'])}/v1", "/models", api_key=key(), timeout=2.0)
    rows = got.get("data") if isinstance(got, dict) else None
    return next((str(r["id"]) for r in rows or [] if isinstance(r, dict) and r.get("id")), None)


def settle(state_dir, rows: Optional[list] = None) -> list:
    """Each `strata` row whose launch process has returned: what it said, read once."""
    from halo_harness.bg_run import pid_alive
    from halo_harness.providers import local_runtime as R
    rows = R.load_registry(state_dir) if rows is None else rows
    todo = [e for e in rows if e.get("kind") == NAME and not e.get("settled")
            and not (isinstance(e.get("pid"), int) and pid_alive(e["pid"]))]
    if not todo:
        return []
    out = []
    for e in todo:
        text = _launch_text(e)
        h = health(e["port"]) if e.get("port") else {"ok": False, "loaded": False}
        fields = {"pid": None, "settled": True, "ready": bool(h["loaded"]),
                  "serving": _SERVING in text or "Already serving these choices" in text or h["ok"]}
        m = _ENGINE_LOG.findall(text)
        if m:
            fields["engine_log"] = m[-1].strip()
            from halo_harness.strata.requirements import binary
            got = status_rows(binary()[0]) or []
            run = next((r for r in got if str(r.get("port")) == str(e.get("port"))), None)
            fields["profile"] = (run or {}).get("profile") or e.get("profile")
            srv = server_log_for(fields["engine_log"], fields["profile"])
            if srv is not None and srv.is_file():
                fields["log"] = str(srv)
            elif Path(fields["engine_log"]).expanduser().is_file():
                fields["log"] = str(Path(fields["engine_log"]).expanduser())
        if h["ok"]:
            fields["model"] = _model_id(e) or e.get("model")
        e.update(fields)
        out.append(e)
    with R._registry_lock(state_dir):
        cur = R.load_registry(state_dir)
        for e in cur:
            hit = next((x for x in out if x.get("id") == e.get("id") and x.get("port") == e.get("port")), None)
            if hit is not None:
                e.update(hit)
        R.save_registry(state_dir, cur)
    from halo_harness.strata.launch import write_entry
    for e in out:
        if e.get("serving"):
            write_entry(e)
    return out


def stop_row(e: dict, *, state_dir) -> dict:
    from halo_harness.providers import local_runtime as R
    from halo_harness.strata.launch import forget
    from halo_harness.strata.requirements import _run, binary
    prefix, _src = binary()
    run = next((r for r in status_rows(prefix) or [] if str(r.get("port")) == str(e.get("port"))), None)
    if run is not None:
        rc, out = _run(list(prefix) + ["launch", "--stop", "--preset", str(run.get("name"))], timeout=200.0)
        how = (out.strip().splitlines() or [f"strata launch --stop answered {rc}"])[-1]
    elif prefix is None:
        how = "strata is not on PATH any more: its server is stopped where it runs (strata launch --stop)"
    else:
        how = f"nothing from strata launch serves port {e.get('port')} any more"
    R.drop_registry_entries(state_dir, [(e.get("model"), e.get("pid"))])
    forget()
    return {"ok": True, "id": e.get("id"), "say": f"stopped strata {e.get('id')} ({e.get('model')} on port "
                                                  f"{e.get('port')}): {how}"}


__all__ = ["KEY_ENV", "alive", "health", "server_log_for", "settle", "status_rows", "stop_row"]
