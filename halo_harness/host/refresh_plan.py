"""halo_harness.host.refresh_plan -- what the off-hours refresh would measure, why, when and how long (Halo 3.3.7.0 R4;
plans/local-model-fit-brief.md G13: "run the capability battery and benchmarks when the card is free, never during a
session, and stamp each model 'verified <date>'").

    settings(home=None) -> {enabled, window, idle_min, max_age_days}     config host.refresh.* (docs/CONFIG.md)
    in_window(spec, now) -> bool       "22:00-07:00" (local time; it may wrap midnight), "off" -> False
    next_start(spec, now) -> epoch | None     start_words(spec, now) -> "tonight 22:00+" | "now (inside 22:00-07:00)"
    why_for(state_dir, host_name, row, *, max_age_days, now) -> {why, says, battery, bench} | None (fresh)
        why: drifted (the digest changed: tag-drift) | unverified (never probed, or an older probe set) | older (verified
        more than max_age_days ago); battery / bench: which of the two it needs
    plan(state_dir, hosts, *, catalogs=None, now=None, settings_=None) -> {rows, total_min, line}
        rows (drifted first, then unverified, then the oldest) {host, model, why, says, battery, bench, minutes}
    next_line(p, s, now) -> "next: qwen3-coder:30b, battery ~4 min, tonight 22:00+" | "nothing to refresh: ..."
    stamp_words(rec) -> "verified 2026-10-31 by the host" | ""
No request but the catalog read (the Ollama panel's 60 s cache, or `catalogs` given); nothing loads here.
"""

from __future__ import annotations

import math
import time
from typing import Optional

WINDOW = "22:00-07:00"
IDLE_MIN = 20
MAX_AGE_DAYS = 14
ORDER = {"drifted": 0, "unverified": 1, "older": 2}
DISK_GB_S = 0.7
BATTERY_CALLS = 9


def _cfg(key: str, default, home=None):
    from halo_harness.host.state import _cfg as cfg
    try:
        return cfg(key, default, home)
    except Exception:
        return default


def settings(home=None) -> dict:
    def num(key, d):
        try:
            return max(0, int(_cfg(key, d, home)))
        except (TypeError, ValueError):
            return d
    window = str(_cfg("host.refresh.window", WINDOW, home) or WINDOW).strip()
    return {"enabled": _cfg("host.refresh.enabled", True, home) is not False and window.lower() != "off",
            "window": window, "idle_min": num("host.refresh.idle_min", IDLE_MIN),
            "max_age_days": num("host.refresh.max_age_days", MAX_AGE_DAYS)}


def _span(spec: str) -> "Optional[tuple]":
    try:
        a, b = str(spec).split("-", 1)
        ah, am = (int(x) for x in a.strip().split(":"))
        bh, bm = (int(x) for x in b.strip().split(":"))
    except (ValueError, TypeError):
        return None
    return ah * 60 + am, bh * 60 + bm


def in_window(spec: str, now: Optional[float] = None) -> bool:
    span = _span(spec) if str(spec or "").lower() != "off" else None
    if span is None:
        return False
    t = time.localtime(time.time() if now is None else now)
    m, (a, b) = t.tm_hour * 60 + t.tm_min, span
    return a <= m < b if a < b else (m >= a or m < b)


def next_start(spec: str, now: Optional[float] = None) -> Optional[float]:
    span = _span(spec) if str(spec or "").lower() != "off" else None
    if span is None:
        return None
    now = time.time() if now is None else now
    if in_window(spec, now):
        return now
    t = time.localtime(now)
    base = now - (t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec)
    start = base + span[0] * 60
    return start if start > now else start + 86400


def start_words(spec: str, now: Optional[float] = None) -> str:
    now = time.time() if now is None else now
    at = next_start(spec, now)
    if at is None:
        return "never (host.refresh.window off)"
    if at <= now:
        return f"now (inside {spec})"
    hm = time.strftime("%H:%M", time.localtime(at))
    same_day = time.localtime(at).tm_yday == time.localtime(now).tm_yday
    return f"tonight {hm}+" if same_day and time.localtime(at).tm_hour >= 18 else f"{'today' if same_day else 'tomorrow'} {hm}+"


def _day(t) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(t)) if isinstance(t, (int, float)) else "never"


def why_for(state_dir, host_name: str, row: dict, *, max_age_days: int, now: Optional[float] = None) -> Optional[dict]:
    from halo_harness.providers.battery_probes import PROBE_SET
    from halo_harness.providers.local_bench_runs import load
    from halo_harness.providers.ollama_capability import profile_for
    now = time.time() if now is None else now
    model, digest = str(row.get("model") or row.get("name") or ""), row.get("digest")
    p = profile_for(state_dir, model, host_name) or {}
    sc = load(state_dir, host_name, model) or {}
    drift = [w for w, rec in (("its profile", p), ("its speed card", sc)) if digest and rec.get("digest")
             and rec["digest"] != digest]
    age = (now - float(p["probed_at"])) / 86400 if isinstance(p.get("probed_at"), (int, float)) else None
    if drift:
        return {"why": "drifted", "says": f"the tag's digest changed: {' and '.join(drift)} were measured on an older "
                                          "build of this tag", "battery": True, "bench": True}
    if not p or p.get("probe_set") != PROBE_SET:
        return {"why": "unverified", "says": "never probed here" if not p else
                f"probed with {p.get('probe_set')}, the battery is {PROBE_SET} now", "battery": True, "bench": not sc}
    if age is not None and age > max_age_days:
        return {"why": "older", "says": f"verified {_day(p.get('probed_at'))}, {int(age)} days ago (host.refresh."
                                        f"max_age_days {max_age_days})", "battery": True, "bench": True}
    if not sc:
        return {"why": "unverified", "says": "no speed card yet", "battery": False, "bench": True}
    return None


def minutes(row: dict, rec: dict, profile: Optional[dict] = None, card: Optional[dict] = None) -> int:
    """The battery's and the quick bench's minutes from the speed card (its cold load, its tok/s), else the profile's."""
    from halo_harness.providers.local_bench import cost_minutes
    from halo_harness.providers.local_bench_runs import mirror
    speed = {k: v for k, v in (mirror(card) if card else {}).items() if v} or (profile or {}).get("speed") or {}
    size = row.get("size") if isinstance(row.get("size"), int) else 8e9
    load_s = speed.get("cold_load_s") or size / 1e9 / DISK_GB_S
    tok = speed.get("tok_s") or 30.0
    n = math.ceil((load_s + BATTERY_CALLS * 400 / tok) / 60) if rec.get("battery") else 0
    return n + (cost_minutes(size, [32768], speed) if rec.get("bench") else 0)


def plan(state_dir, hosts: list, *, catalogs: Optional[dict] = None, now: Optional[float] = None,
         settings_: Optional[dict] = None) -> dict:
    from halo_harness.providers.ollama_capability import profile_for
    s = settings_ or settings(state_dir)
    rows = []
    for h in hosts or []:
        if catalogs is not None:
            cat = catalogs.get(h.name) or {}
        else:
            from halo_harness.studio.ollama_hosts_view import catalog_of
            cat = catalog_of(h)
        for r in cat.get("models") or []:
            if not isinstance(r, dict) or "embed" in str(r.get("model") or r.get("name") or "").lower():
                continue
            rec = why_for(state_dir, h.name, r, max_age_days=s["max_age_days"], now=now)
            if rec is None:
                continue
            model = str(r.get("model") or r.get("name"))
            from halo_harness.providers.local_bench_runs import load
            p = profile_for(state_dir, model, h.name)
            rows.append({"host": h.name, "model": model, **rec, "minutes": minutes(r, rec, p, load(state_dir, h.name, model)),
                         "age": float((p or {}).get("probed_at") or 0)})
    rows.sort(key=lambda x: (ORDER[x["why"]], x["age"], x["model"]))
    total = sum(r["minutes"] for r in rows)
    return {"rows": rows, "total_min": total, "line": next_line({"rows": rows}, s, now)}


def next_line(p: dict, s: dict, now: Optional[float] = None) -> str:
    if not s.get("enabled"):
        return "the off-hours refresh is off (host.refresh.enabled false, or host.refresh.window off)"
    rows = p.get("rows") or []
    if not rows:
        return f"nothing to refresh: every model here was verified within {s.get('max_age_days')} days"
    r = rows[0]
    what = " + ".join(w for w in ("battery", "bench") if r.get(w)) or "battery"
    more = f"; {len(rows) - 1} more after it" if len(rows) > 1 else ""
    return (f"next: {r['model']} on {r['host']} ({r['why']}: {r['says']}), {what} ~{r['minutes']} min, "
            f"{start_words(s['window'], now)} once the card has been idle {s['idle_min']} min{more}")


def stamp_words(rec: Optional[dict]) -> str:
    rec = rec or {}
    if not rec.get("verified_by"):
        return ""
    return f"verified {_day(rec.get('refreshed_at') or rec.get('probed_at') or rec.get('at'))} by {rec['verified_by']}"
