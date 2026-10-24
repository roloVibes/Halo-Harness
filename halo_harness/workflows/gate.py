"""halo_harness.workflows.gate -- the quality gate of a workflow run, widened
(Halo 3.2.0.0 R5; orchestra/gate.py `quality_gate` calls `widen` for a goal
with a `workflow`).

On top of the tests and the record check the gate already runs:

* every typed output (`artifact:<schema>`) its stage's lanes saved
  (`lanes/<n>/artifacts/<name>.json`) is read and checked against the pack's
  schema (packs/typed.py); a missing or mismatching artifact is a RETURN: the
  lane goes back to its worker with the problems;
* every `verify.evidence` item is read -- an output or a give of the stage
  (what its lanes saved), or a file on the finished branch -- and must be
  there and not empty. The evidence joins the record check (`record` rows
  `evidence:<item>`, `artifact:<name>`): the judge reads these files, not a
  worker's summary (3.1.8.0 R3 will widen what the judge reads);
* when the run's tests fail and name no worker's unit, each stage's own
  `verify.test` runs alone to find the stage that fails, and that stage's
  lanes go back with the tail;
* a stage's `retries` is its lanes' return cap; at it the run stops.

A lane `skipped` by its `when` has no outputs and no evidence to check.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from halo_harness.workflows.bounds import bound


def _lanes_of(goal, lanes: list, stage_id: str) -> list:
    st = next((s for s in (goal.workflow or {}).get("stages") or [] if s.get("id") == stage_id), {})
    jobs = set(st.get("jobs") or [])
    return [lane for lane in lanes if lane.job.id in jobs and not lane.data().get("skipped")]


def _rows(lane, name: str) -> list:
    return [g for g in lane.data().get("gave") or [] if g.get("name") == name]


def _artifacts(run_dir, goal, lanes, record: list, problems: dict) -> None:
    from halo_harness.orchestra.goal import repo_root_of
    from halo_harness.packs.discover import find
    from halo_harness.packs.typed import artifact_schema, check
    wf = goal.workflow or {}
    pack = find(str(wf.get("pack") or ""), cwd=repo_root_of(run_dir))
    for name, out in (wf.get("outputs") or {}).items():
        if not out.get("schema"):
            continue
        schema = artifact_schema(pack.root, out["schema"]) if pack is not None else None
        for lane in _lanes_of(goal, lanes, out.get("from")):
            rows = [r for r in _rows(lane, name) if str(r.get("path") or "").endswith(".json")]
            if not rows:
                lines = [f"{name}: not saved -- save it as lanes/{lane.n}/artifacts/{name}.json (JSON matching {out['schema']})"]
            else:
                try:
                    doc = json.loads((Path(run_dir) / rows[0]["path"]).read_text(encoding="utf-8-sig"))
                    lines = [f"{name}: {p}" for p in check(doc, schema)] if schema is not None else \
                        [f"{name}: the pack's schema {out['schema']} cannot be read"]
                except (OSError, ValueError) as e:
                    lines = [f"{name}: {rows[0]['path']} is not JSON ({e})"]
            record.append({"lane": lane.n, "key": f"artifact:{name}", "equal": not lines, "judge": False,
                           "artifact": name, "schema": out["schema"], "problems": lines})
            if lines:
                problems.setdefault(lane.n, []).extend(lines)


def _digest(path: Path) -> "tuple[int, str]":
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest()[:16]


def _evidence(run_dir, goal, lanes, cwd, record: list, problems: dict) -> None:
    for st in (goal.workflow or {}).get("stages") or []:
        items = ((st.get("verify") or {}) if isinstance(st.get("verify"), dict) else {}).get("evidence") or []
        for lane in _lanes_of(goal, lanes, st.get("id")) if items else []:
            for item in items:
                rows = _rows(lane, item)
                paths = [Path(run_dir) / r["path"] for r in rows if r.get("kind") != "files"] if rows else [Path(cwd) / item]
                there = [p for p in paths if p.is_file() and p.stat().st_size > 0]
                size, sha = _digest(there[0]) if there else (0, "")
                record.append({"lane": lane.n, "key": f"evidence:{item}", "equal": bool(there), "judge": False,
                               "evidence": item, "bytes": size, "sha256": sha})
                if not there:
                    problems.setdefault(lane.n, []).append(
                        f"evidence {item}: " + ("empty or not saved" if rows else f"{item} is not on the finished branch"))


def _stage_tests(run_dir, goal, lanes, cwd, problems: dict) -> None:
    from halo_harness.orchestra.gate import run_tests
    for st in (goal.workflow or {}).get("stages") or []:
        cmd = ((st.get("verify") or {}) if isinstance(st.get("verify"), dict) else {}).get("test")
        if not cmd:
            continue
        got = run_tests(run_dir, replace(goal, test=str(cmd)), cwd)
        if not got.ok:
            for lane in _lanes_of(goal, lanes, st.get("id")):
                problems.setdefault(lane.n, []).append(f"the stage's test `{cmd}` fails:\n{got.tail}")


def _cap(goal, lane) -> int:
    own = bound(goal, lane.job.id, "retries")
    return int(own) if isinstance(own, int) else int(goal.return_cap)


def widen(result, run_dir, goal, lanes: list, cwd):
    """`result` (the tests and the record check) with the workflow's outputs, evidence and stage tests."""
    record, problems = list(result.record), {}
    _artifacts(run_dir, goal, lanes, record, problems)
    _evidence(run_dir, goal, lanes, cwd, record, problems)
    if not result.tests.ok and not result.back:
        _stage_tests(run_dir, goal, lanes, cwd, problems)
    extra_ok = all(r.get("equal") for r in record[len(result.record):])
    by_n = {lane.n: lane for lane in lanes}
    back = sorted(set(result.back) | set(problems))
    capped = [n for n in back if by_n[n].pieces_returned >= _cap(goal, by_n[n])]
    record_ok = result.record_ok and extra_ok
    if not back:
        return replace(result, record=record, record_ok=record_ok)
    if capped:
        why = "; ".join(problems.get(n, ["the tests still fail"])[0].splitlines()[0] for n in capped)
        stages = ", ".join(f"{n} ({(goal.workflow.get('jobs') or {}).get(by_n[n].job.id, {}).get('stage')})" for n in capped)
        return replace(result, ok=False, record=record, record_ok=record_ok, back=[],
                       stop_reason=f"lane {stages} reached the return cap ({max(_cap(goal, by_n[n]) for n in capped)}) "
                                   f"and its piece still fails the gate: {why}")
    from halo_harness.orchestra import events as run_events
    for n in sorted(problems):
        run_events.log(run_dir, "gate", f"lane {n}: {len(problems[n])} problem(s) with its outputs: "
                       + problems[n][0].splitlines()[0], lane=n, problems=problems[n])
    notes = {n: "The gate sent your piece back:\n" + "\n".join(f"- {p}" for p in problems[n])
             + "\nFix every one; save the artifact again where it was." for n in problems}
    return replace(result, ok=False, record=record, record_ok=record_ok, back=back, stop_reason="", notes=notes)
