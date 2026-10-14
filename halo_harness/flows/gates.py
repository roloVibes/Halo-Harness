"""halo_harness.flows.gates -- the human gate a flow step waits on.

The step writes `steps/<n>.gate.json`

    {"id": "<run>:<step>[:<request>]", "run", "step", "n", "round",
     "position": "You" | "<org position>", "text", "artboards": [...],
     "actions": ["accept", "redo", "stop"], "opened": ts}

logs a `gate` line and polls `steps/<n>.answer.json`

    {"id", "round", "action": "accept" | "redo" | "stop", "instruction", "ts"}

which `halo flow answer <run> <step> accept|redo "<text>"|stop` writes (or
Studio, or a test's `answer_gate`). An answer for another id or round is
ignored; a consumed answer and its gate file are removed. `stop.json`
written while a gate is open answers it with `stop`.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import jsonl

ACTIONS = ("accept", "redo", "stop")
_ALIASES = {"a": "accept", "approve": "accept", "yes": "accept", "y": "accept", "ok": "accept",
            "r": "redo", "edit": "redo", "e": "redo", "s": "stop", "no": "stop"}


def gate_path(run_dir, n: int) -> Path:
    return Path(run_dir) / "steps" / f"{int(n)}.gate.json"


def answer_path(run_dir, n: int) -> Path:
    return Path(run_dir) / "steps" / f"{int(n)}.answer.json"


def open_gate(run_dir) -> Optional[dict]:
    """The open gate of this run (the lowest step number), or None."""
    steps = Path(run_dir) / "steps"
    found = sorted(steps.glob("*.gate.json"), key=lambda p: int(p.name.split(".")[0]) if p.name.split(".")[0].isdigit() else 0) \
        if steps.is_dir() else []
    for p in found:
        data = jsonl.read_json(p, None)
        if isinstance(data, dict):
            return data
    return None


def normalize_action(action: str) -> Optional[str]:
    a = str(action or "").strip().lower()
    a = _ALIASES.get(a, a)
    return a if a in ACTIONS else None


def post_gate(flow, n: int, gate: dict) -> dict:
    gate = dict(gate, n=int(n), run=flow.run_dir.name, opened=round(time.time(), 3))
    gate.setdefault("actions", list(ACTIONS))
    gate.setdefault("round", 1)
    try:
        os.unlink(answer_path(flow.run_dir, n))  # a stale answer never answers a new gate
    except OSError:
        pass
    jsonl.write_json(gate_path(flow.run_dir, n), gate)
    flow.log("gate", f"waiting for you at {gate.get('step')}: {gate.get('position', 'You')} "
                     f"(round {gate['round']}) -- halo flow answer {flow.run_dir.name} {gate.get('step')} "
                     f"accept|redo \"<text>\"|stop", step=gate.get("step"), gate=gate)
    return gate


def close_gate(run_dir, n: int) -> None:
    for p in (gate_path(run_dir, n), answer_path(run_dir, n)):
        try:
            os.unlink(p)
        except OSError:
            pass


def write_answer(run_dir, step: str, action: str, instruction: str = "") -> "tuple[bool, str]":
    """What `halo flow answer` does: (ok, message)."""
    run_dir = Path(run_dir)
    act = normalize_action(action)
    if act is None:
        return False, f"the answer is accept, redo \"<text>\" or stop, got {action!r}"
    flow = jsonl.read_json(run_dir / "flow.json", {}) or {}
    ids = [s.get("id") for s in flow.get("steps") or []]
    if step in ids:
        n = ids.index(step) + 1
    elif str(step).isdigit() and 1 <= int(step) <= len(ids):
        n = int(step)
    else:
        return False, f"run {run_dir.name} has no step {step!r} (steps: {', '.join(map(str, ids))})"
    gate = jsonl.read_json(gate_path(run_dir, n), None)
    if not isinstance(gate, dict):
        return False, f"step {step} of run {run_dir.name} is not waiting for an answer"
    if act not in (gate.get("actions") or ACTIONS):
        return False, f"step {step} takes {', '.join(gate.get('actions') or ACTIONS)}"
    jsonl.write_json(answer_path(run_dir, n), {"id": gate.get("id"), "round": gate.get("round"), "action": act,
                                               "instruction": str(instruction or ""), "ts": round(time.time(), 3)})
    return True, f"answered {gate.get('id')} (round {gate.get('round')}): {act}" + (f" -- {instruction}" if instruction else "")


def wait_answer(flow, n: int, gate: dict, *, poll_s: float = 0.5, auto_accept: bool = False,
                answer_gate: Optional[Callable] = None, stop_check: Optional[Callable] = None) -> dict:
    """Block until the gate is answered; `{"action", "instruction"}`."""
    from halo_harness.flows.state import stop_requested
    step = gate.get("step")
    if auto_accept:
        close_gate(flow.run_dir, n)
        flow.log("gate", f"{step}: accepted automatically (--yes)", step=step, id=gate.get("id"), action="accept",
                 auto=True)
        return {"action": "accept", "instruction": ""}
    if answer_gate is not None:
        answer_gate(dict(gate, run_dir=str(flow.run_dir)))
    path = answer_path(flow.run_dir, n)
    while True:
        ans = jsonl.read_json(path, None)
        if isinstance(ans, dict) and ans.get("id") == gate.get("id") and ans.get("round") in (None, gate.get("round")):
            close_gate(flow.run_dir, n)
            act = normalize_action(ans.get("action")) or "stop"
            text = str(ans.get("instruction") or "")
            flow.log("gate", f"{step}: {act}" + (f" -- {text}" if text else ""), step=step, id=gate.get("id"),
                     action=act, instruction=text, round=gate.get("round"))
            return {"action": act, "instruction": text}
        reason = stop_requested(flow.run_dir) or (stop_check() if stop_check else None)
        if reason:
            close_gate(flow.run_dir, n)
            flow.log("gate", f"{step}: stop -- {reason}", step=step, id=gate.get("id"), action="stop")
            return {"action": "stop", "instruction": reason}
        time.sleep(poll_s)
