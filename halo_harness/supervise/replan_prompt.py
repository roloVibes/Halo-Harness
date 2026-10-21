"""halo_harness.supervise.replan_prompt -- what the supervisor asks a drifting
run's lead (Halo 3.1.8.0 R2, docs/SUPERVISE.md "Replanning").

The split prompt's shape (orchestra/split.py `split_prompt`) over the plan so
far: the merged lanes pinned, every lane LEFT with its state, model, returns
and blocks, why the run drifted (drift.py's lines), the claimable units, the
four moves and the strict answer shape replan_plan.py checks. For a lane that
came back, what came back: the probe's contrast list when a probe of this run
ran (`<run>/probe.json`, coach_compare.contrast's rows in coach_compose's
words), else the gate's last verdict as its worker read it (`returned_text`
in the lane file, the text the gate or a failed merge sent back), else the
lane's last error.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from halo_harness.orchestra import jsonl

TEXT_MAX = 1500

MOVES = (
    "Your moves, for any lane left (one or more):\n"
    '- a different model: keep its id and claims and give "model": "<ref>" (or "bio": "<bio>")\n'
    '- a split: two or more new jobs, each with "from": "<its id>", whose claims divide its claims (no unit in two)\n'
    '- a second specialist beside a stuck lane: a new job with "assist": "<its id>", the same claims and a "bio"; '
    "it reads the units and never edits them, and its final reply is handed to that lane's worker, which runs after it\n"
    '- a retry with the contrast as context: keep its id and claims and give "retry": true; its worker runs again '
    "with what came back\n"
    "A lane you keep as it is, list as it is. Name EVERY lane left, by its own id or as the \"from\" of its parts. "
    "Answer with JSON only:\n"
    '{"jobs": [{"id": "job-2", "title": "one line", "claims": ["file#unit"], "model": "<ref>", "retry": true}], '
    '"why": "one line"}\n'
    'If STOP WHEN already applies, answer {"stop": "the reason"} instead. Give each job "est_tokens": '
    '{"in": <input tokens>, "out": <output tokens>}, your estimate of what its worker will use.'
)


def _indent(text: str, pad: str = "        ") -> str:
    return "\n".join(pad + line for line in str(text).splitlines()) or pad + "(empty)"


def context(run_dir, n: int, lane: dict) -> str:
    """What came back for lane `n` ('' when nothing did)."""
    probe = jsonl.read_json(Path(run_dir) / "probe.json", {}) or {}
    rows = probe.get("contrast") if isinstance(probe, dict) else None
    if isinstance(rows, list) and rows:
        from halo_harness.orchestra.coach_compose import row_line
        ref, k = probe.get("reference") or {}, len([r for r in rows if isinstance(r, dict) and r.get("rank")]) + 1
        lines = []
        for r in rows:
            try:
                lines.append("- " + row_line(r, ref, k))
            except (KeyError, TypeError, ValueError):
                continue
        if lines:
            return "the probe's contrast (what differed between the run and its candidates):\n" + "\n".join(lines)
    text = str(lane.get("returned_text") or "").strip()
    if text:
        return "the gate's last verdict, as its worker read it:\n" + text[-TEXT_MAX:]
    error = str(lane.get("error") or "").strip()
    return f"its last error: {error[-TEXT_MAX:]}" if error else ""


def refusals(run_dir, n: int, lane: dict, events: Optional[list] = None) -> int:
    """Claim refusals the lane's worker met (events.jsonl `claim` lines with op `refused`)."""
    events = jsonl.read_lines(Path(run_dir) / "events.jsonl") if events is None else events
    holder = str(lane.get("holder") or "")
    return sum(1 for e in events if e.get("kind") == "claim" and (e.get("data") or {}).get("op") == "refused"
               and ((e.get("data") or {}).get("lane_n") == n or (holder and (e.get("data") or {}).get("holder") == holder)))


def _model(job: dict, lane: dict, rows: list) -> str:
    ref = str(job.get("model") or lane.get("model") or "")
    if not ref:
        return "the worker role's model"
    from halo_harness.orchestra.coach_prices import price_words
    return f"{ref} ({price_words(rows, ref)})"


def _units(run_dir, goal) -> str:
    from halo_harness.orchestra.goal import repo_root_of
    from halo_harness.orchestra.index import index_file
    repo, rows = repo_root_of(run_dir), []
    for rel in goal.files:
        try:
            rows += [f"  {u.key}  ({u.kind}, lines {u.start_line}-{u.end_line})" for u in index_file(repo / rel, root=repo)]
        except (OSError, ValueError, SyntaxError):
            rows.append(f"  {rel}  (could not be read)")
    return "\n".join(rows)


def lane_lines(run_dir, drifts: list, rows: Optional[list] = None) -> "tuple[list, list]":
    """`(pinned lines, left lines)` of the plan so far; `drifts` drift.py's rows as dicts."""
    from halo_harness.supervise.drift import lanes_left, plan_lanes
    jobs, files = plan_lanes(run_dir)
    left = lanes_left(jobs, files)
    events = jsonl.read_lines(Path(run_dir) / "events.jsonl")
    rows = rows if rows is not None else []
    pinned, out = [], []
    for n in sorted(jobs):
        job, lane = jobs[n], files.get(n, {})
        head = f"  {job.get('id')} (lane {n}): {job.get('title') or ''}"
        claims = ", ".join(str(c) for c in job.get("claims") or [])
        if n not in left:
            pinned.append(f"{head}  [merged; claims {claims}]")
            continue
        blocks = [f"{d.get('kind')} {float(d.get('value') or 0):.0f}s" for d in drifts
                  if d.get("lane") == n and d.get("kind") in ("blocked", "stalled")]
        out.append(f"{head}\n      state {lane.get('state') or 'not started'}, model {_model(job, lane, rows)}, "
                   f"sent back {int(lane.get('pieces_returned') or 0)} times, "
                   f"{refusals(run_dir, n, lane, events)} claim refusals" + (f", {', '.join(blocks)}" if blocks else "")
                   + f"\n      claims: {claims}")
        came = context(run_dir, n, lane) if int(lane.get("pieces_returned") or 0) or lane.get("error") else ""
        if came:
            first, _, rest = came.partition("\n")
            out.append(f"      what came back, {first}" + (f"\n{_indent(rest)}" if rest else ""))
    return pinned, out


def prompt(run_dir, goal, drifts: list, problems: Optional[list] = None, rows: Optional[list] = None) -> str:
    """The replan ask for `goal` (orchestra/goal.py's Goal) of the run at `run_dir`; `drifts` drift.py's rows
    as dicts (replan.json's `why`)."""
    pinned, left = lane_lines(run_dir, drifts, rows)
    why = [f"{d.get('kind')}: {d.get('text')}" for d in drifts]
    text = (
        "You are the lead orchestrator. The run you split is drifting, so the supervisor paused the lanes left "
        "(workers that were running finished their step; nothing was killed). Plan the lanes LEFT again.\n\n"
        f"WHAT YOU WANT: {goal.what}\nDONE WHEN: {goal.done_when}\nSTOP WHEN: {goal.stop_when}\n\n"
        "Why the supervisor asks (the drift):\n" + "\n".join(f"- {w}" for w in why) + "\n\n"
        "The plan so far. Merged lanes are pinned: leave them out of your answer and never claim their units.\n"
        + ("\n".join(pinned) if pinned else "  (no lane is merged yet)") + "\n"
        "The lanes left:\n" + "\n".join(left) + "\n\n"
        f"Claimable units of the shared files (key, kind, lines):\n{_units(run_dir, goal)}\n\n" + MOVES
    )
    if problems:
        text += "\n\nYour previous answer had these problems; fix every one:\n" + "\n".join(f"- {p}" for p in problems)
    return text
