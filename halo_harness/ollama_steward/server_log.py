"""halo_harness.ollama_steward.server_log -- Halo 3.3.4.0 R2: a read-only
tail of the local Ollama server's log and a `/api/ps` poll, turned into
events (server_rules.py, server_context.py) in `<state>/ollama/events.jsonl`
(server_events.py).

- `tail(path, state, from_start=False)`: the new whole lines of the log
  file. The file is opened read-only for each read and closed at once (on
  Windows a shared read handle: Ollama keeps writing and rotating it). The
  first read starts at the end (`from_start`: the top); a rotation (the
  file's first line changed: Ollama renames server.log to server-1.log at a
  start) finishes the old file from the saved offset, then reads the new one.
- `tail_journal(state)`: on Linux with no log file, `journalctl -u ollama -o
  cat --show-cursor` (`--since` now on the first read, `--after-cursor` then)
  through `providers.ollama_hw._run_tool`, the subprocess seam every probe uses.
- `scan(state_dir, host)`: one catch-up read (`halo ollama events`; R3: ssh).
- `watch(state_dir, host, stop)`: the tail every TAIL_S and `/api/version` +
  `/api/ps` every POLL_S as one loop until `stop` is set (`halo ollama
  events --watch` today; R4's steward job owns it later). A new startup
  block re-reads the hardware card.

Nothing here writes to the server, sends it a model request or changes a
setting. The read position and the quiet-period marks live in
`<state>/ollama/server-log-state.json`.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.ollama_steward import ledger

STATE_FILE = "server-log-state.json"
TAIL_S, POLL_S = 2.0, 20.0
_HEAD = 200
_MAX_READ = 16 * 2 ** 20
_JOURNAL = ["journalctl", "-u", "ollama", "-o", "cat", "--no-pager", "--show-cursor"]


def state_path(state_dir) -> Path:
    return ledger.ledger_dir(state_dir) / STATE_FILE


def load_state(state_dir) -> dict:
    try:
        st = json.loads(state_path(state_dir).read_text(encoding="utf-8"))
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state_dir, st: dict) -> None:
    try:
        p = state_path(state_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(st), encoding="utf-8")
    except OSError:
        pass


def _head(path: Path) -> str:
    try:
        with open(path, "rb") as f:
            return f.read(_HEAD).decode("utf-8", "replace")
    except OSError:
        return ""


def _read(path: Path, offset: int) -> "tuple[list, int]":
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            data = f.read(_MAX_READ)
    except OSError:
        return [], offset
    end = data.rfind(b"\n")
    if end < 0:
        return [], offset
    return data[:end].decode("utf-8", "replace").split("\n"), offset + end + 1


def rotated_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}-1{path.suffix}")


def tail(path, state: dict, *, from_start: bool = False) -> "tuple[list, dict]":  # new whole lines since `state`
    path = Path(path)
    st = dict(state or {})
    head = _head(path)
    try:
        size = path.stat().st_size
    except OSError:
        return [], st
    if st.get("path") != str(path) or not isinstance(st.get("offset"), int):
        st = {**st, "path": str(path), "offset": 0 if from_start else size, "head": head}
    lines: list = []
    if st.get("head") and not ledger.same_file(st["head"], head):
        old = rotated_path(path)
        if ledger.same_file(st["head"], _head(old)):
            lines, _ = _read(old, st["offset"])
        st.update(offset=0, head=head)
    elif size < st["offset"]:
        st["offset"] = 0
    more, offset = _read(path, st["offset"])
    st.update(offset=offset, head=head if len(head) > len(st.get("head") or "") else st.get("head") or head)
    return [x.rstrip("\r") for x in lines + more], st


def tail_journal(state: dict, *, runner: Optional[Callable] = None,
                 from_start: bool = False) -> "tuple[list, dict]":
    """New journald lines of the ollama unit -> (lines, the new state)."""
    from halo_harness.providers.ollama_hw import _run_tool
    st = dict(state or {})
    cmd = list(_JOURNAL)
    if st.get("cursor"):
        cmd += ["--after-cursor", st["cursor"]]
    elif not from_start:
        cmd += ["--since", time.strftime("%Y-%m-%d %H:%M:%S")]
    out = _run_tool(cmd, timeout=10.0, runner=runner)
    if out is None:
        return [], st
    lines = []
    for line in out.splitlines():
        if line.startswith("-- cursor: "):
            st["cursor"] = line[len("-- cursor: "):].strip()
        elif line.strip() and not line.startswith("-- No entries --"):
            lines.append(line)
    st["source"] = "journalctl -u ollama"
    return lines, st


def source_for(host, *, path=None, platform: Optional[str] = None) -> "tuple[Optional[Path], Optional[str]]":
    """(the log file or None for journald, why not) for `host`'s server log."""
    from halo_harness.ollama_steward.hardware_readers import server_log_path
    from halo_harness.fleet.ollama_share import served_here
    if path is not None:
        return Path(path), None
    if host is not None and not served_here(host.url):  # 3.3.6.0 R3: read over ssh in read_new (server_log_remote.py)
        return None, f"the server log of '{host.name}' is on that machine ({'read over ssh' if getattr(host, 'ssh', None) else 'no ssh entry'})"
    target = server_log_path(platform)
    if target.exists():
        return target, None
    if (platform or sys.platform).startswith("linux"):
        return None, None
    return None, f"no server log at {target}"


def _remote(host) -> bool:
    from halo_harness.fleet.ollama_share import served_here
    return host is not None and not served_here(getattr(host, "url", ""))


def read_new(state_dir, host, *, path=None, platform=None, runner=None, from_start=False,
             st: Optional[dict] = None) -> "tuple[list, dict, Optional[str]]":
    """(new lines, the state, why nothing could be read); `from_start` reads
    the log again from its top (its events are written again)."""
    st = load_state(state_dir) if st is None else st
    if from_start:
        st = {"quiet": st.get("quiet") or {}}
    if path is None and _remote(host):  # 3.3.6.0 R3: that machine's log over its ssh: entry
        from halo_harness.ollama_steward.server_log_remote import read_new_remote
        lines, why = read_new_remote(state_dir, host, from_start=from_start)
        return lines, st, why
    target, why = source_for(host, path=path, platform=platform)
    if why:
        return [], st, why
    if target is None:
        from halo_harness.config.paths import background_net_disabled
        if runner is None and background_net_disabled():
            return [], st, "journald not read (background reads are off)"
        lines, st = tail_journal(st, runner=runner, from_start=from_start)
        return lines, st, None
    lines, st = tail(target, st, from_start=from_start)
    return lines, st, None


def _card_line(host, path, api, runner) -> str:
    try:
        from halo_harness.ollama_steward.hardware import format_card, hardware_card
        return "; ".join(format_card(hardware_card(host, log_path=path, api=api, runner=runner))[:3])
    except Exception:
        return ""


def _emit(state_dir, host, evs: list, st: dict, path, api, runner) -> list:
    from halo_harness.ollama_steward.server_events import record_events
    for ev in evs:
        if ev["kind"] == "startup":
            card = _card_line(host, path, api, runner)
            ev["say"] += f" ({card})" if card else ""
    quiet = st.setdefault("quiet", {})
    return record_events(state_dir, evs, host=getattr(host, "name", None), quiet=quiet)


def scan(state_dir, host, *, path=None, platform=None, runner=None, api=None,
         from_start: bool = False) -> "tuple[list, Optional[str]]":
    """One catch-up read of the log -> (the events written, why nothing was read)."""
    from halo_harness.ollama_steward.server_context import Rules
    lines, st, why = read_new(state_dir, host, path=path, platform=platform, runner=runner, from_start=from_start)
    if why:
        return [], why
    rules = Rules()
    evs = [e for line in lines for e in rules.feed(line)] + rules.flush()
    written = _emit(state_dir, host, evs, st, path, api, runner)
    save_state(state_dir, st)
    return written, None


def _default_api(host):
    from halo_harness.config.paths import background_net_disabled
    if background_net_disabled():
        return lambda _path: None
    from halo_harness.providers.ollama import fetch_ps, probe_version
    return lambda p: probe_version(host) if p == "/api/version" else fetch_ps(host)


def watch(state_dir, host, stop, *, path=None, platform=None, runner=None, api: Optional[Callable] = None,
          on_event: Optional[Callable] = None, from_start: bool = False, tail_s: float = TAIL_S,
          poll_s: float = POLL_S, clock: Callable = time.time) -> None:
    """The tail and the poll as one loop until `stop` (a threading.Event) is set."""
    from halo_harness.ollama_steward.hardware_sources import parse_ps
    from halo_harness.ollama_steward.server_context import Rules
    from halo_harness.ollama_steward.server_events import ps_delta
    api = api or _default_api(host)
    tail_s = max(tail_s, 10.0) if path is None and _remote(host) else tail_s  # 3.3.6.0 R3: an ssh read per 10 s
    rules, before, next_poll, first = Rules(), None, 0.0, True
    st = load_state(state_dir)
    while not stop.is_set():
        lines, st, _why = read_new(state_dir, host, path=path, platform=platform, runner=runner,
                                   from_start=from_start and first, st=st)
        first = False
        evs = [e for line in lines for e in rules.feed(line)]
        now = clock()
        evs += rules.tick(now)
        if now >= next_poll:
            next_poll = now + poll_s
            evs += rules.api_result(isinstance(api("/api/version"), dict), now)
            ps = api("/api/ps")
            if isinstance(ps, dict):
                rows = parse_ps(ps)
                evs += ps_delta(before, rows, now)
                before = rows
        for row in _emit(state_dir, host, evs, st, path, api, runner):
            if on_event is not None:
                on_event(row)
        save_state(state_dir, st)
        stop.wait(tail_s)
