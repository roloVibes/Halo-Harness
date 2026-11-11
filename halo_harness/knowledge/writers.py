"""halo_harness.knowledge.writers -- findings and decisions written where the
knowing happens (Halo 3.1.8.0 R4, docs/KNOWLEDGE.md "Who writes them").

Each writer is one call from the place that already knows the thing:

    judge_resolved(run_dir, lane_n, rows, tests)   orchestra/merge.py: a conflict the judge resolved with
        evidence and the tests held -> a finding per file, "<file>: hunk <k> resolved for lane <n> because
        <evidence line>" (by judge)
    gate_verdict(run_dir, lanes, gate, report)     orchestra/report.py: a finished run whose test passed on the
        finished branch -> a finding per lane, "<unit> passes `<test>` at <sha>" (by gate)
    sent_back(run_dir, lane, why, gate)            orchestra/run.py: the gate sent a lane's piece back -> a
        decision, "lane <n> sent back: <reason>" (by gate)
    (the coach's Apply writes its decision through the coach pack's engine/knowledge_applied.py since 3.4.0.0 B2)
    answered(state_dir, row)                       supervise/decisions.py: the owner's answer to a goal_plan,
        goal_gate, goal_budget or goal_replan row -> a decision with the answer and its why (by supervisor)

`knowledge.write: false` turns every writer off. 3.3.16.2: a run in the guided
first run's sample repo tags what it writes `sample`, and a gate's passed record
caps the project's at `knowledge.gate_keep` (knowledge/curate.py). A writer never raises and
never changes what its caller wrote; each returns the entries it wrote.
The person who answered is never named: `by` is the role that knew.
"""

from __future__ import annotations

import functools
from pathlib import Path

from halo_harness.knowledge.store import one_line, write

SUPERVISOR_KINDS = {"goal_plan": "plan review", "goal_gate": "gate", "goal_budget": "budget", "goal_replan": "replan"}
WHY_CHARS = 1500
BACK_PREFIX = "The gate sent your piece back: "  # outcomes/lane.py's send-back text, said once in the title
NONE_WORDS = ("none run", "none fetched", "no command run", "no file")  # outcomes/lines.py's "nothing here" lines


def enabled() -> bool:
    try:
        from halo_harness.theme import get_config_value
        value = get_config_value("knowledge.write", True)
    except Exception:
        return True
    return str(value).strip().lower() not in ("false", "0", "no", "off")


def _quiet(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not enabled():
            return []
        try:
            return fn(*args, **kwargs) or []
        except Exception:  # the run, the Apply and the answer go on without their knowledge entry
            return []
    return wrapper


def _repo(run_dir) -> str:
    try:
        from halo_harness.orchestra.goal import repo_root_of
        return Path(repo_root_of(run_dir)).resolve().name
    except Exception:
        return ""


def _sample(run_dir) -> dict:
    """3.3.16.2: a run in the guided first run's sample repo (`<state>/start/<day>/basket`) writes its records
    tagged `sample` (meta `sample: true`), so a search from another project never returns them."""
    try:
        from halo_harness.config.paths import bridge_home
        from halo_harness.orchestra.goal import repo_root_of
        from halo_harness.knowledge.rank import sample_root
        Path(repo_root_of(run_dir)).resolve().relative_to(sample_root(bridge_home()).resolve())
    except Exception:
        return {}
    return {"tags": ["sample"], "meta": {"sample": True}}


def _tags(base: list, sample: dict) -> list:
    return base + sample.get("tags", [])


def tests_line(tests) -> str:
    """`tests: `<command>` exit <n>, <k> passed` for a gate's TestResult."""
    if tests is None or not getattr(tests, "command", ""):
        return "tests: none run (the goal names no test)"
    passed = getattr(tests, "passed", None)
    return f"tests: `{one_line(tests.command, 120)}` exit {tests.returncode}" + (f", {passed} passed" if passed else "")


def _lane_lines(run_dir, n) -> list:
    from halo_harness.outcomes.lane import report_lines
    return [ln for ln in report_lines(run_dir, n) if not ln.startswith("no transcript")]


@_quiet
def judge_resolved(run_dir, lane_n: int, rows: list, tests) -> list:
    from halo_harness.orchestra import gitops
    from halo_harness.outcomes.lane import judge_evidence
    run_dir, out, sample = Path(run_dir), [], _sample(run_dir)
    for row in rows:
        if not (row.get("applied") and row.get("tests_ok")):
            continue
        lines = judge_evidence(run_dir, lane_n, row["file"])
        if not lines:
            continue
        said = [ln for ln in lines if not any(w in ln for w in NONE_WORDS)] or lines  # a line that shows something
        because = ([ln for ln in said if "incoming)" in ln.split(":", 1)[0]] or said)[0].split("): ", 1)[-1]
        hunks = row.get("hunks") or []
        which = f"hunk {hunks[0]['index']}" if len(hunks) == 1 else f"hunks 1-{len(hunks)}"
        spans = ", ".join(f"lines {h['start_line']}-{h['end_line']}" for h in hunks[:4])
        body = (f"What: the fresh judge's answer for {which} of {row['file']} was applied by code, and the tests "
                f"held.\n\nWhere: {row['file']} ({spans}), lane {lane_n} merging into "
                f"{gitops.finished_branch(run_dir.name)} in run {run_dir.name}.\n\nWhy: the judge read what the "
                f"lanes ran and read, never their summaries: {'; '.join(lines[:4])}.")
        out.append(write("finding", f"{row['file']}: {which} resolved for lane {lane_n} because {because}", body=body,
                         evidence=lines + [tests_line(tests)], by="judge", run=run_dir.name, repo=_repo(run_dir),
                         tags=_tags(["orchestra", "merge", "judge"], sample), meta=sample.get("meta")))
    return out


@_quiet
def gate_verdict(run_dir, lanes: list, gate, report: dict) -> list:
    if report.get("status") != "finished" or gate is None or not gate.tests.ok or not gate.tests.command:
        return []
    run_dir, out, sample = Path(run_dir), [], _sample(run_dir)
    sha = str(report.get("finished") or "")[:12] or "the finished branch"
    for lane in lanes:
        units = [] if lane.data().get("assist") else list(lane.job.claims)
        if not units:
            continue
        shown = ", ".join(units[:3]) + (f" (+{len(units) - 3})" if len(units) > 3 else "")
        mine = [ln for ln in _lane_lines(run_dir, lane.n) if ln.startswith("tests: `")]
        body = (f"What: lane {lane.n}'s piece ({lane.job.title}) is merged, and the goal's test passes on the "
                f"finished branch.\n\nWhere: {report.get('branch')} at {sha} in run {run_dir.name}; the units "
                f"{', '.join(units)}.\n\nWhy: the gate ran `{gate.tests.command}` on the finished branch: exit "
                f"{gate.tests.returncode}" + (f", {gate.tests.passed} passed." if gate.tests.passed else "."))
        out.append(write("finding", f"{shown} passes `{one_line(gate.tests.command, 120)}` at {sha}", body=body,
                         evidence=[tests_line(gate.tests)] + mine, by="gate", run=run_dir.name, repo=_repo(run_dir),
                         tags=_tags(["orchestra", "gate"], sample), meta=sample.get("meta")))
    if out:  # 3.3.16.2: a project keeps its newest `knowledge.gate_keep` passed-gate records
        from halo_harness.knowledge.curate import cap_passed_gates
        cap_passed_gates(_repo(run_dir))
    return out


@_quiet
def sent_back(run_dir, lane, why: str, gate) -> list:
    run_dir = Path(run_dir)
    why = str(why or "").strip() or "the gate sent the piece back"
    first = one_line(why.splitlines()[0].replace(BACK_PREFIX, "", 1), 200)
    body = (f"What: the gate sent lane {lane.n}'s piece ({lane.job.title}) back to its worker "
            f"(returned {lane.pieces_returned} time{'s' if lane.pieces_returned != 1 else ''}).\n\nWhere: run "
            f"{run_dir.name}.\n\nWhy: {why[:WHY_CHARS]}")
    evidence = [tests_line(getattr(gate, "tests", None))] + _lane_lines(run_dir, lane.n)
    sample = _sample(run_dir)
    return [write("decision", f"lane {lane.n} sent back: {first}", body=body, evidence=evidence, by="gate",
                  run=run_dir.name, repo=_repo(run_dir), alternatives=["merge the piece as it is", "stop the run"],
                  tags=_tags(["orchestra", "gate", "sent-back"], sample), meta=sample.get("meta"))]


@_quiet
def answered(state_dir, row: dict) -> list:
    kind, answer = row.get("kind"), row.get("answer") or {}
    if kind not in SUPERVISOR_KINDS or not answer or answer.get("key") in (None, "o"):
        return []
    keys, key = row.get("keys") or {}, answer["key"]
    label, word, goal = keys.get(key, key), SUPERVISOR_KINDS[kind], row.get("goal") or "?"
    text, detail = str(answer.get("text") or "").strip(), one_line(row.get("detail"), 400)
    body = (f"What: the owner answered \"{label}\" on the supervisor's {word} decision for goal {goal}: "
            f"{one_line(row.get('what'), 300)}.\n\nWhy: {text[:WHY_CHARS] or 'no reason was given with the answer'}."
            + (f"\n\nWhere: {detail}" if detail else ""))
    evidence = [f"answer: {key} ({label})" + (f" -- {one_line(text, 300)}" if text else "")] + ([detail] if detail else [])
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    run_dir = str(target.get("run_dir") or "")
    return [write("decision", f"{one_line(row.get('what'), 200)} -> {label}", body=body, evidence=evidence,
                  by="supervisor", run=Path(run_dir).name if run_dir else "", repo=_repo(run_dir) if run_dir else "",
                  alternatives=[v for k, v in keys.items() if k not in (key, "o")], tags=["supervise", kind],
                  state_dir=state_dir)]
