"""halo_harness.flows.watch -- `halo flow run --watch` after the run: keep
sampling the live posts' analytics on the metrics step's `every` interval
until `days` have passed since the first post (or `halo flow stop`, or Ctrl-C).

`watch_metrics(run_dir, *, cli=None, say=print, sleep=None, clock=time.time,
max_polls=None, slice_s=5.0) -> polls`. No `every` on the step, or no live
posts (dry runs have no metrics), means nothing to poll: it returns 0.
"""

from __future__ import annotations

import calendar
import time
from pathlib import Path

from halo_harness.flows.metrics_pull import live_posts, pull
from halo_harness.flows.postiz import PostizCli
from halo_harness.flows.postiz_parse import parse_every
from halo_harness.flows.state import Flow, read_flow, stop_requested

SLEEP = None  # a test seam: replaces time.sleep


def metrics_step(spec: dict) -> dict:
    return next((s for s in spec.get("steps") or [] if isinstance(s, dict) and s.get("kind") == "metrics"), {})


def project_of(flow: dict):
    from halo_harness.design.store import Project
    if flow.get("project_path"):
        return Project(Path(flow["project_path"]))
    return Project.open(str(flow.get("project") or ""))


def _first_post_time(posts: list, now: float) -> float:
    stamps = []
    for p in posts:
        try:
            stamps.append(calendar.timegm(time.strptime(str(p.get("ts")), "%Y-%m-%dT%H:%M:%S")))
        except ValueError:
            pass
    return min(stamps) if stamps else now


def watch_metrics(run_dir, *, cli=None, say=print, sleep=None, clock=time.time, max_polls=None,
                  slice_s: float = 5.0) -> int:
    run_dir = Path(run_dir)
    flow_data = read_flow(run_dir)
    step = metrics_step(flow_data.get("spec") or {})
    interval = parse_every(step.get("every"))
    project = project_of(flow_data)
    if interval is None or project is None:
        return 0
    posts = live_posts(project.posts(), run_dir.name)
    if not posts:
        say("dry run: no metrics to poll")
        return 0
    cli = cli or PostizCli(cwd=str(Path.cwd()))
    if not (cli.available() and cli.credentials()):
        say("metrics polling needs the postiz CLI and its credentials (halo postiz doctor)")
        return 0
    days = int(step.get("days") or 7)
    deadline = _first_post_time(posts, clock()) + days * 86400
    sleep, flow, polls = sleep or SLEEP or time.sleep, Flow(run_dir, clock=clock), 0
    say(f"watching metrics every {step.get('every')} for {days} days (halo flow stop {run_dir.name}, or Ctrl-C, ends it)")
    while clock() < deadline and (max_polls is None or polls < max_polls):
        waited = 0.0
        while waited < interval and not stop_requested(run_dir):
            sleep(min(slice_s, interval - waited))
            waited += slice_s
        if stop_requested(run_dir):
            say("metrics polling stopped")
            break
        got = pull(cli, flow, project, live_posts(project.posts(), run_dir.name), days, run_dir.name,
                   str(step.get("id") or "metrics"), clock)
        polls += 1
        say(f"poll {polls}: {len(got['samples'])} samples" + (f", {len(got['errors'])} failed" if got["errors"] else ""))
    return polls
