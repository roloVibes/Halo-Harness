"""halo_harness.local_log_cli -- Halo 3.3.8.0 R2: a local server's log and events from the terminal (local_hf_cli.py
dispatches them), any server the steward reads: one Halo started (`halo local serve`), a `huggingface.local_servers`
entry (llama-server, LM Studio, mlx_lm.server), one the probe found (`auto:<port>`).

- `halo local log <server> [-n N] [--kind fit|headroom|truncation|failure|all] [--follow]`: the status line
  (ollama_steward/log_status_hf.py), then the newest lines, each marked with its group; `--follow` reads again every
  FOLLOW_S until Ctrl+C. A server Halo started is also named by its port or its model (providers/local_server.tail).
- `halo local events <server> [--since 24h] [--kind K] [--from-start] [--json]`: the log read now (server_log_hf.scan)
  and its events, newest last, then the kinds that runtime's log never prints (not asked).
Read-only: nothing is sent to the server and nothing on it changes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

FOLLOW_S = 2.0
SEAMS: dict = {}  # "rounds": how many --follow reads before it stops (the tests' seam), "sleep": fn(s)


def _state():
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def _server(name: str):
    from halo_harness.ollama_steward.servers_hf import by_name, roster
    s = by_name(name, _state())
    if s is not None:
        return s
    from halo_harness.providers.local_server import _entry
    e = _entry(_state(), name)
    if e is not None and e.get("id"):
        return next((x for x in roster(_state()) if x.id == e.get("id")), None)
    return None


def _old_row(name: str, n: int) -> bool:
    """A registry row from before 3.3.5.0 R5 (no id): its log the way `halo local log` read it then."""
    from halo_harness.providers.local_server import tail
    got = tail(name, n, state_dir=_state())
    if not got["ok"]:
        return False
    print(f"{got['path']}:")
    print("\n".join(got["lines"]) or "(empty)")
    return True


def _show(lines: list, kind: str) -> None:
    from halo_harness.ollama_steward.log_status import group_of
    for line in lines:
        g = group_of(line)
        if kind in ("", "all") or g == kind:
            print(f"[{g or '-':<10}] {line}")


def _unknown(name: str, prog: str) -> int:
    print(f"{prog}: no local server named {name!r}: halo local servers lists the ones Halo started, "
          "huggingface.local_servers names the others (halo config show huggingface.local_servers)", file=sys.stderr)
    return 1


def cmd_log(argv: list) -> int:
    from halo_harness.ollama_steward.log_status_hf import status
    from halo_harness.ollama_steward.log_tail import local_tail
    from halo_harness.ollama_steward.server_log_hf import tail_lines
    p = argparse.ArgumentParser(prog="halo local log", description="The newest lines of a local server's log, read-only "
                                "(llama-server, LM Studio, mlx_lm.server), each marked fit, headroom, truncation or failure.")
    p.add_argument("server", help="its name (huggingface.local_servers, auto:<port>), or the id, port or model of one "
                   "Halo started")
    p.add_argument("-n", type=int, default=40, help="how many lines (40)")
    p.add_argument("--kind", default="all", choices=("fit", "headroom", "truncation", "failure", "all"))
    p.add_argument("--follow", action="store_true", help=f"read again every {FOLLOW_S:g} s (Ctrl+C stops)")
    a = p.parse_args(argv)
    s = _server(a.server)
    n = max(1, min(int(a.n), 5000))
    if s is None:
        return 0 if _old_row(a.server, n) else _unknown(a.server, "halo local log")
    st = status(_state(), s)
    lines, source, why = tail_lines(s, n)
    if why:
        print(f"log of '{s.name}' ({s.runtime or 'a local server'}): {st['line']}")
        print(f"no log lines: {why}")
        return 1
    print(f"# {source} -- '{s.name}' ({s.runtime or 'a local server'}): {st['state']}, the newest {len(lines)} lines")
    _show(lines, a.kind)
    rounds, sleep = SEAMS.get("rounds"), SEAMS.get("sleep") or time.sleep
    last = lines[-1] if lines else None
    try:
        while a.follow and (rounds is None or rounds > 0):
            rounds = None if rounds is None else rounds - 1
            sleep(FOLLOW_S)
            fresh = local_tail(source, n) if not source.startswith("via host") else tail_lines(s, n)[0]
            new = fresh[len(fresh) - fresh[::-1].index(last):] if last in fresh else fresh
            _show(new, a.kind)
            last = fresh[-1] if fresh else last
    except KeyboardInterrupt:
        pass
    return 0


def cmd_events(argv: list) -> int:
    from halo_harness.ollama_steward.server_events import format_event, read_events
    from halo_harness.ollama_steward.server_log_hf import scan
    from halo_harness.ollama_steward.server_rules_hf import not_asked
    p = argparse.ArgumentParser(prog="halo local events", description="A local server's own words as events (cut "
                                "prompts, cut replies, a spill, out of memory, a failed load, a crash ...), newest last. "
                                "Its log is read read-only; nothing is sent to the server.")
    p.add_argument("server", help="its name, or the id, port or model of one Halo started")
    p.add_argument("--since", default="24h", help="how far back: 1h, 24h (the default), 7d, ...")
    p.add_argument("--kind", default=None, help="only this kind (prompt-trimmed, reply-cut, cpu-spill, ...)")
    p.add_argument("--from-start", action="store_true", help="read its log from the top, not from the last read")
    p.add_argument("--json", action="store_true", help="the events as JSON lines")
    a = p.parse_args(argv)
    s = _server(a.server)
    if s is None:
        return _unknown(a.server, "halo local events")
    _written, why = scan(_state(), s, from_start=a.from_start)
    try:
        rows = read_events(_state(), since=a.since, kind=a.kind, host=s.name)
    except ValueError as e:
        print(f"halo local events: {e}", file=sys.stderr)
        return 2
    for e in rows:
        print(json.dumps(e, default=str) if a.json else format_event(e))
    if not a.json:
        if not rows:
            print(f"no events yet for {s.name}" + (f" ({why})" if why else " (--from-start reads its log from the top)"))
        quiet = not_asked(s.runtime)
        print(f"its log never says: {', '.join(quiet)} (not asked of {s.runtime or 'llama-server'})" if quiet else
              f"{s.runtime or 'llama-server'} says every kind the steward reads")
    return 0
