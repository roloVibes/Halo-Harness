"""halo_harness.packs.manifest_bundle_claims -- a bundle's claims beyond one reservation (Halo 3.3.8.0 R4; docs/
MODELS-bundles.md "Several reservations, a schedule, a priority"; packs/manifest_bundle.py reads the rest of `bundle:`):

    bundle:
      reservations:                       # several, each like `reservation:` plus `host` and `min_free_gb`
        - {model: reasoner, host: pool}   # the pool for one lane (host: a paired host's name, an ollama.hosts name,
        - {model: coder}                  #   or `pool`; left out: the default host, this machine's card)
      schedule: {hours: "09:00-18:00"}     # the hours the claims are held, the host's local clock (it may wrap
                                           #   midnight); outside them the bundle claims nothing
      priority: high                       # every reservation's default (high | normal | low): when two claims
                                           #   collide the lower one is pre-empted and told (local_sched/preempt.py)
      min_free_gb: 4                       # the GB each card keeps free for tasks beside the claims

    lines(raw, needs, one_lines) -> [one line per problem]     (one_lines: manifest_bundle._reservation_lines)
    normalize(raw, needs, norm) -> {reservations, schedule, priority, min_free_gb}   norm: manifest_bundle's
        normalizer of one reservation; `reservation` (the single block) comes first, then `reservations`
    hours_ok(spec) -> bool       in_hours(spec, now=None) -> bool (host/refresh_plan.in_window's rule)
Shape only: the verdict across the parts is local_sched/bundle_parts.py, the claims local_sched/reserve_parts.py.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

PRIORITIES = ("high", "normal", "low")
HOURS_RE = re.compile(r"^\s*([01]?\d|2[0-3]):[0-5]\d\s*-\s*([01]?\d|2[0-3]):[0-5]\d\s*$")
POOL = "pool"


def hours_ok(spec) -> bool:
    return isinstance(spec, str) and bool(HOURS_RE.match(spec))


def in_hours(spec: Optional[str], now: Optional[float] = None) -> bool:
    if not spec:
        return True
    from halo_harness.host.refresh_plan import in_window
    return in_window(str(spec).strip(), now)


def _num_line(where: str, v) -> list:
    if v is None or (isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0):
        return []
    return [f"{where}: {v!r} is not a size in GB (0 or more)"]


def lines(raw: dict, needs: dict, one_lines: Callable) -> list:
    out = []
    many = raw.get("reservations")
    if many is not None and not isinstance(many, list):
        out.append("bundle.reservations: a list of reservations ([{model, host?, ...}, ...])")
        many = []
    items = ([raw["reservation"]] if isinstance(raw.get("reservation"), dict) else []) + list(many or [])
    for i, res in enumerate(many or []):
        out += [ln.replace("bundle.reservation", f"bundle.reservations[{i}]", 1) for ln in one_lines(res, needs)]
    seen: dict = {}
    for i, res in enumerate(items):
        if not isinstance(res, dict):
            continue
        h = res.get("host")
        if h is not None and (not isinstance(h, str) or not h.strip()):
            out.append(f"bundle.reservations[{i}].host: a paired host's name, an ollama.hosts name, or pool")
        out += _num_line(f"bundle.reservations[{i}].min_free_gb", res.get("min_free_gb"))
        key = str(h or "").strip().lower()
        if key in seen:
            out.append(f"bundle.reservations: two reservations on {key or 'the default host'} ({seen[key]} and "
                       f"{res.get('model')}): one per host -- merge them")
        seen[key] = res.get("model")
    sched = raw.get("schedule")
    if sched is not None and not (isinstance(sched, dict) and hours_ok(sched.get("hours"))):
        out.append("bundle.schedule: {hours: \"HH:MM-HH:MM\"} (the host's local clock; it may wrap midnight, "
                   "e.g. \"22:00-07:00\")")
    if raw.get("priority") is not None and raw.get("priority") not in PRIORITIES:
        out.append(f"bundle.priority: {raw.get('priority')!r} is not one of {', '.join(PRIORITIES)}")
    out += _num_line("bundle.min_free_gb", raw.get("min_free_gb"))
    return out


def normalize(raw: dict, needs: dict, norm: Callable) -> dict:
    """{reservations: [each normalized + host, min_free_gb, priority defaulted to the bundle's], schedule, priority,
    min_free_gb}; norm(res) -> manifest_bundle's normalized reservation | None."""
    prio = raw.get("priority") if raw.get("priority") in PRIORITIES else "normal"
    floor = raw.get("min_free_gb") if isinstance(raw.get("min_free_gb"), (int, float)) and not isinstance(
        raw.get("min_free_gb"), bool) else None
    items = ([raw["reservation"]] if isinstance(raw.get("reservation"), dict) else []) + [
        r for r in (raw.get("reservations") if isinstance(raw.get("reservations"), list) else []) if isinstance(r, dict)]
    out = []
    for res in items:
        n = norm(res)
        if n is None:
            continue
        host = res.get("host").strip() if isinstance(res.get("host"), str) and res["host"].strip() else None
        own = res.get("min_free_gb")
        n.update(host=host, priority=res.get("priority") if res.get("priority") in PRIORITIES else prio,
                 min_free_gb=own if isinstance(own, (int, float)) and not isinstance(own, bool) else floor)
        out.append(n)
    sched = raw.get("schedule") if isinstance(raw.get("schedule"), dict) and hours_ok(raw["schedule"].get("hours")) \
        else None
    return {"reservations": out, "schedule": {"hours": sched["hours"].strip()} if sched else None, "priority": prio,
            "min_free_gb": floor}
