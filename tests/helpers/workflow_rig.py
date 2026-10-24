"""tests.helpers.workflow_rig -- a scratch home with the doc-review pack
installed (bash granted, a catalog model that calls tools), a git repo with
two Markdown files under docs/, and a fake lead and stage worker for the
workflow runs (Halo 3.2.0.0 R5). No model is ever called: the fakes answer
from the stage each lane is for.

    with WorkflowRig() as w:
        c = w.compile(docs="docs")                    # workflows.compile.compile_workflow
        run_dir = w.new_run(c.goal)
        report = w.run(run_dir, worker=StageWorker())  # orchestra.run.run with the fakes
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.helpers.packs_home import FIXTURES, PacksHome

TOOLS_ROW = {"ref": "or:anthropic/claude-sonnet-4.6", "provider": "openrouter", "tools": True}
GOOD_REPORT = {"summary": "One dead link.", "findings": [{"file": "docs/guide.md", "line": 3, "finding": "a dead link",
                                                          "severity": "high"}]}
BAD_REPORT = json.loads((FIXTURES.parent / "workflows" / "report-bad.json").read_text(encoding="utf-8"))


def git(repo, *args) -> str:
    out = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise RuntimeError(f"git {args}: {out.stderr}")
    return out.stdout


class FakeLead:
    """Answers the pinned plan's call: each job's brief refined (or `answers` as given)."""

    def __init__(self, *answers):
        self.answers, self.prompts = list(answers), []

    def __call__(self, prompt: str):
        self.prompts.append(prompt)
        if self.answers:
            text = self.answers.pop(0)
        else:
            ids = [line.split(" ", 2)[1] for line in prompt.splitlines() if line.startswith("- job-")]
            text = json.dumps({"jobs": [{"id": i, "brief": f"refined brief for {i}"} for i in ids]})
        return {"text": text, "cost_usd": 0.001, "session_id": f"lead-{len(self.prompts)}"}


class StageWorker:
    """Per lane, by its stage: read -> notes as its reply; judge -> the verdict (`verdict`, '' skips write);
    write -> artifacts/<n>/report.json (`reports` in order, one per pass; the last one repeats)."""

    def __init__(self, verdict: str = "fix the dead link in docs/guide.md first", reports=None, cost: float = 0.01):
        self.verdict, self.reports, self.cost = verdict, list(reports or [GOOD_REPORT]), cost
        self.calls = []

    def __call__(self, lane):
        from halo_harness.orchestra.goal import load_goal
        from halo_harness.orchestra.handoff import artifacts_dir
        goal = load_goal(lane.run_dir / "goal.json")
        row = goal.workflow["jobs"][lane.job.id]
        self.calls.append((lane.n, row["stage"], lane.prompt, lane.retry_text))
        if row["stage"] == "read":
            return {"text": f"{row['item']}: line 3 has a dead link", "cost_usd": self.cost}
        if row["stage"] == "judge":
            return {"text": self.verdict, "cost_usd": self.cost}
        doc = self.reports.pop(0) if len(self.reports) > 1 else self.reports[0]
        folder = artifacts_dir(lane.run_dir, lane.n)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "report.json").write_text(json.dumps(doc), encoding="utf-8")
        return {"text": "wrote the report", "cost_usd": self.cost}


def fake_judge(hunks, goal, file):
    return {"text": "", "session_id": "judge", "messages_before": 0}


class WorkflowRig(PacksHome):
    INSTALL = True  # 3.2.0.0 R6: tests/test_reference_pack.py installs it itself (halo pack install doc-review)

    def __enter__(self):
        super().__enter__()
        for rel, text in (("docs/guide.md", "# Guide\n\nRead [this](missing.md).\n"),
                          ("docs/intro.md", "# Intro\n\nHello.\n"), ("README.md", "# Repo\n")):
            p = self.repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")
        git(self.repo, "init", "-q")
        for key, value in (("user.name", "t"), ("user.email", "t@t"), ("core.autocrlf", "false"), ("commit.gpgsign", "false")):
            git(self.repo, "config", key, value)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "docs to review")
        self.catalog([TOOLS_ROW])
        if self.INSTALL:
            self.install(self.source(), enable=True, grants=["bash"])
        return self

    def workflow(self, ref: str = "doc-review/review"):
        from halo_harness.workflows.spec import find
        wf, why = find(ref, cwd=self.repo)
        assert wf is not None, why
        return wf

    def compile(self, ref: str = "doc-review/review", **inputs):
        from halo_harness.workflows.compile import compile_workflow
        return compile_workflow(self.workflow(ref), {k: str(v) for k, v in inputs.items()}, repo=self.repo, cwd=self.repo)

    def new_run(self, goal) -> Path:
        from halo_harness.orchestra.goal import new_run
        return new_run(self.repo, goal)

    def run(self, run_dir, *, worker=None, lead=None, approve: bool = True):
        """orchestra.run.run with the fakes; a review run's plan is approved from another thread."""
        import threading
        from halo_harness.orchestra import plan as P
        from halo_harness.orchestra.run import run
        stop = threading.Event()

        def approver():
            while not stop.is_set():
                if P.is_planned(run_dir):
                    P.approve(run_dir, P.current_jobs(run_dir), by="test")
                    return
                stop.wait(0.05)
        t = threading.Thread(target=approver, daemon=True) if approve else None
        if t is not None:
            t.start()
        try:
            return run(run_dir, model_calls=lead or FakeLead(), spawn=worker or StageWorker(), judge=fake_judge,
                       plan_poll_s=0.05)
        finally:
            stop.set()
