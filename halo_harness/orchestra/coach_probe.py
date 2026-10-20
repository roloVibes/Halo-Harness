"""halo_harness.orchestra.coach_probe -- the coach probes (Halo 3.1.6.0 R2,
after Google's Harness², arXiv 2610.14224): before the coach offers Apply,
it tries two candidate overlays of the run's harness on the same goal and
keeps what the deliverables support. Off unless asked.

    estimate(run_dir, k)  the cost line shown before anything runs: "probe: N runs, up to $X"
                          (N = 2k; each run's cap = the run's cost_usd x coach.probe.budget_factor)
    draft(run_dir, k)     the run's lead drafts k pairs (invariant + domain, coach_probe_schema.py) in
                          one one-shot call: coach_ask's lead, the same path, the same HALO_COACH_FAKE seam
    probe(run_dir, k)     draft -> a probe run per candidate (probe_runs.py) -> the anonymized compare
                          (coach_compare.py) -> compose (coach_compose.py) -> clean up; the result is one
                          coach card (coach_probe_card.py)

`<run>/probe.json`, written as each step ends:

    {"state": "running|done|failed", "step", "line", "k", "factor", "cap_usd", "runs", "card": "probe-<ts>",
     "candidates": [{id, kind, pair, overlay, dropped, skipped?}], "reference": {deliverable},
     "outcomes": {id: {status, stop_reason, deliverable, delivered, notes, cleanup}},
     "judge": {labels, best, ranking, why, model, cost_usd, error}, "contrast": [rows],
     "pick": "invariant|domain|merged|kept", "picked": [ids], "why", "overlay", "apply": {changes, skipped},
     "cost": {"draft", "runs", "judge", "total"}, "started", "ended", "ts", "error"}
`ASK` (prompt, model, cwd) -> {text, ok, error, cost_usd} replaces the draft call (tests).
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import jsonl
from halo_harness.orchestra.coach_probe_schema import KINDS, clean, facts, is_empty

FILE = "probe.json"
ASK: Optional[Callable] = None
K_MAX = 4
_SHAPE = ('{"pairs": [{"invariant": {"lead": {"model": "<ref>", "effort": "low|medium|high|xhigh|max", "prompt_notes": '
          '"..."}, "workers": {"model": "<ref>", "prompt_notes": "...", "max_iterations": 40, "tools": {"allow": [...], '
          '"deny": [...]}}, "bios": {"<bio>": {"model", "prompt_notes", "max_iterations", "tools"}}, "why": "..."}, '
          '"domain": {"workers": {"prompt_notes": "..."}, "bios": {"<bio>": {"prompt_notes": "...", "use_for": '
          '["word"]}}, "plan": [{"job": "job-2", "after": ["job-1"]}], "why": "..."}}]}')


def money(x) -> str:
    return f"${float(x or 0):.4f}"


def read(run_dir) -> Optional[dict]:
    data = jsonl.read_json(Path(run_dir) / FILE, None)
    return data if isinstance(data, dict) else None


def settings(k=None, factor=None) -> "tuple[int, float]":
    """k (pairs, 1..K_MAX) and the budget factor: the arguments, else coach.probe.k / coach.probe.budget_factor."""
    from halo_harness.theme import get_config_value
    try:
        k = int(k if k is not None else get_config_value("coach.probe.k", 1) or 1)
    except (TypeError, ValueError):
        k = 1
    try:
        factor = float(factor if factor is not None else get_config_value("coach.probe.budget_factor", 1.5) or 1.5)
    except (TypeError, ValueError):
        factor = 1.5
    return max(1, min(K_MAX, k)), (factor if factor > 0 else 1.5)


def estimate(run_dir, k=None, factor=None) -> dict:
    """{k, factor, runs, ref_usd, cap_usd, total_usd, line}: what the probe may spend, before it starts."""
    k, factor = settings(k, factor)
    report = jsonl.read_json(Path(run_dir) / "report.json", {}) or {}
    ref = float(report.get("cost_usd") or 0.0) if isinstance(report, dict) else 0.0
    cap, runs = round(ref * factor, 6), 2 * k
    return {"k": k, "factor": factor, "runs": runs, "ref_usd": ref, "cap_usd": cap, "total_usd": round(cap * runs, 6),
            "line": f"probe: {runs} runs, up to {money(cap * runs)} (each stops at {money(cap)}: the run's "
                    f"{money(ref)} x {factor:g})"}


def probe_line(data: Optional[dict]) -> str:
    """The report's and the Fleet digest's probe line ('' before a probe ended)."""
    if not data or data.get("state") != "done":
        return ""
    return f"probe: {data.get('runs')} runs, {money((data.get('cost') or {}).get('total'))}, picked: {data.get('pick')}"


def draft_prompt(f: dict, k: int, cards: list) -> str:
    g = f["goal"]
    report = jsonl.read_json(Path(f["run_dir"]) / "report.json", {}) or {}
    lanes = "\n".join(f"  lane {l['n']} ({l['job']}): bio {l['bio'] or '(none)'}, model {l['model'] or '(the role table)'}, "
                      f"${l['cost_usd']:.4f}" for l in f["lanes"]) or "  (no lanes)"
    jobs = "\n".join(f"  {j.get('id')}: {j.get('title')} (claims {', '.join(j.get('claims') or [])})"
                     + (f", after {', '.join(j['after'])}" if j.get("after") else "") for j in f["jobs"]) or "  (none)"
    seen = "\n".join(f"  - [{c.get('severity')}] {c.get('kind')}: {c.get('text')} (why: {'; '.join(c.get('why') or [])})"
                     for c in cards) or "  - (no card)"
    return (f"You led this Orchestra run. Before the coach offers a change, it will run the same goal again under "
            f"candidate setups of the run's harness and compare what each delivers. Draft {k} pair(s) of candidates.\n\n"
            "Each pair has two kinds: `invariant` changes how the agents work whatever the goal (planning, tool use, "
            "context budget, delegation: the lead's model and effort, the workers' model, notes, max_iterations, "
            "tools); `domain` adds what this goal needs (procedure, knowledge, constraints: notes per bio, use_for "
            "words, a plan edit `after`). Keep each note under 600 characters and name only the bios and jobs below.\n\n"
            f"WHAT YOU WANT: {g.what}\nDONE WHEN: {g.done_when}\nSTOP WHEN: {g.stop_when}\n\n"
            f"The run: {report.get('status')}, tests {'pass' if report.get('tests_ok') else 'fail'}, "
            f"{money(report.get('cost_usd'))}, {float(report.get('elapsed_s') or 0):.1f}s\n{lanes}\n"
            f"The plan's jobs:\n{jobs}\nThe run's bios: {', '.join(f['bios']) or '(none)'}\n"
            f"The lineup: {f['lineup'] or '(none)'}; the lead role {f['lead_role']}, the worker role {f['worker_role']}\n"
            f"The coach's cards from the run's files:\n{seen}\n\n"
            f"Answer with JSON only, {k} pair(s) in this shape (leave out what you do not change):\n{_SHAPE}\n")


def _fake(prompt: str, model: str, cwd) -> dict:
    if os.environ.get("HALO_COACH_FAKE", "").strip().lower() == "error":
        return {"text": "", "ok": False, "error": "the fake lead failed (HALO_COACH_FAKE=error)"}
    m = re.search(r"Draft (\d+) pair", prompt)
    pairs = [{"invariant": {"lead": {"effort": "high"},
                            "workers": {"prompt_notes": "Claim every unit before you edit it, and run the goal's test "
                                                        f"command before you finish (pair {i}).", "max_iterations": 40},
                            "why": "the workers edit before they claim and finish without the tests"},
              "domain": {"workers": {"prompt_notes": "Keep each function to what its docstring says and change "
                                                     f"nothing outside your claimed units (pair {i})."},
                         "why": "the goal's functions are specified by their docstrings"}}
             for i in range(1, int(m.group(1) if m else 1) + 1)]
    return {"text": json.dumps({"pairs": pairs}), "ok": True, "cost_usd": 0.0}


def _caller() -> Callable:
    if ASK is not None:
        return ASK
    if os.environ.get("HALO_COACH_FAKE", "").strip().lower() not in ("", "0", "false", "no", "off"):
        return _fake
    from halo_harness.orchestra.adapters import one_shot
    return lambda prompt, model, cwd: one_shot(prompt, model=model or None, cwd=cwd)


def draft(run_dir, k: int = 1, *, ask: Optional[Callable] = None, cwd=None, state_dir=None, f=None) -> dict:
    """{candidates, model, role, cost_usd, error}: k pairs drafted by the run's lead and cleaned to the schema."""
    from halo_harness.orchestra.coach_ask import lead_of
    from halo_harness.orchestra.split import parse_answer
    f = f or facts(run_dir, cwd=cwd, state_dir=state_dir)
    role, model = lead_of(run_dir, "orchestra", cwd=f["cwd"], state_dir=state_dir)
    try:
        from halo_harness.orchestra.coach import cached
        cards = cached(run_dir, cwd=f["cwd"], state_dir=state_dir).get("suggestions") or []
    except Exception:
        cards = []
    out = {"candidates": [], "model": model, "role": role, "cost_usd": 0.0, "error": ""}
    try:
        got = (ask or _caller())(draft_prompt(f, k, [c for c in cards if c.get("kind") != "probe"]), model, f["cwd"])
    except Exception as e:  # a provider error is one line
        got = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    out["cost_usd"] = float(got.get("cost_usd") or 0.0)
    obj = parse_answer(got.get("text")) if got.get("ok", True) else None
    pairs = (obj.get("pairs") if isinstance((obj or {}).get("pairs"), list) else [obj]) if isinstance(obj, dict) else []
    if not pairs:
        out["error"] = str(got.get("error") or "the lead's answer has no candidates in JSON").splitlines()[0][:200]
        return out
    tag = "p" + secrets.token_hex(2)
    for i, pair in enumerate(pairs[:k], 1):
        for kind in KINDS:
            overlay, dropped = clean(kind, (pair or {}).get(kind) if isinstance(pair, dict) else None, f)
            c = {"id": f"{tag}-{kind}-{i}", "kind": kind, "pair": i, "overlay": overlay, "dropped": dropped}
            out["candidates"].append(dict(c, skipped="nothing left to try after the schema check") if is_empty(overlay) else c)
    return out


_LIVE: dict = {}  # run folder -> the thread of a probe started in this process (`start`)


def live(run_dir) -> bool:
    t = _LIVE.get(str(Path(run_dir).resolve()))
    return bool(t is not None and t.is_alive())


def start(run_dir, **kw) -> bool:
    """`probe(run_dir, **kw)` on a daemon thread (/coach, Studio); False when one already runs for this run here."""
    if live(run_dir):
        return False
    t = threading.Thread(target=probe, args=(run_dir,), kwargs=kw, name=f"halo-coach-probe-{Path(run_dir).name}", daemon=True)
    _LIVE[str(Path(run_dir).resolve())] = t
    t.start()
    return True


def probe(run_dir, *, k=None, factor=None, cwd=None, state_dir=None, on_step: Optional[Callable] = None,
          rng=None) -> dict:
    """The whole probe; probe.json's final shape. Never raises for a model or run failure (state: failed)."""
    from halo_harness.orchestra import coach_compare as C
    from halo_harness.orchestra import coach_compose as M
    from halo_harness.orchestra import probe_runs as PR
    run_dir, lock = Path(run_dir), threading.Lock()
    est = estimate(run_dir, k, factor)
    started = time.time()
    data = {"state": "running", "k": est["k"], "factor": est["factor"], "runs": est["runs"], "cap_usd": est["cap_usd"],
            "estimate": est["line"], "card": f"probe-{int(started)}", "started": round(started, 3), "outcomes": {}}

    def step(name: str, line: str, **extra) -> None:
        with lock:
            data.update(step=name, line=line, ts=round(time.time(), 3))
            jsonl.write_json(run_dir / FILE, data)
        if on_step is not None:
            on_step(line, step=name, **extra)
    step("draft", f"the run's lead drafts {est['k']} pair(s) of candidates; {est['line']}")
    verdict = {}
    try:
        f = facts(run_dir, cwd=cwd, state_dir=state_dir)
        if not f["jobs"]:
            raise RuntimeError("the run has no split to run again: it stopped before its lead split the goal")
        drafted = draft(run_dir, est["k"], cwd=cwd, state_dir=state_dir, f=f)
        data.update(candidates=drafted["candidates"],
                    lead={"model": drafted["model"], "role": drafted["role"], "cost_usd": drafted["cost_usd"]})
        if drafted["error"] or all(c.get("skipped") for c in drafted["candidates"]):
            raise RuntimeError(drafted["error"] or "no candidate left to try after the schema check")
        step("runs", f"{est['runs']} probe run(s) from the run's base commit, each up to {money(est['cap_usd'])}")
        data["outcomes"] = PR.run_all(run_dir, drafted["candidates"], f, est["cap_usd"],
                                      on_step=lambda line, **d: step("runs", line, **d))
        step("compare", "the judge compares the anonymized deliverables")
        ref = C.deliverable(run_dir, patch_path=PR.probes_dir(run_dir) / PR.REF_PATCH)
        rows = dict({"reference": ref}, **{o["id"]: o["deliverable"] for o in data["outcomes"].values() if o.get("deliverable")})
        from halo_harness.orchestra.adapters import role_model
        verdict = C.judge(f["goal"], rows, model=role_model("judge") or drafted["model"], cwd=f["cwd"], rng=rng,
                          prompt_path=PR.probes_dir(run_dir) / "judge.prompt.txt")
        contrast = C.contrast(ref, data["outcomes"], verdict)
        composed = M.compose(drafted["candidates"], contrast, ref)
        changes, skipped = M.changes(composed["overlay"], f) if composed["pick"] != "kept" else ([], [])
        data.update(reference=ref, judge=verdict, contrast=contrast, pick=composed["pick"], picked=composed["from"],
                    why=composed["why"], overlay=composed["overlay"], apply={"changes": changes, "skipped": skipped},
                    state="done")
    except Exception as e:  # a failed draft, a broken repo: the probe ends with the reason
        data.update(state="failed", error=f"{type(e).__name__}: {e}" if not isinstance(e, RuntimeError) else str(e))
    finally:  # every probe folder of this draft loses its worktrees and branches, whatever happened above
        for c in data.get("candidates") or []:
            if (PR.probes_dir(run_dir) / c["id"]).is_dir():
                o = data["outcomes"].setdefault(c["id"], {"id": c["id"], "kind": c["kind"], "status": "stopped"})
                o["cleanup"] = PR.cleanup(PR.probes_dir(run_dir) / c["id"])
    runs = sum(float((o.get("deliverable") or {}).get("cost_usd") or 0) for o in data["outcomes"].values())
    draft_usd = float((data.get("lead") or {}).get("cost_usd") or 0.0)
    total = round(runs + draft_usd + float(verdict.get("cost_usd") or 0.0), 6)
    data.update(cost={"draft": draft_usd, "runs": round(runs, 6), "judge": float(verdict.get("cost_usd") or 0.0),
                      "total": total}, ended=round(time.time(), 3))
    step("done" if data["state"] == "done" else "failed",
         probe_line(data) if data["state"] == "done" else f"probe failed: {data.get('error')}")
    try:
        from halo_harness.orchestra.coach import cached
        cached(run_dir, cwd=cwd, state_dir=state_dir)  # the coach's runs.json takes the probe line (Fleet digest)
    except Exception:
        pass
    return data
