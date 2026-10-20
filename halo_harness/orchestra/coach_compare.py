"""halo_harness.orchestra.coach_compare -- the probe's compare (Halo 3.1.6.0 R2):
the deliverables of the reference run and its probe runs, an anonymized
judge, and the contrast compose reads (orchestra/coach_compose.py).

A deliverable, the same for every run (`deliverable(run_dir, patch_path=)`):

    {"status", "stop_reason", "tests_ok", "passed", "failing": [names], "cost_usd", "elapsed_s",
     "lanes", "steps", "stat": "<git diff --shortstat base..finished>", "patch_lines", "patch": "<file>"}

`cost_usd` is the run's cost after the split (`split_usd`, the lead's split,
is left out: a probe reuses the reference's split, so only the work after it
compares). `steps` = every worker pass of every lane (a `writing` line in its
history: a first try, a retry, a piece sent back) + every merge conflict a
judge resolved. The patch (`base..finished`, else the stopped run's merge
branch) is written beside the run (probe_runs.PATCH / REF_PATCH).

The judge (`judge(goal, rows)`): one fresh bare session with no tools
(adapters.one_shot) on the judge role's model, else the run's lead's, given
the goal's WHAT YOU WANT and DONE WHEN, then the deliverables labelled A, B,
C ... in a shuffled order -- whether it finished, its tests, cost, time,
lanes, steps, diffstat and the first PATCH_LINES lines of its patch -- with no
harness, run, bio, model or candidate named. It answers one JSON `{best,
ranking, why}`; an answer that cannot be read is ranked by code (finished,
tests, passed, steps, cost) and says so. `JUDGE` (prompt, model, cwd) ->
{text, ok, error, cost_usd} replaces the call (tests); `HALO_COACH_FAKE=1`
answers with a fake judge that ranks by the same order, no model.

`contrast(ref, outcomes, verdict)`: per candidate the tests delta (passed
counts when both runs printed them, else pass/fail), the cost delta and
ratio, the steps delta, the judge's rank and the reference's, and the axes it
won (`tests`, `rank`, `cost`: cheaper with no fewer tests). A probe that did
not finish wins nothing.
"""

from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import gitops, jsonl

PATCH_LINES = 400
JUDGE: Optional[Callable] = None
_BLOCK = re.compile(r"^Deliverable ([A-Z])\n  finished: (\w+).*?\n  tests: (pass|fail)(?:, (\d+) passed)?.*?\n"
                    r"  cost: \$([\d.]+); time: [\d.]+s; lanes: (\d+); steps: (\d+)", re.M)


def _head(repo, ref: str) -> str:
    try:
        return gitops.head(repo, ref)
    except gitops.GitError:
        return ""


def deliverable(run_dir, *, patch_path) -> dict:
    """What one run delivered (the patch written to `patch_path`)."""
    from halo_harness.orchestra.gate import failing_tests, passed_count
    from halo_harness.orchestra.goal import repo_root_of
    from halo_harness.orchestra.lanes import list_lanes
    run_dir, patch_path = Path(run_dir), Path(patch_path)
    report = jsonl.read_json(run_dir / "report.json", {}) or {}
    split = jsonl.read_json(run_dir / "split.json", {}) or {}
    base, lead_usd = str(split.get("base") or ""), float(split.get("lead_cost_usd") or 0.0)
    repo = repo_root_of(run_dir)
    head = str(report.get("finished") or "") or (_head(repo, report["branch"]) if report.get("branch") and
                                                 gitops.branch_exists(repo, report["branch"]) else "")
    text = gitops.git(["diff", f"{base}..{head}"], repo).stdout if base and head else ""
    stat = gitops.git(["diff", "--shortstat", f"{base}..{head}"], repo).stdout.strip() if base and head else ""
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(text, encoding="utf-8", newline="\n")
    tail = str(report.get("tests_tail") or "")
    merge = jsonl.read_json(run_dir / "merge.json", {}) or {}
    lanes = list_lanes(run_dir)
    steps = sum(sum(1 for h in lane.data().get("history") or [] if h.get("state") == "writing") for lane in lanes)
    return {"status": str(report.get("status") or "missing"), "stop_reason": str(report.get("stop_reason") or ""),
            "tests_ok": bool(report.get("tests_ok")), "passed": passed_count(tail), "failing": failing_tests(tail) or [],
            "cost_usd": round(max(0.0, float(report.get("cost_usd") or 0.0) - lead_usd), 6), "split_usd": lead_usd,
            "elapsed_s": float(report.get("elapsed_s") or 0.0),
            "lanes": len(lanes), "steps": steps + len(merge.get("conflicts") or []), "stat": stat,
            "patch_lines": len(text.splitlines()), "patch": patch_path.name, "patch_path": str(patch_path)}


def _patch_head(d: dict) -> str:
    try:
        lines = Path(d.get("patch_path") or "").read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    more = f"\n... ({len(lines) - PATCH_LINES} more lines)" if len(lines) > PATCH_LINES else ""
    return "\n".join(lines[:PATCH_LINES]) + more


def _tests(d: dict) -> str:
    text = "pass" if d.get("tests_ok") else "fail"
    text += f", {d['passed']} passed" if d.get("passed") is not None else ""
    return text + (f"; failing: {', '.join(d['failing'][:8])}" if d.get("failing") else "")


def judge_prompt(goal, rows: list) -> str:
    """The anonymized compare: rows are (label, deliverable)."""
    blocks = [f"Deliverable {label}\n  finished: {'yes' if d.get('status') == 'finished' else 'no, it stopped early'}\n"
              f"  tests: {_tests(d)}\n  cost: ${float(d.get('cost_usd') or 0):.4f}; time: {float(d.get('elapsed_s') or 0):.1f}s; "
              f"lanes: {d.get('lanes')}; steps: {d.get('steps')}\n  diff: {d.get('stat') or 'no change'}\n"
              f"  patch (the first {PATCH_LINES} lines):\n```diff\n{_patch_head(d)}\n```" for label, d in rows]
    return ("You compare finished work on one goal. The same goal was attempted several times from the same starting "
            "commit; how each attempt was set up is not shown and does not matter. Judge what each one delivered: does "
            "it do what WHAT YOU WANT asks and meet DONE WHEN, do its tests pass, is the change clean and no larger than "
            "the goal needs. Cost and steps break a tie.\n\n"
            f"WHAT YOU WANT: {goal.what}\nDONE WHEN: {goal.done_when}\n\n" + "\n\n".join(blocks)
            + '\n\nAnswer with JSON only: {"best": "<label>", "ranking": ["<label>", ...], "why": "<one paragraph of at '
              'most 120 words citing what you saw in the deliverables>"}. The ranking lists every label once, best first.')


def _order(facts: dict):
    finished, tests, passed, cost, steps = facts
    return (0 if finished else 1, 0 if tests else 1, -(passed or 0), steps, cost)


def _fake(prompt: str, model: str, cwd) -> dict:
    if os.environ.get("HALO_COACH_FAKE", "").strip().lower() == "error":
        return {"text": "", "ok": False, "error": "the fake judge failed (HALO_COACH_FAKE=error)"}
    seen = {m[0]: (m[1] == "yes", m[2] == "pass", int(m[3]) if m[3] else None, float(m[4]), int(m[6]))
            for m in _BLOCK.findall(prompt)}
    ranking = sorted(seen, key=lambda L: (_order(seen[L]), L))
    best = ranking[0] if ranking else "A"
    top = seen.get(best) or (False, False, None, 0.0, 0)
    why = (f"Deliverable {best} {'passes' if top[1] else 'fails'} its tests in {top[4]} steps at ${top[3]:.4f}, the "
           f"best of {len(ranking)} (the fake judge ranks finished, tests, passed, steps, then cost).")
    return {"text": json.dumps({"best": best, "ranking": ranking, "why": why}), "ok": True, "cost_usd": 0.0}


def _caller() -> Callable:
    if JUDGE is not None:
        return JUDGE
    if os.environ.get("HALO_COACH_FAKE", "").strip().lower() not in ("", "0", "false", "no", "off"):
        return _fake
    from halo_harness.orchestra.adapters import one_shot
    return lambda prompt, model, cwd: one_shot(prompt, model=model or None, cwd=cwd)


def parse_verdict(text: str, labels: list) -> "tuple[str, list, str, str]":
    """(best, ranking, why, error) from the judge's answer; error '' when it could be read."""
    from halo_harness.orchestra.split import parse_answer
    obj = parse_answer(text)
    if not isinstance(obj, dict):
        return "", [], "", "the judge's answer has no JSON object"
    ranking = list(dict.fromkeys(str(x).strip().upper() for x in obj.get("ranking") or [] if str(x).strip().upper() in labels))
    best = str(obj.get("best") or "").strip().upper()
    if best not in labels:
        if not ranking:
            return "", [], "", f"the judge's best {obj.get('best')!r} is not one of {', '.join(labels)}"
        best = ranking[0]
    ranking = [best] + [L for L in ranking + labels if L != best]
    why = re.sub(r"\s+", " ", str(obj.get("why") or "")).strip()[:1200]
    return best, list(dict.fromkeys(ranking)), why, ""


def judge(goal, rows: dict, *, model: str = "", cwd=None, rng: Optional[random.Random] = None,
          prompt_path=None) -> dict:
    """The verdict over {key: deliverable}: {labels, best, ranking (keys, best first), why, model, cost_usd, error}."""
    order = sorted(rows)
    (rng or random.Random()).shuffle(order)
    labels = {chr(65 + i): k for i, k in enumerate(order)}
    prompt = judge_prompt(goal, [(L, rows[k]) for L, k in labels.items()])
    if prompt_path is not None:
        Path(prompt_path).write_text(prompt, encoding="utf-8", newline="\n")
    try:
        got = _caller()(prompt, model, cwd)
        best, ranking, why, error = parse_verdict(got.get("text"), list(labels)) if got.get("ok", True) else \
            ("", [], "", str(got.get("error") or "the judge failed").splitlines()[0][:200])
    except Exception as e:  # a provider error is one line, and code ranks
        got, best, ranking, why, error = {}, "", [], "", f"{type(e).__name__}: {e}".splitlines()[0][:200]
    if error:
        def key(L):
            d = rows[labels[L]]
            return _order((d.get("status") == "finished", d.get("tests_ok"), d.get("passed"), d.get("cost_usd"), d.get("steps")))
        ranking = sorted(labels, key=lambda L: (key(L), L))
        best, why = ranking[0], f"the judge did not answer ({error}); ranked by code: finished, tests, passed, steps, cost"
    return {"labels": labels, "best": labels[best], "ranking": [labels[L] for L in ranking], "ranking_labels": ranking,
            "why": why, "model": model, "cost_usd": float(got.get("cost_usd") or 0.0), "error": error}


def contrast(ref: dict, outcomes: dict, verdict: dict) -> list:
    """One row per candidate: its deltas against the reference, the judge's rank and the axes it won."""
    rank = {k: i + 1 for i, k in enumerate(verdict.get("ranking") or [])}
    ref_rank, rows = rank.get("reference"), []
    for o in outcomes.values():
        d = o.get("deliverable") or {}
        row = {"id": o["id"], "kind": o["kind"], "pair": o.get("pair", 1), "status": o.get("status"),
               "stop_reason": o.get("stop_reason") or "", "rank": rank.get(o["id"]), "ref_rank": ref_rank, "wins": []}
        if not d:
            rows.append(dict(row, error=o.get("error") or ""))
            continue
        both = d.get("passed") is not None and ref.get("passed") is not None
        tests = (d["passed"] - ref["passed"]) if both else int(bool(d.get("tests_ok"))) - int(bool(ref.get("tests_ok")))
        cost, ref_cost = float(d.get("cost_usd") or 0.0), float(ref.get("cost_usd") or 0.0)
        done = d.get("status") == "finished"
        wins = [w for w, ok in (("tests", tests > 0), ("rank", bool(ref_rank and row["rank"] and row["rank"] < ref_rank)),
                                ("cost", tests >= 0 and cost < ref_cost - 1e-12)) if ok and done]
        rows.append(dict(row, tests_ok=bool(d.get("tests_ok")), passed=d.get("passed"), tests_delta=tests,
                         tests_by="passed" if both else "pass/fail", cost_usd=round(cost, 6),
                         cost_delta=round(cost - ref_cost, 6), cost_x=round(cost / ref_cost, 3) if ref_cost else None,
                         steps=d.get("steps"), steps_delta=int(d.get("steps") or 0) - int(ref.get("steps") or 0),
                         stat=d.get("stat") or "", wins=wins))
    return sorted(rows, key=lambda r: (r["rank"] or 99, r["id"]))
