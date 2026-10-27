"""tests.helpers.studio_team_rig -- what the Studio Team tab's Chrome checks
and tools/capture_team.py look at (Halo 3.0.8.0 round R2). One scratch home
(the shipped lineups, so every member's lineup resolves) with an in-process
Studio whose folder is a git repo holding tests/helpers/team_rig.py's team
(`TEAM_UI`: the rig's team, with the `notes` block claimed per file and a
fourth stage, `post`, an agent stage with a required gate after `review`,
so the run stays open for Stop; 3.1.4.0: it was a flow stage), and the team
runner's seams set to `HeldFakes` (team_rig.Fakes; no model is ever called):
a member's spawn can wait on an Event after its writes went through the real
TeamClaimGuard, so a stage stays `running` and its claims stay `writing`
while a test looks. `touch(block, rel, text)` writes a file of a block by
hand (a holder `you`, a change line, the run's `change` event) and
`release(block)` lets go. Every touched variable is restored and the home
removed on close.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from pathlib import Path

from tests.helpers import team_rig as R

TEAM_UI = (R.TEAM.replace("{id: notes, kind: file, path: NOTES.md, claims: none}", "{id: notes, kind: file, path: NOTES.md, claims: file}")
           + '    - {id: post, kind: agent, members: [writer], reads: [copy], trigger: "stage_done:review", gate: required}\n')
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET")


class HeldFakes(R.Fakes):
    """`hold[(member, stage)]` = an Event the spawn waits on (30 s at most) after its writes."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.hold: dict = {}
        self.reached: dict = {}

    def spawn(self, member, prompt, *, cwd, env, stage, run_dir):
        key = (member["name"], stage)
        out = super().spawn(member, prompt, cwd=cwd, env=env, stage=stage, run_dir=run_dir)
        if key in self.hold:
            self.reached.setdefault(key, threading.Event()).set()
            self.hold[key].wait(30)
        return out


class StudioTeamRig:
    def __init__(self, text: str = TEAM_UI, live: bool = True) -> None:
        self._saved = {k: os.environ.get(k) for k in _VARS}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        self.home = Path(tempfile.mkdtemp(prefix="studio-team-"))
        os.environ["BRIDGE_TEST_HOME"] = str(self.home)
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        from halo_harness.providers.config import default_state_dir
        from halo_harness.teams_yaml import ensure_builtin_team_templates
        self.state = Path(default_state_dir())
        self.state.mkdir(parents=True, exist_ok=True)
        ensure_builtin_team_templates(state_dir=self.state)
        self.root, _ = R.repo(text, at=self.home / "proj")
        self.fakes = HeldFakes()
        self.fakes.writes["writer"] = [("Write", self.root / "content" / "intro.md", {"content": "# Intro\n\nhello, launch\n\n## Overview\n\nmore\n"})]
        from halo_harness.studio import team_api
        self._runner = team_api.RUNNER
        if live:
            team_api.RUNNER = self.fakes.seams
        from halo_harness.studio.server import start_server
        self.server = start_server(port=0, cwd=self.root, state_dir=self.state)
        threading.Thread(target=self.server.serve_forever, daemon=True, name="rig-team-studio").start()

    def url(self, mode: str = "team", extra: str = "") -> str:
        """3.3.2.0 R3: every panel open (open=all, tests/helpers/studio_full.py) unless `extra` names its own."""
        from halo_harness.studio.server import url_for
        from tests.helpers.studio_full import full
        return full(url_for(self.server, mode).replace("#t=", f"&tour=off{extra}#t="))

    def api(self, method: str, path: str, body=None):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=30)
        try:
            conn.request(method, "/api/" + path, body=json.dumps(body).encode("utf-8") if body is not None else None,
                         headers={"Authorization": "Bearer " + self.server.token, "Content-Type": "application/json"})
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
        finally:
            conn.close()

    def team(self) -> dict:
        from halo_harness.team import spec as S
        return S.load_team(self.root, self.state)

    def run_dir(self) -> Path:
        from halo_harness.team import board as BD
        return BD.latest_run(self.root)

    def touch(self, block_id: str, rel: str, text: str) -> str:
        """Write `rel` (inside block `block_id`) by hand, through the real guard: holder `you`."""
        from halo_harness.permissions import Decision
        from halo_harness.team.guard import TeamClaimGuard
        team = self.team()
        scope = {"root": str(self.root), "run_dir": str(self.run_dir() or ""), "stage": "", "member": "you", "holder": "you",
                 "writes": [block_id], "blocks": team["blocks"]}
        path = self.root / rel
        d = TeamClaimGuard(scope).check("Write", {"file_path": str(path), "content": text}, Decision("allow", "base"))
        if d is not None and d.action == "allow":
            path.write_text(text, encoding="utf-8")
        return d.action if d is not None else "none"

    def release(self, block_id: str, holder: str = "you") -> list:
        from halo_harness.team import blocks as B
        team = self.team()
        block = next(b for b in team["blocks"] if b["id"] == block_id)
        return B.release_holder(self.root, block, holder, note="the hand edit is over")

    def close(self) -> None:
        for ev in self.fakes.hold.values():
            ev.set()
        from halo_harness.studio import team_api, team_live
        try:
            self.api("POST", "team/stop", {"reason": "the rig closes"})
        except Exception:
            pass
        team_live.wait(self.root, 10.0)
        team_api.RUNNER = self._runner
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.home, ignore_errors=True)

    def __enter__(self) -> "StudioTeamRig":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
