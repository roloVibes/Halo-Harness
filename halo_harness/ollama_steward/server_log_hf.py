"""halo_harness.ollama_steward.server_log_hf -- Halo 3.3.8.0 R2: the log of each local server (llama-server, LM Studio,
mlx_lm.server), read the way server_log.py reads Ollama's: read-only, the new whole lines since the last read
(server_log.tail: the offset, a truncation or a rotation followed), turned into events (server_context_hf.Rules) in
`<state>/ollama/events.jsonl` with `host` = the server's name (servers_hf.py).

    source_for_server(server, *, platform=None, root=None) -> (path | None, why)
        a server Halo started: the process log Halo keeps (<state>/local/servers/<id>.log); LM Studio: the newest file
        of its server-logs folder (~/.lmstudio/server-logs, else ~/.cache/lm-studio/server-logs; `root` stands in for
        the home folder); a manual entry's `log`; else why it cannot be read from here
    read_new(state_dir, server, *, from_start=False, root=None) -> (lines, state, why)
    scan(state_dir, server, *, from_start=False, root=None, at=None) -> (events written, why)
    tail_servers(state_dir, now=None, *, servers=None, root=None) -> [event]   the steward job's tick, every TAIL_S;
        a log seen for the first time is read from its top when it is at most FIRST_MAX (its load block says the
        window per slot), else from its end
    tail_lines(server, n=200, *, root=None) -> (lines, source, why)            the bounded raw tail

The read positions live in `<state>/ollama/server-log-servers.json` ({name: {path, offset, head, quiet, dead}}), apart
from Ollama's `server-log-state.json`, which its watch thread writes whole every two seconds. A server Halo started
whose process is gone while its registry row stays (a `halo local stop` drops the row) is one death event, with the
command Halo launched it with. Nothing here starts, restarts or configures a server.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

STATE_FILE = "server-log-servers.json"
TAIL_S = 10.0
FIRST_MAX = 4 * 2 ** 20  # a log first seen at most this big is read from its top
LMSTUDIO_DIRS = ((".lmstudio", "server-logs"), (".cache", "lm-studio", "server-logs"))
_LAST: dict = {}
_RULES: dict = {}


def _path(state_dir) -> Path:
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir) / STATE_FILE


def load_state(state_dir) -> dict:
    try:
        st = json.loads(_path(state_dir).read_text(encoding="utf-8"))
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def save_server_state(state_dir, name: str, st: dict) -> None:
    from halo_harness.filelock import file_lock
    p = _path(state_dir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(p.with_suffix(".lock"), timeout=2.0):
            full = load_state(state_dir)
            full[name] = st
            p.write_text(json.dumps(full), encoding="utf-8")
    except OSError:
        pass


def lmstudio_log(root=None) -> "tuple[Optional[Path], list]":
    """(the newest LM Studio server-log file, the folders looked in)."""
    if root is None:
        from halo_harness.config.paths import home
        root = home()
    dirs = [Path(root).joinpath(*parts) for parts in LMSTUDIO_DIRS]
    files: list = []
    for d in dirs:
        try:
            files += [f for f in d.rglob("*.log") if f.is_file()]
        except OSError:
            continue
    if not files:
        return None, dirs
    try:
        return max(files, key=lambda f: (f.stat().st_mtime, f.name)), dirs
    except OSError:
        return None, dirs


def source_for_server(server, *, platform: Optional[str] = None, root=None) -> "tuple[Optional[Path], Optional[str]]":
    from halo_harness.ollama_steward.servers_hf import is_local
    name = getattr(server, "name", "?")
    if getattr(server, "log", None):
        p = Path(server.log).expanduser()
        return (p, None) if p.is_file() else (None, f"the server log of '{name}' is not at {p} (yet)")
    if not is_local(server):
        return None, (f"the server log of '{name}' is on that machine: a halo host there reads it (halo ollama "
                      "hardware --host), or set `log` on its huggingface.local_servers entry to a path read here")
    if getattr(server, "runtime", None) == "lmstudio":
        p, dirs = lmstudio_log(root)
        if p is not None:
            return p, None
        return None, (f"no LM Studio server log under {' or '.join(str(d) for d in dirs)}: LM Studio writes one while "
                      "its server runs (Developer -> Start Server)")
    return None, (f"the server log of '{name}' is not readable from here: start it with `halo local serve` or set "
                  "`log` on its huggingface.local_servers entry")


def read_new(state_dir, server, *, from_start: bool = False, root=None,
             st: Optional[dict] = None) -> "tuple[list, dict, Optional[str]]":
    from halo_harness.ollama_steward.server_log import tail
    st = dict((load_state(state_dir).get(server.name) or {}) if st is None else st)
    if from_start:
        st = {"quiet": st.get("quiet") or {}, "dead": st.get("dead")}
    target, why = source_for_server(server, root=root)
    if target is None:
        return [], st, why
    moved = bool(st.get("path")) and st.get("path") != str(target)  # LM Studio's newest file of a new day
    if moved:
        st = {"quiet": st.get("quiet") or {}, "dead": st.get("dead")}
    lines, st = tail(target, st, from_start=from_start or moved)
    return lines, st, None


def _rules(state_dir, server, fresh: bool):
    from halo_harness.ollama_steward.server_context_hf import Rules
    if fresh:
        return Rules(server.runtime)
    key = (str(state_dir), server.name)
    r = _RULES.get(key)
    if r is None or r.runtime != (server.runtime or "llama-server"):
        r = _RULES[key] = Rules(server.runtime)
    return r


def _death(server, st: dict, lines: list) -> list:
    """A server Halo started whose process is gone: one event per pid, the launch command beside it."""
    from halo_harness.ollama_steward.server_rules import event
    pid = getattr(server, "pid", None)
    if getattr(server, "source", "") == "manual" and not getattr(server, "id", None) or not isinstance(pid, int):
        return []
    from halo_harness.bg_run import pid_alive
    if st.get("dead") == pid or pid_alive(pid):
        return []
    st["dead"] = pid
    last = next((x for x in reversed(lines) if x.strip()), "")
    rt = server.runtime or "llama-server"
    return [event("other-error", f"{rt} {server.name} exited: its process {pid} is gone (no `halo local stop`)" +
                  (f"; its last line: {last.strip()[:120]}" if last else ""), f"{rt} terminated: pid {pid}; {last}"[:400],
                  at=time.time(), model=server.model, runtime=rt, death=True, launch=server.launch, pid=pid)]


def scan(state_dir, server, *, from_start: bool = False, root=None, at=None) -> "tuple[list, Optional[str]]":
    """One read of the server's log -> (the events written, why nothing was read)."""
    from halo_harness.ollama_steward.server_events import record_events
    lines, st, why = read_new(state_dir, server, from_start=from_start, root=root)
    rules = _rules(state_dir, server, from_start)
    evs = [e for x in lines for e in rules.feed(x, at=at)] + rules.flush()
    evs += _death(server, st, lines)
    if server.runtime == "tensorfold" and not from_start:  # 3.3.9.3: its queue from /health or /metrics (loopback)
        from halo_harness.ollama_steward.servers_hf import is_local
        evs += _tf_stats(server) if is_local(server) else []
    if server.runtime == "strata":  # 3.3.9.2: Strata's log never names the model it serves; the roster row does
        for e in evs:
            e["model"] = e.get("model") or server.model or "strata"
    for e in evs:
        e["data"].setdefault("runtime", server.runtime or "llama-server")
        if server.launch and e["kind"] in ("gpu-memory", "other-error", "load-failed"):
            e["data"].setdefault("launch", server.launch)
    quiet = st.setdefault("quiet", {})
    written = record_events(state_dir, evs, host=server.name, quiet=quiet)
    if why is None or written:
        save_server_state(state_dir, server.name, st)
    return written, why


def _tf_stats(server) -> list:
    try:
        from halo_harness.ollama_steward.server_stats_tensorfold import read
        return read(server)
    except Exception:
        return []


def tail_servers(state_dir, now: Optional[float] = None, *, servers=None, root=None) -> list:
    """Every local server on this machine whose log is readable, read at most every TAIL_S (the job's tick)."""
    from halo_harness.ollama_steward.servers_hf import is_local, roster
    now = time.time() if now is None else now
    out = []
    for s in roster(state_dir) if servers is None else servers:
        key = (str(state_dir), s.name)
        if not (is_local(s) or s.log) or now - _LAST.get(key, 0.0) < TAIL_S:
            continue
        _LAST[key] = now
        try:
            out += scan(state_dir, s, root=root, **{"at": now, **_first_sight(state_dir, s, root)})[0]
        except Exception:
            continue
    return out


def _first_sight(state_dir, server, root) -> dict:
    """A log the steward never read: from its top when it is small (its load block holds the window per slot), the
    lines with no timestamp of their own dated by the file's modification time, not by now."""
    if (load_state(state_dir).get(server.name) or {}).get("path"):
        return {}
    target, _why = source_for_server(server, root=root)
    try:
        st = target.stat() if target is not None else None
    except OSError:
        st = None
    return {"from_start": True, "at": st.st_mtime} if st is not None and st.st_size <= FIRST_MAX else {}


def tail_lines(server, n: int = 200, *, root=None) -> "tuple[list, str, Optional[str]]":
    """(the newest `n` lines, where they were read, why nothing was read) for a server."""
    from halo_harness.ollama_steward.log_tail import local_tail
    target, why = source_for_server(server, root=root)
    if target is None:
        from halo_harness.ollama_steward.host_reads_hf import tail_via_host
        got = tail_via_host(server, n)
        return got if got is not None else ([], "", why)
    return local_tail(target, n), str(target), None


def reset() -> None:
    _LAST.clear()
    _RULES.clear()
