"""halo_harness.providers.speed -- Halo 2.0.4 round 3 (deliverable 1): the
picker's own "speed" column. 2.0.3-brief A2: "the harness's own observed
figure first, since it is the only source that works for every provider
... median time-to-first-token and tokens per second from telemetry
(stats --models already has ttft_ms), shown ... once a model has been
used at least three times, blank before."

Reads ONLY the already-aggregated telemetry stats-cache
(`telemetry.cache_path()`/`_load_cache`) and runs `aggregate_by_model`
over whatever `SessionSummary`s it finds there -- it never re-scans a
raw session `*.jsonl` file itself (that only happens inside
`telemetry.scan`, when a cached entry's size/mtime no longer match).
`Controller.list_models()` is documented as "UI thread, synchronous,
cheap" and this needs to run once per picker open (never once per row),
so staying cache-only here keeps that promise regardless of how large
`~/.halo/sessions` has grown; a session that never ran `halo stats`/
`/stats` simply has an empty (or stale) cache, and every row's speed
column reads blank until one does -- a documented tradeoff, not a bug.
"""

from __future__ import annotations

from typing import Optional


def speed_by_ref(state_dir, *, min_calls: int = 3) -> dict:
    """`{ref: {"ttft_s": float, "tokens_per_second": float}}` -- a ref
    with fewer than `min_calls` recorded calls, or no usable latency data
    at all, is simply absent (the caller's own `format_speed`/
    `unknown_as_qmark` renders that as the picker's blank "?"). Never
    raises: any failure (corrupt cache, missing module) yields `{}`,
    exactly like "no cache yet" -- a telemetry hiccup must never break the
    picker."""
    out: dict = {}
    try:
        from halo_harness import telemetry
        cache = telemetry._load_cache()
        summaries = []
        for entry in cache.values():
            if isinstance(entry, dict) and isinstance(entry.get("summary"), dict):
                try:
                    summaries.append(telemetry.SessionSummary.from_dict(entry["summary"]))
                except Exception:
                    continue
        if not summaries:
            return out
        for row in telemetry.aggregate_by_model(summaries):
            calls = row.get("calls") or 0
            if calls < min_calls:
                continue
            ref = row.get("model")
            if not ref:
                continue
            speed_entry = _speed_fields(row, calls)
            if speed_entry:
                out[ref] = speed_entry
    except Exception:
        return {}
    return out


def _speed_fields(row: dict, calls: int) -> dict:
    """One aggregated `aggregate_by_model` row -> `{"ttft_s",
    "tokens_per_second"}` (either or both keys present, never a key with
    a non-useful value). `tokens_per_second` is approximated from the
    GENERATION phase only (total latency minus the time-to-first-token),
    not the whole call -- a rough-but-honest rate, since the TTFT wait
    itself produced no tokens at all and would otherwise understate the
    model's real per-token speed."""
    out: dict = {}
    ttft_ms: "Optional[float]" = row.get("ttft_p50_ms")
    if isinstance(ttft_ms, (int, float)) and ttft_ms >= 0:
        out["ttft_s"] = ttft_ms / 1000.0
    avg_latency_ms = row.get("avg_latency_ms")
    tokens_out = row.get("tokens_out") or 0
    if (isinstance(avg_latency_ms, (int, float)) and isinstance(ttft_ms, (int, float))
            and tokens_out > 0 and calls > 0):
        completion_ms_per_call = max(avg_latency_ms - ttft_ms, 1.0)
        total_completion_s = (completion_ms_per_call * calls) / 1000.0
        if total_completion_s > 0:
            out["tokens_per_second"] = tokens_out / total_completion_s
    return out
