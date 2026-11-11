"""halo_harness.fleet.delegate -- one part handed to another harness of the fleet (Halo 3.0.8.0; moved here from the
team package in 3.4.0.0 B, when the team file left the core: the two-machine check's mission step uses it).

`FleetDelegate` reuses the fleet mission path (fleet/mission_dispatch.py): the hub this machine runs (`halo studio
--fleet` or `halo fleet serve`) sends the `run_task` command to one of the member harness's live sessions (a TUI
session first, so under `fleet.allow_control: ask` its owner gets the card). Each delegated part is a one-part
mission in the hub's store (state `drafted`, part 1 on that harness), so it also shows in `halo fleet mission status`.

    send(member, task) -> (status, body)   200 running | 202 asked | 403 refused |
                                           404 no such member | 409 offline | 503 no hub
    poll(handle) -> None | {ok, state, text, cost_usd, error, run_id?, report?}
                                           (parts/1/result.json, handback.md, report.json)
    stop(handle, reason) -> bool           agent_stop on the part's session
"""

from __future__ import annotations

from typing import Optional

from halo_harness.ext import core as _core
from . import mission as M, mission_store as S
from .mission_dispatch import SKIP_KINDS, WAIT_S, Dispatch


class FleetDelegate:
    def __init__(self, home=None):
        identity = _core.module("peers.identity")
        self.home = home if home is not None else identity.home()

    def _call(self, route: str, body: dict):
        from .hub import running_call
        return running_call(self.home, "POST", route, body, timeout=WAIT_S + 6)

    def _view(self) -> Optional[dict]:
        from .hub import running_view
        return running_view(self.home)

    @staticmethod
    def _session(h: dict) -> Optional[str]:
        rows = [s for s in h.get("sessions") or [] if s.get("kind") not in SKIP_KINDS]
        rows.sort(key=lambda s: (s.get("kind") != "tui", -(s.get("started") or 0)))
        return rows[0].get("session_id") if rows else None

    def send(self, member: dict, task: dict) -> "tuple[int, dict]":
        part = {"kind": "files", "title": task.get("title"), "brief": task.get("brief"), "claims": [], "outputs": []}
        return self._dispatch(str(member.get("harness") or ""), part, task, member.get("name"), None)

    def _dispatch(self, name: str, part: dict, task: dict, who, repo) -> "tuple[int, dict]":
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
            return 409, {"error": f"{name} has no live session to run the part in"}
        fleet_name = _core.get("peers.identity", "fleet_name")
        mid = M.new_id()
        part = dict(part, id="1", harness=h.get("id"), harness_name=h.get("name"), depends_on=[])
        doc = M.new_doc(mid=mid, goal=f"{task.get('title') or 'a delegated part'}: {who}",
                        by=fleet_name(self.home))
        doc["parts"] = {"1": M.new_part_state(part)}
        if repo:
            doc["repo"] = repo
        S.create(self.home, doc)
        jsonl = _core.module("orchestra.jsonl")
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
        out = {"ok": ok, "state": "done" if ok else "failed", "text": text, "cost_usd": float(res.get("cost_usd") or 0.0),
               "error": "" if ok else str(res.get("error") or res.get("state")), "session_id": res.get("session_id")}
        if res.get("run_id"):  # 3.1.2.0 R2: an orchestra stage's run, and its report
            report = S.read_text(base, f"parts/{handle['part']}/report.json")
            try:
                out.update(run_id=res["run_id"], report=json.loads(report) if report else None)
            except ValueError:
                out.update(run_id=res["run_id"], report=None)
        return out

    def stop(self, handle: dict, reason: str) -> bool:
        got = self._call("local/command", {"harness": handle.get("harness_id"), "session_id": handle.get("session_id"),
                                           "cmd": "agent_stop", "fields": {"agent_id": "main", "reason": reason},
                                           "wait_s": WAIT_S})
        return bool(got and got[0] == 200)
