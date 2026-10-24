"""halo_harness.isolation.doctor_rows -- `halo doctor`'s isolation and secrets rows (Halo 3.1.8.0 R5).

    [OK] Isolation: container (docker); user (sudo) -- opt-in, declared by: none
    [WARN] Isolation: lineup ci declares container: no docker or podman on this host
    [OK] Secrets: 1password (op on PATH) -- declared by: bio reviewer
    [WARN] Secrets: bio reviewer declares 1password: no `op` on PATH

Which modes this host can run (docker or podman on PATH; a POSIX host with
sudo for a scoped user, and, for each user a lineup or bio names, whether
`sudo -n` runs as that user without a password), and whether the broker a
lineup or bio declares is here. `sudo -n -u <name> true` is the only
process either row starts, and only on a POSIX host outside the test
environment (BRIDGE_TEST_NO_BACKGROUND_NET), like the capability catalog.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

OK, WARN = "[OK]", "[WARN]"


def _sudo_ok(user: str, which, runner) -> bool:
    try:
        proc = runner([which("sudo"), "-n", "-u", user, "true"], capture_output=True, text=True, timeout=5,
                      stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def isolation_row(declared: list, *, which=shutil.which, runner=subprocess.run, platform: str = sys.platform,
                  spawn: bool = True) -> str:
    from halo_harness.isolation.container import engine
    exe = engine(which)
    can = [f"container ({os.path.basename(exe).split('.')[0]})" if exe else "container: no docker or podman"]
    if platform == "win32":
        can.append("user: not on Windows")
    else:
        can.append("user (sudo)" if which("sudo") else "user: no sudo")
    users = sorted({iso.get("user") for _l, iso, _s in declared if iso and iso.get("mode") == "user" and iso.get("user")})
    if users and platform != "win32" and which("sudo") and spawn:
        can += [f"sudo -n as {u}: {'ok' if _sudo_ok(u, which, runner) else 'asks for a password'}" for u in users]
    gaps = []
    for label, iso, _s in declared:
        if not iso:
            continue
        if iso.get("mode") == "container" and not exe:
            gaps.append(f"{label} declares container: no docker or podman on this host")
        elif iso.get("mode") == "user" and platform == "win32":
            gaps.append(f"{label} declares user: not available on Windows; use container")
        elif iso.get("mode") == "user" and not which("sudo"):
            gaps.append(f"{label} declares user: no sudo on this host")
    who = ", ".join(label for label, iso, _s in declared if iso) or "none"
    if gaps:
        return f"{WARN} Isolation: {'; '.join(gaps)} -> see: docs/ISOLATION.md"
    return f"{OK} Isolation: {'; '.join(can)} -- opt-in, declared by: {who}"


def secrets_row(declared: list, *, which=shutil.which) -> str:
    from halo_harness.isolation.brokers import BrokerError, load
    have = []
    try:
        have.append("1password (op on PATH)" if load("1password").present(which) else "1password: no `op` on PATH")
    except BrokerError:
        pass
    gaps = []
    for label, _iso, sec in declared:
        if not sec:
            continue
        try:
            mod = load(sec.get("broker") or "")
        except BrokerError as e:
            gaps.append(f"{label}: {str(e).removeprefix('secrets: ')}")
            continue
        if not mod.present(which):
            gaps.append(f"{label} declares {mod.NAME}: no `{mod.CLI}` on PATH")
    who = ", ".join(label for label, _iso, sec in declared if sec) or "none"
    if gaps:
        return f"{WARN} Secrets: {'; '.join(gaps)} -> see: docs/ISOLATION.md"
    return f"{OK} Secrets: {'; '.join(have)}; env (ENV:<KEY>) -- opt-in, declared by: {who}"


def entries(cwd=None) -> "list[tuple[str, str]]":
    """doctor's one call: `[("isolation", line), ("secrets", line)]`. Never raises."""
    try:
        from halo_harness.isolation.declared import declared
        found = declared(cwd=cwd)
        spawn = not os.environ.get("BRIDGE_TEST_NO_BACKGROUND_NET")
        return [("isolation", isolation_row(found, spawn=spawn)), ("secrets", secrets_row(found))]
    except Exception as e:
        return [("isolation", f"{WARN} Isolation: the check failed ({type(e).__name__})")]
