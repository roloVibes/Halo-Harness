"""halo_harness.providers.model_row_measured -- the `measured` key of a catalog
row (Halo 3.1.9.0 R1): what this host has MEASURED about a model, as opposed
to what a catalog states. Every source is a file the host already keeps, read
once per batch (never once per row, never the network):

  gym             `<state>/gym/<host>/<digest>.json` (gym.py): the overall
                  score, tool-call accuracy, edit success, tokens/s
  tools_probe     the Ollama tool-call probe (`ollama-capabilities.json`),
                  carried in by the local rows themselves
  tools_rejected  True while `learned-rules.json` holds a live (24 h)
                  tools-rejected rule for the endpoint (Databricks learns it)
  ttft_s / tokens_per_second   telemetry's own median (providers/speed.py,
                  3+ calls), never a router's advertised figure
  canary          the preflight canary census (`canary-census.json`):
                  ok, and the tools / vision checks

A row with nothing measured has `measured: None`; otherwise every one of the
six keys is present, None where that one source has nothing.
"""

from __future__ import annotations

from typing import Optional

MEASURED_KEYS = ("gym", "tools_probe", "tools_rejected", "ttft_s", "tokens_per_second", "canary")


def _gym_entry(found: list) -> Optional[dict]:
    from halo_harness.gym import overall_score
    if not found:
        return None
    best = found[0]
    score = overall_score(best)
    if score is None:
        return None

    def _metric(key):
        s = ((best.get(key) or {}) if isinstance(best.get(key), dict) else {}).get("score")
        return round(float(s), 3) if isinstance(s, (int, float)) and not isinstance(s, bool) else None
    tps = best.get("tokens_per_second")
    return {"score": round(score, 3), "tool_call_accuracy": _metric("tool_call_accuracy"),
            "edit_success": _metric("edit_success"),
            "tokens_per_second": round(float(tps), 1) if isinstance(tps, (int, float)) else None}


def _canary_entry(lane) -> Optional[dict]:
    if not isinstance(lane, dict):
        return None
    checks = lane.get("checks") if isinstance(lane.get("checks"), dict) else {}
    return {"ok": bool(lane.get("ok")), "tools": checks.get("tools"), "vision": checks.get("vision"),
            "recorded": lane.get("recorded")}


def canary_preflight(state_dir) -> dict:
    """`{ref: {"tools": bool|None, "vision": bool|None}}` from the census --
    the shape `capabilities.score(..., preflight=)` reads."""
    try:
        from halo_harness.preflight import load_canary_census
        lanes = load_canary_census(state_dir).get("lanes") or {}
    except Exception:
        return {}
    out = {}
    for ref, lane in lanes.items():
        entry = _canary_entry(lane)
        if entry:
            out[ref] = {"tools": entry["tools"], "vision": entry["vision"]}
    return out


def measured_index(state_dir, rows: list, *, speeds: Optional[dict] = None) -> dict:
    """`{ref: measured-dict}` for every row with something measured."""
    from halo_harness.providers.learned_rules import tools_rejected_endpoints
    results: list = []
    try:
        from halo_harness.gym import find_results_for_model, iter_results
        results = iter_results(state_dir)
    except Exception:
        find_results_for_model = None  # type: ignore[assignment]
    try:
        from halo_harness.preflight import load_canary_census
        lanes = load_canary_census(state_dir).get("lanes") or {}
    except Exception:
        lanes = {}
    try:
        rejected = tools_rejected_endpoints(state_dir)
    except Exception:
        rejected = set()
    speeds = speeds or {}
    out: dict = {}
    for row in rows:
        ref = row.get("ref")
        if not ref or row.get("provider") == "alias":
            continue
        carried = row.get("measured") if isinstance(row.get("measured"), dict) else {}
        entry = {key: None for key in MEASURED_KEYS}
        entry["tools_probe"] = carried.get("tools_probe")
        if results and find_results_for_model is not None:
            try:
                entry["gym"] = _gym_entry(find_results_for_model(state_dir, ref, results=results))
            except Exception:
                entry["gym"] = None
        if row.get("provider") == "databricks" and ref.startswith("dbx:") and f"databricks:{ref[4:]}" in rejected:
            entry["tools_rejected"] = True
        speed = speeds.get(ref) or {}
        entry["ttft_s"] = speed.get("ttft_s")
        entry["tokens_per_second"] = speed.get("tokens_per_second")
        entry["canary"] = _canary_entry(lanes.get(ref))
        if any(v is not None for v in entry.values()):
            out[ref] = entry
    return out
