"""tests.test_flows_postiz2 -- posting inside a flow run (Halo 3.0.4.0 round
R4): a dry run writes posts.json and spawns nothing; live without the CLI or
credentials stops with the reason; live over the fake uploads once, posts per
platform, records ids and totals the metrics in the report; a failed
platform stops the run after the others went out and a resume does not post
them again; platform matching; no secret anywhere.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from tests.helpers import fake_postiz  # noqa: E402
from tests.helpers.fake_comfy import FakeComfy  # noqa: E402
from tests.helpers.fake_flow import FakeOrg, make_adapters  # noqa: E402
from tests.helpers.postiz_rig import (  # noqa: E402
    COPY4, FOUR, KEY, _cli, _fake, _go, _project, no_secret as _no_secret, spec_with as _spec)
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_dry_run_writes_posts_and_spawns_nothing(ctx: Ctx):
    d, log = _fake()
    with fake_postiz.put_on_path(d, key=KEY):
        run_dir, report = _go(_spec(False))
    ctx.check(f"finished, got {report.get('stop_reason')}", report["status"] == "finished")
    ctx.check("the fake was never spawned", fake_postiz.calls(log) == [])
    posts = _project(run_dir).posts()
    ctx.check(f"four dry-run posts, got {[p['platform'] for p in posts]}", [p["platform"] for p in posts] == FOUR.split(",")
              and all(p["dry_run"] and "post_id" not in p for p in posts))
    yt = posts[0]
    ctx.check(f"the YouTube post has its JSON title and text, got {yt}", yt["text"] == "Watch the flow run"
              and yt["title"] == "Halo 3.0.4 teaser" and yt["run"] == run_dir.name and yt["step"] == "publish")
    ctx.check("the argv is the postiz command that would run", yt["argv"][:4] == ["postiz", "posts:create", "-c", "Watch the flow run"]
              and "-i" in yt["argv"] and "--settings" in yt["argv"])
    ctx.check("the report lists the dry runs", [(p["platform"], p["dry_run"], p["post_id"]) for p in report["posts"]]
              == [(p, True, None) for p in FOUR.split(",")])
    notes = [e["text"] for e in __import__("halo_harness.flows.state", fromlist=["x"]).read_events(run_dir) if e["kind"] == "metric"]
    ctx.check(f"the metrics step says dry run: no metrics, got {notes}", any("dry run: no metrics" in n for n in notes)
              and report["metrics"]["samples"] == 0 and report["metrics"]["summary"].find("dry run: no metrics") >= 0)
    _no_secret(ctx, run_dir)


@test
def test_header_fallback_in_a_run(ctx: Ctx):
    run_dir, report = _go(_spec(False), platforms="x,instagram", copy="X:\nShort post for X #halo\n\nInstagram:\nLonger caption #halo",
                          project="postiz-header")
    posts = _project(run_dir).posts()
    ctx.check(f"R3's heading split still works, got {[p['text'] for p in posts]}",
              [p["text"] for p in posts] == ["Short post for X #halo", "Longer caption #halo"])


@test
def test_live_needs_the_cli_and_credentials(ctx: Ctx):
    with tempfile.TemporaryDirectory() as empty, fake_postiz.put_on_path(empty, key=KEY, exclusive=True):
        run_dir, report = _go(_spec(True), project="postiz-nocli")
    ctx.check(f"no CLI stops the run with a one-line reason, got {report.get('stop_reason')}", report["status"] == "stopped"
              and report["stop_reason"].startswith("publish: live: true needs the postiz CLI on PATH") and "\n" not in report["stop_reason"])
    ctx.check("nothing was written as a post", _project(run_dir).posts() == [])
    d, log = _fake()
    with fake_postiz.put_on_path(d, exclusive=True):
        _run2, report2 = _go(_spec(True), project="postiz-nokey")
    ctx.check(f"no credentials stops it too, got {report2.get('stop_reason')}", report2["status"] == "stopped"
              and "needs Postiz credentials" in report2["stop_reason"] and fake_postiz.calls(log) == [])


@test
def test_live_posts_through_the_fake_and_metrics_total(ctx: Ctx):
    from halo_harness.flows.state import read_events
    d, log = _fake()
    with fake_postiz.put_on_path(d, key=KEY):
        run_dir, report = _go(_spec(True), project="postiz-live")
    ctx.check(f"finished, got {report.get('stop_reason')}", report["status"] == "finished")
    argvs = [c["argv"] for c in fake_postiz.calls(log)]
    verbs = [a[0] for a in argvs]
    ctx.check(f"one integrations:list, ONE upload for the one media file, four posts:create, four analytics, got {verbs}",
              verbs.count("integrations:list") == 1 and verbs.count("upload") == 1 and verbs.count("posts:create") == 4
              and verbs.count("analytics:post") == 4)
    posts = _project(run_dir).posts()
    ctx.check(f"each post has its id, integration and schedule, got {posts[0]}", [p["post_id"] for p in posts] == ["post-1", "post-2", "post-3", "post-4"]
              and [p["integration_id"] for p in posts] == ["int-yt", "int-ig", "int-x", "int-tt"]
              and all(p["dry_run"] is False and p["scheduled_at"].endswith("Z") and p["media_urls"][0].endswith("/render.png") for p in posts))
    create = next(a for a in argvs if a[0] == "posts:create" and a[a.index("-i") + 1] == "int-yt")
    ctx.check(f"YouTube gets its title in --settings, TikTok DIRECT_POST, got {create}", '"title":"Halo 3.0.4 teaser"' in create[create.index("--settings") + 1]
              and any('"content_posting_method":"DIRECT_POST"' in x for a in argvs if a[0] == "posts:create" for x in a))
    lines = _project(run_dir).metrics()
    ctx.check(f"metrics.jsonl has one line per live post, got {len(lines)}", [m["post_id"] for m in lines] == ["post-1", "post-2", "post-3", "post-4"]
              and all({"ts", "post_id", "platform", "days", "metrics", "run", "step"} <= set(m) and m["days"] == 7 and m["step"] == "measure" for m in lines))
    ctx.check("the raw answer is kept", lines[0]["metrics"][0]["label"] == "Views")
    t = report["metrics"]["totals"]
    ctx.check(f"the report totals the latest sample per post (k=1..4: views 100k, likes 10k), got {t}",
              t == {"views": 1000, "likes": 100, "comments": 20, "shares": 10} and report["metrics"]["posts"] == 4
              and report["metrics"]["summary"] == "views 1000, likes 100, comments 20, shares 10 across 4 posts")
    ctx.check("the report posts carry ids and times", all(p["post_id"] and p["scheduled_at"] for p in report["posts"]))
    kinds = [e["kind"] for e in read_events(run_dir)]
    post_events = [e for e in read_events(run_dir) if e["kind"] == "post"]
    ctx.check("flow_post lines say dry_run false", len(post_events) == 4 and all(e["data"]["dry_run"] is False for e in post_events))
    _no_secret(ctx, run_dir)
    code, out, _ = _cli("flow", "posts", run_dir.name)
    ctx.check(f"halo flow posts prints id, schedule and text, got {out}", code == 0 and "youtube: live, post post-1, scheduled" in out
              and "    Watch the flow run" in out and "x: live, post post-3" in out)
    with fake_postiz.put_on_path(d, key=KEY):
        code, out, _ = _cli("flow", "metrics", run_dir.name, "--days", "3")
    ctx.check(f"halo flow metrics pulls once with -d 3 and totals, got {out}", code == 0 and "total: views 1000, likes 100, comments 20, shares 10 across 4 posts" in out
              and "youtube post post-1 (3 days): views 100, likes 10, comments 2, shares 1" in out)
    ctx.check("the on-demand pull appended four more samples and used -d 3", len(_project(run_dir).metrics()) == 8
              and [a for a in [c["argv"] for c in fake_postiz.calls(log)] if a[0] == "analytics:post"][-1][-2:] == ["-d", "3"])
    rep = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    ctx.check("the report was refreshed and keeps its status", rep["status"] == "finished" and rep["metrics"]["samples"] == 8)
    _no_secret(ctx, run_dir, out)


@test
def test_failed_platform_stops_after_the_others_and_resume_does_not_repost(ctx: Ctx):
    from halo_harness.flows.run import run
    d, log = _fake(fail_create_for=["int-tt"])
    with fake_postiz.put_on_path(d, key=KEY):
        run_dir, report = _go(_spec(True), project="postiz-fail")
        ctx.check(f"the run stops naming the platform and the CLI's message, got {report.get('stop_reason')}", report["status"] == "stopped"
                  and "tiktok: postiz posts:create failed (exit 1)" in report["stop_reason"] and KEY not in report["stop_reason"])
        posts = _project(run_dir).posts()
        ctx.check(f"three live posts and one error entry were saved, got {[(p['platform'], p.get('post_id'), bool(p.get('error'))) for p in posts]}",
                  [(p["platform"], bool(p.get("post_id")), bool(p.get("error"))) for p in posts]
                  == [("youtube", True, False), ("instagram", True, False), ("x", True, False), ("tiktok", False, True)])
        cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
        cfg["fail_create_for"] = []
        (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        with FakeComfy() as fake:
            again = run(run_dir, adapters=make_adapters(fake.url, run_org=FakeOrg(copy=COPY4), auto_accept=True))
    ctx.check(f"the resume finishes, got {again.get('stop_reason')}", again["status"] == "finished")
    creates = [c["argv"] for c in fake_postiz.calls(log) if c["argv"][0] == "posts:create"]
    ctx.check(f"only the failed platform was posted again (3 ok + 1 failed + 1 retry = 5 creates, got {len(creates)})", len(creates) == 5)
    live = [p for p in _project(run_dir).posts() if p.get("post_id")]
    ctx.check("four live posts, none twice", sorted(p["platform"] for p in live) == sorted(FOUR.split(",")))
    _no_secret(ctx, run_dir)
    d2, log2 = _fake(fail_upload=True)
    with fake_postiz.put_on_path(d2, key=KEY):
        _r, rep2 = _go(_spec(True), project="postiz-noupload")
    ctx.check(f"an upload failure stops with the stderr tail, got {rep2.get('stop_reason')}", rep2["status"] == "stopped"
              and "413 payload too large" in rep2["stop_reason"])


@test
def test_missing_integration_is_reported_per_platform(ctx: Ctx):
    d, log = _fake(integrations=[{"id": "int-x", "identifier": "twitter", "name": "@halo", "disabled": False},
                                 {"id": "int-ig", "identifier": "instagram", "name": "halo.ig", "disabled": True}])
    with fake_postiz.put_on_path(d, key=KEY):
        run_dir, report = _go(_spec(True), platforms="x,instagram,tiktok", project="postiz-missing")
    reason = report["stop_reason"]
    ctx.check(f"x matches the twitter integration, instagram is disabled, tiktok is missing, got {reason}",
              "instagram: the postiz integration halo.ig for instagram is disabled" in reason
              and "tiktok: no connected postiz integration for tiktok" in reason and "x:" not in reason)
    posts = _project(run_dir).posts()
    ctx.check("x went out through the twitter integration", posts[0].get("integration_id") == "int-x" and posts[0].get("post_id") == "post-1")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="flow postiz run tests"))
