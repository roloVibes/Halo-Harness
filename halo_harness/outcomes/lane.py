"""halo_harness.outcomes.lane -- an Orchestra lane's evidence and what the gate
does with it (Halo 3.1.8.0 R3, docs/OUTCOMES.md "The judge reads the evidence").

* `write_lane(run_dir, lane, goal)` -- after each worker pass (workers.run_lane):
  the evidence of every session the lane's workers ran (`session_ids`, each
  found by `transcript.find_log`) at `<run>/lanes/<n>/evidence.json`. The
  lane's kind is its bio's (outcomes/kinds.py), else `code` (`other` for a
  replan's specialist, which edits nothing).
* `evidence_back(run_dir, goal, lanes, tests)` -- the gate's one rule, before
  the record check: a `code` lane with no test run in its work (when the goal
  has a `test`) goes back with "no test run in this lane's work: run <test>",
  a `research` lane with no source with "no source fetched or read". Once per
  lane (`evidence_returned` on its file), never past the return cap, and only
  when a transcript was read (no transcript: nothing to judge). Each send-back
  is one `gate` line in events.jsonl. Returns `{lane: the text it goes back with}`.
* `lanes_lines(run_dir, lanes)` -- `{lane: evidence lines}`: the gate's
  verdict and the run report carry them.
* `with_evidence(goal, run_dir, lane_n, file)` -- the goal the conflict judge
  is given, with `evidence`: the lines of the incoming lane and of every other
  lane that wrote the file (tests, sources, reproductions; never a summary).
  3.2.1.0 R2: in a workflow run the incoming lane's stage evidence too, the
  gate's own lines (workflows/gate.py `lane_evidence`, read in the lane's
  worktree): `lane N (stage <id>, incoming): evidence <item>: <bytes> bytes,
  sha256 <12 chars>` or `...: evidence <item>: missing`.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Optional

from halo_harness.outcomes import evidence as E
from halo_harness.outcomes.lines import judge_lines, lines
from halo_harness.outcomes.transcript import find_log, read_nodes

EVIDENCE = "evidence.json"
CODE_LINE = "no test run in this lane's work: run {test}"
RESEARCH_LINE = "no source fetched or read"


def evidence_path(run_dir, n) -> Path:
    return Path(run_dir) / "lanes" / str(int(n)) / EVIDENCE


def load_lane(run_dir, n) -> Optional[E.Evidence]:
    return E.load(evidence_path(run_dir, n))


def _bio(name: str, cwd) -> dict:
    if not name:
        return {}
    try:
        from halo_harness.agents_yaml import resolve_agent_bio
        return resolve_agent_bio(name, cwd=cwd) or {}
    except Exception:
        return {}


def gather_lane(run_dir, lane, goal) -> E.Evidence:
    data, job = lane.data(), lane.job
    sessions = [str(s) for s in data.get("session_ids") or [] if s]
    nodes: list = []
    for sid in sessions:
        path = find_log(sid, cwd=lane.worktree)
        if path is not None:
            nodes.extend(read_nodes(path))
    bio_name = str(data.get("bio") or getattr(job, "bio", "") or "")
    try:
        from halo_harness.orchestra.goal import repo_root_of
        repo = repo_root_of(run_dir)
    except Exception:
        repo = None
    bio = _bio(bio_name, repo) or bio_name
    return E.gather(nodes, bio, cwd=lane.worktree, default_kind="other" if data.get("assist") else "code",
                    test_command=str(getattr(goal, "test", "") or ""), model=str(data.get("model") or getattr(job, "model", "") or ""),
                    cost_usd=float(data.get("cost_usd") or 0.0), base=str(data.get("base") or "") or None, sessions=sessions)


def write_lane(run_dir, lane, goal) -> Optional[E.Evidence]:
    """The lane's evidence.json, rewritten after each pass; never raises (None when it could not be gathered)."""
    try:
        ev = gather_lane(run_dir, lane, goal)
        E.write(evidence_path(run_dir, lane.n), ev)
        return ev
    except Exception:
        return None


def _rule(ev: E.Evidence, goal) -> str:
    test = str(getattr(goal, "test", "") or "").strip()
    if ev.kind == "code" and test and not ev.tests:
        return CODE_LINE.format(test=test)
    if ev.kind == "research" and not ev.sources:
        return RESEARCH_LINE
    return ""


def evidence_back(run_dir, goal, lanes: list, tests) -> dict:
    """`{lane: text}` for the lanes the gate sends back for missing evidence (see the module docstring)."""
    from halo_harness.orchestra import events as run_events
    out = {}
    for lane in lanes:
        ev = load_lane(run_dir, lane.n)
        if ev is None or not ev.transcript or lane.data().get("evidence_returned"):
            continue
        line = _rule(ev, goal)
        if not line or lane.pieces_returned >= int(getattr(goal, "return_cap", 0) or 0):
            continue
        lane.update(evidence_returned=line)
        text = f"The gate sent your piece back: {line}."
        if not getattr(tests, "ok", True) and getattr(tests, "tail", ""):
            text += f"\nThe tests also fail on the finished branch:\n{tests.tail}"
        out[lane.n] = text
        run_events.log(run_dir, "gate", f"lane {lane.n} sent back for its evidence: {line}", lane=lane.n,
                       evidence=line)
    return out


def lanes_lines(run_dir, lanes: list) -> dict:
    out = {}
    for lane in lanes:
        n = getattr(lane, "n", lane)
        ev = load_lane(run_dir, n)
        if ev is not None:
            out[int(n)] = lines(ev)
    return out


def report_lines(run_dir, n) -> list:
    ev = load_lane(run_dir, n)
    return lines(ev) if ev is not None else []


def _wrote(ev: E.Evidence, file: str) -> bool:
    want = str(file).replace("\\", "/")
    return any(str(p).replace("\\", "/").endswith(want) for p in ev.written)


def judge_evidence(run_dir, lane_n: int, file: str) -> list:
    """`lane N (kind): <line>` for the incoming lane and every other lane that wrote `file`."""
    out = []
    for path in sorted((Path(run_dir) / "lanes").glob(f"*/{EVIDENCE}"), key=lambda p: (p.parent.name != str(lane_n),
                                                                                      p.parent.name)):
        if not path.parent.name.isdigit():
            continue
        ev = E.load(path)
        n = int(path.parent.name)
        if ev is None or not ev.transcript or (n != int(lane_n) and not _wrote(ev, file)):
            continue
        who = "incoming" if n == int(lane_n) else "merged"
        out += [f"lane {n} ({ev.kind}, {who}): {line}" for line in judge_lines(ev)]
    cut = sum(1 for line in out if line.startswith(f"lane {int(lane_n)} ("))
    return out[:cut] + stage_lines(run_dir, int(lane_n)) + out[cut:]


def stage_lines(run_dir, n: int) -> list:
    """A workflow lane's `evidence <item>` lines for the judge, as the gate reads them ([] for a run without one)."""
    try:
        from halo_harness.orchestra.goal import load_goal
        from halo_harness.orchestra.lanes import load_lane as orchestra_lane
        from halo_harness.workflows.gate import evidence_line, lane_evidence, stage_of
        goal = load_goal(Path(run_dir) / "goal.json")
        lane = orchestra_lane(run_dir, n) if getattr(goal, "workflow", None) else None
        if lane is None:
            return []
        return [f"lane {n} (stage {stage_of(goal, lane)}, incoming): {evidence_line(e)}"
                for e in lane_evidence(run_dir, goal, lane, lane.worktree)]
    except Exception:  # the judge's evidence never takes a merge down
        return []


def with_evidence(goal, run_dir, lane_n: int, file: str):
    """The goal with its `evidence` lines for the judge (the goal itself when there are none)."""
    try:
        found = judge_evidence(run_dir, lane_n, file)
    except Exception:
        found = []
    if not found:
        return goal
    if isinstance(goal, dict):
        return dict(goal, evidence=found)
    out = copy.copy(goal)
    out.evidence = found
    return out
