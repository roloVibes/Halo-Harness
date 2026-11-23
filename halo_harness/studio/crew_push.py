"""halo_harness.studio.crew_push -- an agent saved in Studio's Agents form reaches the sessions running now (Halo
3.6.0.15 UN, the design's rule U3): after a 200 of POST, PUT or DELETE crew/agent/<name> (studio/crew_api.py), each live
top session whose folder sees the scope is sent `agent_put` / `agent_gone` on its control socket (remote/agent_control.py;
the session puts it into its agents at main's next step, crew/use_now.py).

    targets(req, scope) -> [row]                  the live top sessions a save of that scope reaches: yours, every one;
                                                  a project's, those whose project is Studio's; never a row marked
                                                  `unreachable_since` (remote/registry.py)
    put_live(req, name, body, scope, text) -> [{session_id, took, why}]   why "unreached": the session did not answer
    gone_live(req, name, scope) -> [{session_id, queued}]

No thread, no timer, no watcher: it runs inside the request that saved. Whether a session is on Auto is the SESSION's
answer (why "map" or "off"), never guessed here.
"""

from __future__ import annotations

import hashlib


def _repo(path) -> str:
    from halo_harness.crew.session_tool import _same_path
    from halo_harness.crew.store import repo_of
    return _same_path(repo_of(path))


def targets(req, scope: str) -> list:
    from halo_harness.remote import registry
    here = _repo(req.cwd) if scope == "project" else None
    out: list = []
    for row in registry.list_live():
        if not isinstance(row, dict) or not row.get("session_id") or row.get("parent") \
                or row.get(registry.UNREACHABLE):
            continue
        if here is not None:
            root = (row.get("project") or {}).get("root") or row.get("cwd")
            if not root or _repo(root) != here:
                continue
        out.append(row)
    return out


def put_live(req, name: str, body: dict, scope: str, text: str) -> list:
    from halo_harness.studio.live_agents_api import caller, forward
    try:
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()  # of the very text written
        out: list = []
        for row in targets(req, scope):
            sid = row["session_id"]
            try:  # one session's bad answer is that session's alone: the others' answers stay
                status, got = forward(sid, "agent_put", {"name": name, "body": body, "scope": scope, "sha256": sha,
                                                          **caller()})
                item = ({"took": bool(got.get("took")), "why": str(got.get("why") or "")} if status == 200
                        else {"took": False, "why": "unreached"})
            except Exception:
                item = {"took": False, "why": "unreached"}
            out.append({"session_id": sid, **item})
        return out
    except Exception:  # a push never fails the save
        return []


def gone_live(req, name: str, scope: str) -> list:
    from halo_harness.studio.live_agents_api import caller, forward
    try:
        out: list = []
        for row in targets(req, scope):
            sid = row["session_id"]
            try:
                status, got = forward(sid, "agent_gone", {"name": name, "scope": scope, **caller()})
                queued = status == 200 and bool(got.get("queued"))
            except Exception:
                queued = False
            out.append({"session_id": sid, "queued": queued})
        return out
    except Exception:
        return []
