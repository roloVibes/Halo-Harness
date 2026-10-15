"""tests.helpers.studio_fleet_parts -- pieces of tests/helpers/studio_fleet_rig.py
(Halo 3.0.5.0 "Fleet"; split out in R4 to keep the rig small): the scripted
model steps, the real Session factory, and (R4) a FINISHED past session of
this harness seeded in the rig's state directory: a main agent that edited
basket.py and spawned a reviewer sub-agent that handed back, with usage lines,
so the replay, the recordings and the digest have a whole session to read.
"""
from __future__ import annotations

import json
import tempfile
import threading
import time
from pathlib import Path

from tests.helpers.mock_openai import _finish

PAST_SID = "5eed0000past00000000000000000001"
PAST_REVIEWER = "rv0past1"


def said_then_tool(text: str, *calls) -> list:
    """One assistant message: a line of text, then tool calls."""
    tcs = [{"index": i, "id": cid, "type": "function", "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a, cid) in enumerate(calls)]
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"content": text}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": tcs}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]}]


def held(gate: threading.Event, chunks: list, seen: "list | None" = None):
    def step(handler, body):
        if seen is not None:
            seen.append(body)
        gate.wait(600)
        _finish(handler, chunks)
    return step


def recorded(chunks: list, seen: list):
    def step(handler, body):
        seen.append(body)
        _finish(handler, chunks)
    return step


def spawn(kind: str, prompt: str, model: str, cid: str) -> tuple:
    return ("Agent", {"description": prompt.split(":")[0], "prompt": prompt, "subagent_type": kind, "model": model}, cid)


def make_session(root: Path, proj: Path, mock, model: str):
    """A real agent.loop.Session on the mock upstream, auto mode, three sub-agent kinds."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.config.agents_md import AgentSpec
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    specs = {n: AgentSpec(name=n, description=d, tools=None, disallowed_tools=[], body=f"You are the {n}.")
             for n, d in (("implementer", "writes the change"), ("researcher", "reads and reports"), ("general-purpose", "general"))}
    return Session(cwd=proj, model_ref=parse_model_ref(model), model_profile=ModelProfile(),
                   creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
                   state_dir=Path(tempfile.mkdtemp(prefix="fleet-state-", dir=root)), model_label=model,
                   session_context=SessionContext(cwd=proj, model_label=model, bare=True),
                   openrouter_base_url=mock.base_url, max_turns=10,
                   permission_engine=PermissionEngine(mode="auto", cwd=proj), agents=specs, routes={})


def _lines(path: Path, nodes: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(n) for n in nodes) + "\n", encoding="utf-8")


def seed_past(state: Path, proj: Path, t0: "float | None" = None) -> Path:
    """The finished past session `PAST_SID` (an hour ago, 10 minutes long); its main transcript's path."""
    t0 = t0 if t0 is not None else time.time() - 3600
    folder = state / "sessions" / "past-shop"
    main = folder / f"{PAST_SID}.jsonl"
    edit = {"type": "tool_use", "id": "call_p1", "name": "Edit",
            "input": {"file_path": str(proj / "basket.py"), "old_string": "sum(", "new_string": "discounted("}}
    _lines(main, [
        {"type": "meta", "ts": t0, "cwd": str(proj), "model": "or:mock/qwen3-lead", "title": "fix the basket rounding"},
        {"type": "user", "ts": t0 + 1, "content": "Fix the rounding in basket.py and have it reviewed"},
        {"type": "assistant", "ts": t0 + 30, "content": [{"type": "text", "text": "Editing basket.py first."}, edit]},
        {"type": "tool_result", "ts": t0 + 31, "tool_use_id": "call_p1", "tool": "Edit", "content": "ok"},
        {"type": "usage", "ts": t0 + 31, "usage": {}, "cost_usd": 0.012},
        {"type": "assistant", "ts": t0 + 60, "content": [{"type": "tool_use", "id": "call_p2", "name": "Agent",
                                                          "input": {"subagent_type": "reviewer", "prompt": "Review basket.py"}}]},
        {"type": "tool_result", "ts": t0 + 540, "tool_use_id": "call_p2", "tool": "Agent",
         "content": "One finding, fixed (https://example.com/pr/7). </script><script>alert(1)</script>"},
        {"type": "assistant", "ts": t0 + 600, "content": [{"type": "text", "text": "Rounding fixed and reviewed."}]},
        {"type": "usage", "ts": t0 + 600, "usage": {}, "cost_usd": 0.008}])
    sub = folder / PAST_SID / "subagents"
    (sub / f"agent-{PAST_REVIEWER}.meta.json").parent.mkdir(parents=True, exist_ok=True)
    (sub / f"agent-{PAST_REVIEWER}.meta.json").write_text(json.dumps({
        "agent_id": PAST_REVIEWER, "type": "reviewer", "role": "reviewer", "lineup": "halo-dev-cycle", "model": "or:mock/glm-5",
        "started": t0 + 61, "finished": t0 + 539, "status": "completed", "is_error": False}), encoding="utf-8")
    _lines(sub / f"agent-{PAST_REVIEWER}.jsonl", [
        {"type": "user", "ts": t0 + 61, "content": "Review basket.py"},
        {"type": "assistant", "ts": t0 + 120, "content": [{"type": "tool_use", "id": "call_r1", "name": "Read",
                                                           "input": {"file_path": str(proj / "basket.py")}}]},
        {"type": "tool_result", "ts": t0 + 121, "tool_use_id": "call_r1", "tool": "Read", "content": "def total(items): ..."},
        {"type": "assistant", "ts": t0 + 530, "content": [{"type": "text", "text": "One finding: round after the discount."}]},
        {"type": "usage", "ts": t0 + 530, "usage": {}, "cost_usd": 0.005}])
    return main


def quiet_health():
    """(R4b) Studio's health panel reads every harness's providers: in the rig they answer from here, no network.
    Returns the undo."""
    from halo_harness.fleet import health
    saved = health._provider
    health._provider = lambda name, label, probe: {"name": label, "configured": True, "reachable": True if probe else None, "note": ""}
    health.forget()
    return lambda: (setattr(health, "_provider", saved), health.forget())
