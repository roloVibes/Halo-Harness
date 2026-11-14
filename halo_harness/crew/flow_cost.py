"""halo_harness.crew.flow_cost -- what a workflow costs and writes, said before it runs (Halo 3.6.0.0 R2).

    band(wf, resolve, state_dir) -> {low, high, unknown: [agent], line}
    writes(wf, resolve, state_dir) -> [line]

One agent turn is priced as one typical task on its model's catalog price (crew/trial.py `estimate`: ~20k tokens in,
~2k out). The low end: every step that always runs, once, at half a typical task. The high end: every step, each
round up to its repeat's `max`, plus each round's yes/no check by the step's last agent. An agent on Auto has no price
until Auto picks its model: it is named under `unknown`, and the line says "unknown until the first run". A
workflow's own `max_usd` caps the high end and is said.
"""

from __future__ import annotations

from typing import Callable

from halo_harness.crew.changes import use_word
from halo_harness.crew.runner import rounds_of


def _usd(raw, state_dir, memo: dict):
    if raw is None:
        return None
    model = str(raw.get("model") or "auto")
    if model not in memo:
        from halo_harness.crew.trial import estimate
        memo[model] = estimate({"model": model}, state_dir).get("usd")
    return memo[model]


def band(wf: dict, resolve: Callable, state_dir=None) -> dict:
    low = high = 0.0
    unknown: list = []
    auto: list = []
    memo: dict = {}
    steps = [s for s in wf.get("steps") or [] if isinstance(s, dict)]
    for s in steps:
        names = list(s.get("agents") or [])
        per = []
        for n in names:
            u = _usd(resolve(n), state_dir, memo)
            if u is None:
                if n not in unknown:
                    unknown.append(n)
                    if str((resolve(n) or {}).get("model") or "auto") == "auto":
                        auto.append(n)
                per.append(0.0)
            else:
                per.append(float(u))
        rounds = rounds_of(s)
        checks = rounds if isinstance(s.get("repeat"), dict) else 0
        if s.get("when") in (None, "always"):
            low += sum(per) * 0.5
        high += sum(per) * rounds + (per[-1] if per else 0.0) * checks
    cap = wf.get("max_usd") if isinstance(wf.get("max_usd"), (int, float)) and not isinstance(wf.get("max_usd"), bool) else None
    if cap is not None:
        high, low = min(high, float(cap)), min(low, float(cap))
    return {"low": round(low, 4), "high": round(high, 4), "unknown": unknown, "cap": cap, "line": line(low, high, unknown, cap, len(steps), auto)}


def _why(unknown: list, auto: list) -> str:
    priced = [n for n in unknown if n not in auto]
    bits = [f"Auto picks the model ({', '.join(auto[:4])})"] if auto else []
    bits += [f"no catalog price for the model of {', '.join(priced[:4])}"] if priced else []
    return "; ".join(bits)


def line(low: float, high: float, unknown: list, cap, n: int, auto=()) -> str:
    if not n:
        return "nothing yet: add a step"
    auto = list(auto)
    if high <= 0 and unknown:
        out = "unknown until the first run: " + _why(unknown, auto)
    else:
        out = f"about ${low:.2f} to ${high:.2f} a run"
        if unknown:
            out += "; some steps unknown until the first run: " + _why(unknown, auto)
    if cap is not None:
        out += f"; it stops at ${float(cap):.2f} a run"
    return out


def writes(wf: dict, resolve: Callable, state_dir=None) -> "list[str]":
    name = str(wf.get("name") or "workflow")
    out = [f"Save writes ~/.halo/crew/workflows/{name}.yaml (nothing else)."]
    seen: list = []
    parts = []
    for s in wf.get("steps") or []:
        for n in (s.get("agents") or []) if isinstance(s, dict) else []:
            if n in seen:
                continue
            seen.append(n)
            raw = resolve(n)
            if raw is None:
                parts.append(f"{n} (not an agent yet)")
                continue
            ws = [use_word(u) for u in raw.get("uses") or [] if u != "read"]
            parts.append(f"{n} ({', '.join(ws) if ws else 'reads only'})")
    if parts:
        out.append("A run changes only what its agents may change: " + "; ".join(parts) + ".")
    return out
