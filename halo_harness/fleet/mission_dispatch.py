"""halo_harness.fleet.mission_dispatch -- how the hub starts, watches and
stops a mission's parts (Halo 3.0.6.0 "Fleet Missions" round R7).

A part on the hub's own harness starts in this process
(mission_worker.start_local); a part on a member goes as the `run_task`
fleet command through one of its live sessions (a TUI session first: under
`fleet.allow_control: ask` its owner gets the card there). The answer maps
to the part's state: 200 running, 202 asked (the owner's card is open; the
outcome comes on the command's state), 403 refused (failed, with the
member's reason), anything else failed. A part is over when its
`parts/<n>/result.json` is in the mission folder (written here, or pushed by
the member over mission_files); a member that stays offline past
OFFLINE_FAIL_S fails its running parts. A part is stopped like any agent:
its session (found by the `mission` / `part` on its registry row) gets
`agent_stop` on its main agent.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from halo_harness.fleet import mission_store as S
from halo_harness.fleet import mission_worker

WAIT_S = 4.0
OFFLINE_FAIL_S = 180.0
SKIP_KINDS = ("mission-worker", "orchestra-worker", "flow")


class Dispatch:
    def __init__(self, home, hub=None) -> None:
        self.home, self.hub = home, hub
        self._offline: dict = {}

    # ---- the fleet --------------------------------------------------------------------------
    def local_id(self) -> str:
        if self.hub is not None:
            return str(self.hub.state.identity.get("id"))
        from halo_harness.fleet.identity import harness
        return harness(self.home)["id"]

    def view(self) -> dict:
        if self.hub is not None:
            return self.hub.state.view()
        from halo_harness.fleet.local_view import harness_entry, sessions
        return {"harnesses": [harness_entry(sessions(), self.home)]}

    def entries(self, view: Optional[dict] = None) -> list:
        """Every harness that can take a part now: this one and the online members, with a catalog."""
        view = view or self.view()
        if self.hub is not None:
            rows = self.hub.state.caps.entries(view)
        else:
            from halo_harness.fleet.hub_capabilities import entry, local_catalog
            rows = [entry(h, local_catalog(self.home)) for h in view.get("harnesses") or [] if h.get("local")]
        return [r for r in rows if r.get("catalog") and (r.get("local") or r.get("online"))]

    @staticmethod
    def load(view: dict) -> dict:
        return {str(h.get("id")): sum(int(s.get("agents_live") or 0) for s in h.get("sessions") or [])
                for h in view.get("harnesses") or []}

    def _member(self, hid: str):
        return self.hub.state.members.get(hid) if self.hub is not None else None

    def session_for(self, hid: str) -> Optional[str]:
        m = self._member(hid)
        rows = [s for s in (m.sessions() if m is not None else []) if s.get("kind") not in SKIP_KINDS]
        rows.sort(key=lambda s: (s.get("kind") != "tui", -(s.get("started") or 0)))
        return rows[0].get("session_id") if rows else None

    # ---- one part ---------------------------------------------------------------------------
    @staticmethod
    def fields(doc: dict, part: dict, plan: Optional[dict] = None) -> dict:
        parts = list((plan or {}).get("parts") or [])
        total = sum(float(p.get("est_cost_usd") or 0) for p in parts)
        est = float(part.get("est_cost_usd") or 0)
        budget = (float(doc["budget_usd"]) * est / total) if doc.get("budget_usd") and total > 0 else (est or None)
        repo = doc.get("repo") or {}
        return {"mission": doc["id"], "part": part["id"], "title": part.get("title"), "brief": part.get("brief"),
                "kind": part.get("kind") or "files", "claims": list(part.get("claims") or []),
                "outputs": list(part.get("outputs") or []), "depends_on": list(part.get("depends_on") or []),
                "repo": repo.get("name") if part.get("kind") == "repo" else None, "base": repo.get("base"),
                "branch": f"mission/{doc['id']}/{part['id']}", "budget_usd": round(budget, 4) if budget else None,
                "mirror": {"mode": "shared" if doc.get("shared") else "hub"}}

    def start(self, doc: dict, part: dict, plan: Optional[dict] = None) -> dict:
        """The part state fields after starting it."""
        hid, now = str(part.get("harness") or ""), time.time()
        f = self.fields(doc, part, plan)
        if hid == self.local_id():
            root = S.local(self.home, doc["id"]).get("repo_root")
            try:
                mission_worker.start_local(self.home, f, repo_root=root)
            except ValueError as e:
                return {"state": "failed", "error": str(e), "ended": now}
            return {"state": "running", "started": now}
        if self.hub is None:
            return {"state": "failed", "error": "no fleet hub runs here to reach that harness", "ended": now}
        sid = self.session_for(hid)
        if sid is None:
            name = getattr(self._member(hid), "name", hid)
            return {"state": "failed", "error": f"{name} has no live session to run the part in", "ended": now}
        status, out = self.hub.state.commands.send(hid, sid, "run_task", f, by=self.hub.state.name, wait_s=WAIT_S)
        cid = (out or {}).get("command_id")
        if status == 200:
            return {"state": "running", "started": now, "command_id": cid, "via_session": sid}
        if status in (202, 504):
            return {"state": "asked", "command_id": cid, "via_session": sid}
        return {"state": "failed", "command_id": cid, "error": str((out or {}).get("error") or status), "ended": now}

    def result(self, mid: str, pid: str) -> Optional[dict]:
        raw = S.read_text(S.folder(self.home, mid), f"parts/{pid}/result.json")
        try:
            data = json.loads(raw) if raw else None
        except ValueError:
            return None
        return data if isinstance(data, dict) and data.get("state") else None

    def poll(self, doc: dict, pid: str, ps: dict) -> Optional[dict]:
        """New part state fields, or None when nothing changed."""
        now, hid = time.time(), str(ps.get("harness") or "")
        res = self.result(doc["id"], pid)
        if res is not None:
            return {"state": res["state"] if res["state"] in ("done", "failed", "stopped") else "failed",
                    "cost_usd": float(res.get("cost_usd") or 0.0), "error": res.get("error"), "ended": res.get("ended") or now,
                    "session_id": res.get("session_id") or ps.get("session_id"), "files": list(res.get("files") or [])[:500],
                    "branch": res.get("branch"), "head": res.get("head"), "bundle": bool(res.get("bundle")),
                    "refused_list": [r for r in res.get("refused") or [] if isinstance(r, dict)][:50]}
        if ps.get("state") == "asked" and self.hub is not None and ps.get("command_id"):
            c = self.hub.state.commands.get(ps["command_id"]) or {}
            if c.get("state") == "done":
                return {"state": "running", "started": now}
            if c.get("state") in ("refused", "error"):
                return {"state": "failed", "error": c.get("error") or c["state"], "ended": now}
            return None
        if hid == self.local_id():
            if (doc["id"], pid) not in mission_worker.running(doc["id"]) and ps.get("state") == "running":
                time.sleep(0.2)
                return None if self.result(doc["id"], pid) else {"state": "failed", "ended": now,
                                                                  "error": "the worker ended without a result"}
            return None
        m = self._member(hid)
        if m is not None and not m.online:
            first = self._offline.setdefault((doc["id"], pid), now)
            if now - first > OFFLINE_FAIL_S:
                return {"state": "failed", "error": f"{m.name} went offline", "ended": now}
        else:
            self._offline.pop((doc["id"], pid), None)
        return None

    def part_session(self, doc: dict, pid: str, ps: dict) -> Optional[str]:
        for h in self.view().get("harnesses") or []:
            if str(h.get("id")) == str(ps.get("harness")):
                for s in h.get("sessions") or []:
                    if s.get("mission") == doc["id"] and str(s.get("part")) == str(pid):
                        return s.get("session_id")
        return ps.get("session_id")

    def stop(self, doc: dict, pid: str, ps: dict, reason: str) -> bool:
        if str(ps.get("harness")) == self.local_id():
            return mission_worker.stop(doc["id"], pid, reason)
        sid = self.part_session(doc, pid, ps)
        if self.hub is None or not sid:
            return False
        status, _ = self.hub.state.commands.send(str(ps.get("harness")), sid, "agent_stop",
                                                 {"agent_id": "main", "reason": reason}, by=self.hub.state.name, wait_s=WAIT_S)
        return status == 200
