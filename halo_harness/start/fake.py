"""halo_harness.start.fake -- the lead, workers and judge `halo start` uses
with `HALO_START_FAKE=1` (Halo 3.1.1.0 R1): the whole guided run without a
model, for the tests and a dry look.

The lead splits the goal into one lane per function of basket.py; each
worker joins its lane, claims its keys and writes the function's body
itself (the sample's known solutions), marking each claim written and
releasing it as a real worker does through the Orchestra tools; the judge
answers a conflict with the first side. Each call reports a tiny cost.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ENV = "HALO_START_FAKE"

SOLUTIONS = {
    "add_item": ["    entry = basket.setdefault(name, [Decimal(price), 0])", "    entry[1] += qty", "    return basket"],
    "remove_item": ["    entry = basket[name]", "    entry[1] -= qty", "    if entry[1] <= 0:",
                    "        del basket[name]", "    return basket"],
    "subtotal": ['    return sum((price * qty for price, qty in basket.values()), Decimal("0"))'],
    "apply_discount": ['    cut = amount * (100 - Decimal(percent)) / 100',
                       '    return cut.quantize(Decimal("0.01"), rounding="ROUND_HALF_UP")'],
    "total": ["    return apply_discount(subtotal(basket), percent)"],
}
FUNCS = tuple(SOLUTIONS)


def enabled() -> bool:
    return os.environ.get(ENV, "").strip().lower() in ("1", "true", "yes", "on")


def lead(prompt: str) -> dict:
    jobs = [{"title": f"write {f}", "claims": [f"basket.py#{f}"]} for f in FUNCS]
    return {"text": json.dumps({"jobs": jobs}), "cost_usd": 0.001, "session_id": "start-fake-lead"}


def write_function(path: Path, name: str, body: list) -> None:
    """Replace the body of `name` (after its one-line docstring, up to the blank lines before the next def)."""
    lines = path.read_text(encoding="utf-8").split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith(f"def {name}("))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("def ")), len(lines))
    while end > start and not lines[end - 1].strip():
        end -= 1
    lines[start + 2:end] = body
    path.write_text("\n".join(lines), encoding="utf-8", newline="")


def worker(lane) -> dict:
    from halo_harness.orchestra.claims import ClaimLog
    from halo_harness.orchestra.workers import join_lane, record_written
    holder = f"start-fake-worker{lane.n}/main"
    join_lane(lane.run_dir, lane.n, holder)
    log = ClaimLog(lane.run_dir)
    path = lane.worktree / "basket.py"
    for key in lane.job.claims:
        name = key.split("#", 1)[1]
        if not log.claim(holder, key).ok:
            raise RuntimeError(f"the fake worker could not claim {key}")
        log.mark_writing(holder, key)
        write_function(path, name, SOLUTIONS[name])
        log.mark_written(holder, key)
        record_written(lane.run_dir, holder, key, lane.worktree)
        log.release(holder, key)
    return {"text": f"wrote {', '.join(lane.job.claims)}", "cost_usd": 0.002, "session_id": holder.split("/")[0]}


def judge(hunks, goal, file) -> dict:
    first = hunks[0] if hunks else {}
    text = first.get("ours") if isinstance(first, dict) else ""
    return {"text": str(text or ""), "session_id": "start-fake-judge", "messages_before": 0, "cost_usd": 0.0005}


def adapters() -> dict:
    """The keyword arguments `orchestra.run.run()` takes."""
    return {"model_calls": lead, "spawn": worker, "judge": judge}
