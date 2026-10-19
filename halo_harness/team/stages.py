"""halo_harness.team.stages -- one stage's prompt, its gate and its acceptance.

An agent stage's member gets one prompt: the brief (its path and text), each
block it reads (path, the ledger's state.json, the last CHANGES_N lines of
changes.jsonl), the blocks it writes (its claim scope), the stage's own
`prompt`, the other members' hand-backs when it is the lead, and a redo's
text. The gate is kept in the stage folder:

    stages/<id>/gate.json    {id: "<run>:<stage>:<round>", run, stage, round, text, summary,
                              acceptance: {ok, note} | null, actions: [accept, redo, stop], opened}
    stages/<id>/answer.json  {id, round, action: accept | redo | stop, text, ts}

`halo team answer`, Studio and the tests write the answer; the runner reads
it, logs a `gate` line and removes both files. Acceptance runs as
`TeamControl.evaluate_stage` does (an `expect` checked on the stage result,
or a `prompt` sent through the ACCEPT seam).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import jsonl
from halo_harness.team import blocks as B
from halo_harness.team import board as BD
from halo_harness.team import spec as S
from halo_harness.team.gate_actions import ACTIONS, normalize_action

CHANGES_N = 10
BRIEF_CAP = 20000


def _read(path: Path, cap: int) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(missing)"
    return text if len(text) <= cap else text[:cap] + f"\n... ({len(text) - cap} more characters in the file)"


def read_context(team: dict, stage: dict, n: int = CHANGES_N) -> str:
    root = Path(team["root"])
    out = [f"THE BRIEF ({team['brief']}), read it first:\n{_read(root / team['brief'], BRIEF_CAP)}"]
    for bid in stage.get("reads") or []:
        block = S.block_by_id(team, bid)
        if block is None:
            continue
        state = jsonl.read_json(B.ledger_dir(root, block) / "state.json", None)
        lines = B.changes(root, block)[-n:]
        recent = "\n".join(f"  {c.get('member')} ({c.get('stage')}) {c.get('op')} {c.get('key')}" for c in lines)
        out.append(f"BLOCK `{bid}` ({block['kind']} {block['path']}, claims {block['claims']}), read it at "
                   f"{root / block['path']}\n  state: {state or 'no writes yet'}\n"
                   f"  last changes:\n{recent or '  (none)'}")
    return "\n\n".join(out)


def scope_text(team: dict, stage: dict) -> str:
    writes = []
    for bid in stage.get("writes") or []:
        block = S.block_by_id(team, bid)
        if block:
            writes.append(f"`{bid}` ({block['kind']} {block['path']}, claims {block['claims']})")
    if not writes:
        return "THIS STAGE WRITES NO BLOCK: read, decide and report; leave the files as they are."
    return ("YOU WRITE ONLY IN: " + ", ".join(writes) + ". A write elsewhere comes back refused with the reason; "
            "a part another member holds comes back naming who holds it -- write another part or wait.")


def stage_prompt(team: dict, stage: dict, member: dict, *, lead: str, handbacks: "Optional[dict]" = None,
                 redo: str = "") -> str:
    task = stage.get("prompt") or f"Do stage `{stage['id']}` of team `{team['name']}` as the brief describes."
    parts = [f"You are `{member['name']}` (lineup `{member['lineup']}`, alias `{member['role']}`) in team "
             f"`{team['name']}`, stage `{stage['id']}`.", read_context(team, stage), scope_text(team, stage),
             f"THE TASK: {task}"]
    if handbacks:
        parts.append("YOU LEAD THIS STAGE: merge and decide. The other members' hand-backs:\n"
                     + "\n\n".join(f"--- {name} ---\n{text}" for name, text in handbacks.items()))
    if redo:
        parts.append(f"THE LEAD ASKED FOR A REDO: {redo}")
    parts.append("End with a short hand-back: what you changed, where, and anything left open.")
    if member["name"] != lead and not handbacks:
        parts.append(f"`{lead}` leads this stage and merges your hand-back.")
    return "\n\n".join(parts)


# ---- the gate -----------------------------------------------------------------

def gate_id(run_dir, sid: str, rnd: int) -> str:
    return f"{Path(run_dir).name}:{sid}:{int(rnd)}"


def open_gate(run_dir, sid: str, rnd: int, *, summary: str, acceptance: Optional[dict], gate: str) -> dict:
    data = {"id": gate_id(run_dir, sid, rnd), "run": Path(run_dir).name, "stage": sid, "round": int(rnd),
            "gate": gate, "text": f"stage {sid} round {rnd} is done: accept, redo \"<text>\" or stop",
            "summary": summary[:2000], "acceptance": acceptance, "actions": list(ACTIONS),
            "opened": round(time.time(), 3)}
    try:
        os.unlink(BD.stage_dir(run_dir, sid) / "answer.json")
    except OSError:
        pass
    BD.write_stage_file(run_dir, sid, "gate.json", data)
    BD.log(run_dir, "gate", f"waiting at {sid} (round {rnd}): halo team answer {sid} accept|redo|stop",
           stage=sid, gate=data)
    return data


def read_gate(run_dir, sid: str) -> Optional[dict]:
    data = BD.read_stage_file(run_dir, sid, "gate.json", None)
    return data if isinstance(data, dict) else None


def write_answer(run_dir, sid: str, action: str, text: str = "") -> "tuple[bool, str]":
    act = normalize_action(action)
    if act is None:
        return False, f"the answer is accept, redo \"<text>\" or stop, got {action!r}"
    gate = read_gate(run_dir, sid)
    if gate is None:
        return False, f"stage {sid} of run {Path(run_dir).name} is not waiting for an answer"
    BD.write_stage_file(run_dir, sid, "answer.json", {"id": gate["id"], "round": gate["round"], "action": act,
                                                      "text": str(text or ""), "ts": round(time.time(), 3)})
    return True, f"answered {gate['id']}: {act}" + (f" -- {text}" if text else "")


def take_answer(run_dir, sid: str) -> Optional[dict]:
    """The answer to the open gate (and the gate closes), or None."""
    gate = read_gate(run_dir, sid)
    ans = BD.read_stage_file(run_dir, sid, "answer.json", None)
    if gate is None or not isinstance(ans, dict) or ans.get("id") != gate.get("id"):
        return None
    close_gate(run_dir, sid)
    act = normalize_action(ans.get("action")) or "stop"
    out = {"action": act, "text": str(ans.get("text") or ""), "ts": ans.get("ts"), "round": gate.get("round")}
    BD.log(run_dir, "gate", f"{sid}: {act}" + (f" -- {out['text']}" if out["text"] else ""), stage=sid, action=act,
           answer=out)
    return out


def close_gate(run_dir, sid: str) -> None:
    for name in ("gate.json", "answer.json"):
        try:
            os.unlink(Path(run_dir) / "stages" / sid / name)
        except OSError:
            pass


# ---- acceptance -----------------------------------------------------------------

def evaluate(team: dict, stage: dict, text: str, call_fn: Optional[Callable] = None) -> Optional[dict]:
    """`{ok, note}` for a stage with an acceptance, else None."""
    acc = stage.get("acceptance")
    if not acc or not (acc.get("expect") or acc.get("prompt")):
        return None
    from halo_harness.teams_runtime import TeamControl
    control = TeamControl(name=team.get("name") or "team", template={})
    lead = S.member_by_name(team, stage.get("lead") or "")
    ok, note = control.evaluate_stage({"name": stage["id"], "role": lead["role"] if lead else None,
                                       "acceptance": {k: v for k, v in acc.items() if v}}, text, call_fn)
    return {"ok": bool(ok), "note": note}
