"""tests.helpers.card_seed -- what the report card reads (Halo 3.4.1.0 R3 "Time"): tests/helpers/replay_seed.py's session
(main on or:mock/lead, a scout on or:mock/scout that hands back, a fixer on or:mock/fixer that fails -- three models; a
permission card and a question to the owner; $0.03, 100 s) with the fixer's transcript given three file calls: a Write
inside the project (`src/basket.py`), an Edit whose result was an error (not an artefact) and a Write outside the project
(its name only). Beside it tests/helpers/compare_seed.py's second session (an unpriced call) and goal run. No model.
tests/test_report_card.py and the Chrome driver tests/helpers/studio_report_card.py read it.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.helpers.compare_seed import RUN, SID_B, seed_b, seed_run
from tests.helpers.replay_seed import SID, T0, seed

__all__ = ["RUN", "SID", "SID_B", "seed_all", "OUTSIDE"]
OUTSIDE = "C:/Elsewhere/notes-outside.md"


def seed_all(state: Path) -> Path:
    """The three records under `state` (and the goal run's repo beside it); returns the repo."""
    seed(state)
    seed_b(state)
    repo = state.parent / "repo"
    seed_run(repo)
    proj = str(state.parent / "work" / "secret-project")
    log = state / "sessions" / "seed-proj" / SID / "subagents" / "agent-fixer1.jsonl"
    rows = [{"type": "user", "ts": T0 + 11, "content": "fix it"},
            {"type": "assistant", "ts": T0 + 30, "content": [{"type": "tool_use", "id": "w1", "name": "Write",
                                                              "input": {"file_path": proj + "/src/basket.py", "content": "x = 1\n" * 400}}]},
            {"type": "tool_result", "ts": T0 + 31, "tool_use_id": "w1", "tool": "Write", "content": "ok"},
            {"type": "assistant", "ts": T0 + 32, "content": [{"type": "tool_use", "id": "w2", "name": "Edit",
                                                              "input": {"file_path": proj + "/src/broken.py", "old_string": "a", "new_string": "b"}}]},
            {"type": "tool_result", "ts": T0 + 33, "tool_use_id": "w2", "tool": "Edit", "content": "no match", "is_error": True},
            {"type": "assistant", "ts": T0 + 34, "content": [{"type": "tool_use", "id": "w3", "name": "Write",
                                                              "input": {"file_path": OUTSIDE, "content": "notes"}}]},
            {"type": "tool_result", "ts": T0 + 35, "tool_use_id": "w3", "tool": "Write", "content": "ok"},
            {"type": "assistant", "ts": T0 + 40, "content": [{"type": "text", "text": "trying"}]}]
    log.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return repo
