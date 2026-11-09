"""halo_harness.remote.status -- `/remote` and the TUI's remote chip (Halo 2.0.9 round 4 as remote/dialog_model.py, the
Signal dialog's model; 3.3.13.0 R3: the Signal bridge is the signal pack, so `/remote` is the control socket's status).

    text(args="") -> str   this session's control socket and the registry, `remote.enabled`, the transports listening
                           (remote/notify.py) and every pack service the supervisor runs (supervise/services_rows.py);
                           `/remote signal ...` says in one line where the Signal bridge went
    chip() -> str          the chip when no phone is attached to this session: the transports listening ("signal"),
                           or the first pack service that should run and does not ("signal/bridge stopped"); "" for none
"""

from __future__ import annotations


def _services() -> list:
    try:
        from halo_harness.supervise.services_rows import rows
        return rows()
    except Exception:
        return []


def text(args: str = "") -> str:
    from halo_harness.remote.cli import SIGNAL_MOVED
    from halo_harness.remote.fleet_identity import remote_enabled
    from halo_harness.remote.notify import listening
    from halo_harness.remote.runtime import status_line
    words = (args or "").split()
    if words and words[0].lower() in ("signal", "pair", "off", "on", "peers", "unpair"):
        return SIGNAL_MOVED.replace("halo remote signal: ", "/remote " + words[0] + ": ")
    names = listening()
    lines = [status_line(), f"remote.enabled: {'true' if remote_enabled() else 'false (every transport stays silent)'}",
             "transports listening: " + (", ".join(names) if names else "none")]
    svc = _services()
    if svc:
        from halo_harness.supervise.services_rows import state_line
        lines.append("pack services (halo supervise services):")
        lines += [f"  {r['key']}  {state_line(r)}" for r in svc]
    lines.append("The Signal bridge is the signal pack: halo pack install signal, then /signal.")
    return "\n".join(lines)


def chip() -> str:
    try:
        from halo_harness.remote.notify import listening
        names = listening()
    except Exception:
        names = []
    if names:
        return " ".join(names)
    for r in _services():
        if r.get("autostart") and r.get("state") != "running":
            return f"{r['key']} {r.get('state') or 'off'}"
    return ""
