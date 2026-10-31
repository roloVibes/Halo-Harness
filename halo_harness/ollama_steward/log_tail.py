"""halo_harness.ollama_steward.log_tail -- Halo 3.3.6.0 R3: the bounded raw tail of a host's server log and the
steward's reads of the remote ones (server_log_remote.py holds the command and the per-host state).

    tail_lines(host, n=200, *, runner=None, ssh_runner=None, platform=None) -> (lines, source, why)
        any host: this machine's rotation set (server.log, server-1.log, ... by mtime), journald on a Linux with
        no file, or that machine's over its `ssh:` entry
    local_tail(path, n=200) -> lines
    remote_tail(host, n=200, *, runner=None, timeout=5.0, tail_bytes=TAIL_BYTES) -> (lines, source, why)
    scan_remote(state_dir, host, *, runner=None, from_start=False) -> (events written, why)
    tail_remote_hosts(state_dir, now=None, *, hosts=None) -> [event]   job.py's tick: every REMOTE_S per host
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.ollama_steward import server_log_remote as R

_LAST: dict = {}
_RULES: dict = {}


def local_tail(path, n: int = 200) -> list:
    """The newest `n` lines across `path`'s rotation set (server.log, server-1.log, ... by mtime)."""
    p = Path(path)
    try:
        files = sorted(p.parent.glob(f"{p.stem}*{p.suffix}"), key=lambda f: -f.stat().st_mtime)[:3]
    except OSError:
        return []
    lines: list = []
    for f in files:
        try:
            with open(f, "rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - R.TAIL_BYTES))
                data = fh.read()
        except OSError:
            continue
        part = data.decode("utf-8", "replace").splitlines()
        lines = (part[1:] if size > R.TAIL_BYTES else part) + lines
        if len(lines) >= n:
            break
    return [x.rstrip("\r") for x in lines[-n:]]


def remote_tail(host, n: int = 200, *, runner: Optional[Callable] = None, timeout: float = 5.0,
                tail_bytes: int = R.TAIL_BYTES) -> "tuple[list, str, Optional[str]]":
    """The newest `n` lines of that machine's log (the last `tail_bytes` of the newest two files of the rotation
    set, or the journal)."""
    run, why = R.runner_for(host, runner, timeout)
    if run is None:
        return [], "", why
    got = R._call(run, {}, timeout, tail=tail_bytes, jargs=f"-n {int(n)}")
    if got is None:
        return [], "", "the ssh read did not answer"
    if got["kind"] == "journal":
        rows = [x for x in got["lines"] if x.strip() and not x.startswith("-- ")]
        return rows[-n:], f"ssh {host.ssh}: journalctl -u ollama", None
    if not got["files"]:
        return [], "", "no server log on that machine"
    lines: list = []
    for f in reversed(got["files"]):
        data = f["data"] if f["data"].endswith(b"\n") else f["data"] + b"\n"
        part = R._whole(data)[0]
        lines += part[1:] if f["size"] > tail_bytes else part  # the first line of a cut tail is a partial one
    return lines[-n:], f"ssh {host.ssh}: {got['files'][0]['path']}", None


def tail_lines(host, n: int = 200, *, runner: Optional[Callable] = None, ssh_runner: Optional[Callable] = None,
               platform: Optional[str] = None) -> "tuple[list, str, Optional[str]]":
    """(the newest `n` lines, where they were read, why nothing was read) for any configured host."""
    from halo_harness.fleet.ollama_share import served_here
    from halo_harness.ollama_steward.hardware_readers import server_log_path
    if host is not None and not served_here(host.url):
        if ssh_runner is None:  # 3.3.7.0 R1: a paired halo host serves the tail before ssh (prompt sizes, no bodies)
            from halo_harness.ollama_steward.host_reads import tail_of
            got = tail_of(host, n)
            if got is not None and (got[0] or not got[2] or not getattr(host, "ssh", None)):
                return got  # a host that did not answer falls through to the ssh entry, when there is one
        if not getattr(host, "ssh", None):
            return [], "", f"the server log of '{host.name}' is on that machine (no ssh entry)"
        return remote_tail(host, n, runner=ssh_runner)
    target = server_log_path(platform)
    if target.exists():
        return local_tail(target, n), str(target), None
    if (platform or sys.platform).startswith("linux"):
        from halo_harness.config.paths import background_net_disabled
        if runner is None and background_net_disabled():
            return [], "journalctl -u ollama", "journald not read (background reads are off)"
        from halo_harness.providers.ollama_hw import _run_tool
        out = _run_tool(["journalctl", "-u", "ollama", "-o", "cat", "--no-pager", "-n", str(int(n))], timeout=10.0,
                        runner=runner)
        return ((out or "").splitlines()[-n:], "journalctl -u ollama",
                None if out is not None else "journalctl did not answer")
    return [], str(target), f"no server log at {target}"


def scan_remote(state_dir, host, *, runner: Optional[Callable] = None, from_start: bool = False) -> "tuple[list, Optional[str]]":
    """One read of that host's log turned into events (written with `host` = its name here)."""
    from halo_harness.ollama_steward.server_context import Rules
    from halo_harness.ollama_steward.server_events import record_events
    lines, why = R.read_new_remote(state_dir, host, runner=runner, from_start=from_start)
    rules = Rules() if from_start else _RULES.setdefault((str(state_dir), host.name), Rules())
    evs = [e for line in lines for e in rules.feed(line)] + (rules.flush() if from_start else [])
    st = R.host_state(state_dir, host.name)
    quiet = st.setdefault("quiet", {})
    written = record_events(state_dir, evs, host=host.name, quiet=quiet)
    if written:
        R._save(state_dir, host.name, {**R.host_state(state_dir, host.name), "quiet": quiet})
    return written, why


def tail_remote_hosts(state_dir, now: Optional[float] = None, *, hosts=None) -> list:
    """Every configured host with `ssh:` that this machine does not serve, read at most every REMOTE_S."""
    from halo_harness.fleet.ollama_share import served_here
    now = time.time() if now is None else now
    if hosts is None:
        from halo_harness.providers.ollama import resolve_ollama_hosts
        hosts = resolve_ollama_hosts()
    out = []
    for h in hosts:
        key = (str(state_dir), h.name)
        if not getattr(h, "ssh", None) or served_here(h.url) or now - _LAST.get(key, 0.0) < R.REMOTE_S:
            continue
        _LAST[key] = now
        try:
            out += scan_remote(state_dir, h)[0]
        except Exception:
            continue
    return out
