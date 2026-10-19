"""halo_harness.fleet.live_check_fakes -- the `--fake` seams for the
two-machine check (Halo 3.1.2.0 R3; fleet/live_check.py drives it).

With `--fake` the check needs no model on either box: a mission part writes
its file and hands back without a turn, a delegated orchestra stage (a
team's, on a member with the repo checked out) returns a canned report, and a recall query the member answers returns one
canned hit (only for the member's own home, so the hub's own index stays
empty for that query -- the check proves the hit came from the member).
`install()` sets the three seams and returns a `restore()` that puts back
whatever was there. On a real box only the member runs `--fake`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

NMAP_LINE = "Nmap version 7.95 ( https://nmap.org )"


def _fake_build() -> Callable:
    """A mission_worker.BUILD that writes the part's one file and hands back, no model."""
    from tests.helpers.fake_remote_session import FakeSession  # test-only import; --fake is a check/test path

    def build(cwd, home=None):
        session = FakeSession(f"lc{time.time_ns():x}"[:32].ljust(32, "0"))

        def run(prompt: str, handle=None) -> dict:
            part = "1"
            for token in prompt.split():
                if token.isdigit():
                    part = token
                    break
            target = Path(cwd) / "artifacts" / part / "scan.txt"
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(NMAP_LINE + "\n", encoding="utf-8")
            except OSError:
                pass
            return {"ok": True, "text": f"Wrote scan.txt: {NMAP_LINE}", "cost_usd": 0.0,
                    "error": "", "session_id": session.log.session_id}
        return session, run, lambda: None
    return build


def _fake_orchestra() -> Callable:
    rid = time.strftime("%Y%m%d-%H%M%S-or")

    def orchestra(goal, root):
        return {"ok": True, "text": f"Orchestra run {rid} finished", "cost_usd": 0.0, "run_id": rid,
                "report": {"status": "finished", "kind": "orchestra", "what": (goal or {}).get("what")}}
    return orchestra


def _fake_search(member_home: Optional[Path]) -> Callable:
    want = Path(member_home).resolve() if member_home is not None else None

    def search(query, k, home):
        if want is not None and Path(home).resolve() != want:
            return []  # the hub's own index does not answer a member-only query
        return [{"id": "/member/recall-note.md", "score": 0.97, "title": "live-check recall note",
                 "kind": "memory", "excerpt": "the live-check planted this on the member's index only"}]
    return search


def install(member_home: Optional[Path] = None) -> Callable:
    """Set the three fake seams; returns restore()."""
    from halo_harness import recall_fleet as RF
    from halo_harness.fleet import mission_stage_run as MSR
    from halo_harness.fleet import mission_worker as MW
    saved = (MW.BUILD, MSR.ORCHESTRA, RF.SEARCH)
    MW.BUILD = _fake_build()
    MSR.ORCHESTRA = _fake_orchestra()
    RF.SEARCH = _fake_search(member_home)

    def restore() -> None:
        MW.BUILD, MSR.ORCHESTRA, RF.SEARCH = saved
    return restore
