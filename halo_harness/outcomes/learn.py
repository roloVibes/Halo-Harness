"""halo_harness.outcomes.learn -- Auto learns (Halo 3.1.9.0 R3, docs/ROLES.md
"Auto learns", docs/OUTCOMES.md "What was learned").

The numbers: per model and task kind (outcomes/kinds.py), the checked agent
tasks of `~/.halo/coach/outcomes.jsonl` from the last `window_days`
(outcomes/measured.py's rates over those rows), and how many of them were
the model's own pick (`picked: auto | measured` on the row). They feed:

* the `auto` pick (`models_auto.pick` calls `relearn`): each candidate's
  score is multiplied by `weight(model, kind, stats, cfg)` --

      fewer than `min_tasks` checked tasks:  1.0 (nothing learned yet)
      else:                                  0.5 + 0.5 x rate
                                             (rate 1.0 -> 1.0, 0.5 -> 0.75, 0.0 -> 0.5)

  (band low ranks by price first, so there the weight decides among equal
  prices); the reason gains "(learned: code 1/4 on <model>, so <picked>
  instead)" when the numbers changed the choice and "(code 5/5 here)" when
  they confirmed it;
* the roster (providers/roster.py): a model whose rate for a kind is below
  `drop_below` over `min_tasks` or more tasks leaves that kind's leaders and
  is named on one line, "dropped for code: <model> (1/4 checked tasks)";
* `halo outcomes learned` / `forget` (outcomes/learn_cli.py), the marks of
  `halo models --measured` and `halo models analyze`, Studio's model picker.

Config `models.learn`: `true` (the default), `false`, or an object
`{enabled, min_tasks: 3, window_days: 30 (0: every row), drop_below: 0.34}`.
Off: every weight is 1.0 and nothing is dropped (R2's order). A bio's
`preference: measured` (outcomes/routing.py) ranks by rate as before.
"""

from __future__ import annotations

import time
from typing import Optional

DEFAULTS = {"enabled": True, "min_tasks": 3, "window_days": 30, "drop_below": 0.34}
PICKED = ("auto", "measured")
MAX_DROPPED = 3  # the roster's drop line names at most this many models
_UNSET = object()
_OFF = ("false", "off", "no", "0")


def settings(raw=_UNSET) -> dict:
    """The rule's numbers from config `models.learn` (see the module docstring); a knob that does not read
    keeps its default."""
    if raw is _UNSET:
        try:
            from halo_harness.theme import get_config_value
            raw = get_config_value("models.learn", default=True)
        except Exception:
            raw = True
    out = dict(DEFAULTS)
    if isinstance(raw, str):
        raw = raw.strip().lower() not in _OFF
    if isinstance(raw, bool):
        out["enabled"] = raw
        return out
    if not isinstance(raw, dict):
        return out
    on = raw.get("enabled", True)
    out["enabled"] = not (on is False or (isinstance(on, str) and on.strip().lower() in _OFF))
    for key, lo, hi in (("min_tasks", 1, 100_000), ("window_days", 0, 36_500), ("drop_below", 0.0, 1.0)):
        v = raw.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi:
            out[key] = int(v) if key == "min_tasks" else v
    return out


def since(cfg: dict, now: Optional[float] = None) -> Optional[float]:
    """The window's start (epoch s), None with `window_days` 0 (every row counts)."""
    days = float(cfg.get("window_days") or 0)
    return None if days <= 0 else (time.time() if now is None else now) - days * 86400


def window_words(cfg: dict) -> str:
    days = cfg.get("window_days") or 0
    return f"the last {days:g} days" if days else "every row"


def numbers(state_dir=None, cfg: Optional[dict] = None, *, now: Optional[float] = None,
            rows: Optional[list] = None) -> dict:
    """`{(model, kind): {n, passed, returned, failed, rate, cost_mean, picked}}` over the window's checked
    tasks; `rows`: outcome rows to read instead of `state_dir`'s file. {} without either."""
    from halo_harness.outcomes.measured import success_by_model_kind
    from halo_harness.outcomes.records import RATED, read
    cfg = settings() if cfg is None else cfg
    start = since(cfg, now)
    if rows is None:
        if state_dir is None:
            return {}
        rows = read(state_dir, since=start)
    else:
        rows = [r for r in rows if start is None or float(r.get("ts") or 0) >= start]
    out = success_by_model_kind(rows=rows)
    for s in out.values():
        s["picked"] = 0
    for r in rows:
        key = (str(r.get("model") or "").strip(), str(r.get("kind") or "other"))
        if key in out and r.get("outcome") in RATED and r.get("check") and r.get("picked") in PICKED:
            out[key]["picked"] += 1
    return out


def counted(stat, cfg: dict) -> bool:
    return isinstance(stat, dict) and int(stat.get("n") or 0) >= int(cfg["min_tasks"])


def weight(model: str, kind: str, stats: dict, cfg: Optional[dict] = None) -> float:
    """The factor on `model`'s score for a `kind` task: 1.0 while learning is off or under `min_tasks`
    checked tasks, else 0.5 + 0.5 x its rate."""
    cfg = settings() if cfg is None else cfg
    s = (stats or {}).get((model, kind))
    if not cfg["enabled"] or not counted(s, cfg):
        return 1.0
    rate = max(0.0, min(1.0, float(s.get("rate") or 0.0)))
    return round(0.5 + 0.5 * rate, 4)


def is_dropped(stat, cfg: dict) -> bool:
    return bool(cfg["enabled"]) and counted(stat, cfg) and float(stat.get("rate") or 0.0) < float(cfg["drop_below"])


def dropped(stats: dict, cfg: dict, refs=None) -> list:
    """`[(kind, model, stat)]` dropped (only models in `refs` when given), worst first: the lowest rate, then
    the most tasks, then the names."""
    found = [(k, m, s) for (m, k), s in (stats or {}).items() if (refs is None or m in refs) and is_dropped(s, cfg)]
    return sorted(found, key=lambda t: (float(t[2].get("rate") or 0.0), -int(t[2].get("n") or 0), t[0], t[1]))


def tasks(stat) -> str:
    return f"{int(stat.get('passed') or 0)}/{int(stat.get('n') or 0)}"


def drop_line(drops: list, limit: int = MAX_DROPPED) -> str:
    """The roster's one line: "- dropped for code: or:v/x (1/4 checked tasks); dropped for plan: ..."."""
    if not drops:
        return ""
    by_kind: dict = {}
    for kind, ref, s in drops[:limit]:
        by_kind.setdefault(kind, []).append(f"{ref} ({tasks(s)} checked tasks)")
    text = "; ".join(f"dropped for {kind}: " + ", ".join(items) for kind, items in by_kind.items())
    more = len(drops) - min(limit, len(drops))
    return "- " + text + (f" (+{more} more: `halo outcomes learned`)" if more else "")


def marks(state_dir, cfg: Optional[dict] = None, *, now: Optional[float] = None) -> dict:
    """`{(model, kind): "dropped for code (1/4 in the last 30 days)"}`: the marks `halo models --measured` and
    `halo models analyze` print. {} when nothing is dropped or learning is off."""
    cfg = settings() if cfg is None else cfg
    if not cfg["enabled"]:
        return {}
    try:
        nums = numbers(state_dir, cfg, now=now)
    except Exception:
        return {}
    return {(m, k): f"dropped for {k} ({tasks(s)} in {window_words(cfg)})" for k, m, s in dropped(nums, cfg)}


def learned_rows(stats: dict, cfg: dict) -> list:
    """One dict per model and kind (the most tasks first per model): the numbers, the weight, dropped."""
    out = []
    for (model, kind), s in sorted(stats.items(), key=lambda t: (t[0][0], -t[1]["n"], t[0][1])):
        out.append({"model": model, "kind": kind, **s, "weight": weight(model, kind, stats, cfg),
                    "counted": counted(s, cfg), "dropped": is_dropped(s, cfg)})
    return out


def by_model(state_dir, cfg: Optional[dict] = None) -> dict:
    """`{model: {kind: {n, passed, rate, picked, weight, counted, dropped, days}}}` -- Studio's catalog rows
    carry it (`learned`)."""
    cfg = settings() if cfg is None else cfg
    out: dict = {}
    for r in learned_rows(numbers(state_dir, cfg), cfg):
        out.setdefault(r["model"], {})[r["kind"]] = {k: r[k] for k in ("n", "passed", "rate", "picked", "weight",
                                                                           "counted", "dropped")}
        out[r["model"]][r["kind"]]["days"] = cfg.get("window_days") or 0
    return out


def relearn(state_dir, cands: list, needs: list, band: str, main_ref: str, first: tuple, *, kind: str = "",
            role: str = "", stats: Optional[dict] = None, cfg: Optional[dict] = None) -> tuple:
    """`(choice, words)`: the auto pick's `(best, ordered, rule, tie)` with what was measured weighing in, and
    the words its reason ends with ("" when nothing was learned for these candidates). `first`:
    models_auto._choose's answer without the weights; `kind`: the task's kind (default: from `role`'s words);
    `stats`: `numbers`' answer (default: read from `state_dir`; none without one)."""
    cfg = settings() if cfg is None else cfg
    if not cfg["enabled"] or not cands:
        return first, ""
    if not kind:
        from halo_harness.outcomes.kinds import kind_of
        kind = kind_of(None, role)
    if stats is None:
        try:
            stats = numbers(state_dir, cfg)
        except Exception:
            stats = {}
    weights = {c.ref: weight(c.ref, kind, stats, cfg) for c in cands}
    if all(w == 1.0 for w in weights.values()):
        chosen = first
    else:
        from halo_harness.models_auto import _choose
        chosen = _choose(cands, needs, band, main_ref, weights=weights)
    before, after = first[0].ref, chosen[0].ref
    if before != after:
        lost = stats.get((before, kind)) or {}
        return chosen, f" (learned: {kind} {tasks(lost)} on {before}, so {after} instead)"
    mine = stats.get((after, kind))
    return chosen, (f" ({kind} {tasks(mine)} here)" if counted(mine, cfg) else "")
