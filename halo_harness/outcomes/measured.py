"""halo_harness.outcomes.measured -- success per model and task kind, from
`outcomes.jsonl` (Halo 3.1.8.0 R3, docs/OUTCOMES.md "Measured success").

    success_by_model_kind(state_dir, since=None)
        -> {(model, kind): {n, passed, returned, failed, rate, cost_mean}}

A rate counts the tasks something checked (`check` set: the Orchestra gate,
an acceptance, a stage gate) whose outcome is `passed`, `returned` or
`failed` -- the newest row per task (records.read). `rate` is first-time
success: `passed / n` (a piece sent back and accepted later counts as
`returned`, not passed). `stopped` and `done` rows are not rated, nor rows
whose model is not a model ref (`auto`, `measured`, `default`, empty).
A rate is shown and routed on from `MIN_N` (3) checked tasks.

`by_model(state_dir)` -> `{model: {kind: {n, passed, rate}}}`: what
`capabilities_facts.measured(row)["outcomes"]` carries (providers/model_row_measured.py).
`words(kind, stat)` -> "4/5 code"; `row_words(outcomes)` -> "code 4/5, research 3/3".
"""

from __future__ import annotations

from typing import Optional

MIN_N = 3
NOT_MODELS = ("", "auto", "measured", "default", "inherit", "main")


def success_by_model_kind(state_dir=None, since: Optional[float] = None, rows: Optional[list] = None) -> dict:
    from halo_harness.outcomes.records import RATED, read
    rows = read(state_dir, since=since) if rows is None else rows
    acc: dict = {}
    for r in rows:
        model = str(r.get("model") or "").strip()
        if r.get("outcome") not in RATED or not r.get("check") or model.lower() in NOT_MODELS:
            continue
        s = acc.setdefault((model, str(r.get("kind") or "other")), {"n": 0, "passed": 0, "returned": 0, "failed": 0,
                                                                    "cost": 0.0})
        s["n"] += 1
        s[r["outcome"]] += 1
        s["cost"] += float(r.get("cost_usd") or 0.0)
    out = {}
    for key, s in acc.items():
        out[key] = {"n": s["n"], "passed": s["passed"], "returned": s["returned"], "failed": s["failed"],
                    "rate": round(s["passed"] / s["n"], 3), "cost_mean": round(s["cost"] / s["n"], 6)}
    return out


def by_model(state_dir=None, since: Optional[float] = None) -> dict:
    out: dict = {}
    for (model, kind), s in success_by_model_kind(state_dir, since).items():
        out.setdefault(model, {})[kind] = {"n": s["n"], "passed": s["passed"], "rate": s["rate"]}
    return out


def signature(state_dir=None) -> str:
    """A short hash of what the best-at lines show ((model, kind, n, passed) from MIN_N tasks), '' when nothing:
    a best-at cache source (models_best_at.source_mtimes) that moves only when a shown number moves."""
    try:
        shown_now = sorted((m, k, s["n"], s["passed"]) for (m, k), s in success_by_model_kind(state_dir).items()
                           if s["n"] >= MIN_N)
    except Exception:
        return ""
    if not shown_now:
        return ""
    import hashlib
    return hashlib.sha256(repr(shown_now).encode("utf-8")).hexdigest()[:16]


def words(kind: str, stat: dict) -> str:
    return f"{int(stat.get('passed') or 0)}/{int(stat.get('n') or 0)} {kind}"


def shown(outcomes) -> list:
    """`[(kind, stat)]` with at least MIN_N checked tasks, the most measured first."""
    if not isinstance(outcomes, dict):
        return []
    rows = [(k, s) for k, s in outcomes.items() if isinstance(s, dict) and int(s.get("n") or 0) >= MIN_N]
    return sorted(rows, key=lambda t: (-int(t[1].get("n") or 0), t[0]))


def row_words(outcomes) -> str:
    """"code 4/5, research 3/3" (the kinds with MIN_N or more checked tasks), '' when none."""
    return ", ".join(f"{k} {int(s.get('passed') or 0)}/{int(s.get('n') or 0)}" for k, s in shown(outcomes))


def table_lines(stats: dict) -> list:
    """`halo models --measured`: one row per model and kind, the most measured first."""
    if not stats:
        return ["Nothing measured yet: outcomes.jsonl gets a row per checked agent task (an Orchestra lane, "
                "a sub-agent with an acceptance); `halo outcomes` lists them."]
    lines = [f"{'model':<44} {'kind':<9} {'n':>3}  {'passed':>6}  {'rate':>5}  {'mean cost':>9}"]
    for (model, kind), s in sorted(stats.items(), key=lambda t: (t[0][0], -t[1]["n"], t[0][1])):
        mark = "" if s["n"] >= MIN_N else "  (fewer than 3: not routed on)"
        lines.append(f"{model:<44} {kind:<9} {s['n']:>3}  {s['passed']:>3}/{s['n']:<2}  {s['rate'] * 100:>4.0f}%  "
                     f"${s['cost_mean']:>8.4f}{mark}")
    return lines
