"""halo_harness.remote.doctor_check -- `halo doctor`'s remote-control checks
(Halo 2.0.9 round 4). `entries()` returns `[(id, line)]` in the doctor's own
`[OK]` / `[WARN]` / `[MISSING]` vocabulary (so `halo doctor --json` gets the
same `{id, status, message, fix}` records as every other check).

Quiet by default: with `remote.enabled` (the Signal bridge's switch) false and
no signal.json there is one line, naming both switches (`fleet.enabled` opens
the control sockets). Otherwise: the Signal bridge, signal-cli (present,
the 0.14.9 pin, warn at 90 days from its release), the JRE when the JVM build
is used, permissions under `~/.halo/remote/`, and -- when a proxy is
configured -- the seven `*.signal.org` hosts to allow.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

OK, WARN = "[OK]", "[WARN]"
PRIVATE_FILES = ("signal.json", "peers.json", "pending.json", "audit.jsonl", "registration-pin", "bridge.json", "register.json")


def _fix(line: str, cmd: str = "", see: str = "") -> str:
    from halo_harness.doctor import _fix as fix
    return fix(line, cmd=cmd or None, see=see or None)


def proxy_configured(env=None) -> bool:
    env = os.environ if env is None else env
    return any(env.get(k) for k in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")) or \
        "proxyHost" in (env.get("JAVA_TOOL_OPTIONS") or "")


def _live_count() -> int:
    """Live sessions in the registry, counted without touching the file (doctor writes nothing)."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.remote import registry
    path = bridge_home() / "run" / registry.FILENAME
    try:
        return sum(1 for r in registry._load(path) if registry._entry_alive(r)) if path.exists() else 0
    except Exception:
        return 0


def _read_cfg(directory: Path) -> dict:
    import json
    try:
        raw = json.loads((directory / "signal.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _control_line() -> tuple:
    from halo_harness.remote import runtime
    count = _live_count()
    plural = "" if count == 1 else "s"
    sockets = "on (fleet.enabled)" if runtime.fleet_enabled() else "off (fleet.enabled is false)"
    on = runtime.remote_enabled()
    bridge = "on (remote.enabled)" if on else "off (remote.enabled is false)"
    return on, (f"{OK} Remote control: control sockets {sockets}, Signal bridge {bridge} -- "
                f"{count} live session{plural} in the registry")


def _signal_cli_line(cfg: dict) -> tuple:
    """`(line, binary_words)`."""
    from halo_harness.remote import cli_common, signal_install as inst
    words = cli_common.binary_words(cfg)
    version = inst.version_of(words)
    if version is None:
        return _fix(f"{WARN} signal-cli: not found or not runnable ({' '.join(words)})", "halo remote signal setup"), words
    age = inst.age_days()
    if version != inst.VERSION:
        return _fix(f"{WARN} signal-cli: {version} found, Halo is pinned to {inst.VERSION}", "halo remote signal setup"), words
    if age > inst.STALE_AFTER_DAYS:
        return _fix(f"{WARN} signal-cli: {version} was released {inst.RELEASED}, {int(age)} days ago (over {inst.STALE_AFTER_DAYS}); "
                    "signal-cli builds older than about three months can stop working", see="docs/REMOTE.md (signal-cli version)"), words
    return f"{OK} signal-cli: {version} (pinned {inst.VERSION}, released {inst.RELEASED}, {int(age)} days ago)", words


def _uses_jvm(words: list) -> bool:
    from halo_harness.remote import signal_install as inst
    exe = Path(words[-1]) if words else Path("")
    return exe.suffix.lower() == ".bat" or (exe.parent.parent / "lib").is_dir() or not inst.native_host()


def _jre_line() -> str:
    from halo_harness.remote import signal_install as inst
    major = inst.java_major()
    if major is None:
        return _fix(f"{WARN} Java runtime: none found, and this signal-cli build needs JRE {inst.MIN_JRE} or newer",
                    see="https://adoptium.net/ (install a JRE 25)")
    if major < inst.MIN_JRE:
        return _fix(f"{WARN} Java runtime: {major} found, this signal-cli build needs {inst.MIN_JRE} or newer", see="https://adoptium.net/")
    return f"{OK} Java runtime: {major} (signal-cli needs {inst.MIN_JRE}+)"


def _perms_line(directory: Path) -> str:
    if os.name == "nt":
        return f"{OK} {directory}: permissions follow your Windows account (not checked)"
    loose = []
    try:
        if stat.S_IMODE(directory.stat().st_mode) & 0o077:
            loose.append(directory.name + "/")
        for name in PRIVATE_FILES:
            f = directory / name
            if f.exists() and stat.S_IMODE(f.stat().st_mode) & 0o077:
                loose.append(name)
    except OSError as e:
        return f"{WARN} {directory}: could not read permissions ({e})"
    if loose:
        return _fix(f"{WARN} {directory}: group/other can access {', '.join(loose)}",
                    f"chmod 700 {directory} && chmod 600 {directory}/*.json")
    return f"{OK} {directory}: directory 0700, files 0600"


def _egress_line(jvm: bool) -> str:
    from halo_harness.remote.signal_install import HOSTS
    hosts = ", ".join(HOSTS)
    base = f"Proxy configured: allow {hosts} (TCP 443, WebSockets) for signal-cli"
    if jvm and "proxyHost" not in (os.environ.get("JAVA_TOOL_OPTIONS") or ""):
        return _fix(f"{WARN} {base}; the JVM build ignores HTTPS_PROXY, set JAVA_TOOL_OPTIONS=-Dhttps.proxyHost=... -Dhttps.proxyPort=...",
                    see="docs/REMOTE.md (proxied VM)")
    return f"{OK} {base}"


def entries() -> list:
    from halo_harness.config.paths import bridge_home
    from halo_harness.remote import bridge_state
    from halo_harness.remote.signal_config import signal_enabled
    on, control = _control_line()
    out = [("remote", control)]
    directory = bridge_home() / "remote"
    if not (on or directory.is_dir() or signal_enabled()):
        return out
    if not (directory / "signal.json").exists():
        out.append(("remote_signal_cli", _fix(f"{WARN} Signal bridge: not set up yet", "halo remote signal setup")))
        if directory.is_dir():
            out.append(("remote_dir", _perms_line(directory)))
        return out
    cfg = _read_cfg(directory)
    b = bridge_state.read(directory / "bridge.json")
    out.append(("remote_bridge", f"{OK} Signal bridge: {b['state']}" + (f" (pid {b['pid']})" if b["running"] else "")
                + f", remote.signal.enabled {str(signal_enabled()).lower()}"))
    line, words = _signal_cli_line(cfg)
    out.append(("remote_signal_cli", line))
    jvm = _uses_jvm(words)
    if jvm:
        out.append(("remote_jre", _jre_line()))
    out.append(("remote_dir", _perms_line(directory)))
    if proxy_configured():
        out.append(("remote_egress", _egress_line(jvm)))
    return out
