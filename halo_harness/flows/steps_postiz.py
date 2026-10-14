"""halo_harness.flows.steps_postiz -- the post and metrics steps (Postiz).

* post, `live: false` (the default): one entry per platform appended to the
  design project's `posts.json`: `{platform, text, title?, media, dry_run:
  true, argv, run, step, ts}` where `argv` is the postiz command that would
  publish it; each is logged as a `post` line. Nothing is spawned.
* post, `live: true`: needs the `postiz` CLI on PATH and credentials (else
  the run stops with a one-line reason). Each platform maps to a connected
  integration; every media file is uploaded once, one `posts:create` per
  platform, `{post_id, scheduled_at, dry_run: false}` recorded as it lands
  (a resumed step keeps the posts already made). A platform that fails is
  recorded with its `error` and stops the run after the others went out.
* metrics: with live posts it samples `analytics:post` once into
  `metrics.jsonl` (`halo flow run --watch` keeps sampling every `every` for
  `days`; `halo flow metrics <run>` samples on demand); dry-run posts
  produce a `metric` line "dry run: no metrics".
"""

from __future__ import annotations

import time

from halo_harness.flows.metrics_pull import live_posts, pull
from halo_harness.flows.post_text import platform_text, split_posts  # noqa: F401  (platform_text: R3 import path)
from halo_harness.flows.postiz import PostizCli, PostizError, iso_utc, platform_settings
from halo_harness.flows.refs import resolve_value
from halo_harness.flows.state import StopFlow

_ALIASES = {"x": ("x", "twitter"), "instagram": ("instagram", "instagram-standalone")}


def match_integration(platform: str, integrations: list) -> "tuple[dict | None, str]":
    """(the enabled integration for `platform`, else None and why)."""
    names = _ALIASES.get(str(platform).lower(), (str(platform).lower(),))
    hits = [i for i in integrations if str(i.get("platform")).lower() in names]
    enabled = [i for i in hits if not i.get("disabled")]
    if enabled:
        return enabled[0], ""
    if hits:
        return None, f"the postiz integration {hits[0].get('name') or hits[0].get('id')} for {platform} is disabled"
    return None, f"no connected postiz integration for {platform} (halo postiz doctor lists them)"


def _live_cli(ctx) -> PostizCli:
    cli = PostizCli(cwd=ctx.cwd)
    if not cli.available():
        raise StopFlow(f"{ctx.sid}: live: true needs the postiz CLI on PATH (npm i -g postiz); "
                       "halo postiz doctor checks it, or set live: false")
    if not cli.credentials():
        raise StopFlow(f"{ctx.sid}: live: true needs Postiz credentials: POSTIZ_API_KEY in the env file or postiz auth:login")
    return cli


def _save(project, rows: list) -> None:
    from halo_harness.design.jsonio import _write_json, project_lock
    with project_lock(project.path):
        _write_json(project.path / "posts.json", rows)


def post(ctx) -> dict:
    inputs = resolve_value(ctx.step.get("inputs") or {}, ctx.outputs)
    media = [str(m) for m in (inputs.get("media") or [])]
    platforms = inputs.get("platforms") or []
    platforms = platforms if isinstance(platforms, list) else [platforms]
    live = ctx.step.get("live") is True
    cli = _live_cli(ctx) if live else None
    bodies = split_posts(inputs.get("text") or "", platforms)
    project = ctx.project()
    rows = project.posts()
    when = str(ctx.step.get("when") or "") or (iso_utc(60) if live else "<when>")
    made = {r.get("platform"): r for r in live_posts(rows, ctx.run) if r.get("step") == ctx.sid}
    integrations = cli.integrations() if live else []
    uploads: dict = {}
    entries, failed = [], []
    for platform in platforms or ["(no platform)"]:
        body = bodies.get(platform) or {}
        text, title = str(body.get("text") or ""), str(body.get("title") or "")
        settings = platform_settings(platform, title, text)
        entry = {"platform": platform, "text": text, **({"title": title} if title else {}), "media": media,
                 "dry_run": not live, "run": ctx.run, "step": ctx.sid}
        if not live:
            entry.update(argv=PostizCli.create_argv(text, media, f"<{platform} integration id>", when, settings))
            entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
            ctx.flow.log("post", f"dry run: {platform}, {len(text)} chars, {len(media)} media", step=ctx.sid,
                         platform=platform, dry_run=True)
        elif platform in made:
            entry = made[platform]
            ctx.flow.log("note", f"{ctx.sid}: {platform} was already posted as {entry['post_id']}", step=ctx.sid)
        else:
            integration, why = match_integration(platform, integrations)
            try:
                if integration is None:
                    raise PostizError(why)
                urls = []
                for path in media:
                    if path not in uploads:
                        up = cli.upload(path)
                        uploads[path] = up["url"] or up["id"]
                    urls.append(uploads[path])
                res = cli.create_post(text, urls, integration["id"], when=when, settings=settings)
                entry.update(integration_id=integration["id"], media_urls=urls, post_id=res["post_id"],
                             scheduled_at=res["scheduled_at"], argv=cli.calls[-1])
                ctx.flow.log("post", f"{platform} posted as {res['post_id']}, scheduled {res['scheduled_at']}",
                             step=ctx.sid, platform=platform, dry_run=False, post_id=res["post_id"])
            except PostizError as e:
                entry.update(error=str(e), argv=e.argv or (cli.calls[-1] if cli.calls else []))
                failed.append(f"{platform}: {e}")
                ctx.flow.log("post", f"{platform} failed: {e}", step=ctx.sid, platform=platform, dry_run=False,
                             error=str(e))
            entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        entries.append(entry)
        if live and entry not in rows:
            rows = rows + [entry]
            _save(project, rows)
    if not live:
        _save(project, rows + entries)
    if failed:
        raise StopFlow(f"{ctx.sid}: " + "; ".join(failed))
    return {"posts": entries, "dry_run": not live, "path": str(project.path / "posts.json")}


def metrics(ctx) -> dict:
    every, days = ctx.step.get("every") or "6h", int(ctx.step.get("days") or 7)
    project = ctx.project()
    posts = live_posts(project.posts(), ctx.run)
    base = {"every": every, "days": days, "path": str(project.path / "metrics.jsonl")}
    if not posts:
        ctx.flow.log("metric", f"{ctx.sid}: dry run: no metrics (the posts are dry runs; live: true on the post step "
                               "posts for real)", step=ctx.sid, every=every, days=days, dry_run=True)
        return dict(base, samples=0, dry_run=True)
    cli = PostizCli(cwd=ctx.cwd)
    if not (cli.available() and cli.credentials()):
        ctx.flow.log("metric", f"{ctx.sid}: no metrics pulled: the postiz CLI or its credentials are missing "
                               "(halo postiz doctor)", step=ctx.sid, every=every, days=days)
        return dict(base, samples=0, dry_run=False)
    got = pull(cli, ctx.flow, project, posts, days, ctx.run, ctx.sid)
    return dict(base, samples=len(got["samples"]), errors=got["errors"], dry_run=False)
