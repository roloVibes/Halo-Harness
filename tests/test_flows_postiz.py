"""tests.test_flows_postiz -- the Postiz client and the text/metric readers
(Halo 3.0.4.0 round R4): `PostizCli` round trips over a fake `postiz`
executable (JSON and table integrations, upload, posts:create, posts:status,
analytics, the failure messages with the stderr tail and the key scrubbed,
the key reaching the child by name), the Copywriter's per-platform text (a
fenced JSON block, the header fallback), the analytics totals, `every`
durations and the Project readers. The real CLI is never needed.
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
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
KEY = "pzk-SECRET-0123456789"


def _fake(**options):
    d = Path(tempfile.mkdtemp(prefix="fake-postiz-"))
    log = d / "calls.jsonl"
    fake_postiz.install(d, log, **options)
    return d, log


@test
def test_availability_and_credentials(ctx: Ctx):
    from halo_harness.flows.postiz import PostizCli
    home = Path(tempfile.mkdtemp(prefix="postiz-home-"))
    empty = tempfile.mkdtemp(prefix="no-postiz-")
    cli = PostizCli(env={"PATH": empty}, home=home)
    ctx.check("no postiz on PATH -> not available", not cli.available())
    ctx.check("no key, no credentials file -> no credentials", cli.credentials() == "")
    (home / ".postiz").mkdir()
    (home / ".postiz" / "credentials.json").write_text("{}", encoding="utf-8")
    ctx.check("credentials.json counts", cli.credentials() == "~/.postiz/credentials.json")
    ctx.check("the env key counts and is named, never printed",
              PostizCli(env={"PATH": empty, "POSTIZ_API_KEY": KEY}, home=Path(empty)).credentials() == "POSTIZ_API_KEY")
    d, _log = _fake()
    ctx.check("the fake on PATH is available", PostizCli(env={"PATH": str(d)}, home=home).available())
    try:
        cli.integrations()
        ctx.check("calling a missing CLI raises", False)
    except Exception as e:
        ctx.check(f"a missing CLI names the install command, got {e}", "npm i -g postiz" in str(e))


@test
def test_cli_round_trips(ctx: Ctx):
    from halo_harness.flows.postiz import PostizCli
    d, log = _fake()
    cli = PostizCli(env={"PATH": str(d), "POSTIZ_API_KEY": KEY, "POSTIZ_API_URL": "https://api.example"}, cwd=str(d))
    rows = cli.integrations()
    ctx.check(f"integrations from JSON, got {rows[:2]}", [r["platform"] for r in rows] == ["youtube", "instagram", "x", "tiktok"]
              and rows[0] == {"id": "int-yt", "platform": "youtube", "name": "Halo Channel", "disabled": False})
    up = cli.upload(str(d / "hero.png"))
    ctx.check(f"upload returns the id and the url, got {up}", up == {"id": "up-1", "url": "https://postiz.example/uploads/hero.png"})
    res = cli.create_post("hello world #halo", [up["url"]], "int-x", when="2030-01-02T03:04:05Z", settings={"title": "T"})
    ctx.check(f"create_post returns the post id, got {res}", res["post_id"] == "post-1" and res["scheduled_at"] == "2030-01-02T03:04:05Z")
    argv = cli.calls[-1]
    ctx.check(f"posts:create argv, got {argv}", argv[1:] == ["posts:create", "-c", "hello world #halo", "-m", up["url"],
                                                              "-s", "2030-01-02T03:04:05Z", "-i", "int-x",
                                                              "--settings", '{"title":"T"}'])
    auto = cli.create_post("later", [], "int-yt")
    ctx.check("a missing time becomes an ISO UTC time", auto["scheduled_at"].endswith("Z") and "-s" in cli.calls[-1])
    ctx.check("post_status answers", cli.post_status("post-1")["status"] == "QUEUE")
    series = cli.analytics_post("post-3", 14)
    ctx.check("analytics:post passes -d and parses", cli.calls[-1][1:] == ["analytics:post", "post-3", "-d", "14"]
              and series[0]["label"] == "Views")
    ctx.check("analytics:platform", cli.analytics_platform("int-yt", 30)[0]["label"] == "Followers"
              and cli.calls[-1][1:] == ["analytics:platform", "int-yt", "-d", "30"])
    from tests.helpers.fake_postiz import calls
    seen = calls(log)
    ctx.check("every call was recorded, with the key in the child's env by name", len(seen) == len(cli.calls)
              and all(c["has_key"] for c in seen))
    ctx.check("the log never holds the key", KEY not in log.read_text(encoding="utf-8"))


@test
def test_integrations_table_banner_and_wrapper(ctx: Ctx):
    from halo_harness.flows.postiz import PostizCli
    from halo_harness.flows.postiz_parse import parse_integrations
    d, _ = _fake(table=True, integrations=[{"id": "a1", "identifier": "x", "name": "Halo X", "disabled": True},
                                           {"id": "b2", "identifier": "youtube", "name": "Chan", "disabled": False}])
    rows = PostizCli(env={"PATH": str(d)}).integrations()
    ctx.check(f"the column table parses, got {rows}", rows == [
        {"id": "a1", "platform": "x", "name": "Halo X", "disabled": True},
        {"id": "b2", "platform": "youtube", "name": "Chan", "disabled": False}])
    d2, _ = _fake(banner=True)
    ctx.check("a banner line before the JSON is skipped", len(PostizCli(env={"PATH": str(d2)}).integrations()) == 4)
    wrapped = json.dumps({"integrations": [{"id": "z", "providerIdentifier": "TikTok", "name": "t"}]})
    ctx.check("a wrapped object and providerIdentifier work", parse_integrations(wrapped)[0]["platform"] == "tiktok")
    box = "\u2502 id \u2502 platform \u2502 name \u2502\n\u2502 q9 \u2502 instagram \u2502 gram \u2502\n"
    ctx.check("a box-drawn table parses", parse_integrations(box) == [{"id": "q9", "platform": "instagram", "name": "gram", "disabled": False}])


@test
def test_failures_carry_argv_and_stderr_tail_and_hide_the_key(ctx: Ctx):
    from halo_harness.flows.postiz import PostizCli, PostizError
    d, _ = _fake(fail_upload=True, fail_create_for=["int-tt"])
    cli = PostizCli(env={"PATH": str(d), "POSTIZ_API_KEY": KEY})
    try:
        cli.upload("hero.png")
        ctx.check("a failing upload raises", False)
    except PostizError as e:
        ctx.check(f"the upload error has the stderr tail, got {e}", "413 payload too large" in str(e) and "exit 1" in str(e))
        ctx.check("and the argv", e.argv[1:] == ["upload", "hero.png"])
    try:
        cli.create_post("x", [], "int-tt", when="2030-01-01T00:00:00Z")
        ctx.check("a failing create raises", False)
    except PostizError as e:
        ctx.check(f"the create error shows stderr with the key scrubbed, got {e}", "create failed for int-tt" in str(e)
                  and KEY not in str(e) and "***" in str(e))
    d2, _ = _fake(fail_analytics=True)
    try:
        PostizCli(env={"PATH": str(d2)}).analytics_post("post-1", 7)
        ctx.check("a failing analytics call raises", False)
    except PostizError as e:
        ctx.check("analytics failure message", "analytics unavailable" in str(e))


@test
def test_split_posts_json_and_header_fallback(ctx: Ctx):
    from halo_harness.flows.post_text import split_posts
    plats = ["youtube", "instagram", "x", "tiktok"]
    block = ('Here you go.\n```json\n{"youtube": {"title": "Halo 3.0.4 in 60s", "text": "Watch the flow"}, '
             '"Instagram": {"caption": "a caption #halo"}, "twitter": "short x post", "tik tok": {"text": "tt text"}}\n```\n')
    got = split_posts(block, plats)
    ctx.check(f"JSON per platform, aliases and caption keys, got {got}", got == {
        "youtube": {"text": "Watch the flow", "title": "Halo 3.0.4 in 60s"}, "instagram": {"text": "a caption #halo"},
        "x": {"text": "short x post"}, "tiktok": {"text": "tt text"}})
    part = split_posts('{"x": "only x"}', ["x", "instagram"])
    ctx.check("a platform missing from the JSON falls back to the whole text", part["x"]["text"] == "only x"
              and part["instagram"]["text"] == '{"x": "only x"}')
    heads = split_posts("X:\nShort post for X #halo\n\nInstagram:\nA longer caption #halo #ai", ["x", "instagram"])
    ctx.check(f"the header fallback still splits, got {heads}", heads["x"]["text"] == "Short post for X #halo"
              and heads["instagram"]["text"] == "A longer caption #halo #ai")
    ctx.check("a mapping is used as it is", split_posts({"x": "hi", "instagram": {"text": "ig"}}, ["x", "instagram", "tiktok"])
              == {"x": {"text": "hi"}, "instagram": {"text": "ig"}, "tiktok": {}})
    ctx.check("plain text goes to every platform", split_posts("one text", ["x", "tiktok"])["tiktok"]["text"] == "one text")


@test
def test_metric_totals_every_and_project_readers(ctx: Ctx):
    from halo_harness.design.store import Project
    from halo_harness.flows.postiz_parse import find_id, format_totals, metric_totals, parse_every
    series = [{"label": "Views", "data": [{"total": "40"}, {"total": "90"}]}, {"label": "Likes", "data": [{"total": 7}]},
              {"label": "Comments", "data": []}, {"label": "Retweets", "data": [{"total": "2"}]}, {"label": "Followers", "data": [{"total": "5"}]}]
    ctx.check("series: the latest point of views/likes/shares, unknown labels ignored",
              metric_totals(series) == {"views": 90, "likes": 7, "shares": 2})
    ctx.check("a plain mapping", metric_totals({"views": 10, "likes": "3", "stats": {"comments": 1}}) == {"views": 10, "likes": 3, "comments": 1})
    ctx.check("missing / None give nothing", metric_totals({"missing": True}) == {} and metric_totals(None) == {})
    ctx.check("totals text", format_totals({"views": 90, "likes": 7}, 2) == "views 90, likes 7 across 2 posts"
              and format_totals({}, 2) == "")
    ctx.check("post ids", find_id([{"postId": "p1"}]) == "p1" and find_id({"posts": [{"id": 7}]}) == "7" and find_id({}) == "")
    ctx.check("durations", [parse_every(x) for x in ("30s", "15m", "6h", "1d", "2w", "soon", None)]
              == [30.0, 900.0, 21600.0, 86400.0, 1209600.0, None, None])
    root = Path(tempfile.mkdtemp(prefix="proj-"))
    p = Project(root)
    ctx.check("no files -> empty readers", p.posts() == [] and p.metrics() == [])
    (root / "posts.json").write_text(json.dumps([{"platform": "x"}, "junk"]), encoding="utf-8")
    (root / "metrics.jsonl").write_text('{"n": 1}\nnot json\n{"n": 2}\n{"n": 3}\n', encoding="utf-8")
    ctx.check("posts() keeps the mappings", p.posts() == [{"platform": "x"}])
    ctx.check("metrics() skips torn lines and takes the last N", [m["n"] for m in p.metrics()] == [1, 2, 3]
              and [m["n"] for m in p.metrics(limit=2)] == [2, 3])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="flow postiz tests"))
