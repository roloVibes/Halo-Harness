"""tests.helpers.studio_fleet_mseed -- a fleet mission over the Studio Fleet
rig (tests/helpers/studio_fleet_rig.py) for the Halo 3.0.6.0 R8 Chrome
scenario (tests/helpers/studio_fleet_mission.py) and tools/capture_fleet.py.
No model is ever called: the lead is tests/helpers/mission_seed's FakeLead
with ANSWER, the judge its FakeJudge, the hub's own part runs mission_seed's
fake worker (held by a gate until `release_local`).

The plan (the rig's catalogs: this harness `rolo@studio` has ComfyUI, the
member `kali@lab` has gridcraft):

    1  Chart the basket prices        repo   needs gridcraft -> pinned to kali@lab
    2  Render the pricing cover       files  needs comfyui   -> pinned to rolo@studio
    3  Link the chart from the notes  repo   the lead puts it on kali@lab; waits for 2 (depends_on)
                                             and after 1 (both claim docs/pricing/**: sequenced)

`hold_tasks` makes the member answer `run_task` with `asked` (its owner has
the card), `allow_member` then answers `done` and announces the part's
`mission-worker` session (its main agent on a gridcraft call); `ask_here`
plays the other side on this harness: another hub's run_task under
`fleet.allow_control: ask`, so a `mission_ask` row opens in Attention.
"""
from __future__ import annotations

import json
import threading
import time

GOAL = "Chart the basket prices, render a cover for the pricing page and link the chart from the notes"
WORKER_SID = "5e55000000000000000000000000beef"


def answer() -> str:
    parts = [{"id": "chart", "title": "Chart the basket prices", "brief": "Write docs/pricing/prices.xlsx with a chart of every basket price.",
              "kind": "repo", "needs": ["gridcraft"], "claims": ["docs/pricing/**"], "outputs": [], "est_cost_usd": 0.3},
             {"id": "cover", "title": "Render the pricing cover", "brief": "Render a 1600x900 cover for the pricing page; save cover.png.",
              "kind": "files", "needs": ["comfyui"], "outputs": ["cover.png"], "est_cost_usd": 0.2},
             {"id": "link", "title": "Link the chart from the notes", "brief": "Add the chart and the cover to docs/pricing/index.md.",
              "kind": "repo", "harness": "kali@lab", "reason": "next to the chart it links", "needs": [],
              "claims": ["docs/pricing/index.md"], "depends_on": ["cover"], "est_cost_usd": 0.1}]
    return json.dumps({"parts": parts, "merge_order": ["chart", "link"]})


class MissionFakes:
    """The fakes and the member's held run_task; undone on close (added to the rig's closers)."""

    def __init__(self, rig) -> None:
        from halo_harness.fleet import mission_api as A
        from halo_harness.fleet import mission_worker as W
        from tests.helpers.mission_seed import FakeJudge, FakeLead, worker
        from tests.helpers.studio_fleet_rig import wait_for
        self.rig, self.held, self.started = rig, [], []
        self.gate = threading.Event()
        A.LEAD, A.JUDGE = FakeLead(answer()), FakeJudge()
        W.BUILD = worker({"2": {"cost": 0.042, "text": "cover.png rendered"}}, self.started, {"2": self.gate})
        self._reply = rig.hub.state.commands.reply
        rig.closers.append(self.close)
        if not wait_for(lambda: rig.hub.state.caps.catalogs.get(rig.member_id), 30):
            raise RuntimeError("the hub never got the member's catalog")

    def hold_tasks(self) -> None:
        """The member's owner gets a card for each run_task: it is answered `asked` until allow_member."""
        def reply(hid, body):
            doc = next((d for d in self.rig.member_cmds if d.get("cid") == body.get("cid")), {})
            if doc.get("cmd") == "run_task" and body.get("state") == "done":
                self.held.append(doc)
                body = {"cid": body["cid"], "state": "asked"}
            return self._reply(hid, body)
        self.rig.hub.state.commands.reply = reply

    def allow_member(self, mid: str) -> bool:
        """Its owner allows: the command is done and the part's mission-worker session announces."""
        from tests.helpers.studio_fleet_rig import wait_for
        if not wait_for(lambda: self.held, 20):
            return False
        doc = self.held.pop(0)
        fields = doc.get("fields") or {}
        self._reply(self.rig.member_id, {"cid": doc["cid"], "state": "done", "result": {"started": True, "mission": mid,
                                                                                     "part": fields.get("part")}})
        self.announce_worker(mid, str(fields.get("part")))
        return True

    def announce_worker(self, mid: str, part: str) -> None:
        from halo_harness import __version__
        from halo_harness.fleet.capabilities import summary
        from tests.helpers.studio_fleet_member import announce_body, catalog, session_row
        rec = {"id": self.rig.member_id, "name": "kali@lab", "host": "kali", "user": "kali", "os": "linux", "version": __version__}
        row = {**session_row(rec), "session_id": WORKER_SID, "title": f"mission {mid} part {part}", "kind": "mission-worker",
               "mission": mid, "part": part, "status": "busy", "pending": {}, "started": time.time(), "cost_usd": 0.0071,
               "project": {"root": "shop", "repo": "shop", "branch": f"mission/{mid}/{part}", "dirty": True},
               "agents": [{"agent_id": "main", "parent": None, "name": "main", "role": "main", "bio": "general",
                           "lineup": "halo-dev-cycle", "model": "ol:qwen3-coder:30b", "kind": "main",
                           "task": "Chart the basket prices", "since": time.time(), "state": "running", "turns": 2,
                           "cost_usd": 0.0071, "current": "gridcraft: write_range B2:D9", "last_text": ""}]}
        body = announce_body(rec)
        cat = catalog()
        self.rig.hub.state.announce(self.rig.member_id, {**body, "sessions": [*body["sessions"], row],
                                                         "capabilities_summary": summary(cat), "capabilities_hash": cat["hash"]})

    def release_local(self) -> None:
        self.gate.set()

    def ask_here(self, mid: str = "m-20261015-0b5e", part: str = "2") -> dict:
        """Another hub asks this harness to run a part (fleet.allow_control: ask): a mission_ask card opens here."""
        from halo_harness.fleet import control
        out: dict = {}
        fields = {"mission": mid, "part": part, "title": "Index the shop's prices", "brief": "List every price in shop/",
                  "kind": "files", "claims": [f"artifacts/{part}/**"], "outputs": ["prices.csv"], "depends_on": [],
                  "branch": f"mission/{mid}/{part}", "mirror": {"mode": "hub"}}
        doc = {"cmd": "run_task", "cid": "c0ffee01", "fields": fields, "by": "lab-hub", "hub": "lab-hub"}
        pol = {"share": "full", "allow_control": "ask", "hub_entry": None}

        def run() -> None:
            out.update(control.run(self.rig.act.handle, doc, pol))
        threading.Thread(target=run, daemon=True, name="rig-ask-here").start()
        return out

    def close(self) -> None:
        from halo_harness.fleet import mission_worker as W
        from tests.helpers.mission_seed import reset_fakes
        self.gate.set()
        self.rig.hub.state.commands.reply = self._reply
        for run in list(W.RUNNING.values()):
            try:
                run.stop("the rig closes")
            except Exception:
                pass
        reset_fakes()


def plan_by_api(rig) -> dict:
    """Plan the mission without the UI (the capture): the route's view."""
    status, view = rig.api("POST", "fleet/missions", {"goal": GOAL, "constraints": "keep the shop's prices as they are",
                                                      "budget_usd": 1.5})
    if status != 200:
        raise RuntimeError(f"the plan failed: {status} {view}")
    return view
