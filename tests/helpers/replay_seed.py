"""tests.helpers.replay_seed -- one session on disk for the replay tests (Halo 3.4.1.0 R1 "Time"): main thinks, spawns
a scout (reads, hands back at +50 s, done at +59) and a fixer (fails at +90), waits on a permission card (+20 to +26,
answered allow) and asks a question (+70 to +80), done at +100. A fake key sits in the title, the scout's task, the
question and the hand-back; the project path in the meta. tests/test_replay_file.py and the Chrome driver
tests/helpers/studio_replay_time.py read it.
"""
from __future__ import annotations

import json
from pathlib import Path

FAKE_KEY = "sk-or-v1-" + "c0ffee12" * 8  # built here: never a key-shaped literal in the tree
ENV_KEY = "OPENROUTER_API_KEY=" + "zq" * 14
SID = "replay0000seed0000000000000001"
T0 = 1_790_000_000.0


def _lines(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def seed(state: Path) -> Path:
    folder = state / "sessions" / "seed-proj"
    proj = str(state.parent / "work" / "secret-project")
    _lines(folder / f"{SID}.jsonl", [
        {"type": "meta", "ts": T0, "cwd": proj, "model": "or:mock/lead", "title": f"ship it {FAKE_KEY}"},
        {"type": "user", "ts": T0 + 1, "content": "Ship the basket fix"},
        {"type": "assistant", "ts": T0 + 5, "content": [{"type": "thinking", "thinking": "plan first"}]},
        {"type": "assistant", "ts": T0 + 10, "content": [{"type": "tool_use", "id": "a1", "name": "Agent",
                                                          "input": {"subagent_type": "scout", "prompt": "look"}}]},
        {"type": "tool_result", "ts": T0 + 60, "tool_use_id": "a1", "tool": "Agent", "content": "done"},
        {"type": "usage", "ts": T0 + 60, "usage": {}, "cost_usd": 0.02},
        {"type": "assistant", "ts": T0 + 70, "content": [{"type": "tool_use", "id": "q1", "name": "AskUserQuestion",
                                                          "input": {"questions": [{"question": f"may I push? {FAKE_KEY}"}]}}]},
        {"type": "tool_result", "ts": T0 + 80, "tool_use_id": "q1", "tool": "AskUserQuestion", "content": "yes"},
        {"type": "assistant", "ts": T0 + 100, "content": [{"type": "text", "text": "All done."}]},
        {"type": "meta", "ts": T0 + 100, "timeline": {"message_end_ms": 100000, "permission_waits": [
            {"start_ms": 20000, "end_ms": 26000, "decision": "allow", "what": "Bash: rm -rf build"}]}}])
    sub = folder / SID / "subagents"
    for aid, kind, t1, err, task in (("scout1", "scout", T0 + 59, False, f"find the bug {ENV_KEY}"),
                                     ("fixer1", "fixer", T0 + 90, True, "fix it")):
        (sub / f"agent-{aid}.meta.json").parent.mkdir(parents=True, exist_ok=True)
        (sub / f"agent-{aid}.meta.json").write_text(json.dumps({
            "agent_id": aid, "type": kind, "role": kind, "lineup": "dev", "model": "or:mock/" + kind, "started": T0 + 11,
            "finished": t1, "status": "failed" if err else "completed", "is_error": err, "description": task}), encoding="utf-8")
    _lines(sub / "agent-scout1.jsonl", [
        {"type": "user", "ts": T0 + 11, "content": f"find the bug {ENV_KEY}"},
        {"type": "assistant", "ts": T0 + 20, "content": [{"type": "tool_use", "id": "r1", "name": "Read", "input": {"file_path": proj + "/b.py"}}]},
        {"type": "tool_result", "ts": T0 + 21, "tool_use_id": "r1", "tool": "Read", "content": "x"},
        {"type": "usage", "ts": T0 + 30, "usage": {}, "cost_usd": 0.01},
        {"type": "assistant", "ts": T0 + 50, "content": [{"type": "text", "text": f"Found it, key was {FAKE_KEY}"}]}])
    _lines(sub / "agent-fixer1.jsonl", [{"type": "user", "ts": T0 + 11, "content": "fix it"},
                                       {"type": "assistant", "ts": T0 + 40, "content": [{"type": "text", "text": "trying"}]}])
    return folder / f"{SID}.jsonl"
