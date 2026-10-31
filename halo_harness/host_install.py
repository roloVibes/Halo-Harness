"""halo_harness.host_install -- `halo host install | uninstall` (Halo 3.3.7.0 R1; docs/HOST.md "Install").

The service file goes through remote/daemon_units.write_unit, the writer `halo supervise --service` uses, under
`<state>/host/`: a systemd user unit `halo-host.service` (Linux), a launchd agent `com.halo.host` (macOS), a Task
Scheduler task `Halo Host` at logon (Windows), each running `[python, -m, halo_harness.cli, host, serve,
--foreground, ...]`. Halo never enables it: it prints the one enable command and the user runs it; `uninstall`
removes the file it wrote and prints the one disable command. `install` says, in one line, that a machine
serves no Ollama host and writes nothing (ollama.hosts and the synthesized default, fleet/ollama_share.served_here) unless --anyway.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from halo_harness.fleet import identity
from halo_harness.remote import cli_common as C

UNIT = {"stem": "halo-host", "label": "com.halo.host", "task": "Halo Host",
        "desc": "Halo host (the model-free monitor of this machine's model servers)"}


def argv_for(port: Optional[int] = None, bind: Optional[str] = None) -> list:
    out = [sys.executable, "-m", "halo_harness.cli", "host", "serve", "--foreground"]
    return out + (["--port", str(int(port))] if port is not None else []) + (["--bind", bind] if bind else [])


def disable_command(os_n: str, path) -> str:
    if os_n == "linux":
        return f"systemctl --user disable --now {path.name}"
    if os_n == "macos":
        return f"launchctl bootout gui/$(id -u)/{UNIT['label']}"
    return f'schtasks /Delete /TN "{UNIT["task"]}" /F'


def _parser(verb: str, description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo host {verb}", description=description)
    p.add_argument("--os", choices=("linux", "macos", "windows"), default=None,
                   help="write (or remove) the service file for another OS (default: this one)")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    return p


def unit_path(home, os_n: str):
    from halo_harness.host.state import host_dir
    from halo_harness.remote.daemon_units import files_for
    return host_dir(home) / files_for(UNIT["stem"], UNIT["label"])[os_n]


def cmd_install(argv: list) -> int:
    p = _parser("install", "Write halo host's service file (never enabled by Halo) and print the one enable command.")
    p.add_argument("--port", type=int, default=None, help="the port the service listens on (default: host.port, 7431)")
    p.add_argument("--bind", default=None, help="the address it listens on (default: host.bind, 0.0.0.0)")
    p.add_argument("--anyway", action="store_true", help="write it even when this machine serves no Ollama host")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.host.state import host_dir, served_hosts
    from halo_harness.remote.daemon_units import os_name, write_unit
    if not served_hosts() and not a.anyway:
        return C.fail(a.json, "nothing_served", "halo host install: this machine serves no Ollama host (no ollama.hosts "
                                                "entry, nor the default, is on this machine); --anyway writes it all the same")
    home = identity.home()
    os_n = a.os or os_name()
    path, enable = write_unit(os_n, argv_for(a.port, a.bind), env={}, unit=UNIT, out_dir=host_dir(home))
    if a.json:
        C.emit_json({"ok": True, "unit": str(path), "enable": enable, "os": os_n, "argv": argv_for(a.port, a.bind)})
    else:
        print(f"Wrote {path}\nHalo does not enable it. To start halo host at login, run:\n  {enable}")
    return 0


def cmd_uninstall(argv: list) -> int:
    a, rc = C.parse(_parser("uninstall", "Remove the service file `halo host install` wrote; print the disable command."),
                    argv)
    if a is None:
        return rc
    from halo_harness.remote.daemon_units import os_name
    os_n = a.os or os_name()
    path = unit_path(identity.home(), os_n)
    removed = path.exists()
    if removed:
        try:
            path.unlink()
        except OSError as e:
            return C.fail(a.json, "not_removed", f"halo host uninstall: {path} could not be removed: {e}")
    off = disable_command(os_n, path)
    if a.json:
        C.emit_json({"ok": True, "removed": str(path) if removed else None, "disable": off, "os": os_n})
    else:
        print((f"Removed {path}." if removed else f"No service file at {path}.")
              + f"\nIf the service was enabled, run:\n  {off}")
    return 0
