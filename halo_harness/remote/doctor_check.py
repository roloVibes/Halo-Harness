"""halo_harness.remote.doctor_check -- `halo doctor`'s remote-control rows (Halo 2.0.9 round 4; 3.3.13.0 R3: the Signal
bridge's rows left with it for the signal pack). `entries()` returns `[(id, line)]` in the doctor's own `[OK]` /
`[WARN]` vocabulary (so `halo doctor --json` gets the same `{id, status, message, fix}` records as every other check):

    remote             the control sockets (fleet.enabled), remote.enabled, the live sessions, the transports listening
    service_<pack>_<name>   one row per pack service the supervisor knows (supervise/services_rows.py): running is OK;
                       an autostart service that is stopped or failed is a WARN with its line (the signal pack's bridge
                       says here what it needs: signal-cli, an account, the supervisor)
"""

from __future__ import annotations

OK, WARN = "[OK]", "[WARN]"


def _fix(line: str, cmd: str = "", see: str = "") -> str:
    from halo_harness.doctor import _fix as fix
    return fix(line, cmd=cmd or None, see=see or None)


def _live_count() -> int:
    """Live sessions in the registry, counted without touching the file (doctor writes nothing)."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.remote import registry
    path = bridge_home() / "run" / registry.FILENAME
    try:
        return sum(1 for r in registry._load(path) if registry._entry_alive(r)) if path.exists() else 0
    except Exception:
        return 0


def _control_line() -> str:
    from halo_harness.remote import runtime
    from halo_harness.remote.notify import listening
    count = _live_count()
    sockets = "on (fleet.enabled)" if runtime.fleet_enabled() else "off (fleet.enabled is false)"
    names = listening()
    switch = "remote.enabled on" if runtime.remote_enabled() else "remote.enabled off (every transport silent)"
    return (f"{OK} Remote control: control sockets {sockets}, {switch}, transports listening: "
            f"{', '.join(names) if names else 'none'} -- {count} live session{'' if count == 1 else 's'} in the registry")


def service_entries() -> list:
    try:
        from halo_harness.supervise.services_rows import rows, state_line
        got = rows()
    except Exception:
        return []
    out = []
    for r in got:
        rid = "service_" + str(r["key"]).replace("/", "_").replace("-", "_")
        line = f"pack service {r['key']}: {state_line(r)}"
        if r.get("state") == "running" or not r.get("autostart"):
            out.append((rid, f"{OK} {line}"))
        else:
            out.append((rid, _fix(f"{WARN} {line}", "halo supervise services", see="docs/SUPERVISE.md (Pack services)")))
    return out


def entries() -> list:
    return [("remote", _control_line())] + service_entries()
