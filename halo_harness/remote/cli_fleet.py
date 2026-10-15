"""halo_harness.remote.cli_fleet -- `halo remote agents | steer | stop` (Halo
3.0.5.0 "Fleet" round R1): a live session's agent tree from a terminal, over
the session's control socket (remote/agent_control.py has the wire).

    halo remote agents <sid>                                   the tree: id, name, state, cost, model, what it does
    halo remote steer <sid> --agent <aid> [--redirect] TEXT    a note that agent reads before its next model call
    halo remote stop <sid> --agent <aid> [--reason TEXT]       stop it (and its subtree) at its next tool boundary

`<sid>` is a session id or a unique prefix (`halo remote sessions` lists
them); `--agent main` is the main agent. Every verb takes `--json`. The
commands go out with `by` = `fleet.name` and `via` = "halo remote".
"""

from __future__ import annotations

import argparse

from halo_harness.remote import cli_common as C

VERBS = ("agents", "steer", "stop")
CALL_TIMEOUT_S = 5.0


def _parser(verb: str, description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo remote {verb}", description=description)
    p.add_argument("session", help="a live session id, or a unique prefix of one")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    return p


def _entry(prefix: str):
    from halo_harness.remote import registry
    rows = registry.list_live()
    hits = [r for r in rows if r.get("session_id") == prefix] or \
        [r for r in rows if str(r.get("session_id") or "").startswith(prefix)]
    if len(hits) == 1:
        return hits[0], ""
    if not hits:
        return None, f"No live session matches {prefix!r} (`halo remote sessions` lists them)."
    return None, f"{len(hits)} live sessions start with {prefix!r}; give more of the id."


def _send(a, cmd: str, **fields):
    """`(result, 0)` or `(None, exit code)` after saying why."""
    entry, err = _entry(a.session)
    if entry is None:
        return None, C.fail(a.json, "no_session", err)
    from halo_harness.remote.client import ControlClient, default_token_for
    from halo_harness.remote.fleet_identity import fleet_name
    client = None
    try:
        client = ControlClient(str(entry.get("endpoint") or ""), default_token_for(entry), timeout=CALL_TIMEOUT_S)
        resp = client.call(cmd, by=fleet_name(), via="halo remote", **fields)
    except Exception as e:  # refused, closed, timed out
        return None, C.fail(a.json, "unreachable", f"Session {a.session}: {type(e).__name__}: {e}")
    finally:
        if client is not None:
            client.close()
    if not resp.get("ok"):
        return None, C.fail(a.json, "refused", str(resp.get("error") or "the session refused the command"))
    return resp.get("result") or {}, 0


def cmd_agents(argv: list) -> int:
    a, rc = C.parse(_parser("agents", "List a live session's agents: the main agent and every sub-agent."), argv)
    if a is None:
        return rc
    res, rc = _send(a, "agents")
    if res is None:
        return rc
    rows = res.get("agents") or []
    if a.json:
        C.emit_json({"ok": True, "agents": rows})
        return 0
    from halo_harness.agent.agent_hooks import format_tree
    print(f"{len(rows)} agent(s) in session {a.session}: id, name, state, cost, model, what it is doing")
    for line in format_tree(rows):
        print("  " + line)
    return 0


def cmd_steer(argv: list) -> int:
    p = _parser("steer", "Send one agent a note it reads before its next model call.")
    p.add_argument("--agent", required=True, metavar="AGENT_ID", help="the agent's id (`main` for the main agent)")
    p.add_argument("--redirect", action="store_true", help="replace the rest of its task with TEXT")
    p.add_argument("text", nargs="+", help="the note")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    res, rc = _send(a, "agent_steer", agent_id=a.agent, text=" ".join(a.text), mode="redirect" if a.redirect else "nudge")
    if res is None:
        return rc
    if a.json:
        C.emit_json({"ok": True, **res})
    else:
        print(f"Steer for {res.get('agent_id')} delivered ({res.get('delivered')}, {res.get('mode')}); "
              "it lands before that agent's next model call.")
    return 0


def cmd_stop(argv: list) -> int:
    p = _parser("stop", "Stop one agent (and every agent under it) at its next tool boundary.")
    p.add_argument("--agent", required=True, metavar="AGENT_ID", help="the agent's id (`main` interrupts the turn)")
    p.add_argument("--reason", default="", help="what its parent is told")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    res, rc = _send(a, "agent_stop", agent_id=a.agent, reason=a.reason)
    if res is None:
        return rc
    if a.json:
        C.emit_json({"ok": True, **res})
    elif res.get("interrupted"):
        print("The main agent's turn was interrupted.")
    else:
        print(f"Stopping {', '.join(res.get('stopping') or [str(res.get('agent_id'))])} at the next tool boundary; "
              "its parent gets the stopped hand-back and carries on.")
    return 0
