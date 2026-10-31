"""halo_harness.session_trace_cli -- `halo session export <id> [--md FILE]`
(Halo 3.3.0.0 R6): a session's Markdown trace (session_trace.py), the same
bytes Studio's Export button downloads (`GET sessions/<sid>/trace.md`) and
the TUI's `/export` writes beside the session log.

    halo session export <id>             writes halo-trace-<id>-<yyyy-mm-dd-hhmm>.md here and prints its path
    halo session export <id> --md FILE   writes FILE
    halo session export <id> --md -      prints the trace

    halo session show <id> [--json]      3.3.7.0 R2 (G15): the offline promise -- what left this machine, each
                                         local call's host (agent/offline_promise.py)
    halo session postmortem [--session ID] [--turn N] [--agent ID] [--json]   3.3.6.0 R4: why one answer came
                                         out as it did (agent/postmortem.py); no session: the newest that called a
                                         local model; no turn: its newest

`<id>` is a session id or a unique prefix of one, looked up across every
project's sessions under the state dir (`~/.halo/sessions/<slug>/<id>.jsonl`).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional


def find_session_log(sid: str) -> "tuple[Optional[Path], str]":
    """(the log, '') for a session id or a unique prefix; (None, why) otherwise."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.safe_id import is_safe_session_id
    if not is_safe_session_id(sid):
        return None, f"not a session id: {sid!r}"
    root = bridge_home() / "sessions"
    exact = sorted(root.glob(f"*/{sid}.jsonl")) if root.is_dir() else []
    hits = exact or (sorted(root.glob(f"*/{sid}*.jsonl")) if root.is_dir() else [])
    stems = sorted({p.stem for p in hits})
    if not hits:
        return None, f"no session {sid!r} in the state dir's sessions/ (each id is a <id>.jsonl under sessions/<project>/)"
    if len(stems) > 1:
        return None, f"{sid!r} matches {len(stems)} sessions: {', '.join(stems[:5])}"
    return max(hits, key=lambda p: p.stat().st_mtime), ""


def _tiers(lineup: Optional[str], cwd: Optional[str]) -> dict:
    """{agent name: tier name} of the lineup, best effort ({} when it does not load)."""
    if not lineup:
        return {}
    try:
        from halo_harness.teams_tiers import effective_tiers, main_key
        from halo_harness.teams_yaml import load_team_template_raw
        template = load_team_template_raw(lineup, cwd=cwd) or {}
        out = {m: t["name"] for t in effective_tiers(template) for m in t["members"]}
        lead = main_key(template.get("agents"))
        if lead and lead in out:
            out["main"] = out[lead]
        return out
    except Exception:
        return {}


def trace_for_path(path: Path) -> str:
    """The trace of the log at `path`, its tiers resolved from the session's own cwd and lineup."""
    from halo_harness.session_trace import _agents, _read, trace_markdown
    nodes = _read(path)
    cwd = next((n.get("cwd") for n in nodes if n.get("type") == "meta" and n.get("cwd")), None)
    lineup = next((i["lineup"] for i, _ in _agents(path) if i.get("lineup")), None)
    return trace_markdown(path, lineup=lineup, tiers=_tiers(lineup, cwd))


def trace_name(sid: str, now: Optional[float] = None) -> str:
    return f"halo-trace-{sid}-{time.strftime('%Y-%m-%d-%H%M', time.localtime(now or time.time()))}.md"


def write_trace(path: Path, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(trace_for_path(path).encode("utf-8"))
    return out


def cmd_session(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="halo session", description="A session's records.")
    sub = parser.add_subparsers(dest="verb")
    exp = sub.add_parser("export", help="Write a session as one Markdown trace file",
                         description="Write a session as one Markdown trace file: a header with the totals, then one "
                                     "entry per row (prompts, text, tool calls and results, steers, nudges, permission "
                                     "answers, turn ends, compactions, errors), keys masked, home paths as ~.")
    exp.add_argument("session", metavar="ID", help="Session id or unique prefix")
    exp.add_argument("--md", default=None, metavar="FILE",
                     help="Write to FILE (- prints it; default: halo-trace-<id>-<yyyy-mm-dd-hhmm>.md here)")
    pm = sub.add_parser("postmortem", help="Why one answer came out as it did: cut, memory, thinking, tools, cache",
                        description="One assistant turn reconstructed from the traffic ledger and the session log: "
                                    "was the prompt cut, memory-dominated, thinking only, no tools, an empty reply "
                                    "from a small budget, the cache reused -- one line, the details beneath.")
    pm.add_argument("--session", default=None, metavar="ID")
    pm.add_argument("--turn", type=int, default=None)
    pm.add_argument("--agent", default=None, metavar="ID", help="a sub-agent's own session id")
    pm.add_argument("--json", action="store_true")
    show = sub.add_parser("show", help="A session's offline promise: what left this machine, each call's host",
                          description="3.3.7.0 R2 (G15): '100 % local -- 0 tokens left this machine', or which calls "
                                      "left it and to where, read from the session log and the traffic ledger.")
    show.add_argument("session", metavar="ID", help="Session id or unique prefix")
    show.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.verb == "postmortem":
        return _postmortem(args)
    if args.verb == "show":
        return _show(args)
    if args.verb != "export":
        parser.print_help()
        return 0 if not argv else 2
    path, why = find_session_log(args.session)
    if path is None:
        print(f"halo session export: {why}", file=sys.stderr)
        return 1
    if args.md == "-":
        text = trace_for_path(path)
        buf = getattr(sys.stdout, "buffer", None)
        buf.write(text.encode("utf-8")) if buf is not None else sys.stdout.write(text)
        sys.stdout.flush()
        return 0
    out = write_trace(path, Path(args.md) if args.md else Path.cwd() / trace_name(path.stem))
    print(f"wrote {out}")
    return 0


def _postmortem(args) -> int:
    import json
    from halo_harness.agent.postmortem import postmortem
    from halo_harness.config.paths import bridge_home
    from halo_harness.ollama_steward.ledger import read_calls
    state = bridge_home()
    sid = args.agent or args.session
    if not sid:
        turns = [x for x in read_calls(state) if x.get("kind") == "turn" and x.get("session")]
        sid = turns[-1]["session"] if turns else None
    if not sid:
        print("halo session postmortem: no session has called a local model yet (the traffic ledger is empty)",
              file=sys.stderr)
        return 1
    got = postmortem(state, sid, turn=args.turn)
    if args.json:
        print(json.dumps(got, indent=2, default=str))
        return 0 if got.get("ok") else 1
    print(f"turn {got.get('turn')} of {sid}: {got['line']}")
    for line in got.get("details") or []:
        print(f"  {line}")
    return 0 if got.get("ok") else 1


def _show(args) -> int:
    import json
    from halo_harness.agent.offline_promise import promise
    from halo_harness.config.paths import bridge_home
    path, why = find_session_log(args.session)
    if path is None:
        print(f"halo session show: {why}", file=sys.stderr)
        return 1
    got = promise(bridge_home(), path.stem, log_path=path)
    if args.json:
        print(json.dumps({"session": path.stem, **got}, indent=2, default=str))
        return 0
    print(f"session {path.stem}: {got['line']}")
    for line in got["per_call"]:
        print(f"  {line}")
    return 0
