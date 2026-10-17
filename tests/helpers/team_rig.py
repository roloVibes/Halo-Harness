"""tests.helpers.team_rig -- a temp git repo holding a team file, and the
fakes for team/run.py's seams (no model is ever called).

`repo(text=TEAM)` -> (root, state_dir): a fresh git repo with `docs/BRIEF.md`,
`content/` and `.halo/team.yaml`, plus a state dir of its own. `Fakes()`
records every seam call; its spawn writes through the real TeamClaimGuard
when `writes` maps a member to (tool, path, input) calls.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

TEAM = """\
name: launch
brief: docs/BRIEF.md
members:
  - {name: writer, lineup: standard, role: main}
  - {name: editor, lineup: standard, role: reviewer}
  - {name: remote, lineup: standard, role: coder, harness: kali}
blocks:
  - {id: copy, kind: folder, path: content/, claims: section}
  - {id: site, kind: folder, path: site/, claims: file}
  - {id: notes, kind: file, path: NOTES.md, claims: none}
workflow:
  stages:
    - {id: draft, kind: agent, members: [writer], reads: [brief], writes: [copy], trigger: manual,
       gate: required, acceptance: {expect: "draft"}}
    - {id: review, kind: agent, members: [editor, writer], lead: writer, reads: [copy], writes: [copy],
       trigger: "stage_done:draft"}
    - {id: build, kind: orchestra, goal: {what: "Build the site", done_when: "it renders", workers: 2},
       writes: [site], trigger: "block_change:notes", settle_s: 5}
    - {id: post, kind: flow, flow: social-post, reads: [copy], trigger: "stage_done:review"}
"""


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(root), check=True, capture_output=True, text=True, encoding="utf-8",
                   stdin=subprocess.DEVNULL)


def repo(text: str = TEAM, *, brief: bool = True, at=None) -> "tuple[Path, Path]":
    """`at`: build the repo in that (new) folder, e.g. a Studio's own cwd."""
    if at is not None:
        Path(at).mkdir(parents=True, exist_ok=True)
    root = Path(at).resolve() if at is not None else Path(tempfile.mkdtemp(prefix="team-repo-")).resolve()
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    (root / "content").mkdir()
    (root / "content" / "intro.md").write_text("# Intro\n\nhello\n\n## Overview\n\nmore\n", encoding="utf-8")
    if brief:
        (root / "docs").mkdir()
        (root / "docs" / "BRIEF.md").write_text("Launch the thing.\n", encoding="utf-8")
    (root / ".halo").mkdir()
    (root / ".halo" / "team.yaml").write_text(text, encoding="utf-8")
    state = Path(tempfile.mkdtemp(prefix="team-state-")).resolve()
    return root, state


class Fakes:
    """Every seam of team/run.py, recording its calls."""

    def __init__(self, texts=None, fail=(), dispatch_status=200):
        self.calls: list = []
        self.texts = dict(texts or {})
        self.fail = set(fail)
        self.dispatch_status = dispatch_status
        self.polls: list = []      # queued poll answers for the delegate
        self.writes: dict = {}     # member -> [(tool, path, input)] run through the guard

    def spawn(self, member, prompt, *, cwd, env, stage, run_dir):
        self.calls.append(("spawn", member["name"], stage, prompt))
        decisions = []
        from halo_harness.team import SCOPE_ENV
        from halo_harness.team.guard import TeamClaimGuard
        from halo_harness.permissions import Decision
        guard = TeamClaimGuard.from_file(env[SCOPE_ENV])
        for tool, path, ti in self.writes.get(member["name"], []):
            d = guard.check(tool, dict(ti, file_path=str(path)), Decision("allow", "base"))
            decisions.append(d)
            if d is not None and d.action == "allow" and tool == "Write":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text(ti.get("content", ""), encoding="utf-8")
        self.calls.append(("decisions", member["name"], [d.action if d else None for d in decisions],
                           [d.reason if d else "" for d in decisions]))
        if member["name"] in self.fail:
            return {"ok": False, "error": f"{member['name']} broke"}
        return {"ok": True, "text": self.texts.get(stage, f"{stage} draft by {member['name']}"), "cost_usd": 0.01,
                "session_id": f"s-{member['name']}"}

    def orchestra(self, goal, *, root, stage, run_dir):
        self.calls.append(("orchestra", stage, goal))
        return {"ok": True, "text": "orchestra finished", "cost_usd": 0.02, "run_id": "20260101-000000-abcd"}

    def flow(self, name, *, intake, cwd, stage, run_dir):
        self.calls.append(("flow", stage, name, intake))
        return {"ok": True, "text": "flow finished", "cost_usd": 0.03, "run_id": "20260101-000000-ef01"}

    # DISPATCH
    def send(self, member, task):
        self.calls.append(("send", member["name"], task["stage"]))
        if self.dispatch_status == 403:
            return 403, {"error": "the owner said no"}
        return self.dispatch_status, {"handle": {"mission": "m-20260101-0001", "part": "1"}}

    def poll(self, handle):
        return self.polls.pop(0) if self.polls else None

    def stop(self, handle, reason):
        self.calls.append(("stop", handle.get("member"), reason))
        return True

    def seams(self) -> dict:
        return {"spawn": self.spawn, "orchestra": self.orchestra, "flow": self.flow, "dispatch": self}
