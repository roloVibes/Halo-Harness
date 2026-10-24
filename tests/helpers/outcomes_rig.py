"""tests.helpers.outcomes_rig -- the fixture transcripts (tests/fixtures/outcomes/)
and a worker for the Orchestra mock rig that leaves a transcript behind, the
way a real `halo -p` worker does (Halo 3.1.8.0 R3, docs/OUTCOMES.md).

* `nodes(name)` -- a fixture transcript's session-log nodes (or entries);
* `home()` -- a fresh BRIDGE_TEST_HOME for one test (BRIDGE_STATE_DIR unset),
  restored after: the outcomes rows a run appends land in it;
* `TranscriptWorker(inner, plan)` -- runs the fixture FakeWorker, then writes
  the session file `<state>/sessions/<slug of the worktree>/<id>.jsonl` with the
  nodes `plan[lane][pass]` names (the last one repeats; a lane `plan` lacks
  leaves no transcript), and hands back that session id;
* `test_run(command, output)` -- the two nodes of one Bash call that ran tests.
No model is called.
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
import uuid
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "outcomes"


def nodes(name: str) -> list:
    from halo_harness.outcomes.transcript import read_nodes
    return read_nodes(FIX / f"{name}.jsonl")


@contextlib.contextmanager
def home(prefix: str = "outcomes-"):
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    d = Path(tempfile.mkdtemp(prefix=prefix))
    os.environ["BRIDGE_TEST_HOME"] = str(d)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    try:
        yield d / ".halo"
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def test_run(command: str, output: str = "Ran 5 tests in 0.004s\n\nOK", tool_id: str = "tr1") -> list:
    return [{"type": "assistant", "ts": 1.0, "content": [{"type": "tool_use", "id": tool_id, "name": "Bash",
                                                          "input": {"command": command}}]},
            {"type": "tool_result", "ts": 2.0, "tool_use_id": tool_id, "tool": "Bash", "content": output, "is_error": False}]


def write_session(worktree, session_id: str, rows: list) -> Path:
    from halo_harness.config.paths import bridge_home, project_slug
    path = bridge_home() / "sessions" / project_slug(worktree) / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


class TranscriptWorker:
    def __init__(self, inner, plan: dict):
        self.inner, self.plan, self.passes, self.prompts = inner, dict(plan), {}, {}

    def __call__(self, lane):
        out = self.inner(lane)
        k = self.passes.get(lane.n, 0)
        self.passes[lane.n] = k + 1
        self.prompts.setdefault(lane.n, []).append(lane.prompt)
        steps = self.plan.get(lane.n)
        if not steps or not isinstance(out, dict):
            return out
        step = steps[min(k, len(steps) - 1)]
        rows = step(lane) if callable(step) else nodes(step)
        sid = f"lane{lane.n}-pass{k + 1}-{uuid.uuid4().hex[:6]}"
        write_session(lane.worktree, sid, rows)
        return dict(out, session_id=sid, model="or:mock/lane-coder")
