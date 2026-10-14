"""halo_harness.flows.cli_posts -- `halo flow posts`, `halo flow metrics` and
`halo postiz doctor`.

    halo flow posts <run>                  the run's posts: platform, dry run / post id, schedule, text
    halo flow metrics <run> [--days N]     sample the run's live posts once, print and total them
    halo postiz doctor                     the CLI, the credentials (never the key), the integrations
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from halo_harness.flows import state
from halo_harness.flows.metrics_pull import live_posts, pull, run_totals
from halo_harness.flows.postiz import PostizCli, PostizError
from halo_harness.flows.postiz_parse import format_totals, metric_totals
from halo_harness.flows.watch import metrics_step, project_of

PLATFORMS = ("youtube", "instagram", "x", "tiktok")


def _run_and_project(ref: str):
    run_dir = state.find_run(ref)
    if run_dir is None:
        print(f"halo flow: no run {ref!r} (halo flow runs lists them)", file=sys.stderr)
        return None, None, {}
    flow = state.read_flow(run_dir)
    project = project_of(flow)
    if project is None:
        print(f"halo flow: run {run_dir.name} has no design project yet", file=sys.stderr)
    return run_dir, project, flow


def post_line(r: dict) -> str:
    what = ("dry run" if r.get("dry_run") else f"error: {r['error']}" if r.get("error") else
            f"live, post {r.get('post_id')}" + (f", scheduled {r['scheduled_at']}" if r.get("scheduled_at") else ""))
    return f"{r.get('platform')}: {what}; {len(r.get('text') or '')} chars, {len(r.get('media') or [])} media"


def cmd_posts(rest: list) -> int:
    run_dir, project, _flow = _run_and_project(rest[0] if rest else "last")
    if run_dir is None or project is None:
        return 2
    rows = [r for r in project.posts() if r.get("run") == run_dir.name]
    if not rows:
        print(f"run {run_dir.name} has no posts yet (the post step writes them)")
        return 0
    for r in rows:
        print(post_line(r))
        for line in str(r.get("text") or "").splitlines()[:8]:
            print(f"    {line}")
    return 0


def _refresh_report(run_dir) -> None:
    from halo_harness.flows.report import write_report
    from halo_harness.orchestra import jsonl
    old = jsonl.read_json(run_dir / "report.json", None)
    if isinstance(old, dict):
        finished = float(old.get("finished") or 0) or time.time()
        write_report(run_dir, status=str(old.get("status") or "finished"), stop_reason=str(old.get("stop_reason") or ""),
                     clock=lambda: finished)


def cmd_metrics(rest: list) -> int:
    p = argparse.ArgumentParser(prog="halo flow metrics")
    p.add_argument("run", nargs="?", default="last")
    p.add_argument("--days", type=int, default=None)
    a = p.parse_args(rest)
    run_dir, project, flow = _run_and_project(a.run)
    if run_dir is None or project is None:
        return 2
    posts = live_posts(project.posts(), run_dir.name)
    if not posts:
        print("dry run: no metrics (this run's posts are dry runs; set live: true on its post step)")
        return 0
    step = metrics_step(flow.get("spec") or {})
    days = a.days or int(step.get("days") or 7)
    cli = PostizCli(cwd=os.getcwd())
    if not (cli.available() and cli.credentials()):
        print("halo flow metrics: needs the postiz CLI and its credentials (halo postiz doctor)", file=sys.stderr)
        return 1
    got = pull(cli, state.Flow(run_dir), project, posts, days, run_dir.name, str(step.get("id") or "metrics"))
    for s in got["samples"]:
        print(f"{s['platform']} post {s['post_id']} ({days} days): {format_totals(metric_totals(s['metrics'])) or 'no counts yet'}")
    for err in got["errors"]:
        print(f"failed: {err}", file=sys.stderr)
    totals, n = run_totals([m for m in project.metrics() if m.get("run") == run_dir.name])
    print(f"total: {format_totals(totals, n) or 'no counts yet'}")
    _refresh_report(run_dir)
    return 1 if got["errors"] and not got["samples"] else 0


def cmd_doctor(rest: list) -> int:
    cli = PostizCli(cwd=os.getcwd())
    exe, creds = cli.path(), cli.credentials()
    print(f"postiz CLI: {exe}" if exe else "postiz CLI: not installed (npm i -g postiz)")
    print(f"credentials: found via {creds}" if creds else
          "credentials: none (POSTIZ_API_KEY in the env file, or postiz auth:login)")
    if os.environ.get("POSTIZ_API_URL"):
        print(f"api url: {os.environ['POSTIZ_API_URL']}")
    if not (exe and creds):
        return 1
    try:
        rows = cli.integrations()
    except PostizError as e:
        print(f"integrations: failed: {e}")
        return 1
    from halo_harness.flows.steps_postiz import match_integration
    print(f"integrations ({len(rows)}):")
    for r in rows:
        print(f"  {r['id']}  {r['platform']:<10} {r['name']}" + ("  (disabled)" if r["disabled"] else ""))
    print("platforms: " + ", ".join(f"{p} {'ok' if match_integration(p, rows)[0] else 'missing'}" for p in PLATFORMS))
    return 0


def cmd_postiz(argv: list) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("halo postiz doctor    the postiz CLI, its credentials (never the key) and the connected integrations")
        return 0
    if argv[0] == "doctor":
        return cmd_doctor(argv[1:])
    print(f"halo postiz: unknown command {argv[0]!r} (doctor)", file=sys.stderr)
    return 2
