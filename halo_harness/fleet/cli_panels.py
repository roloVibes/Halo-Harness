"""halo_harness.fleet.cli_panels -- `halo fleet record | digest` (Halo 3.0.5.0
"Fleet" round R4; the dispatcher is cli.py). Both read this harness's own
files and need no hub and no Studio:

    halo fleet record <sid> [--agent <aid>] [--out PATH] [--json]
        a session (or one agent and its sub-agents) as a self-contained HTML replay, from its
        transcripts on disk: ~/.halo/recordings/<sid>[-<aid>].html, or --out
    halo fleet digest [--since 2h|45m|1d|<unix seconds>|<ISO time>] [--json]
        what happened since then, per harness, computed in code: sessions started and ended,
        cost, decisions answered and by whom, files touched, errors, hand-offs (default: 1d)

A session id prefix is enough for `record` when it is unique. Exit codes: 0
done, 1 could not (the reason on stderr), 2 usage.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from halo_harness.fleet import identity
from halo_harness.remote import cli_common as C


def _parser(verb: str, description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo fleet {verb}", description=description)
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    return p


def _session_log(home: Path, sid: str):
    from halo_harness.fleet.history import find
    hit = find(home, sid)
    if hit is not None or len(sid) < 4:
        return hit, []
    root = home / "sessions"
    many = sorted({p for p in root.glob(f"*/{sid}*.jsonl")}) if root.is_dir() and sid.replace("-", "").isalnum() else []
    return (many[0] if len(many) == 1 else None), many


def cmd_record(argv: list) -> int:
    p = _parser("record", "Write a session (or one agent of it) as a self-contained HTML flight recording.")
    p.add_argument("session", help="the session id (a unique prefix is enough)")
    p.add_argument("--agent", default=None, help="only this agent and its sub-agents (its agent id)")
    p.add_argument("--out", default=None, help="write here instead of ~/.halo/recordings/<sid>[-<aid>].html")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.fleet import history, recording
    from halo_harness.privateio import write_private_atomic
    home = identity.home()
    log, many = _session_log(home, a.session)
    if log is None:
        why = (f"{len(many)} sessions start with {a.session!r}; give more of the id" if many
               else f"no session {a.session!r} under {home / 'sessions'}")
        return C.fail(a.json, "no_session", f"halo fleet record: {why}")
    hist = history.read(log)
    if a.agent and not any(x.get("agent_id") == a.agent for x in hist.get("agents") or []):
        ids = ", ".join(str(x.get("agent_id")) for x in hist.get("agents") or [])
        return C.fail(a.json, "no_agent", f"halo fleet record: no agent {a.agent!r} in that session (agents: {ids})")
    name = identity.fleet_name()
    if a.out:
        out = Path(a.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        write_private_atomic(out, recording.render(hist, harness=name, agent=a.agent))
    else:
        out = recording.write(home, hist, harness=name, agent=a.agent)
    shown = recording.scoped(hist, a.agent)
    if a.json:
        C.emit_json({"ok": True, "path": str(out), "session_id": hist.get("session_id"), "agents": len(shown["agents"]),
                     "states": len(shown.get("states") or []), "bytes": out.stat().st_size})
        return 0
    print(f"Recorded {hist.get('title') or hist.get('session_id')} ({len(shown['agents'])} agent(s)) to {out}")
    print("It opens in any browser with no network: Space plays, the bar scrubs, 1 2 3 pick the stream.")
    return 0


def cmd_digest(argv: list) -> int:
    p = _parser("digest", "What happened across the fleet since a moment, per harness (computed, no model).")
    p.add_argument("--since", default="1d", help="2h, 45m, 1d, unix seconds or an ISO time (default 1d)")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.fleet import digest
    try:
        since = digest.parse_since(a.since)
    except ValueError as e:
        return C.fail(a.json, "usage", f"halo fleet digest: {e}")
    me = identity.harness()
    live = []
    try:
        from halo_harness.remote.registry import list_live
        live = [e.get("session_id") for e in list_live() if isinstance(e, dict)]
    except Exception:
        pass
    d = digest.compute(identity.home(), since, local_id=me["id"], local_name=me["name"], live_ids=live)
    if a.json:
        C.emit_json({"ok": True, **d})
    else:
        print(digest.text(d))
    return 0
