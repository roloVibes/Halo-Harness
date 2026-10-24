"""halo_harness.outcomes.session -- a session sub-agent's evidence and outcome,
written when it ends (Halo 3.1.8.0 R3; agent/subagent.py calls `record_subagent`
beside every `subagent_end`: the foreground spawn, a background one, a fan-out
job and a resumed task).

* evidence: `gather` over the child's own log nodes, written beside its
  transcript -- `<session dir>/subagents/agent-<id>.jsonl` gets
  `agent-<id>.evidence.json`;
* the outcome (outcomes/records.py): its acceptance check's when it has one
  (`passed` first time, `returned` after the critique's retry, `failed`; a
  background, fan-out or resumed child, whose spawn path runs no check, gets
  the same local check on its final text), else its stage gate's, else
  `stopped` (stopped or interrupted), `failed` (ended on an error), `done`
  (nothing checked it);
* one outcomes.jsonl row in the parent's state dir: run = the parent
  session's id, task = `agent <id>`.

Never raises: a sub-agent's return is never held up by its record.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def evidence_path_for(child) -> Optional[Path]:
    path = getattr(getattr(child, "log", None), "path", None)
    return Path(path).with_name(Path(path).stem + ".evidence.json") if path else None


def _bio(team_control, role_name, spec_name: str, child) -> dict:
    try:
        if team_control is not None and role_name:
            entry = team_control.assignment_for(role_name)
            bio = team_control.bio_for(role_name)
            if bio:
                return dict(bio, name=str((entry or {}).get("agent") or bio.get("name") or spec_name))
        from halo_harness.agents_yaml import resolve_agent_bio
        return resolve_agent_bio(spec_name, cwd=getattr(child, "cwd", None), state_dir=getattr(child, "state_dir", None)) or {}
    except Exception:
        return {}


def outcome_of(*, is_error: bool, stopped: bool, acceptance: Optional[dict], stage) -> "tuple[str, str]":
    """`(outcome, check)` (see the module docstring)."""
    if stopped:
        return "stopped", ""
    if acceptance is not None and not is_error:
        if acceptance.get("met"):
            return ("returned" if int(acceptance.get("attempts") or 1) > 1 else "passed"), "acceptance"
        return "failed", "acceptance"
    if stage is not None and not is_error:
        return ("passed" if stage[0] else "failed"), "stage"
    return ("failed" if is_error else "done"), ""


def record_subagent(parent, child, *, spec_name: str, role_name=None, team_control=None, agent_id: str = "",
                    is_error: bool = False, stopped: bool = False, acceptance: Optional[dict] = None,
                    stage=None) -> Optional[dict]:
    """The child's evidence.json and its outcomes.jsonl row; the row (None when nothing could be recorded).
    `acceptance`: `{met, why, attempts}` from the acceptance check (its `expect` comes from the bio);
    `stage`: `(ok, line)` from a lineup stage's gate."""
    try:
        from halo_harness.outcomes.evidence import gather, write
        from halo_harness.outcomes.records import append, make_row
        bio = _bio(team_control, role_name, spec_name, child)
        if acceptance is not None:
            acc = bio.get("acceptance") if isinstance(bio.get("acceptance"), dict) else {}
            acceptance = {"expect": str(acc.get("expect") or "non-empty"), "met": bool(acceptance.get("met")),
                          "why": str(acceptance.get("why") or ""), "attempts": int(acceptance.get("attempts") or 1)}
        model = str(getattr(getattr(child, "model_ref", None), "raw", "") or "")
        cost = float(getattr(getattr(child, "cost_meter", None), "total_usd", 0.0) or 0.0)
        ev = gather(child.log.nodes(), bio or spec_name, cwd=getattr(child, "cwd", None),
                    words=" ".join(str(w) for w in (role_name, spec_name) if w), model=model, cost_usd=cost,
                    acceptance=acceptance, sessions=[str(getattr(child.log, "session_id", "") or "")])
        if not ev.bio:
            ev.bio = spec_name
        where = evidence_path_for(child)
        written = write(where, ev) if where is not None else None
        # the check the spawn path ran, else the same check on the final text (a background / fan-out / resumed child)
        outcome, check = outcome_of(is_error=is_error, stopped=stopped, acceptance=ev.acceptance, stage=stage)
        row = make_row(run=str(getattr(getattr(parent, "log", None), "session_id", "") or ""), task=f"agent {agent_id}",
                       source="session", ev=ev, outcome=outcome, check=check,
                       returns=max(0, int((ev.acceptance or {}).get("attempts") or 1) - 1),
                       evidence_path=str(written or ""), role=str(role_name or ""),
                       # 3.1.9.0 R3: whether the spawn picked its model, and why (models_auto_spawn.record)
                       picked=str(getattr(child, "model_picked", "") or "none"),
                       reason=str(getattr(child, "model_reason", "") or ""))
        state_dir = getattr(parent, "state_dir", None)
        if state_dir is None:
            from halo_harness.config.paths import bridge_home
            state_dir = bridge_home()
        append([row], state_dir)
        return row
    except Exception:
        return None
