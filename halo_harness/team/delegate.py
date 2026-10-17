"""halo_harness.team.delegate -- a stage member on another harness of the fleet.

`FleetDelegate` is the default DISPATCH of team/run.py. It reuses the fleet
mission path (fleet/mission_dispatch.py): the hub this machine runs (`halo
studio --fleet` or `halo fleet serve`) sends the `run_task` command to one
of the member harness's live sessions (a TUI session first, so under
`fleet.allow_control: ask` its owner gets the card). To give that command
the mission folder it pushes its hand-back into, each delegated member is a
one-part mission in the hub's store (state `drafted`, goal "team <team>
stage <stage>: <member>", part 1 on that harness), so it also shows in
`halo fleet mission status`.

    send(member, task) -> (status, body)   200 running | 202 asked | 403 refused |
                                           404 no such member | 409 offline | 503 no hub
    poll(handle) -> None | {ok, state, text, cost_usd, error}   (parts/1/result.json + handback.md)
    stop(handle, reason) -> bool           agent_stop on the part's session
"""

from __future__ import annotations

from typing import Optional

from halo_harness.fleet import mission as M
from halo_harness.fleet import mission_store as S
from halo_harness.fleet.mission_dispatch import SKIP_KINDS, WAIT_S, Dispatch


class FleetDelegate:
    def __init__(self, home=None):
        from halo_harness.fleet import identity
        self.home = home if home is not None else identity.home()

    def _call(self, route: str, body: dict):
        from halo_harness.fleet.hub import running_call
        return running_call(self.home, "POST", route, body, timeout=WAIT_S + 6)

    def _view(self) -> Optional[dict]:
        from halo_harness.fleet.hub import running_view
        return running_view(self.home)

    @staticmethod
    def _session(h: dict) -> Optional[str]:
        rows = [s for s in h.get("sessions") or [] if s.get("kind") not in SKIP_KINDS]
        rows.sort(key=lambda s: (s.get("kind") != "tui", -(s.get("started") or 0)))
        return rows[0].get("session_id") if rows else None

    def send(self, member: dict, task: dict) -> "tuple[int, dict]":
        name = str(member.get("harness") or "")
        view = self._view()
        if view is None:
            return 503, {"error": "no fleet hub runs on this machine: start `halo studio --fleet` or "
                                  "`halo fleet serve`, then check `halo fleet who`"}
        h = next((x for x in view.get("harnesses") or [] if name in (x.get("name"), x.get("id"))), None)
        if h is None:
            return 404, {"error": f"{name} is not in this fleet (`halo fleet members` lists them)"}
        if not h.get("online") and not h.get("local"):
            return 409, {"error": f"{name} is offline"}
        sid = self._session(h)
        if sid is None:
            return 409, {"error": f"{name} has no live session to run the stage in"}
        from halo_harness.fleet.identity import fleet_name
        mid = M.new_id()
        part = {"id": "1", "harness": h.get("id"), "harness_name": h.get("name"), "kind": "files",
                "title": task.get("title"), "brief": task.get("brief"), "claims": [], "outputs": [],
                "depends_on": []}
        doc = M.new_doc(mid=mid, goal=f"team {task.get('team')} stage {task.get('stage')}: {member.get('name')}",
                        by=fleet_name(self.home))
        doc["parts"] = {"1": M.new_part_state(part)}
        S.create(self.home, doc)
        from halo_harness.orchestra import jsonl
        jsonl.write_json(S.folder(self.home, mid) / "plan.json", {"parts": [part]})
        fields = Dispatch.fields(doc, part, {"parts": [part]})
        got = self._call("local/command", {"harness": h.get("id"), "session_id": sid, "cmd": "run_task",
                                           "fields": fields, "wait_s": WAIT_S})
        status, out = got if got else (503, {"error": "the hub did not answer"})
        handle = {"mission": mid, "part": "1", "harness_id": h.get("id"), "session_id": sid,
                  "command_id": (out or {}).get("command_id")}
        if status == 200:
            return 200, {"handle": handle}
        if status in (202, 504):
            return 202, {"handle": handle}
        return status if status == 403 else (status or 502), {"error": str((out or {}).get("error") or status)}

    def poll(self, handle: dict) -> Optional[dict]:
        base = S.folder(self.home, handle["mission"])
        raw = S.read_text(base, f"parts/{handle['part']}/result.json")
        if not raw:
            return None
        import json
        try:
            res = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(res, dict) or not res.get("state"):
            return None
        text = S.read_text(base, f"parts/{handle['part']}/handback.md") or ""
        ok = res.get("state") == "done"
        return {"ok": ok, "state": "done" if ok else "failed", "text": text, "cost_usd": float(res.get("cost_usd") or 0.0),
                "error": "" if ok else str(res.get("error") or res.get("state")), "session_id": res.get("session_id")}

    def stop(self, handle: dict, reason: str) -> bool:
        got = self._call("local/command", {"harness": handle.get("harness_id"), "session_id": handle.get("session_id"),
                                           "cmd": "agent_stop", "fields": {"agent_id": "main", "reason": reason},
                                           "wait_s": WAIT_S})
        return bool(got and got[0] == 200)
