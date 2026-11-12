"""halo_harness.studio.fleet_api -- Studio's agent-level routes on a live
session (Halo 3.0.5.0 "Fleet" round R1), mounted under `sessions/` by
studio/sessions_api.py; the same guard as every Studio route.

    GET  sessions/<sid>/agents                       -> {agents: [row, ...]}
    GET  sessions/<sid>/agents/<aid>/tail?n=&kinds=  -> {agent_id, events: [entry, ...]}
    POST sessions/<sid>/agents/<aid>/command {cmd: steer|stop|pause|resume|follow,
                                              text?, mode?, reason?, on?}  -> {ok, result}
    GET  fleet/history?role=&bio=&n=                 -> {role, bio, runs: [run, ...]}   (R3, mounted
                                                        under fleet/ by studio/fleet_pair_api.py)

A history run is one past agent under that role or bio, newest first, read
from this harness's session transcripts: a sub-agent's
`<sid>/subagents/agent-<id>.meta.json` (bio = its `type`, role, lineup,
model, started, finished, status, is_error) with the task (its first user
line) and the cost (its usage lines) from its transcript; role `main` lists
the main sessions themselves. Live Roles shows it on a card nobody runs now.

Rows, entries and command semantics are the control socket's
(remote/agent_control.py). Studio sends `by` = `fleet.name` and `via` =
"Studio". 404: no such live session; 422: a bad command or parameter; 502:
the session refused (its own error) or could not be reached.
"""

from __future__ import annotations

COMMAND_TIMEOUT_S = 5.0
AGENT_COMMANDS = {"steer": "agent_steer", "stop": "agent_stop", "pause": "pause", "resume": "resume",
                  "follow": "agent_follow"}


def caller() -> dict:
    from halo_harness.remote.fleet_identity import fleet_name
    return {"by": fleet_name(), "via": "Studio"}


def forward(sid: str, cmd: str, fields: dict):
    """`(200, result)` or `(404 | 502, {error})`: one request on `sid`'s socket."""
    from halo_harness.remote import registry
    from halo_harness.remote.client import ControlClient, default_token_for
    entry = next((e for e in registry.list_live() if isinstance(e, dict) and e.get("session_id") == sid), None)
    if entry is None:
        return 404, {"error": f"no live session {sid!r}"}
    client = None
    try:
        client = ControlClient(str(entry.get("endpoint") or ""), default_token_for(entry), timeout=COMMAND_TIMEOUT_S)
        resp = client.call(cmd, **fields)
    except Exception as e:  # refused, closed, timed out
        return 502, {"error": f"session {sid}: {type(e).__name__}: {e}"}
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
    if not resp.get("ok"):
        return 502, {"error": str(resp.get("error") or "the session refused the command")}
    return 200, resp.get("result") if isinstance(resp.get("result"), dict) else {}


def get_agents(req):
    return forward(req.params["sid"], "agents", {})


def get_tail(req):
    raw = str(req.query.get("n") or "100")
    if not raw.isdigit() or not 1 <= int(raw) <= 500:
        return 422, {"error": f"n is a whole number from 1 to 500, got {raw!r}", "problems": []}
    fields = {"agent_id": req.params["aid"], "n": int(raw)}
    kinds = [k.strip() for k in str(req.query.get("kinds") or "").split(",") if k.strip()]
    if kinds:
        fields["kinds"] = kinds
    return forward(req.params["sid"], "agent_tail", fields)


def post_agent_command(req):
    body = req.body if isinstance(req.body, dict) else {}
    cmd = str(body.get("cmd") or "")
    if cmd not in AGENT_COMMANDS:
        return 422, {"error": f"cmd is one of {', '.join(AGENT_COMMANDS)}, got {cmd!r}", "problems": []}
    fields = {"agent_id": req.params["aid"], **caller()}
    if cmd == "steer":
        text, mode = str(body.get("text") or "").strip(), str(body.get("mode") or "nudge")
        if not text:
            return 422, {"error": "a steer needs text", "problems": []}
        if mode not in ("nudge", "redirect"):
            return 422, {"error": f"mode is nudge or redirect, got {mode!r}", "problems": []}
        fields.update(text=text, mode=mode)
    elif cmd == "stop":
        fields["reason"] = str(body.get("reason") or "")
    elif cmd == "follow":
        fields["on"] = body.get("on", True) is not False
    status, result = forward(req.params["sid"], AGENT_COMMANDS[cmd], fields)
    return (200, {"ok": True, "result": result}) if status == 200 else (status, result)


# -- the history of a role (3.0.5.0 R3: Live Roles' Live tab when nothing runs) ----------------------------
HISTORY_SCAN = 600  # the newest meta files read per request


def _first_user(path, cap: int = 160) -> str:
    import json
    from halo_harness.agent.agent_transcript import first_line
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for _i, line in zip(range(40), f):
                node = json.loads(line) if line.strip() else {}
                if node.get("type") == "user":
                    content = node.get("content")
                    text = content if isinstance(content, str) else " ".join(
                        b.get("text", "") for b in content or [] if isinstance(b, dict))
                    if text.strip():
                        return first_line(text, cap)
    except (OSError, ValueError):
        pass
    return ""


def _first_ts(path):
    """The first `ts` a transcript names (its meta line): when the session started, on every OS (3.3.18.0: st_ctime
    is the last metadata change on Linux)."""
    from halo_harness.live.session_cost import started
    return started(path)


def _cost(path):
    """3.4.0.1: the one reader of a session's spend (live/session_cost.py); None when nothing in it was priced and
    some model had no price (unknown, never $0)."""
    from halo_harness.live.session_cost import of_record
    got = of_record(path)
    if got is None or (not got["usd"] and got["unknown"]):
        return None
    return got["usd"]


def history(state_dir, *, role: str = "", bio: str = "", n: int = 20) -> list:
    """The last `n` runs under `role` (or `bio`) on this harness, newest first."""
    import json
    from pathlib import Path
    root = Path(state_dir) / "sessions"
    if not root.is_dir():
        return []
    runs: list = []
    if role == "main":
        logs = sorted(root.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:n]
        for p in logs:
            st = p.stat()
            runs.append({"agent_id": "main", "session_id": p.stem, "role": "main", "bio": None, "model": None,
                         "started": _first_ts(p) or st.st_ctime, "finished": st.st_mtime, "status": "session", "is_error": False,
                         "task": _first_user(p), "cost_usd": _cost(p)})
        return runs
    metas = sorted(root.glob("*/*/subagents/agent-*.meta.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in metas[:HISTORY_SCAN]:
        try:
            meta = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(meta, dict) or not ((role and meta.get("role") == role) or (bio and meta.get("type") == bio)):
            continue
        log = p.with_name(p.name[:-len(".meta.json")] + ".jsonl")
        runs.append({"agent_id": meta.get("agent_id"), "session_id": p.parent.parent.name, "role": meta.get("role"),
                     "bio": meta.get("type"), "lineup": meta.get("lineup"), "model": meta.get("model"),
                     "started": meta.get("started"), "finished": meta.get("finished"),
                     "status": meta.get("status") or "?", "is_error": bool(meta.get("is_error")),
                     "task": _first_user(log), "cost_usd": _cost(log)})
        if len(runs) >= n:
            break
    return runs


def get_history(req):
    role, bio = str(req.query.get("role") or "").strip(), str(req.query.get("bio") or "").strip()
    raw = str(req.query.get("n") or "20")
    if not raw.isdigit() or not 1 <= int(raw) <= 50:
        return 422, {"error": f"n is a whole number from 1 to 50, got {raw!r}", "problems": []}
    if not role and not bio:
        return 422, {"error": "name a role or a bio (?role=reviewer, ?bio=implementer)", "problems": []}
    runs = history(req.state_dir, role=role, bio=bio, n=int(raw))
    if role == "main":  # 3.4.0.1 (defect 22): a goal run's or a mission's own sessions name their owner (History folds them)
        from halo_harness.live.history_owner import owners
        own = owners(req.cwd, req.state_dir, [r.get("session_id") for r in runs])  # 3.4.1.0 R5: + each session's repo
        runs = [{**r, "part_of": own[r["session_id"]]} if r.get("session_id") in own else r for r in runs]
    return 200, {"role": role, "bio": bio, "runs": runs}


ROUTES = [("GET", r"^sessions/(?P<sid>[A-Za-z0-9_.:-]+)/agents$", get_agents),
          ("GET", r"^sessions/(?P<sid>[A-Za-z0-9_.:-]+)/agents/(?P<aid>[A-Za-z0-9_.:-]+)/tail$", get_tail),
          ("POST", r"^sessions/(?P<sid>[A-Za-z0-9_.:-]+)/agents/(?P<aid>[A-Za-z0-9_.:-]+)/command$", post_agent_command)]
