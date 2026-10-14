"""halo_harness.flows.metrics_pull -- sampling Postiz analytics into the
project: one `metrics.jsonl` line `{ts, post_id, platform, days, metrics:
<the raw answer>, run, step}` per live post, one `metric` event per sample.

Used by the `metrics` step, `halo flow metrics` and the `--watch` poller.
"""

from __future__ import annotations

import time
from typing import Callable

from halo_harness.flows.postiz import PostizError
from halo_harness.flows.postiz_parse import format_totals, metric_totals
from halo_harness.orchestra import jsonl


def live_posts(rows: list, run: "str | None" = None) -> list:
    """The posts that really went out (have a post id), of one run when `run` is given."""
    return [r for r in rows if r.get("post_id") and not r.get("dry_run") and (run is None or r.get("run") == run)]


def latest_per_post(samples: list) -> dict:
    out: dict = {}
    for s in samples:
        if s.get("post_id"):
            out[s["post_id"]] = s
    return out


def run_totals(samples: list) -> "tuple[dict, int]":
    """(views/likes/comments/shares summed over each post's latest sample, number of posts)."""
    latest = latest_per_post(samples)
    totals: dict = {}
    for s in latest.values():
        for k, v in metric_totals(s.get("metrics")).items():
            totals[k] = totals.get(k, 0) + v
    return totals, len(latest)


def pull(cli, flow, project, posts: list, days: int, run: str, step: str, clock: Callable = time.time) -> dict:
    """Sample every post once. Returns {"samples": [lines written], "errors": [text]}."""
    written, errors = [], []
    path = project.path / "metrics.jsonl"
    for p in posts:
        pid, platform = str(p.get("post_id")), p.get("platform")
        try:
            raw = cli.analytics_post(pid, days)
        except PostizError as e:
            errors.append(f"{platform} {pid}: {e}")
            flow.log("metric", f"metrics for {platform} post {pid} failed: {e}", step=step, platform=platform,
                     post_id=pid, error=str(e))
            continue
        line = {"ts": round(clock(), 3), "post_id": pid, "platform": platform, "days": days, "metrics": raw,
                "run": run, "step": step}
        with jsonl.locked(path):
            jsonl.append_line(path, line)
        written.append(line)
        totals = metric_totals(raw)
        note = format_totals(totals) or ("missing: postiz posts:missing lists the provider's content"
                                         if isinstance(raw, dict) and raw.get("missing") else "no counts yet")
        flow.log("metric", f"{platform} post {pid}: {note}", step=step, platform=platform, post_id=pid, days=days,
                 totals=totals)
    return {"samples": written, "errors": errors}
