"""halo_harness.orchestra.worker_result -- what a worker's `spawn(lane)` returned,
as the fields run_lane keeps (orchestra/workers.py).

`spawn` returns None, a string (the reply) or a dict with any of `text`,
`cost_usd`, `session_id`, `ok`, `error`, and (3.0.9.0 R3, for the coach)
`model` (the model the worker's result names) and `denied` (its
`permission_denials`: `[{tool_name, tool_input, reason}]`).
`record_denied` keeps the model on the lane when the job named none and
appends each denied call to the lane's `denied` list and to events.jsonl
as one `note` line with `denied: true`.
"""

from __future__ import annotations

from halo_harness.orchestra import events as run_events


def result_fields(result) -> dict:
    if isinstance(result, dict):
        return {"text": str(result.get("text") or ""), "cost_usd": float(result.get("cost_usd") or 0.0),
                "session_id": result.get("session_id"), "ok": result.get("ok", True) is not False,
                "error": str(result.get("error") or ""), "model": str(result.get("model") or ""),
                "denied": [d for d in result.get("denied") or [] if isinstance(d, dict)]}
    return {"text": str(result or ""), "cost_usd": 0.0, "session_id": None, "ok": True, "error": "", "model": "",
            "denied": []}


def record_denied(run_dir, lane, data: dict, fields: dict) -> None:
    """The model the worker ran on and every tool call it was denied (one `note` line each)."""
    denied = [{"tool_name": str(d.get("tool_name") or ""), "reason": str(d.get("reason") or "")[:300]}
              for d in fields.get("denied") or []]
    if fields.get("model") and not data.get("model"):
        lane.update(model=fields["model"])
    if not denied:
        return
    lane.update(denied=list(data.get("denied") or []) + denied)
    for d in denied:
        run_events.log(run_dir, "note", f"lane {lane.n}: {d['tool_name']} denied: {d['reason']}", lane=lane.n,
                       denied=True, tool=d["tool_name"], reason=d["reason"])
