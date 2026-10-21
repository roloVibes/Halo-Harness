"""halo_harness.supervise.settings -- the `supervise` section of config.json
(Halo 3.1.8.0 R1; docs/CONFIG.md).

    tick_s        5      seconds between two ticks
    max_running   1      goals running at once
    replan        none   (R2: auto | none) what the supervisor does with a run that drifts
    asks          park   park: a supervised job's ask waits in Attention (tick_s * 720 at most);
                         deny: it is denied at once, as any `halo -p` run
    budget_usd    unset  the whole queue's cap: every goal's spend together
    retries       1      a goal that stopped on a crash or a failed worker runs again from its checkpoint this often
    max_minutes   0      a goal's time limit (0: none); past it the run stops and the goal parks
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

DEFAULTS = {"tick_s": 5.0, "max_running": 1, "replan": "none", "asks": "park", "budget_usd": None, "retries": 1,
            "max_minutes": 0}
ASKS = ("park", "deny")
REPLAN = ("none", "auto")
WAIT_TICKS = 720  # a parked ask waits tick_s * 720 at most (an hour at the default tick)


def _num(value, default, *, lo: float = 0.0, whole: bool = False):
    try:
        n = int(value) if whole else float(value)
    except (TypeError, ValueError):
        return default
    if isinstance(value, bool) or n < lo:
        return default
    return n


def settings(state_dir: Optional[Path] = None) -> dict:
    """The section with its defaults; a value it does not understand takes the default."""
    raw: dict = {}
    try:
        if state_dir is None:
            from halo_harness.theme import get_config_value
            raw = get_config_value("supervise", {}) or {}
        else:
            import json
            data = json.loads((Path(state_dir) / "config.json").read_text(encoding="utf-8"))
            raw = data.get("supervise") or {} if isinstance(data, dict) else {}
    except Exception:
        raw = {}
    raw = raw if isinstance(raw, dict) else {}
    out = dict(DEFAULTS)
    out["tick_s"] = max(0.05, _num(raw.get("tick_s"), DEFAULTS["tick_s"]))
    out["max_running"] = max(1, _num(raw.get("max_running"), DEFAULTS["max_running"], whole=True))
    out["replan"] = raw.get("replan") if raw.get("replan") in REPLAN else DEFAULTS["replan"]
    out["asks"] = raw.get("asks") if raw.get("asks") in ASKS else DEFAULTS["asks"]
    cap = raw.get("budget_usd")
    out["budget_usd"] = None if cap in (None, 0) else _num(cap, None)
    out["retries"] = _num(raw.get("retries"), DEFAULTS["retries"], whole=True)
    out["max_minutes"] = _num(raw.get("max_minutes"), DEFAULTS["max_minutes"])
    return out


def ask_wait_s(cfg: dict) -> float:
    """How long a parked ask of a supervised job waits for its answer."""
    return float(cfg.get("tick_s") or DEFAULTS["tick_s"]) * WAIT_TICKS
